from __future__ import annotations

from collections.abc import Iterable

import boto3

from . import checks

ALL_CHECKS = (
    "unattached-volumes",
    "unassociated-eips",
    "gp2-volumes",
    "old-snapshots",
    "idle-instances",
    "bucket-lifecycle",
)


def scan(
    session: boto3.Session,
    regions: Iterable[str],
    selected: Iterable[str] = ALL_CHECKS,
    snapshot_age_days: int = 90,
    cpu_days: int = 14,
    cpu_threshold: float = 5.0,
):
    """Run the selected checks and return a list of Finding objects."""
    selected = set(selected)
    findings = []

    for region in regions:
        ec2 = session.client("ec2", region_name=region)
        if "unattached-volumes" in selected:
            findings += checks.unattached_volumes(ec2, region)
        if "unassociated-eips" in selected:
            findings += checks.unassociated_eips(ec2, region)
        if "gp2-volumes" in selected:
            findings += checks.gp2_volumes(ec2, region)
        if "old-snapshots" in selected:
            findings += checks.old_snapshots(ec2, region, snapshot_age_days)
        if "idle-instances" in selected:
            cloudwatch = session.client("cloudwatch", region_name=region)
            findings += checks.idle_instances(ec2, cloudwatch, region, cpu_days, cpu_threshold)

    if "bucket-lifecycle" in selected:
        findings += checks.buckets_without_lifecycle(session.client("s3"))

    return findings
