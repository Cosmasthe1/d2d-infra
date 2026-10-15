#!/usr/bin/env bash
# One satellite pass over the UERANSIM radio link:  baseline -> replay pass profile -> collect logs -> analyze.
# Usage: ./run_experiment.sh [--sats 24] [--min-el 20] [--lead 60] [--tail 60] [--feeder-ms 0] [--speedup 1] [--aperture 2.0] [--service nbiot_sms|ltem_data|lte_qpsk|lte_16qam]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$HERE/.."
REPO_DIR="${REPO_DIR:-$HERE/docker_open5gs}"
OUT="${OUT:-$HERE/runs/$(date +%Y%m%d-%H%M%S)}"; mkdir -p "$OUT"
PING_TARGET="${PING_TARGET:-8.8.8.8}"      # override if the testbed has no internet path (e.g. an echo host behind the UPF)
SATS=24; MINEL=20; LEAD=60; TAIL=60; FEEDER=0; SPEED=1; APERTURE=2.0; SERVICE=nbiot_sms
while [ $# -gt 0 ]; do case "$1" in
  --sats) SATS=$2; shift 2;; --min-el) MINEL=$2; shift 2;; --lead) LEAD=$2; shift 2;;
  --tail) TAIL=$2; shift 2;; --feeder-ms) FEEDER=$2; shift 2;; --speedup) SPEED=$2; shift 2;;
  --aperture) APERTURE=$2; shift 2;; --service) SERVICE=$2; shift 2;;
  *) echo "unknown arg $1"; exit 2;; esac; done

echo "[1] profile"
( cd "$ROOT/phase0" && PYTHONPATH=. python3 emulation/gen_profile.py --sats "$SATS" --min-el "$MINEL" --lead "$LEAD" --tail "$TAIL" \
    --feeder-ms "$FEEDER" --aperture "$APERTURE" --service "$SERVICE" --out "$OUT/profile.json" )

echo "[2] start gNB + UE and wait for PDU session"
( cd "$REPO_DIR" && set -a && . ./.env && set +a && docker compose -f nr-gnb.yaml up -d && sleep 5 && docker compose -f nr-ue.yaml up -d )
for i in $(seq 1 90); do
  docker logs nr_ue 2>&1 | grep -q "PDU Session establishment is successful" && break
  [ "$i" = 90 ] && { echo "UE did not establish a PDU session in 90 s. See TROUBLESHOOTING (subscriber? OP/OPc? SCTP?)"; exit 1; }
  sleep 1
done
echo "    attached."

echo "[3] baseline (no impairment)"
docker exec nr_ue ping -I uesimtun0 -c 10 -i 0.5 "$PING_TARGET" | tee "$OUT/baseline_ping.txt" | tail -3

echo "[4] replay pass (duration ~ $(python3 -c "import json;print(len(json.load(open('$OUT/profile.json'))['rows']))") s / speedup $SPEED)"
docker exec -d nr_ue sh -c "ping -D -O -I uesimtun0 -i 0.5 $PING_TARGET > /tmp/ping.log 2>&1"
python3 "$HERE/replay_profile.py" "$OUT/profile.json" --speedup "$SPEED" --log "$OUT/replay_events.jsonl" || true
docker exec nr_ue pkill ping || true
docker cp nr_ue:/tmp/ping.log "$OUT/ping.log"

echo "[5] collect logs"
docker logs --timestamps nr_ue  > "$OUT/ue.log"  2>&1
docker logs --timestamps nr_gnb > "$OUT/gnb.log" 2>&1
docker logs --timestamps amf    > "$OUT/amf.log" 2>&1

echo "[6] analyze"
python3 "$HERE/analyze.py" --ping "$OUT/ping.log" --events "$OUT/replay_events.jsonl" --ue-log "$OUT/ue.log" --interval 0.5 | tee "$OUT/summary.txt"
echo "results in $OUT"
