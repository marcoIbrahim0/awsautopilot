from backend.workers.database import session_scope
from backend.models.remediation_run import RemediationRun
from backend.models.action import Action
import json

def check_run_args():
    with session_scope() as session:
        runs = (
            session.query(RemediationRun, Action)
            .join(Action, RemediationRun.action_id == Action.id)
            .filter(RemediationRun.id.in_([
                "8445a29f-a6d6-48cd-ace7-2a2a66cfef3e",
                "faef7581-a19e-4512-80c5-507784279077",
            ]))
            .all()
        )
        for r, a in runs:
            print(f"Run {r.id} for SG {a.resource_id}:")
            if r.artifacts:
                print("Keys:", list(r.artifacts.keys()))
                if "pr_bundle" in r.artifacts:
                    for f in r.artifacts["pr_bundle"].get("files", []):
                        if f["path"].endswith(".tf"):
                            print(f"--- {f['path']} ---")
                            print(f["content"])
            
if __name__ == "__main__":
    check_run_args()
