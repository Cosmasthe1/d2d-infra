"""UDP satellite-channel proxy: forwards datagrams with delay/loss driven by the NTN simulator.

   device --UDP--> [proxy: delay + loss + outage windows] --UDP--> gateway

`speedup` runs simulated time faster than wall clock so a full day of passes can be exercised in a test.
Outside a pass window every datagram is dropped (the device must store-and-forward).
"""
from __future__ import annotations
import asyncio, random, time
from ntn_sim.schedule import link_state


class SatChannelProxy(asyncio.DatagramProtocol):
    def __init__(self, con, lat, lon, target, t_sim0=0.0, speedup=1.0, seed=1, svc_kwargs=None):
        self.con, self.lat, self.lon = con, lat, lon
        self.target, self.t0, self.speedup = target, t_sim0, speedup
        self.wall0 = time.monotonic()
        self.rng = random.Random(seed)
        self.svc_kwargs = svc_kwargs or {}
        self.stats = dict(rx=0, fwd=0, dropped_outage=0, dropped_loss=0)
        self.transport = None
        self.out_transport = None

    def sim_time(self):
        return self.t0 + (time.monotonic() - self.wall0) * self.speedup

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.stats["rx"] += 1
        st = link_state(self.con, self.lat, self.lon, self.sim_time(), **self.svc_kwargs)
        if st is None:
            self.stats["dropped_outage"] += 1
            return
        if self.rng.random() < st["loss_prob"]:
            self.stats["dropped_loss"] += 1
            return
        delay_wall = (st["delay_ms"] / 1000.0) / self.speedup
        asyncio.get_running_loop().call_later(delay_wall, self._send, data)

    def _send(self, data):
        if self.out_transport:
            self.out_transport.sendto(data, self.target)
            self.stats["fwd"] += 1


async def start(proxy: SatChannelProxy, listen=("127.0.0.1", 9000)):
    loop = asyncio.get_running_loop()
    t_in, _ = await loop.create_datagram_endpoint(lambda: proxy, local_addr=listen)
    t_out, _ = await loop.create_datagram_endpoint(asyncio.DatagramProtocol, family=__import__("socket").AF_INET)
    proxy.out_transport = t_out
    return t_in, t_out
