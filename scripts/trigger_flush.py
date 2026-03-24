import sys
from backend.workers.database import session_scope
from backend.models.aws_account import AwsAccount
import subprocess

def run_recompute():
    with session_scope() as session:
        account = session.query(AwsAccount).filter_by(account_id="696505809372").first()
        if not account:
            print("Account not found")
            sys.exit(1)
        tenant_id = str(account.tenant_id)
        
    print(f"Running recompute for tenant {tenant_id} account 696505809372 region eu-north-1")
    cmd = [
        "PYTHONPATH=.", 
        "./venv/bin/python", 
        "scripts/recompute_account_actions.py",
        "--tenant-id", tenant_id,
        "--account-id", "696505809372",
        "--region", "eu-north-1"
    ]
    subprocess.run(" ".join(cmd), shell=True, env={})
    
if __name__ == "__main__":
    run_recompute()
