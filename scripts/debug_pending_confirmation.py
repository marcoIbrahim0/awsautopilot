import sys
import os

def load_ops_env():
    with open("config/.env.ops", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip('"\'')
                    os.environ[k] = v

load_ops_env()

from sqlalchemy import create_engine, text
from backend.config import settings

db_url = settings.DATABASE_URL_SYNC
if not db_url:
    print("No DB URL")
    sys.exit(1)

engine = create_engine(db_url)

with engine.connect() as conn:
    print("--- Stalled Action Group States ---")
    stalled_states_sql = text("""
        SELECT state.action_id, state.latest_run_id, 
               state.latest_run_status_bucket, state.last_attempt_at, state.last_confirmed_at,
               a.action_type, f.id as finding_id, f.status, f.canonical_control_id, f.resource_key,
               f.shadow_status_normalized, f.shadow_last_observed_event_time
        FROM action_group_action_state state
        JOIN actions a ON state.action_id = a.id
        LEFT JOIN action_findings af ON a.id = af.action_id
        LEFT JOIN findings f ON af.finding_id = f.id
        WHERE a.account_id = '696505809372'
          AND state.latest_run_status_bucket = 'run_successful_pending_confirmation'
        ORDER BY state.last_attempt_at DESC
        LIMIT 10
    """)
    res = conn.execute(stalled_states_sql)
    for row in res:
        print(row)

    print("\n--- Recent Remediation Runs for this Account ---")
    runs_sql = text("""
        SELECT r.id, r.mode, r.status, r.created_at, r.completed_at
        FROM remediation_runs r
        JOIN actions a ON r.action_id = a.id
        WHERE a.account_id = '696505809372'
        ORDER BY r.created_at DESC
        LIMIT 5
    """)
    runs_res = conn.execute(runs_sql)
    for row in runs_res:
        print(row)
