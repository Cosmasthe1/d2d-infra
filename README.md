# D2D / Direct-to-Cell infrastructure - implementation

Built in phase order. Each phase has runnable code and tests; Phases 2-3 also generate planning documents from the same models.

| Phase | Folder | What it is | Run |
|---|---|---|---|
| 0 | `phase0/` | NTN simulator: orbits, link budget, Doppler/delay, Kenya coverage, pass schedule, UDP satellite-channel proxy, `tc netem` pass replay | `PYTHONPATH=. python3 run_phase0.py` |
| 1 | `phase1/` | D2D service platform (FastAPI): tenants, device registry, uplink ingest + dedupe, store-and-forward downlink released only during passes, metering/billing | `PYTHONPATH=.:../phase0 uvicorn d2dplatform.main:app` |
| 2a | `testbed/` | Open5GS + UERANSIM testbed with the simulator's pass profile replayed on the radio link (setup, provisioning, experiment, analysis) | `cd testbed && ./setup.sh && ./provision_subscriber.sh && ./run_experiment.sh` |
| 2 | `phase2/` | 6U payload demo: contact analysis over Kenya (RAAN-swept), link closure vs aperture, auto-generated `out/PAYLOAD_SPEC.md` | `PYTHONPATH=.:../phase0 python3 mission_design.py` |
| 3 | `phase3/` | Scenario model (A platform / B +demo+consortium / C own constellation), sensitivity, partner list, decision gates, regulatory checklist | `python3 financial_model.py` |

Tests: `cd phase0 && PYTHONPATH=. pytest tests` ; `cd phase1 && PYTHONPATH=.:../phase0 pytest tests`
Dependencies: numpy, matplotlib, fastapi, uvicorn, httpx, pytest.

## Honest status
- **Verified here:** physics checks, simulator, channel proxy, platform API (all tests pass), generated reports.
- **Not verified here:** the real-stack testbed (`testbed/README.md`) has never run end-to-end; it needs a Linux host with Docker. Its generator, replay driver and analyzer are tested with shims/synthetic data.
- **Models are planning-grade:** spherical Earth, circular two-body orbits, no interference/contention, heuristic required-SNR and loss curves. Use SGP4/real TLEs and 3GPP-conformant link-level simulation before committing hardware money.
- **Phase 3 numbers are placeholders**, and Phases 2c/3 (launch, spectrum, partnerships) are real-world work this repo cannot do for you; it gives you the evidence and gates for doing it.
