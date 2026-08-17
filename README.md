# aws-ebs-snapshot-cleanup

# AWS EBS Snapshot Cleanup with Lambda

An automated, serverless cost-optimization tool built with AWS Lambda and Boto3 to detect and delete orphaned Amazon EBS snapshots based on volume lifecycle and retention age.

---

## Overview

Amazon EBS snapshots provide block-level backups for EC2 volumes. When an EC2 volume is deleted, its historical snapshots remain stored in Amazon S3 indefinitely unless explicitly deleted or managed by lifecycle policies. Over time, these unattached backups accumulate and create unnecessary cloud storage costs.

This project implements an event-driven AWS Lambda function that identifies snapshots whose parent volumes no longer exist, evaluates their age against a user-defined threshold, and removes eligible stale resources safely.

---

## Architecture

```text
                  +-------------------------+
                  |    Amazon EventBridge   |
                  |    (Scheduled Cron)     |
                  +------------+------------+
                               |
                               v
                  +-------------------------+
                  |     AWS Lambda Core     |
                  |   (Python 3.x + Boto3)  |
                  +------------+------------+
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
+-----------------------+             +-----------------------+
|  ec2:DescribeVolumes  |             | ec2:DescribeSnapshots |
+-----------+-----------+             +-----------+-----------+
            |                                     |
            +------------------+------------------+
                               |
                               v
                  +-------------------------+
                  | Evaluate Orphan Status  |
                  |    & Retention Period   |
                  +------------+------------+
                               |
              +----------------+----------------+
              | (DRY_RUN=false)|                | (Log only)
              v                v                v
      +---------------+  +-----------+  +---------------+
      | DeleteSnapshot|  |  CloudWatch |  | Retain Snapshot|
      |   (AWS EC2)   |  | Logs/Audit|  |  (No action)  |
      +---------------+  +-----------+  +---------------+
