import sys
import uuid
from backend.workers.database import session_scope
from backend.models.aws_account import AwsAccount
from backend.workers.jobs.reconcile_inventory_shard import execute_reconcile_inventory_shard_job

def run_reconcile():
    with session_scope() as session:
        account = session.query(AwsAccount).filter_by(account_id="696505809372").first()
        if not account:
            print("Account not found")
            sys.exit(1)
        tenant_id = str(account.tenant_id)

    print(f"Running targeted inventory reconcile for EC2 SGs in tenant {tenant_id}")
    
    # We will enqueue a targeted sync job and process it locally (or just call the function directly)
    # The worker function `execute_reconcile_inventory_shard_job` takes a message dict
    job_payload = {
        "tenant_id": tenant_id,
        "account_id": "696505809372",
        "region": "eu-north-1",
        "service": "ec2",
        "sweep_mode": "targeted",
        "resource_ids": [
            "sg-06f6252fa8a95b61d",
            "sg-0e6e7d6eb96ff8e4a",
            "sg-09bbcfaf0cc221291",
            "sg-0ad32bf6bc05f6252"
        ],
        "run_shard_id": str(uuid.uuid4())
    }
    
    # Because it uses assume_role and my local has STS issues, I will push it to the queue instead, or just let local run it?
    # Wait, pushing to SQS means the production worker picks it up! That's much better.
    import boto3
    from backend.workers.config import settings
    sqs = boto3.client("sqs", region_name="eu-north-1") # or whatever region the queue is in.
    queue_url = settings.SQS_INGEST_QUEUE_URL
    print(f"Pushing to {queue_url}")
    import json
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "job_type": "reconcile_inventory_shard",
            **job_payload
        })
    )
    print("Enqueued successfully!")

if __name__ == "__main__":
    run_reconcile()
