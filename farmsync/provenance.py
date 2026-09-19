"""
Provenance framework (spec section 3).

Every important variable in Farm Sync must be classifiable by how it came to
exist. This module provides the vocabulary and the record structure that later
phases are REQUIRED to populate. The optimiser and UI read provenance so that
nothing agronomic is ever presented as fact without a traceable origin.

Design choice worth stating plainly:
  Provenance is recorded per (parameter, crop, region, season) *field family*,
  not per individual synthetic cell. Recording provenance for every one of the
  500-farmer x N-plot cells would produce noise, not evidence. A field family
  carries the generation method, so the origin of any single cell is fully
  reconstructable from (field-family record + generator seed).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class ProvenanceType(str, Enum):
    # A measured/recorded real value taken from a source as-is.
    OBSERVED = "OBSERVED"
    # Computed from observed values by a stated transformation.
    DERIVED = "DERIVED"
    # Synthetic, but the generating distribution/structure is anchored to a
    # real, citable classification or source (e.g. operational-holding size
    # categories from the Agriculture Census). The *shape* is grounded; the
    # individual value is invented.
    SYNTHETIC_GROUNDED = "SYNTHETIC_GROUNDED"
    # Synthetic and chosen as an experimental variable. No real-world claim.
    SYNTHETIC_EXPERIMENTAL = "SYNTHETIC_EXPERIMENTAL"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    # Explicit marker for a parameter that a later phase MUST source before use.
    # The feasibility engine and optimiser are expected to refuse to treat a
    # REQUIRES_SOURCING agronomic value as valid.
    REQUIRES_SOURCING = "REQUIRES_SOURCING"


@dataclass
class ProvenanceRecord:
    """One row of the provenance dataset (spec section 3 field list)."""
    parameter: str
    provenance_type: ProvenanceType
    value: Optional[str] = None          # representative value or "generated"
    unit: Optional[str] = None
    crop: Optional[str] = None
    region: Optional[str] = None
    season: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    source_year: Optional[int] = None
    transformation: Optional[str] = None
    assumption: Optional[str] = None
    confidence: Confidence = Confidence.MEDIUM
    notes: Optional[str] = None

    def __post_init__(self):
        # Integrity rule (spec section 35): a value that claims a real-world
        # origin must actually carry one. Synthetic-experimental values may not.
        if self.provenance_type in (ProvenanceType.OBSERVED, ProvenanceType.DERIVED):
            if not self.source:
                raise ValueError(
                    f"{self.parameter}: {self.provenance_type} requires a 'source'. "
                    f"Do not label a value OBSERVED/DERIVED without one."
                )
        if self.provenance_type == ProvenanceType.SYNTHETIC_GROUNDED and not self.assumption:
            raise ValueError(
                f"{self.parameter}: SYNTHETIC_GROUNDED requires an 'assumption' "
                f"describing what real structure the value is anchored to."
            )

    def to_row(self) -> dict:
        d = asdict(self)
        d["provenance_type"] = self.provenance_type.value
        d["confidence"] = self.confidence.value
        return d


@dataclass
class ProvenanceRegistry:
    """Collects provenance records and reports completeness (spec section 34)."""
    records: list = field(default_factory=list)

    def add(self, record: ProvenanceRecord) -> None:
        self.records.append(record)

    def rows(self) -> list:
        return [r.to_row() for r in self.records]

    def requires_sourcing(self) -> list:
        """Parameters that a later phase must source before they may be used."""
        return [
            r.to_row() for r in self.records
            if r.confidence == Confidence.REQUIRES_SOURCING
        ]

    def breakdown(self) -> dict:
        counts = {t.value: 0 for t in ProvenanceType}
        for r in self.records:
            counts[r.provenance_type.value] += 1
        return counts

    def completeness_check(self) -> dict:
        """
        A parameter family is 'complete' if it is fully synthetic (no external
        claim) OR it carries a source. Anything marked REQUIRES_SOURCING is
        reported as an open obligation, never silently accepted.
        """
        open_obligations = self.requires_sourcing()
        return {
            "total_records": len(self.records),
            "breakdown": self.breakdown(),
            "open_sourcing_obligations": len(open_obligations),
            "obligations": [r["parameter"] for r in open_obligations],
            "complete": len(open_obligations) == 0,
        }
