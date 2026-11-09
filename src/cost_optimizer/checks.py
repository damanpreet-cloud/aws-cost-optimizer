"""Individual cost checks. Every function only calls Describe/List/Get APIs."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from . import pricing
from .models import Finding


def _paginate(client, operation: str, key: str, **kwargs) -> Iterator[dict]:
    for page in client.get_paginator(operation).paginate(**kwargs):
        yield from page[key]


def unattached_volumes(ec2, region: str) -> Iterator[Finding]:
    """EBS volumes in the 'available' state are billed but not used."""
    filters = [{"Name": "status", "Values": ["available"]}]
    for vol in _paginate(ec2, "describe_volumes", "Volumes", Filters=filters):
        size = vol["Size"]
        saving = size * pricing.ebs_gb_month(vol["VolumeType"])
        yield Finding(
            "unattached-volume",
            vol["VolumeId"],
            region,
            f"{size} GiB {vol['VolumeType']} volume is not attached to any instance",
            round(saving, 2),
        )


def unassociated_eips(ec2, region: str) -> Iterator[Finding]:
    """Elastic IPs not associated with anything are billed hourly."""
    for addr in ec2.describe_addresses()["Addresses"]:
        if "AssociationId" not in addr:
            yield Finding(
                "unassociated-eip",
                addr.get("AllocationId", addr.get("PublicIp", "unknown")),
                region,
                f"Elastic IP {addr.get('PublicIp')} is not associated",
                round(pricing.EIP_IDLE_MONTH, 2),
            )


def gp2_volumes(ec2, region: str) -> Iterator[Finding]:
    """gp3 is cheaper than gp2 with a higher baseline; migration is online."""
    filters = [{"Name": "volume-type", "Values": ["gp2"]}]
    for vol in _paginate(ec2, "describe_volumes", "Volumes", Filters=filters):
        size = vol["Size"]
        saving = size * (pricing.ebs_gb_month("gp2") - pricing.ebs_gb_month("gp3"))
        yield Finding(
            "gp2-to-gp3",
            vol["VolumeId"],
            region,
            f"{size} GiB gp2 volume can be migrated to gp3",
            round(saving, 2),
        )


def old_snapshots(ec2, region: str, days: int = 90) -> Iterator[Finding]:
    """Snapshots older than `days`. Review before deleting: AMIs and backups may use them."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for snap in _paginate(ec2, "describe_snapshots", "Snapshots", OwnerIds=["self"]):
        if snap["StartTime"] < cutoff:
            size = snap.get("VolumeSize", 0)
            yield Finding(
                "old-snapshot",
                snap["SnapshotId"],
                region,
                f"{size} GiB snapshot older than {days} days",
                round(size * pricing.SNAPSHOT_GB_MONTH, 2),
            )


def idle_instances(
    ec2, cloudwatch, region: str, days: int = 14, cpu_threshold: float = 5.0
) -> Iterator[Finding]:
    """Running instances whose daily average CPU never exceeded the threshold."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    filters = [{"Name": "instance-state-name", "Values": ["running"]}]
    for reservation in _paginate(ec2, "describe_instances", "Reservations", Filters=filters):
        for inst in reservation["Instances"]:
            instance_id = inst["InstanceId"]
            stats = cloudwatch.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start,
                EndTime=end,
                Period=86400,
                Statistics=["Average"],
            )
            points = stats["Datapoints"]
            if points and max(p["Average"] for p in points) < cpu_threshold:
                yield Finding(
                    "idle-instance",
                    instance_id,
                    region,
                    f"{inst['InstanceType']} stayed under {cpu_threshold}% CPU for {days} days",
                )


def buckets_without_lifecycle(s3) -> Iterator[Finding]:
    """Buckets with no lifecycle rules never expire or tier data."""
    for bucket in s3.list_buckets()["Buckets"]:
        try:
            s3.get_bucket_lifecycle_configuration(Bucket=bucket["Name"])
        except ClientError as err:
            code = err.response["Error"]["Code"]
            if code == "NoSuchLifecycleConfiguration":
                yield Finding(
                    "bucket-no-lifecycle",
                    bucket["Name"],
                    "global",
                    "No lifecycle rules; consider tiering or expiring old objects",
                )
            elif code not in {"AccessDenied", "NoSuchBucket"}:
                raise
