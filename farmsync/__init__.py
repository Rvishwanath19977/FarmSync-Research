"""
Farm Sync — Farmer-in-the-Loop Collective Crop Planning research demonstrator.

Research prototype. NOT a production farming system.
All farmer/plot records produced by this package are SYNTHETIC and are labelled
as such. No record in this package represents a real, identifiable farmer.

This package is deliberately decoupled from Flask. Route logic lives in
farmsync_routes.py (added later, per the phased build order). The engine here
must be importable and testable without a running web server.

Phase status (per the project spec's development order, section 36):
  [x] Phase 2  research/data schemas
  [x] Phase 3  provenance framework
  [x] Phase 4  farmer + plot synthetic generator (seeded, reproducible)
  [ ] Phase 5  agricultural parameter dataset        (REQUIRES real sourcing)
  [ ] Phase 6  plot-level feasibility engine
  [ ] Phase 7+ optimisation, resilience, LLM boundary, UI, experiments...
"""

DATASET_VERSION = "v0.1.0"
# Master seed. The same master seed regenerates a byte-identical dataset.
DEFAULT_MASTER_SEED = 20260812

__all__ = ["DATASET_VERSION", "DEFAULT_MASTER_SEED"]
