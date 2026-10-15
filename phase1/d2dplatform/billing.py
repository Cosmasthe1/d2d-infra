"""Illustrative pricing, aligned with phase3/financial_model.py (~US$8 per device-month incl. 120 msgs at ~US$0.05/msg wholesale).
Replace with real numbers once Phase 1 pilots reveal wholesale cost per message."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Plan:
    currency: str = "KES"
    monthly_per_device: float = 1000.0
    included_msgs: int = 120
    per_extra_msg: float = 15.0

def invoice(plan: Plan, devices: int, msgs: int) -> dict:
    included = devices * plan.included_msgs
    extra = max(0, msgs - included)
    base = devices * plan.monthly_per_device
    return dict(currency=plan.currency, devices=devices, messages=msgs, included=included, extra_messages=extra,
                base=base, overage=extra * plan.per_extra_msg, total=base + extra * plan.per_extra_msg)
