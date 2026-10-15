"""Phase 3: scenario model for the scale-up decision. ALL INPUTS ARE ILLUSTRATIVE PLACEHOLDERS - replace with quotes.

Scenarios
  A  Platform-only on partner capacity (no satellites of our own)
  B  Platform + 6U demo (Phase 2) + co-investment in a partner/consortium constellation
  C  Own constellation
Outputs: out/scenarios.csv, out/scenarios.png, out/summary.json
"""
import csv, json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(__file__), "out"); os.makedirs(OUT, exist_ok=True)
M = 60
KES_PER_USD = 129.0                 # assumption
MSGS_PER_DEV_MONTH = 120            # 4 msgs/day
TARGET_GM = 0.45                    # target gross margin when pricing
S = {
  "A": dict(name="A: platform on partner capacity", devices_m60=40_000, wholesale0=0.050, wholesale_scale=0.050, scale_month=None,
            capex=[(0, 0.05)], team=[(0, 4), (12, 8), (30, 15)], extra_opex=2_000),
  "B": dict(name="B: + 6U demo + consortium stake", devices_m60=150_000, wholesale0=0.050, wholesale_scale=0.015, scale_month=36,
            capex=[(12, 2.5), (36, 8.0)], team=[(0, 4), (12, 12), (30, 30)], extra_opex=25_000),
  "C": dict(name="C: own constellation", devices_m60=400_000, wholesale0=0.050, wholesale_scale=0.004, scale_month=42,
            capex=[(12, 2.5), (30, 25.0), (42, 35.0)], team=[(0, 4), (12, 15), (30, 60)], extra_opex=120_000),
}
PRICE_FLOOR, PRICE_CAP = 2.0, 8.0   # USD per device-month, assumption
SALARY_USD_MONTH = 3000             # blended loaded cost, assumption


def interp_steps(steps, m):
    v = steps[0][1]
    for mm, val in steps:
        if m >= mm:
            v = val
    return v


def price_for(wholesale):
    """USD/device/month price that achieves TARGET_GM given wholesale cost per message."""
    return MSGS_PER_DEV_MONTH * wholesale / (1 - TARGET_GM)


def run(sc):
    rows, cash = [], 0.0
    for m in range(M + 1):
        # logistic ramp reaching ~devices_m60 at m=60, starting after month 9 (pilots)
        x = (m - 9) / 6.0
        devices = sc["devices_m60"] * (1 / (1 + np.exp(-(x - 4))) if m >= 9 else 0.0) / (1 / (1 + np.exp(-((60 - 9) / 6.0 - 4))))
        sm = sc["scale_month"]
        w = sc["wholesale_scale"] if (sm is not None and m >= sm) else sc["wholesale0"]
        # price targets TARGET_GM at current wholesale cost but stays inside a market band (assumption):
        # customers won't pay more than PRICE_CAP, and we don't price below PRICE_FLOOR even if costs fall.
        price = min(max(price_for(w), PRICE_FLOOR), PRICE_CAP)
        revenue = devices * price
        cogs = devices * MSGS_PER_DEV_MONTH * w
        team = interp_steps(sc["team"], m) * SALARY_USD_MONTH
        opex = team + sc["extra_opex"] + 0.03 * revenue   # + 3% payment/billing/support variable
        capex = sum(c for mm, c in sc["capex"] if mm == m) * 1e6
        net = revenue - cogs - opex - capex
        cash += net
        rows.append(dict(month=m, devices=int(devices), price_usd=round(price, 2), revenue=round(revenue), cogs=round(cogs),
                         opex=round(opex), capex=round(capex), net=round(net), cum_cash=round(cash)))
    return rows


summary, series = {}, {}
for k, sc in S.items():
    r = run(sc); series[k] = r
    cum = np.array([x["cum_cash"] for x in r]); net = np.array([x["net"] for x in r])
    be = next((x["month"] for x in r if x["net"] > 0 and x["month"] > 12 and x["capex"] == 0), None)
    gm = 1 - r[-1]["cogs"] / r[-1]["revenue"] if r[-1]["revenue"] else None
    summary[k] = dict(name=sc["name"], peak_funding_need_usd_m=round(-cum.min() / 1e6, 2),
                      month60_revenue_usd_m=round(r[-1]["revenue"] * 12 / 1e6, 2) , month60_devices=r[-1]["devices"],
                      first_operating_positive_month=be, month60_cum_cash_usd_m=round(cum[-1] / 1e6, 2),
                      gross_margin_m60=round(gm, 2) if gm is not None else None, price_usd_m60=r[-1]["price_usd"])
with open(f"{OUT}/scenarios.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["scenario"] + list(series["A"][0].keys()))
    for k, r in series.items():
        for x in r:
            w.writerow([k] + list(x.values()))
json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=1)

# sensitivity: wholesale cost per message vs price needed and breakeven devices at A's opex
sens = []
for ws in (0.2, 0.1, 0.05, 0.02, 0.01, 0.004):
    p = price_for(ws); gm_per_dev = p * 0.97 - MSGS_PER_DEV_MONTH * ws
    be_dev = (15 * SALARY_USD_MONTH + 2000) / gm_per_dev if gm_per_dev > 0 else float("inf")
    sens.append(dict(wholesale_usd_msg=ws, price_usd_dev_month=round(p, 2), price_kes=round(p * KES_PER_USD),
                     devices_to_cover_15_person_team=int(be_dev) if be_dev != float("inf") else None))
json.dump(sens, open(f"{OUT}/sensitivity.json", "w"), indent=1)

fig, ax = plt.subplots(1, 2, figsize=(12, 4))
for k, r in series.items():
    ax[0].plot([x["month"] for x in r], [x["cum_cash"] / 1e6 for x in r], label=S[k]["name"])
    ax[1].plot([x["month"] for x in r], [x["devices"] / 1e3 for x in r], label=k)
ax[0].set_title("Cumulative cash (USD m)"); ax[1].set_title("Connected devices (thousands)")
for a_ in ax: a_.set_xlabel("month"); a_.grid(alpha=.3)
ax[0].legend(fontsize=8); ax[1].legend()
fig.savefig(f"{OUT}/scenarios.png", dpi=110, bbox_inches="tight")
print(json.dumps(summary, indent=1)); print(json.dumps(sens, indent=0))
