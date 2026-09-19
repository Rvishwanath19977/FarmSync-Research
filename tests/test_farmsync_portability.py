"""Portability regression tests: project-root resolution must be sandbox-free, Windows/Linux
safe, honour explicit overrides, and leave all frozen scientific values identical."""
import os, json, inspect
import pytest
from pathlib import Path

from farmsync import experiment as exp

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(RAW, "des_apy")),
                                reason="raw sources not present")


def test_project_root_resolves_to_repo_root():
    # farmsync/experiment.py -> <root>/farmsync/experiment.py, so project_root() is the repo root
    root = exp.project_root()
    assert (root / "farmsync" / "experiment.py").exists()
    assert str(root) == _ROOT


def test_no_sandbox_path_in_runtime_defaults():
    # none of the artifact loaders may default to a /mnt sandbox path
    for fn in (exp.load_rng_streams, exp.load_seeds, exp.substream):
        sig = inspect.signature(fn)
        assert sig.parameters["base"].default is None, fn.__name__
    # and the source of the runtime modules must be free of the sandbox prefix
    import farmsync.proposed.pipeline as pl
    for mod in (exp, pl):
        src = Path(inspect.getfile(mod)).read_text()
        assert "/mnt/user-data" not in src, mod.__name__


def test_default_base_finds_rng_streams_from_repo():
    streams = exp.load_rng_streams()                 # default base -> project root
    assert "per_seed_substreams" in streams
    assert (exp.project_root() / "results" / "farmsync" / "audit" / "rng_streams.json").exists()


def test_explicit_base_override_still_works():
    explicit = exp.substream(20260812, "farmer_response", base=str(exp.project_root()))
    default = exp.substream(20260812, "farmer_response")
    assert explicit == default


def test_windows_and_posix_path_construction():
    # _resolve must produce a normalised path with no mixed sandbox fragment, both styles of base
    p_posix = exp._resolve("/tmp/repo", exp.RNG_FILE)
    p_win = exp._resolve(r"C:\repo", exp.RNG_FILE)
    assert "/mnt/user-data" not in p_posix and "/mnt/user-data" not in p_win
    # the project-relative tail is preserved
    assert p_posix.endswith(os.path.join("audit", "rng_streams.json")) or p_posix.replace("/", os.sep).endswith(os.path.join("audit", "rng_streams.json"))


def test_frozen_substreams_and_seeds_identical():
    # frozen values must be byte-for-byte what the audit artifact records
    streams = exp.load_rng_streams()["per_seed_substreams"]
    seeds = exp.load_seeds()
    assert len(seeds) == 30                            # frozen 30-replication set
    # every frozen seed's stored substream is returned verbatim (no re-derivation)
    for s, table in streams.items():
        for stream_name, val in table.items():
            assert exp.substream(int(s), stream_name) == val


def test_instance_hash_unchanged_after_portability_fix():
    from farmsync.ingest.run_ingest import run
    from farmsync.ingest import operational as opdata
    run(os.path.join(RAW), os.path.join(RAW, "..", "processed"))
    opdata.load(os.path.join(RAW, "..", "processed"))
    inst = exp.build_instance(20260812, tightness="base")
    assert inst["record"]["instance_hash"] == "5ea24037c2d9cb6a"   # frozen, unchanged
