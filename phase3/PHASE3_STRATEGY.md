# Phase 3 - Scale through partnerships

Numbers in `out/` come from `financial_model.py`. **Every input is a placeholder** (wholesale cost, capex, headcount,
adoption). Their value is the structure: they show which variables decide the outcome. Replace with real quotes before use.

## What the model says (placeholder inputs)
- **Unit economics are decided by wholesale cost per message.** At ~US$0.05/msg and 120 msgs/device/month, hitting a 45% gross
  margin needs ~US$11/device-month, above what many IoT customers pay. At ~US$0.015/msg the same margin needs ~US$3.3.
  See `out/sensitivity.json`.
- **A (platform only)** needs the least capital but is margin-constrained by partner wholesale prices.
- **B (platform + demo + consortium stake)** gets cost per message down without carrying a full constellation.
- **C (own constellation)** has the best long-run margin but an order-of-magnitude larger funding need and a long path to payback.
- Therefore: **start as A, earn B, and only consider C with committed anchor customers and non-dilutive/strategic capital.**

## Decision gates
| Gate | Evidence required | Unlocks |
|---|---|---|
| G1 (end Phase 1) | >=3 paying pilots; measured wholesale cost/msg; platform uptime SLO met | Fund Phase 2 |
| G2 (end Phase 2a) | Emulated link meets margin targets with COTS modules; experimental spectrum route agreed with CA Kenya | Build/launch demo payload |
| G3 (end Phase 2c) | On-orbit link closed with unmodified devices; message delivery within modelled latency | Partner/JV negotiations from strength |
| G4 | Signed anchor customers covering >=40% of target capacity; wholesale cost path <US$0.02/msg | Consider constellation capex |

## Partnership targets (verify current status before outreach)
Public reporting indicates: Airtel Africa and Starlink signed a direct-to-cell deal covering 14 markets (Dec 2025) and went
live in DRC in Aug 2026, with Kenya pending Communications Authority approval; Vodacom (Safaricom's parent) signed an
Africa-wide deal with SpaceX (Nov 2025); MTN South Africa and Lynk ran an unmodified-handset satellite call trial (Mar 2025).

| Type | Candidates | Why they care | Ask |
|---|---|---|---|
| MNOs | Safaricom, Airtel Kenya, Telkom Kenya; regional: MTN, Vodacom | Rural coverage without towers; need enterprise IoT and device-management layer | Pilot as enterprise IoT reseller/aggregator; roaming/interconnect |
| NB-IoT NTN / satellite IoT providers | Skylo, Sateliot, Lynk, others | Need African go-to-market, local integration and vertical apps | Wholesale capacity for Phase 1; revenue share |
| Cubesat integrators / launch | EnduroSat, NanoAvionics, GomSpace; rideshare via Exolaunch / SpaceX Transporter | Phase 2 bus, integration, launch | Quotes for a 6U with deployable antenna; low-inclination rideshare options |
| Government / regulators | Communications Authority of Kenya, Kenya Space Agency, ICT Authority | Licensing, experimental spectrum, national connectivity goals | Experimental licence, policy engagement |
| Anchor customers | EV/fleet operators, carbon-credit verifiers, agri-cooperatives, conservancies, humanitarian agencies | Coverage outside terrestrial networks | Paid pilots with LOIs |
| Funding | Climate/space/connectivity grants, DFIs, strategic VC | Capital for G2-G4 | Staged funding aligned to the gates above |

## Outreach template (MNO / provider)
> Subject: Pilot proposal - enterprise IoT over satellite in Kenya
> We are building a device-management, billing and API layer for narrowband satellite IoT, with a simulator-validated
> link-budget model for Kenya and a working platform (device registry, store-and-forward, metering). We'd like a 90-day pilot
> with [N] devices in [vertical], on your capacity/network, to measure delivery latency, cost per message, and customer demand.
> We can share our coverage and link analysis. Could we schedule 30 minutes?

## Regulatory & compliance checklist (starting point, not legal advice)
- [ ] Engage the CA Kenya on the satellite-to-mobile regime; ask about experimental licences for the Phase 2 test campaign
- [ ] Decide spectrum route: partner-held MNO spectrum vs MSS bands vs experimental; ITU filing timeline if filing own
- [ ] Device type approval for any radio hardware sold or deployed
- [ ] Data Protection Act (Kenya): registration as data controller/processor, location data handling for telematics
- [ ] Contracts: wholesale agreements, SLAs, roaming/interconnect terms
- [ ] Launch licensing and space-object registration pathway with the relevant authority
- [ ] Insurance (launch, in-orbit, third-party)
