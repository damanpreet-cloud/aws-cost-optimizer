"""Rough on-demand list prices (USD) used for savings *estimates*.

Prices vary by region and change over time. Treat results as order-of-magnitude
guidance and confirm in Cost Explorer before acting.
"""

EBS_GB_MONTH = {
    "gp2": 0.10,
    "gp3": 0.08,
    "io1": 0.125,
    "io2": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
    "standard": 0.05,
}
DEFAULT_EBS_GB_MONTH = 0.10
SNAPSHOT_GB_MONTH = 0.05
EIP_IDLE_MONTH = 0.005 * 730  # idle public IPv4 charged hourly


def ebs_gb_month(volume_type: str) -> float:
    return EBS_GB_MONTH.get(volume_type, DEFAULT_EBS_GB_MONTH)
