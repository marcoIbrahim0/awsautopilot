from backend.workers.database import session_scope
from backend.models.remediation_run import RemediationRun

def check_runs():
    with session_scope() as session:
        runs = session.query(RemediationRun).filter_by(account_id="696505809372").all()
        for r in runs:
            # We are interested in run_successful_pending_confirmation
            print(f"Run {r.id}: {r.status} (action {r.action_id})")

if __name__ == "__main__":
    check_runs()
