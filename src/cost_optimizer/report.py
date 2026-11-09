from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence

from .models import Finding


def total_savings(findings: Sequence[Finding]) -> float:
    return round(sum(f.est_monthly_savings for f in findings), 2)


def to_json(findings: Sequence[Finding]) -> str:
    payload = {
        "total_estimated_monthly_savings_usd": total_savings(findings),
        "findings": [f.as_dict() for f in findings],
    }
    return json.dumps(payload, indent=2)


def to_csv(findings: Sequence[Finding]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["check", "resource_id", "region", "est_monthly_savings", "detail"])
    for f in findings:
        writer.writerow([f.check, f.resource_id, f.region, f.est_monthly_savings, f.detail])
    return buf.getvalue()


def to_table(findings: Sequence[Finding]) -> str:
    if not findings:
        return "No findings."
    rows = [("CHECK", "RESOURCE", "REGION", "EST $/MO", "DETAIL")]
    rows += [
        (f.check, f.resource_id, f.region, f"{f.est_monthly_savings:.2f}", f.detail)
        for f in sorted(findings, key=lambda x: -x.est_monthly_savings)
    ]
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    lines = []
    for r in rows:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(4)) + "  " + r[4])
    lines.append("")
    total = total_savings(findings)
    lines.append(f"Estimated monthly savings: ${total:.2f} (rough list-price estimate)")
    return "\n".join(lines)


FORMATTERS = {"table": to_table, "json": to_json, "csv": to_csv}
