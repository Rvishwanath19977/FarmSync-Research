"""
Proposed Phase 1 — voluntary farmer participation (ACCEPT / REJECT).

Isolates the pure participation effect: static B3 plan → voluntary response →
realised allocation. Rejected offers become fallow; NO reassignment, NO
reoptimisation (those belong to later phases). MODIFY/WITHDRAW remain unimplemented
enum placeholders.

Determinism: each response is a hash draw keyed by
    sha256(farmer_response_subseed : farmer_id : plot_id : offered_crop)
so responses are reproducible and independent of iteration order.

Acceptance model is SYNTHETIC_EXPERIMENTAL — it does NOT represent observed Indian
farmer acceptance prevalence. The exact config is recorded in every result.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict

from ..baselines import B1Result, Allocation
from ..schemas import FarmerEvent


@dataclass
class AcceptanceConfig:
    """Inspectable acceptance model. p_accept(farmer) = clip(base + sensitivity*(risk-0.5))."""
    base_accept_prob: float = 0.85
    risk_sensitivity: float = 0.20          # uses existing farmer.risk_tolerance [0,1]
    provenance: str = "SYNTHETIC_EXPERIMENTAL"
    note: str = ("experimental assumption; NOT observed Indian farmer acceptance prevalence; "
                 "risk_tolerance is a provenance-labelled synthetic farmer attribute")

    def p_accept(self, farmer) -> float:
        p = self.base_accept_prob + self.risk_sensitivity * (getattr(farmer, "risk_tolerance", 0.5) - 0.5)
        return max(0.0, min(1.0, round(p, 4)))

    def to_dict(self):
        return asdict(self)


def response_draw(subseed, farmer_id, plot_id, crop) -> float:
    """Deterministic uniform [0,1) keyed by subseed+ids+crop (order-independent)."""
    h = hashlib.sha256(f"{subseed}:{farmer_id}:{plot_id}:{crop}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def apply_participation(planned: B1Result, farmers, subseed, config: AcceptanceConfig,
                        run_id="p1", master_seed=None, instance_hash=None):
    """Return (realised_result, offer_records). Realised = accepted subset of planned.
    Rejected plots become FALLOW; no reassignment/reoptimisation."""
    farmer_by_id = {f.farmer_id: f for f in farmers}
    realised = B1Result()
    offers = []
    # order-stable iteration (sort by ids) — does not affect responses, but keeps output stable
    for a in sorted(planned.allocations, key=lambda x: (x.farmer_id, x.plot_id, x.crop)):
        f = farmer_by_id[a.farmer_id]
        p = config.p_accept(f)
        draw = response_draw(subseed, a.farmer_id, a.plot_id, a.crop)
        accepted = draw < p
        event = FarmerEvent.ACCEPT if accepted else FarmerEvent.REJECT
        if accepted:
            realised.allocations.append(a)
        offers.append({
            "run_id": run_id, "master_seed": master_seed, "instance_hash": instance_hash,
            "farmer_id": a.farmer_id, "plot_id": a.plot_id, "region_season": None,
            "planned_crop": a.crop, "planned_cash_return": a.cash_net,
            "response": event.value, "p_accept": p, "response_draw": round(draw, 6),
            "response_subseed": subseed, "acceptance_provenance": config.provenance,
            "realised_crop": a.crop if accepted else "FALLOW_UNALLOCATED",
            "realised_cash_return": a.cash_net if accepted else 0.0,
            "status": "REALISED" if accepted else "REJECTED_FALLOW",
        })
    assigned = {o["plot_id"] for o in offers if o["status"] == "REALISED"}
    realised.total_return = round(sum(x.net_return for x in realised.allocations), 0)
    return realised, offers
