from __future__ import annotations

import argparse
import sys

import boto3

from .report import FORMATTERS
from .scanner import ALL_CHECKS, scan


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cost-optimizer",
        description="Read-only scan for common AWS cost waste.",
    )
    p.add_argument("--profile", help="AWS profile name")
    p.add_argument(
        "--region",
        action="append",
        help="Region to scan (repeatable). Defaults to the session's region.",
    )
    p.add_argument("--checks", nargs="+", choices=ALL_CHECKS, default=list(ALL_CHECKS))
    p.add_argument("--format", choices=sorted(FORMATTERS), default="table")
    p.add_argument("--snapshot-age-days", type=int, default=90)
    p.add_argument("--cpu-days", type=int, default=14)
    p.add_argument("--cpu-threshold", type=float, default=5.0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = boto3.Session(profile_name=args.profile)
    regions = args.region or [session.region_name]
    if not regions or regions == [None]:
        print("No region configured. Pass --region or set AWS_DEFAULT_REGION.", file=sys.stderr)
        return 2

    findings = scan(
        session,
        regions,
        selected=args.checks,
        snapshot_age_days=args.snapshot_age_days,
        cpu_days=args.cpu_days,
        cpu_threshold=args.cpu_threshold,
    )
    print(FORMATTERS[args.format](findings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
