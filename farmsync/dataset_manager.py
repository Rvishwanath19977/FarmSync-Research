"""
Full Research Dataset Manager (dataset upload / validation / versioning).

Decoupled from Flask — every function here is importable and unit-testable. The
route module calls into this; no validation logic lives in routes.

Integrity stance (spec: "Never silently fix scientifically important errors"):
validation REPORTS problems with file/row/field/reason and blocks activation on
critical errors. It never rewrites or guesses values.

Security: ZIP extraction is path-traversal-safe, size-limited, and type-checked.
Uploaded content is never executed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# --------------------------------------------------------------------------- #
# Supported files + which are relationally required
# --------------------------------------------------------------------------- #

SUPPORTED_FILES = [
    "farmers.csv", "plots.csv", "crops.csv", "regions.csv", "collectives.csv",
    "crop_region_season_params.csv", "plot_crop_suitability.csv",
    "farmer_preferences.csv", "climate_scenarios.csv", "market_scenarios.csv",
    "hazard_zones.csv", "participation_scenarios.csv",
    "parameter_provenance.csv", "dataset_dictionary.csv",
]

# Core relational backbone — must be present and valid for a complete package.
CORE_FILES = ["farmers.csv", "plots.csv", "crops.csv", "regions.csv", "collectives.csv"]

# Required columns per file (subset that validation depends on).
REQUIRED_COLUMNS = {
    "farmers.csv": ["farmer_id", "collective_id", "region_id", "season"],
    "plots.csv": ["plot_id", "farmer_id", "region_id", "area_ha"],
    "crops.csv": ["crop_id", "crop_name"],
    "regions.csv": ["region_id"],
    "collectives.csv": ["collective_id", "region_id", "season"],
    "crop_region_season_params.csv": ["crop_id", "region_id", "season"],
    "plot_crop_suitability.csv": ["plot_id", "crop_id"],
    "farmer_preferences.csv": ["farmer_id"],
    "climate_scenarios.csv": ["region_id"],
    "market_scenarios.csv": ["crop_id"],
    "hazard_zones.csv": ["hazard_zone"],
    "parameter_provenance.csv": ["parameter", "provenance_type"],
}

MAX_ZIP_BYTES = 50 * 1024 * 1024          # 50 MB compressed
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024
VALID_SEASONS = {"kharif", "rabi"}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def load_csv_text(text: str):
    """Parse CSV text into (headers, rows) where each row is a dict + 1-based line no."""
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = []
    for idx, row in enumerate(reader, start=2):   # line 1 is the header
        rows.append({"_line": idx, **row})
    return headers, rows


@dataclass
class DatasetPackage:
    tables: dict = field(default_factory=dict)     # filename -> {"headers": [...], "rows": [...]}
    raw_files: dict = field(default_factory=dict)  # filename -> original bytes (never lost)
    source: str = "unknown"

    def has(self, filename: str) -> bool:
        return filename in self.tables

    def rows(self, filename: str):
        return self.tables.get(filename, {}).get("rows", [])

    def headers(self, filename: str):
        return self.tables.get(filename, {}).get("headers", [])


def package_from_files(files: dict, source: str = "upload") -> DatasetPackage:
    """files: filename -> bytes. Only SUPPORTED_FILES are loaded; others ignored."""
    pkg = DatasetPackage(source=source)
    for name, data in files.items():
        base = os.path.basename(name)
        if base not in SUPPORTED_FILES:
            continue
        pkg.raw_files[base] = data
        headers, rows = load_csv_text(data.decode("utf-8-sig", errors="replace"))
        pkg.tables[base] = {"headers": headers, "rows": rows}
    return pkg


# --------------------------------------------------------------------------- #
# Secure ZIP extraction
# --------------------------------------------------------------------------- #

class ZipSecurityError(Exception):
    pass


def safe_read_zip(zip_bytes: bytes) -> dict:
    """
    Return {filename: bytes} for supported CSVs inside a ZIP, safely.
    Rejects path traversal, oversized archives, and non-CSV members.
    """
    if len(zip_bytes) > MAX_ZIP_BYTES:
        raise ZipSecurityError(f"ZIP exceeds {MAX_ZIP_BYTES} bytes.")
    out, total = {}, 0
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise ZipSecurityError("Not a valid ZIP file.")
    for info in zf.infolist():
        name = info.filename
        base = os.path.basename(name)
        # path traversal / absolute path / parent refs
        if name.startswith("/") or ".." in name.replace("\\", "/").split("/"):
            raise ZipSecurityError(f"Unsafe path in ZIP: {name}")
        if info.is_dir():
            continue
        if not base.lower().endswith(".csv"):
            continue                                  # only accept CSVs
        if base not in SUPPORTED_FILES:
            continue                                  # ignore unexpected CSVs
        if info.file_size > MAX_FILE_BYTES:
            raise ZipSecurityError(f"{base} exceeds per-file size limit.")
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise ZipSecurityError("Uncompressed size limit exceeded (zip bomb guard).")
        out[base] = zf.read(info)                     # read bytes; never execute
    return out


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

@dataclass
class ValidationError:
    file: str
    row: object          # line number or None
    field: str
    reason: str

    def to_row(self):
        return asdict(self)


@dataclass
class ValidationReport:
    passed: bool = True
    counts: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)      # critical -> block activation
    warnings: list = field(default_factory=list)    # non-blocking
    provenance_coverage: float = 0.0

    def add_error(self, file, row, fld, reason):
        self.errors.append(ValidationError(file, row, fld, reason))
        self.passed = False

    def add_warning(self, file, row, fld, reason):
        self.warnings.append(ValidationError(file, row, fld, reason))

    def summary(self):
        return {
            "passed": self.passed,
            "counts": self.counts,
            "provenance_coverage": self.provenance_coverage,
            "missing_references": sum(1 for e in self.errors if "does not exist" in e.reason),
            "errors": [e.to_row() for e in self.errors],
            "warnings": [w.to_row() for w in self.warnings],
        }


def _ids(pkg, filename, key):
    return {r.get(key) for r in pkg.rows(filename) if r.get(key)}


def _check_duplicates(pkg, filename, key, rep):
    seen = set()
    for r in pkg.rows(filename):
        v = r.get(key)
        if v in seen:
            rep.add_error(filename, r["_line"], key, f"duplicate {key} '{v}'")
        seen.add(v)


def validate_package(pkg: DatasetPackage, mode: str = "complete") -> ValidationReport:
    """
    mode = "complete"  -> full relational validation across all present files.
    mode = "farmer_only" -> validate farmers/plots/collectives against built-in
                            crops/regions (references checked against built-in ids
                            supplied via builtin_ids in complete runs; here we only
                            check internal consistency of the farmer-provided files).
    """
    rep = ValidationReport()

    # presence of core files
    for core in CORE_FILES:
        if mode == "farmer_only" and core in ("crops.csv", "regions.csv"):
            continue
        if not pkg.has(core):
            rep.add_error(core, None, "-", f"required file '{core}' is missing")

    # required columns
    for fname, cols in REQUIRED_COLUMNS.items():
        if pkg.has(fname):
            hdr = pkg.headers(fname)
            for c in cols:
                if c not in hdr:
                    rep.add_error(fname, 1, c, f"required column '{c}' missing")

    if not rep.passed:
        return rep   # stop early; downstream checks assume columns exist

    # duplicate primary keys
    for fname, key in [("farmers.csv", "farmer_id"), ("plots.csv", "plot_id"),
                       ("crops.csv", "crop_id"), ("regions.csv", "region_id"),
                       ("collectives.csv", "collective_id")]:
        if pkg.has(fname):
            _check_duplicates(pkg, fname, key, rep)

    region_ids = _ids(pkg, "regions.csv", "region_id")
    crop_ids = _ids(pkg, "crops.csv", "crop_id")
    farmer_ids = _ids(pkg, "farmers.csv", "farmer_id")
    collective_ids = _ids(pkg, "collectives.csv", "collective_id")

    # collectives -> region + season valid
    for r in pkg.rows("collectives.csv"):
        if r.get("region_id") not in region_ids:
            rep.add_error("collectives.csv", r["_line"], "region_id",
                          f"region_id '{r.get('region_id')}' does not exist in regions.csv")
        if r.get("season") not in VALID_SEASONS:
            rep.add_error("collectives.csv", r["_line"], "season",
                          f"invalid season '{r.get('season')}' (expected kharif/rabi)")

    # farmers -> collective + region + season valid
    for r in pkg.rows("farmers.csv"):
        if collective_ids and r.get("collective_id") not in collective_ids:
            rep.add_error("farmers.csv", r["_line"], "collective_id",
                          f"collective_id '{r.get('collective_id')}' does not exist in collectives.csv")
        if region_ids and r.get("region_id") not in region_ids:
            rep.add_error("farmers.csv", r["_line"], "region_id",
                          f"region_id '{r.get('region_id')}' does not exist in regions.csv")
        if r.get("season") not in VALID_SEASONS:
            rep.add_error("farmers.csv", r["_line"], "season",
                          f"invalid season '{r.get('season')}'")

    # plots -> farmer valid, area positive
    plot_owner_counts = {}
    for r in pkg.rows("plots.csv"):
        fid = r.get("farmer_id")
        plot_owner_counts[fid] = plot_owner_counts.get(fid, 0) + 1
        if farmer_ids and fid not in farmer_ids:
            rep.add_error("plots.csv", r["_line"], "farmer_id",
                          f"farmer_id '{fid}' does not exist in farmers.csv")
        try:
            if float(r.get("area_ha")) <= 0:
                rep.add_error("plots.csv", r["_line"], "area_ha", "area_ha must be positive")
        except (TypeError, ValueError):
            rep.add_error("plots.csv", r["_line"], "area_ha",
                          f"area_ha '{r.get('area_ha')}' is not numeric")
        if region_ids and r.get("region_id") and r.get("region_id") not in region_ids:
            rep.add_error("plots.csv", r["_line"], "region_id",
                          f"region_id '{r.get('region_id')}' does not exist in regions.csv")

    # crop-region-season params reference valid combos
    for r in pkg.rows("crop_region_season_params.csv"):
        if crop_ids and r.get("crop_id") not in crop_ids:
            rep.add_error("crop_region_season_params.csv", r["_line"], "crop_id",
                          f"crop_id '{r.get('crop_id')}' does not exist in crops.csv")
        if region_ids and r.get("region_id") not in region_ids:
            rep.add_error("crop_region_season_params.csv", r["_line"], "region_id",
                          f"region_id '{r.get('region_id')}' does not exist in regions.csv")

    # suitability -> valid plot + crop
    plot_ids = _ids(pkg, "plots.csv", "plot_id")
    for r in pkg.rows("plot_crop_suitability.csv"):
        if plot_ids and r.get("plot_id") not in plot_ids:
            rep.add_error("plot_crop_suitability.csv", r["_line"], "plot_id",
                          f"plot_id '{r.get('plot_id')}' does not exist in plots.csv")
        if crop_ids and r.get("crop_id") not in crop_ids:
            rep.add_error("plot_crop_suitability.csv", r["_line"], "crop_id",
                          f"crop_id '{r.get('crop_id')}' does not exist in crops.csv")

    # climate scenarios -> valid region (+ season if present)
    for r in pkg.rows("climate_scenarios.csv"):
        if region_ids and r.get("region_id") and r.get("region_id") not in region_ids:
            rep.add_error("climate_scenarios.csv", r["_line"], "region_id",
                          f"region_id '{r.get('region_id')}' does not exist in regions.csv")

    # market scenarios -> valid crop (+ region if present)
    for r in pkg.rows("market_scenarios.csv"):
        if crop_ids and r.get("crop_id") and r.get("crop_id") not in crop_ids:
            rep.add_error("market_scenarios.csv", r["_line"], "crop_id",
                          f"crop_id '{r.get('crop_id')}' does not exist in crops.csv")

    # farmer preferences -> valid farmer
    for r in pkg.rows("farmer_preferences.csv"):
        if farmer_ids and r.get("farmer_id") not in farmer_ids:
            rep.add_error("farmer_preferences.csv", r["_line"], "farmer_id",
                          f"farmer_id '{r.get('farmer_id')}' does not exist in farmers.csv")

    # every farmer should own at least one plot
    for fid in farmer_ids:
        if plot_owner_counts.get(fid, 0) == 0:
            rep.add_warning("farmers.csv", None, "farmer_id",
                            f"farmer '{fid}' has no plots")

    # provenance coverage
    prov_rows = pkg.rows("parameter_provenance.csv")
    if prov_rows:
        with_source = sum(1 for r in prov_rows
                          if r.get("provenance_type") in ("SYNTHETIC_EXPERIMENTAL",
                                                          "SYNTHETIC_GROUNDED")
                          or r.get("source"))
        rep.provenance_coverage = round(100.0 * with_source / len(prov_rows), 1)
    else:
        rep.add_warning("parameter_provenance.csv", None, "-",
                        "no provenance file supplied")

    rep.counts = {
        "farmers": len(pkg.rows("farmers.csv")),
        "plots": len(pkg.rows("plots.csv")),
        "collectives": len(pkg.rows("collectives.csv")),
        "regions": len(pkg.rows("regions.csv")),
        "crops": len(pkg.rows("crops.csv")),
        "suitability_records": len(pkg.rows("plot_crop_suitability.csv")),
        "climate_scenarios": len(pkg.rows("climate_scenarios.csv")),
        "market_scenarios": len(pkg.rows("market_scenarios.csv")),
        "hazard_zones": len(pkg.rows("hazard_zones.csv")),
    }
    return rep


# --------------------------------------------------------------------------- #
# Hashing + activation / versioning
# --------------------------------------------------------------------------- #

def dataset_hash(pkg: DatasetPackage) -> str:
    """Stable content hash over supported files (order-independent)."""
    h = hashlib.sha256()
    for name in sorted(pkg.raw_files):
        h.update(name.encode())
        h.update(pkg.raw_files[name])
    return h.hexdigest()[:16]


def activate_snapshot(pkg: DatasetPackage, report: ValidationReport,
                      snapshots_dir: str, dataset_name: str = "farmsync") -> dict:
    """
    Write an immutable, versioned snapshot. Raises if validation did not pass.
    Never overwrites an existing snapshot directory.
    """
    if not report.passed:
        raise ValueError("Cannot activate: validation has critical errors.")
    dh = dataset_hash(pkg)
    ts = datetime.now(timezone.utc)
    version = f"{dataset_name}-{ts.strftime('%Y%m%d%H%M%S')}-{dh}"
    target = os.path.join(snapshots_dir, version)
    if os.path.exists(target):
        raise FileExistsError(f"Snapshot {version} already exists; refusing to overwrite.")
    os.makedirs(target, exist_ok=False)
    for name, data in pkg.raw_files.items():
        with open(os.path.join(target, name), "wb") as fh:
            fh.write(data)                      # preserve original uploaded bytes
    manifest = {
        "dataset_name": dataset_name,
        "dataset_version": version,
        "dataset_hash": dh,
        "activated_at": ts.isoformat(),
        "source": pkg.source,
        "record_counts": report.counts,
        "validation_status": "PASSED",
        "files": sorted(pkg.raw_files),
    }
    with open(os.path.join(target, "_manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest
