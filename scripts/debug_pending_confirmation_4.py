import sys
from sqlalchemy import create_engine, text
from backend.config import settings

db_url = settings.DATABASE_URL_SYNC
print(f"Using DB: {db_url}")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("--- Top 10 Stalled Action Group States Globally ---")
    stalled_states_sql = text("""
        SELECT state.latest_run_status_bucket, a.account_id, a.action_type, state.last_attempt_at, state.last_confirmed_at
        FROM action_group_action_state state
        JOIN actions a ON state.action_id = a.id
        WHERE state.latest_run_status_bucket = 'run_successful_pending_confirmation'
        ORDER BY state.last_attempt_at DESC NULLS LAST
        LIMIT 10
    """)
    res = conn.execute(stalled_states_sql)
    for row in res:
        print(row)

    print("\n--- AWS Accounts ---")
    aws_acc_sql = text("""SELECT account_id, tenant_id FROM aws_accounts LIMIT 10""")
    for row in conn.execute(aws_acc_sql):
        print(row)
