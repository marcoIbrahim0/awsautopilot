from backend.workers.database import session_scope
from backend.models.action import Action
from backend.models.remediation_run import RemediationRun

def find_open_actions():
    with session_scope() as session:
        actions = (
            session.query(Action)
            .filter(Action.account_id == "696505809372")
            .filter(Action.control_id == "EC2.53")
            .filter(Action.status == "open")
            .all()
        )
        for action in actions:
            print(f"Action {action.id} | Control {action.control_id} | Resource {action.resource_id} | Region {action.region}")

            runs = session.query(RemediationRun).filter(RemediationRun.action_id == action.id).all()
            if runs:
                latest = max(runs, key=lambda r: r.created_at)
                print(f"  -> Latest run: {latest.id} status={latest.status.value}")
            else:
                print(f"  -> No runs")

if __name__ == "__main__":
    find_open_actions()
