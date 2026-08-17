# AWS EBS Snapshot Cleanup with Lambda

Automated cleanup of stale Amazon EBS snapshots using AWS Lambda and Boto3 to reduce unnecessary cloud storage costs.

## Overview

Amazon EBS snapshots are point-in-time backups of EBS volumes attached to EC2 instances.

Snapshots are useful for:

- Backup and recovery
- Disaster recovery
- Restoring data after failures
- Creating new EBS volumes from previous states

However, snapshots can accumulate over time.

For example:

```text
EBS Volume
    |
    +-- Snapshot 1
    +-- Snapshot 2
    +-- Snapshot 3
    +-- Snapshot 4
    +-- ...
```

If the original EBS volume is eventually deleted, the snapshots created from that volume are not automatically deleted.

Over time, these orphaned snapshots can continue generating snapshot storage costs.

This project automates the identification and cleanup of old orphaned EBS snapshots using AWS Lambda.

---

## Problem

In a growing AWS environment, there may be hundreds of EC2 instances and thousands of EBS snapshots.

Some snapshots may belong to EBS volumes that no longer exist.

Manually finding these snapshots is:

- Time-consuming
- Error-prone
- Difficult to scale
- Easy to forget

The goal of this project is to automatically identify snapshots that:

1. Belong to an EBS volume that no longer exists
2. Are older than the configured retention period

and then remove them when automatic deletion is enabled.

---

## Solution

The Lambda function performs the following workflow:

```text
Fetch Account-Owned Snapshots
            |
            v
Fetch Existing EBS Volumes
            |
            v
Does Source Volume Exist?
       /            \
     YES             NO
      |               |
   RETAIN             v
              Age > RETENTION_DAYS?
                  /          \
                NO            YES
                |              |
             RETAIN          DRY_RUN?
                              /     \
                            YES       NO
                             |         |
                         LOG ONLY    DELETE
```

Lambda execution logs are sent to Amazon CloudWatch.

The Lambda can be triggered manually during testing or automatically using Amazon EventBridge.

---

## Architecture

```text
                    Amazon EventBridge
                     (Daily Schedule)
                            |
                            v
                     AWS Lambda
                  (Python 3.x + Boto3)
                     |           |
                     |           +--------------> CloudWatch Logs
                     |                            (Execution & Monitoring)
                     |
             +-------+-------+
             |               |
             v               v
    DescribeSnapshots   DescribeVolumes
    (Account-Owned      (Existing EBS
     Snapshots)          Volumes)
             |               |
             +-------+-------+
                     |
                     v
            Cleanup Evaluation
                     |
                     v
             Delete if Eligible
```

---

## AWS Services Used

| Service | Purpose |
|---|---|
| AWS Lambda | Runs the snapshot cleanup logic |
| Amazon EC2 | Provides the EBS volumes being evaluated |
| Amazon EBS | Provides persistent block storage and snapshots |
| Amazon EventBridge | Triggers the Lambda on a schedule |
| AWS IAM | Controls Lambda permissions |
| Amazon CloudWatch | Stores Lambda execution logs |

---

## How It Works

The Lambda function uses Boto3, the AWS SDK for Python, to communicate with the EC2 API.

### 1. Fetch Account-Owned Snapshots

The Lambda retrieves snapshots owned by the current AWS account using:

```python
ec2.describe_snapshots()
```

The implementation uses:

```python
OwnerIds=["self"]
```

to retrieve account-owned snapshots.

Pagination is used so the function can handle more than a single API response.

### 2. Fetch Existing EBS Volumes

The Lambda retrieves the EBS volumes that currently exist:

```python
ec2.describe_volumes()
```

The resulting volume IDs are stored in a set for efficient lookup.

### 3. Check Whether the Source Volume Exists

Each EBS snapshot contains the ID of the EBS volume from which it was created.

For example:

```text
Snapshot
    |
    +-- VolumeId = vol-123456
```

The Lambda checks whether the volume still exists.

If the source volume exists, the snapshot is retained.

If the source volume no longer exists, the snapshot proceeds to the age check.

### 4. Check the Retention Period

An orphaned snapshot is not immediately deleted.

The Lambda checks its age against the configured retention period.

For example:

```text
RETENTION_DAYS=30
```

A snapshot that is 10 days old is retained.

A snapshot that is 45 days old becomes eligible for cleanup.

### 5. Dry Run Check

Before deleting an eligible snapshot, the Lambda checks the `DRY_RUN` environment variable.

When:

```text
DRY_RUN=true
```

the Lambda only logs what it would delete:

```text
[DRY RUN] Would delete snapshot: snap-0123456789abcdef0
```

No deletion takes place.

When:

```text
DRY_RUN=false
```

the Lambda calls:

```python
ec2.delete_snapshot()
```

and deletes the eligible snapshot.

---

## Configuration

### RETENTION_DAYS

Defines how old an orphaned snapshot must be before it becomes eligible for deletion.

Default:

```text
30
```

Example:

```text
RETENTION_DAYS=30
```

### DRY_RUN

Controls whether deletion is enabled.

Default:

```text
true
```

Testing:

```text
DRY_RUN=true
```

Automatic deletion:

```text
DRY_RUN=false
```

It is recommended to run the Lambda in dry-run mode first and review the CloudWatch logs before enabling deletion.

---

## IAM Permissions

The Lambda execution role requires:

```text
ec2:DescribeSnapshots
ec2:DescribeVolumes
ec2:DeleteSnapshot
```

These permissions are provided in `iam-policy.json`.

The Lambda execution role also requires permission to write execution logs to CloudWatch.

For example:

```text
AWSLambdaBasicExecutionRole
```

can be attached to the Lambda execution role.

---

## Project Structure

```text
aws-ebs-snapshot-cleanup/
|
├── lambda_function.py
├── iam-policy.json
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Deployment

### Step 1: Create the Lambda Function

Create a new AWS Lambda function using Python.

Upload:

```text
lambda_function.py
```

Set the handler to:

```text
lambda_function.lambda_handler
```

### Step 2: Create the IAM Role

Create an IAM execution role trusted by Lambda.

Attach:

```text
AWSLambdaBasicExecutionRole
```

and the permissions from:

```text
iam-policy.json
```

### Step 3: Configure Environment Variables

Start with:

```text
RETENTION_DAYS=30
DRY_RUN=true
```

### Step 4: Test the Lambda

Invoke the Lambda manually and check the CloudWatch logs.

Example:

```text
Starting EBS Snapshot Cleanup

Retention period: 30 days
Dry run enabled: True

Snapshots found: 20
Existing EBS volumes found: 6

Source volume vol-123456 does not exist
for snapshot snap-0123456789abcdef0

Stale snapshot candidate:
snap-0123456789abcdef0

[DRY RUN] Would delete snapshot:
snap-0123456789abcdef0

Cleanup completed
```

### Step 5: Enable Deletion

After validating the identified snapshots:

```text
DRY_RUN=false
```

The Lambda can then delete snapshots that satisfy the cleanup conditions.

### Step 6: Schedule Automatic Execution

Create an Amazon EventBridge scheduled rule to invoke the Lambda periodically.

For example:

```text
Every 24 hours
      |
      v
EventBridge
      |
      v
Lambda
      |
      v
EBS Snapshot Cleanup
```

---

## Example

Suppose the AWS account contains:

```text
Snapshot A
Volume: vol-111
Age: 10 days

Snapshot B
Volume: vol-222
Age: 45 days

Snapshot C
Volume: vol-333
Age: 90 days
```

But the only existing EBS volume is:

```text
vol-111
```

With:

```text
RETENTION_DAYS=30
```

the Lambda evaluates:

```text
Snapshot A
    |
    +-- Source volume exists
    |
    +-- RETAIN


Snapshot B
    |
    +-- Source volume does not exist
    |
    +-- Older than 30 days
    |
    +-- Eligible for cleanup


Snapshot C
    |
    +-- Source volume does not exist
    |
    +-- Older than 30 days
    |
    +-- Eligible for cleanup
```

If `DRY_RUN=true`, the Lambda only logs the candidates.

If `DRY_RUN=false`, the Lambda attempts to delete them.

---

## Important AWS Considerations

This project is intentionally focused on demonstrating EBS snapshot lifecycle automation.

A production cleanup system should include additional safeguards.

### AMI Dependencies

Some EBS snapshots can be associated with Amazon Machine Images (AMIs).

AWS may prevent deletion of a snapshot that is still required by a registered EBS-backed AMI.

A production implementation should therefore check for AMI dependencies before attempting deletion.

### Snapshot Retention Policies

Not every old snapshot should necessarily be deleted.

Production environments may have different retention requirements:

```text
Development  -> 7 days
Staging      -> 14 days
Production   -> 90 days
```

A more advanced implementation could use snapshot tags to determine the appropriate retention policy.

### AWS Backup and Data Lifecycle Manager

Snapshots may also be managed by services such as:

- AWS Backup
- Amazon Data Lifecycle Manager

A cleanup automation should understand which system owns a snapshot before deleting it.

### Recycle Bin and Snapshot Protection

Production environments may use additional AWS protection mechanisms such as:

- Recycle Bin
- Snapshot locks
- Backup retention policies
- Compliance requirements

These should be considered before enabling automated deletion.

---

## Understanding EBS Snapshot Storage

EBS snapshots are incremental.

The first snapshot captures the required blocks of the volume. Subsequent snapshots store blocks that have changed since previous snapshots.

Because of this, deleting one snapshot does not necessarily free storage equal to the apparent size of that snapshot.

For example:

```text
Snapshot 1
    |
    +-- Blocks A B C D E

Snapshot 2
    |
    +-- Blocks A B C X E

Snapshot 3
    |
    +-- Blocks A B Y X E
```

A block may still be required by another snapshot.

Therefore, the actual storage savings from deleting a snapshot depend on which blocks are no longer referenced by any remaining snapshots.

---

## Why Lambda?

Lambda is suitable for this workload because the cleanup process:

- Runs periodically
- Does not require a continuously running server
- Can interact directly with AWS APIs
- Requires minimal infrastructure management
- Can be triggered automatically
- Produces logs through CloudWatch

This makes it a practical example of serverless infrastructure automation.

---

## Key AWS Concepts Demonstrated

### AWS Lambda

Running cloud automation without managing a dedicated server.

### Boto3

Using the AWS SDK for Python to interact with AWS services programmatically.

### Amazon EBS

Understanding persistent block storage attached to EC2 instances.

### EBS Snapshots

Understanding point-in-time backups of EBS volumes.

### IAM

Using IAM roles and permissions to control what Lambda can do.

### EventBridge

Triggering infrastructure automation on a schedule.

### CloudWatch

Monitoring Lambda execution through logs.

### Cloud Cost Optimization

Identifying unnecessary cloud resources and automating their lifecycle.

---

## Future Improvements

Possible improvements include:

- Tag-based retention policies
- Different retention periods for DEV, STAGING, and PROD
- SNS notifications
- CloudWatch metrics and alarms
- Cost savings estimation
- Snapshot exclusion tags
- AMI dependency checks
- AWS Backup integration
- Multi-region support
- Terraform deployment
- CI/CD deployment pipeline

---

## Key Takeaway

The purpose of this project is not simply to delete old snapshots.

The broader DevOps concept is:

> Automating cloud resource lifecycle management according to defined policies.

Instead of manually checking resources:

```text
Engineer
    |
    v
AWS Console
    |
    v
Find stale snapshots
    |
    v
Delete manually
```

the process becomes:

```text
EventBridge
    |
    v
Lambda
    |
    v
Evaluate snapshots
    |
    v
Apply retention policy
    |
    v
Clean up automatically
    |
    v
CloudWatch
```

This makes the process repeatable, automated, and scalable.

---

## Technologies

```text
Python
AWS Lambda
Boto3
Amazon EC2
Amazon EBS
AWS IAM
Amazon EventBridge
Amazon CloudWatch
```

---

## Disclaimer

This project is intended for learning and portfolio purposes.

Always test cleanup logic in a non-production AWS environment before enabling automatic deletion.
