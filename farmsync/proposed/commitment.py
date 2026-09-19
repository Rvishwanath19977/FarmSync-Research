"""
Proposed Phase 2 — commitment-state progression and progressive locking.

Adds lifecycle state + lock semantics on top of Phase-1 accepted offers. It does NOT
change the realised allocation, does NOT reoptimise, and does NOT implement the Phase-3
stability penalty. Reuses the existing schemas vocabulary (no parallel state system):

  COMMITMENT_LADDER (schemas): VIEWED → TENTATIVE_ACCEPT → CONFIRMED →
                               INPUTS_PURCHASED → LAND_PREPARED → PLANTED
  FarmerEvent (schemas): ACCEPT / REJECT are the Phase-1 behavioural decisions.

Rejection mapping: ParticipationState has no distinct REJECTED value. A Phase-1 REJECT
is therefore a TERMINAL event on a VIEWED offer (viewed-then-rejected); rejected offers
never enter the ladder and can never progress. This reuse is documented rather than
adding a duplicate state.

Lock policy:
  VIEWED                                            -> FLEXIBLE  (changeable)
  TENTATIVE_ACCEPT/CONFIRMED/INPUTS_PURCHASED/
  LAND_PREPARED                                     -> SOFT_LOCK (technically changeable;
                                                        carries commitment info for Phase 3)
  PLANTED                                           -> HARD_LOCK (immutable)

Ladder advances beyond the first step are scripted commitment ACTIONS (COMMIT_ADVANCE),
not new farmer behavioural events — the only behavioural decision remains Phase-1
ACCEPT/REJECT. Transitions are monotonic single-step and validated.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from ..schemas import ParticipationState as PS, COMMITMENT_LADDER, FarmerEvent

LOCK_FLEXIBLE = "FLEXIBLE"
LOCK_SOFT = "SOFT_LOCK"
LOCK_HARD = "HARD_LOCK"

_LADDER_INDEX = {s: i for i, s in enumerate(COMMITMENT_LADDER)}


def lock_level(state: PS) -> str:
    if state == PS.PLANTED:
        return LOCK_HARD
    if state == PS.VIEWED:
        return LOCK_FLEXIBLE
    if state in COMMITMENT_LADDER:
        return LOCK_SOFT
    return LOCK_FLEXIBLE


def can_change_crop(state: PS) -> bool:
    """PLANTED is immutable (hard lock); every other lifecycle state is technically
    changeable (soft/flexible)."""
    return state != PS.PLANTED


def valid_transition(old: PS, new: PS) -> bool:
    """Monotonic single-step forward along COMMITMENT_LADDER only. No skips, no
    backward moves, no self-loops."""
    if old not in _LADDER_INDEX or new not in _LADDER_INDEX:
        return False
    return _LADDER_INDEX[new] == _LADDER_INDEX[old] + 1


@dataclass
class CommitmentRecord:
    run_id: str
    master_seed: int
    instance_hash: str
    farmer_id: str
    plot_id: str
    crop: str
    state: PS = PS.VIEWED
    accepted: bool = True                 # Phase-1 decision (False => terminal rejected)
    sequence: int = 0                     # order surrogate / monotonic counter
    events: list = field(default_factory=list)

    def snapshot(self, event, prev, new, seq, status, reason=""):
        self.events.append({
            "run_id": self.run_id, "master_seed": self.master_seed,
            "instance_hash": self.instance_hash, "farmer_id": self.farmer_id,
            "plot_id": self.plot_id, "crop": self.crop,
            "prev_state": prev.value if prev else None, "new_state": new.value if new else None,
            "event": event, "sequence": seq, "lock_level": lock_level(new) if new else None,
            "can_change_crop": can_change_crop(new) if new else None,
            "status": status, "reason": reason,
        })


class InvalidTransition(Exception):
    pass


class HardLockViolation(Exception):
    pass


def transition(rec: CommitmentRecord, new_state: PS, event: str, seq: int):
    """Apply a validated forward transition; raise InvalidTransition otherwise."""
    if not rec.accepted:
        raise InvalidTransition("rejected offer cannot enter/advance the commitment ladder")
    if not valid_transition(rec.state, new_state):
        raise InvalidTransition(f"{rec.state.value} -> {new_state.value} not a monotonic single step")
    prev = rec.state
    rec.state = new_state
    rec.sequence = seq
    rec.snapshot(event, prev, new_state, seq, "OK")
    return rec


def attempt_crop_change(rec: CommitmentRecord, new_crop: str):
    """Guard: crop mutation is blocked once hard-locked (PLANTED)."""
    if not can_change_crop(rec.state):
        rec.snapshot("MODIFY", rec.state, rec.state, rec.sequence, "BLOCKED",
                     f"hard-locked ({rec.state.value}); crop immutable")
        raise HardLockViolation(f"cannot change crop in {rec.state.value} (hard lock)")
    rec.crop = new_crop
    rec.snapshot("MODIFY", rec.state, rec.state, rec.sequence, "OK", "crop changed (not hard-locked)")
    return rec


def make_records(realised_offers, run_id, master_seed, instance_hash):
    """Build VIEWED CommitmentRecords for Phase-1 ACCEPTED offers; terminal records for
    REJECTED offers (never enter the ladder)."""
    recs = {}
    for o in realised_offers:
        accepted = o["status"] == "REALISED"
        rec = CommitmentRecord(run_id, master_seed, instance_hash, o["farmer_id"],
                               o["plot_id"], o["planned_crop"], PS.VIEWED, accepted)
        if accepted:
            rec.snapshot(FarmerEvent.ACCEPT.value, None, PS.VIEWED, 0, "OK", "phase-1 accepted; entered lifecycle")
        else:
            rec.snapshot(FarmerEvent.REJECT.value, None, PS.VIEWED, 0, "REJECTED_TERMINAL",
                         "phase-1 rejected; never enters commitment ladder")
        recs[(o["farmer_id"], o["plot_id"])] = rec
    return recs


def progress_scripted(recs, seq_start=1):
    """Deterministically advance every ACCEPTED record one ladder step per round until
    PLANTED. Returns per-round state-count snapshots. Rejected records never advance."""
    seq = seq_start
    snapshots = []
    ladder_after_viewed = COMMITMENT_LADDER[1:]         # TENTATIVE_ACCEPT..PLANTED
    accepted = [r for r in recs.values() if r.accepted]
    for step, target in enumerate(ladder_after_viewed, start=1):
        event = FarmerEvent.ACCEPT.value if target == PS.TENTATIVE_ACCEPT else "COMMIT_ADVANCE"
        for r in sorted(accepted, key=lambda x: (x.farmer_id, x.plot_id)):
            transition(r, target, event, seq)
        seq += 1
        counts = state_counts(recs)
        snapshots.append({"round": step, "advanced_to": target.value, "state_counts": counts})
    return snapshots


def state_counts(recs):
    c = {}
    for r in recs.values():
        c[r.state.value] = c.get(r.state.value, 0) + 1
    return c


def lock_counts(recs):
    out = {LOCK_FLEXIBLE: 0, LOCK_SOFT: 0, LOCK_HARD: 0, "REJECTED_TERMINAL": 0}
    for r in recs.values():
        if not r.accepted:
            out["REJECTED_TERMINAL"] += 1
        else:
            out[lock_level(r.state)] += 1
    return out


# Representative state for each lock bucket in the mixed Phase-3 scenario.
_MIXED_BUCKET = {0: PS.VIEWED, 1: PS.CONFIRMED, 2: PS.PLANTED}


def mixed_commitment_scenario(offers, scenario_id="P3_MIXED_V1"):
    """SYNTHETIC_EXPERIMENTAL commitment-timing scenario (NOT observed prevalence).

    Deterministically and order-independently assigns each Phase-1 ACCEPTED offer to one
    of three commitment states — ~1/3 VIEWED(FLEXIBLE), ~1/3 CONFIRMED(SOFT_LOCK),
    ~1/3 PLANTED(HARD_LOCK) — via a stable hash of scenario_id+farmer+plot+crop. Rejected
    offers stay REJECTED_TERMINAL. Proportions are fixed in advance and not tuned.
    Returns {(farmer_id, plot_id): {state, lock, crop, accepted}}."""
    import hashlib
    scen = {}
    for o in offers:
        accepted = o["status"] == "REALISED"
        if accepted:
            h = hashlib.sha256(f"{scenario_id}:{o['farmer_id']}:{o['plot_id']}:{o['planned_crop']}".encode()).hexdigest()
            state = _MIXED_BUCKET[int(h[:8], 16) % 3]
            scen[(o["farmer_id"], o["plot_id"])] = {
                "state": state, "lock": lock_level(state), "crop": o["planned_crop"], "accepted": True}
        else:
            scen[(o["farmer_id"], o["plot_id"])] = {
                "state": PS.VIEWED, "lock": "REJECTED_TERMINAL",
                "crop": o["planned_crop"], "accepted": False}
    return scen
