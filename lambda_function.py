import boto3
import os
from datetime import datetime, timezone, timedelta

ec2 = boto3.client("ec2")

RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "30"))
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"


def get_all_snapshots():
    snapshots = []

    paginator = ec2.get_paginator("describe_snapshots")

    for page in paginator.paginate(OwnerIds=["self"]):
        snapshots.extend(page["Snapshots"])

    return snapshots


def get_existing_volume_ids():
    volume_ids = set()

    paginator = ec2.get_paginator("describe_volumes")

    for page in paginator.paginate():
        for volume in page["Volumes"]:
            volume_ids.add(volume["VolumeId"])

    return volume_ids


def is_old_enough(snapshot):
    snapshot_age = datetime.now(timezone.utc) - snapshot["StartTime"]

    return snapshot_age > timedelta(days=RETENTION_DAYS)


def delete_snapshot(snapshot):
    snapshot_id = snapshot["SnapshotId"]

    if DRY_RUN:
        print(f"[DRY RUN] Would delete snapshot: {snapshot_id}")
        return "dry_run"

    try:
        ec2.delete_snapshot(
            SnapshotId=snapshot_id
        )

        print(f"Deleted snapshot: {snapshot_id}")

        return "deleted"

    except Exception as error:
        print(
            f"Failed to delete snapshot "
            f"{snapshot_id}: {error}"
        )

        return "failed"


def lambda_handler(event, context):

    print("Starting EBS Snapshot Cleanup")
    print(f"Retention period: {RETENTION_DAYS} days")
    print(f"Dry run enabled: {DRY_RUN}")

    snapshots = get_all_snapshots()

    existing_volume_ids = get_existing_volume_ids()

    print(f"Snapshots found: {len(snapshots)}")
    print(
        f"Existing EBS volumes found: "
        f"{len(existing_volume_ids)}"
    )

    stale_snapshots = []

    for snapshot in snapshots:

        snapshot_id = snapshot["SnapshotId"]
        volume_id = snapshot.get("VolumeId")

        # If the source volume no longer exists,
        # the snapshot is considered orphaned.
        if volume_id and volume_id not in existing_volume_ids:

            if is_old_enough(snapshot):

                stale_snapshots.append(snapshot)

                print(
                    f"Stale snapshot found: "
                    f"{snapshot_id} "
                    f"(Volume: {volume_id})"
                )

    print(
        f"Total stale snapshots: "
        f"{len(stale_snapshots)}"
    )

    deleted = 0
    dry_run_count = 0
    failed = 0

    for snapshot in stale_snapshots:

        result = delete_snapshot(snapshot)

        if result == "deleted":
            deleted += 1

        elif result == "dry_run":
            dry_run_count += 1

        elif result == "failed":
            failed += 1

    result = {
        "statusCode": 200,
        "snapshots_checked": len(snapshots),
        "stale_snapshots": len(stale_snapshots),
        "deleted": deleted,
        "dry_run": dry_run_count,
        "failed": failed,
        "retention_days": RETENTION_DAYS,
        "dry_run_enabled": DRY_RUN
    }

    print(f"Cleanup result: {result}")

    return result
