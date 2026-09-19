"""
Dataset manager tests — cross-file validation (incl. collectives), ZIP security,
hashing, and activation/versioning.
"""

import io
import os
import zipfile
import tempfile

import pytest

from farmsync.build_builtin_dataset import build_builtin_dataset
from farmsync.dataset_manager import (
    package_from_files, validate_package, safe_read_zip, ZipSecurityError,
    dataset_hash, activate_snapshot, SUPPORTED_FILES,
)


@pytest.fixture(scope="module")
def builtin_files():
    with tempfile.TemporaryDirectory() as d:
        build_builtin_dataset(d, n_farmers=60, n_collectives=6)
        files = {}
        for name in os.listdir(d):
            with open(os.path.join(d, name), "rb") as f:
                files[name] = f.read()
        yield files


def test_builtin_dataset_has_collectives(builtin_files):
    assert "collectives.csv" in builtin_files
    assert "farmers.csv" in builtin_files


def test_builtin_dataset_validates_clean(builtin_files):
    pkg = package_from_files(builtin_files, source="builtin")
    rep = validate_package(pkg)
    assert rep.passed, rep.summary()["errors"][:5]
    assert rep.counts["collectives"] == 6
    assert rep.counts["farmers"] == 60


def test_collective_bad_region_is_flagged(builtin_files):
    files = dict(builtin_files)
    # corrupt a collective to reference a non-existent region
    text = files["collectives.csv"].decode()
    lines = text.splitlines()
    parts = lines[1].split(",")
    parts[2] = "R999"                       # region_id column
    lines[1] = ",".join(parts)
    files["collectives.csv"] = "\n".join(lines).encode()
    rep = validate_package(package_from_files(files))
    assert not rep.passed
    assert any(e.field == "region_id" and "R999" in e.reason for e in rep.errors)


def test_farmer_referencing_missing_collective_flagged(builtin_files):
    files = dict(builtin_files)
    # remove collectives file entirely -> farmers reference missing collectives
    text = files["farmers.csv"].decode().splitlines()
    parts = text[1].split(",")
    # find collective_id column index from header
    hdr = files["farmers.csv"].decode().splitlines()[0].split(",")
    ci = hdr.index("collective_id")
    parts[ci] = "C99"
    text[1] = ",".join(parts)
    files["farmers.csv"] = "\n".join(text).encode()
    rep = validate_package(package_from_files(files))
    assert not rep.passed
    assert any("C99" in e.reason for e in rep.errors)


def test_negative_plot_area_flagged(builtin_files):
    files = dict(builtin_files)
    hdr = files["plots.csv"].decode().splitlines()[0].split(",")
    ai = hdr.index("area_ha")
    lines = files["plots.csv"].decode().splitlines()
    parts = lines[1].split(",")
    parts[ai] = "-1"
    lines[1] = ",".join(parts)
    files["plots.csv"] = "\n".join(lines).encode()
    rep = validate_package(package_from_files(files))
    assert not rep.passed
    assert any(e.field == "area_ha" for e in rep.errors)


def test_zip_roundtrip_reads_supported_csvs(builtin_files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in builtin_files.items():
            zf.writestr(name, data)
    got = safe_read_zip(buf.getvalue())
    assert "collectives.csv" in got and "farmers.csv" in got


def test_zip_path_traversal_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/evil.csv", "x")
    with pytest.raises(ZipSecurityError):
        safe_read_zip(buf.getvalue())


def test_zip_ignores_non_csv_and_unexpected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("farmers.csv", "farmer_id\nF0001\n")
        zf.writestr("evil.exe", "MZ...")
        zf.writestr("random.csv", "a,b\n1,2\n")
    got = safe_read_zip(buf.getvalue())
    assert "evil.exe" not in got
    assert "random.csv" not in got        # not in SUPPORTED_FILES
    assert "farmers.csv" in got


def test_hash_is_stable_and_order_independent(builtin_files):
    p1 = package_from_files(builtin_files)
    reordered = dict(reversed(list(builtin_files.items())))
    p2 = package_from_files(reordered)
    assert dataset_hash(p1) == dataset_hash(p2)


def test_activation_writes_versioned_snapshot(builtin_files):
    pkg = package_from_files(builtin_files, source="builtin")
    rep = validate_package(pkg)
    with tempfile.TemporaryDirectory() as snaps:
        manifest = activate_snapshot(pkg, rep, snaps, dataset_name="farmsync")
        assert manifest["validation_status"] == "PASSED"
        assert manifest["dataset_hash"] in manifest["dataset_version"]
        snap_dir = os.path.join(snaps, manifest["dataset_version"])
        assert os.path.exists(os.path.join(snap_dir, "_manifest.json"))
        assert os.path.exists(os.path.join(snap_dir, "collectives.csv"))


def test_activation_blocked_on_validation_failure(builtin_files):
    files = dict(builtin_files)
    del files["regions.csv"]              # break a core relational file
    pkg = package_from_files(files)
    rep = validate_package(pkg)
    assert not rep.passed
    with tempfile.TemporaryDirectory() as snaps:
        with pytest.raises(ValueError):
            activate_snapshot(pkg, rep, snaps)
