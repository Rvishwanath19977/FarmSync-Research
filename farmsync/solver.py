"""Central CBC solver factory.

Single place that constructs the CBC solver command for FarmSync's time-limited optimisation calls
(B2, B3, the `_solve`/`_central_solve` helper, and Phase-3 reoptimisation), so the thread setting is
applied uniformly. The number of CBC threads is OS-conditional:

    * Windows      -> threads=0
    * other OSes   -> threads=1   (unchanged from the original behaviour)

Note: `farmsync/ilp_reference.py::b1_ilp_total()` intentionally performs a bare per-farmer audit
solve via `PULP_CBC_CMD(msg=0)` (no time limit / gapRel / thread setting) and does NOT go through
this factory; it returns only an aggregate cash figure with no solver-configuration metadata. Every
call that DOES set an explicit thread count routes through here.

The threads=0 value on Windows has been empirically validated on the real canonical FarmSync
workloads (with threads=1 the canonical 500-farmer solve repeatedly stalled on Windows, while the
small solves did not). No claim is made here about CBC's internal meaning of threads=0; the setting
is used solely because it was empirically validated to complete the real Windows FarmSync solves.

All other solver parameters are preserved exactly except for the pre-Final30 numerical-reproducibility amendment: timeLimit (default 120 s), gapRel (1e-6), and the
existing msg behaviour. Callers continue to treat only an Optimal status as valid.
"""
from __future__ import annotations
import platform
import pulp


def _cbc_threads() -> int:
    return 0 if platform.system() == "Windows" else 1


def cbc_threads() -> int:
    """Public accessor for the effective CBC thread count actually used on this OS.
    Use this for provenance/solver metadata so it reflects the real configuration
    (0 on Windows, 1 elsewhere) rather than a hardcoded value."""
    return _cbc_threads()


def cbc_solver(time_limit=120, gap_rel=1e-6, msg=0):
    """Return a configured PULP_CBC_CMD. threads is OS-conditional (see module docstring)."""
    return pulp.PULP_CBC_CMD(msg=msg, timeLimit=time_limit, gapRel=gap_rel, threads=_cbc_threads())
