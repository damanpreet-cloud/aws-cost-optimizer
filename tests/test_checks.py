from datetime import datetime, timedelta, timezone

import boto3
from moto import mock_aws

from cost_optimizer import checks
from cost_optimizer.report import to_csv, to_json, to_table, total_savings
from cost_optimizer.scanner import scan

REGION = "us-east-1"


def _ec2():
    return boto3.client("ec2", region_name=REGION)


@mock_aws
def test_unattached_volume_is_flagged_with_savings():
    ec2 = _ec2()
    vol = ec2.create_volume(AvailabilityZone=f"{REGION}a", Size=100, VolumeType="gp3")

    findings = list(checks.unattached_volumes(ec2, REGION))

    assert [f.resource_id for f in findings] == [vol["VolumeId"]]
    assert findings[0].est_monthly_savings == 8.0  # 100 GiB * $0.08


@mock_aws
def test_unassociated_eip_is_flagged():
    ec2 = _ec2()
    alloc = ec2.allocate_address(Domain="vpc")

    findings = list(checks.unassociated_eips(ec2, REGION))

    assert [f.resource_id for f in findings] == [alloc["AllocationId"]]
    assert findings[0].est_monthly_savings == 3.65


@mock_aws
def test_gp2_volume_suggests_gp3_migration():
    ec2 = _ec2()
    ec2.create_volume(AvailabilityZone=f"{REGION}a", Size=200, VolumeType="gp2")
    ec2.create_volume(AvailabilityZone=f"{REGION}a", Size=200, VolumeType="gp3")

    findings = list(checks.gp2_volumes(ec2, REGION))

    assert len(findings) == 1
    assert findings[0].est_monthly_savings == 4.0  # 200 GiB * ($0.10 - $0.08)


@mock_aws
def test_old_snapshots_respects_age_threshold():
    ec2 = _ec2()
    vol = ec2.create_volume(AvailabilityZone=f"{REGION}a", Size=10)
    snap_id = ec2.create_snapshot(VolumeId=vol["VolumeId"])["SnapshotId"]

    # moto pre-seeds unrelated snapshots, so look for ours by ID.
    recent = {f.resource_id for f in checks.old_snapshots(ec2, REGION, days=90)}
    assert snap_id not in recent

    aged = {f.resource_id for f in checks.old_snapshots(ec2, REGION, days=0)}
    assert snap_id in aged


@mock_aws
def test_idle_instance_detected_from_low_cpu():
    ec2 = _ec2()
    cw = boto3.client("cloudwatch", region_name=REGION)
    image = ec2.describe_images()["Images"][0]["ImageId"]
    instance_id = ec2.run_instances(ImageId=image, MinCount=1, MaxCount=1)["Instances"][0][
        "InstanceId"
    ]
    cw.put_metric_data(
        Namespace="AWS/EC2",
        MetricData=[
            {
                "MetricName": "CPUUtilization",
                "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                "Timestamp": datetime.now(timezone.utc) - timedelta(days=1),
                "Value": 1.5,
                "Unit": "Percent",
            }
        ],
    )

    findings = list(checks.idle_instances(ec2, cw, REGION))

    assert [f.resource_id for f in findings] == [instance_id]


@mock_aws
def test_bucket_without_lifecycle_flagged_then_cleared():
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="demo-bucket")

    assert [f.resource_id for f in checks.buckets_without_lifecycle(s3)] == ["demo-bucket"]

    s3.put_bucket_lifecycle_configuration(
        Bucket="demo-bucket",
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "expire-old",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Expiration": {"Days": 365},
                }
            ]
        },
    )

    assert list(checks.buckets_without_lifecycle(s3)) == []


@mock_aws
def test_scan_and_reports():
    ec2 = _ec2()
    ec2.create_volume(AvailabilityZone=f"{REGION}a", Size=50, VolumeType="gp2")
    ec2.allocate_address(Domain="vpc")

    findings = scan(
        boto3.Session(region_name=REGION),
        [REGION],
        selected=["unattached-volumes", "unassociated-eips", "gp2-volumes"],
    )

    assert total_savings(findings) == round(50 * 0.10 + 3.65 + 50 * 0.02, 2)
    assert "unattached-volume" in to_table(findings)
    assert "total_estimated_monthly_savings_usd" in to_json(findings)
    assert to_csv(findings).startswith("check,resource_id")
