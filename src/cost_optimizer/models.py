from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    check: str
    resource_id: str
    region: str
    detail: str
    est_monthly_savings: float = 0.0  # USD, rough estimate; 0.0 means "not estimated"

    def as_dict(self) -> dict:
        return asdict(self)
