# aws-cost-optimizer

A small, read-only command-line tool that scans an AWS account for common cost waste and estimates the monthly savings. It only calls Describe, List and Get APIs and never changes anything.

## What it checks

| Check | Finds | Estimate |
|-------|-------|----------|
| `unattached-volumes` | EBS volumes in the `available` state | size x per-GiB price |
| `unassociated-eips` | Elastic IPs not attached to anything | hourly idle IPv4 charge |
| `gp2-volumes` | gp2 volumes that can move to cheaper gp3 | price difference |
| `old-snapshots` | Snapshots older than N days (default 90) | size x snapshot price |
| `idle-instances` | Running instances with low CPU for N days (default 14, under 5%) | not estimated |
| `bucket-lifecycle` | S3 buckets with no lifecycle rules | not estimated |

## Install and run

```bash
pip install -e ".[dev]"

cost-optimizer --region ca-central-1 --region us-east-1
cost-optimizer --profile prod --format json > findings.json
cost-optimizer --checks unattached-volumes gp2-volumes --format csv
```

Example table output:

```text
CHECK              RESOURCE               REGION        EST $/MO  DETAIL
unattached-volume  vol-0abc123example     ca-central-1  40.00     400 GiB gp3 volume is not attached to any instance
unassociated-eip   eipalloc-0def456       ca-central-1  3.65      Elastic IP 203.0.113.10 is not associated

Estimated monthly savings: $43.65 (rough list-price estimate)
```

## Permissions

`iam-policy.json` contains the minimal read-only policy. Attach it to the role or user running the scan. For multiple accounts, assume a read-only role per account.

## Caveats

- Savings are rough list-price estimates (see `pricing.py`), not your bill. Confirm in Cost Explorer.
- A snapshot flagged as old may back an AMI or a compliance retention rule. Review before deleting.
- Low CPU does not always mean idle: memory-bound, network-bound and bursty workloads can look quiet. Use as a starting point for review.
- The tool reports; it does not delete. That is deliberate.

## Development

```bash
ruff check .
pytest -q
```

Tests use `moto` to mock AWS, so they run without credentials or cost.

## Roadmap

- NAT gateway and data transfer hotspots from Cost Explorer
- Rightsizing hints from Compute Optimizer
- Multi-account scanning through AWS Organizations
- Idle load balancers and unused RDS instances

## License

MIT
