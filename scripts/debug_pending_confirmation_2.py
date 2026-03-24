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
engine = create_engine(db_url)

with engine.connect() as conn:
    print("--- Top 5 Recent Action Group Action States for Account 696505809372 ---")
    stalled_states_sql = text("""
        SELECT state.latest_run_status_bucket, a.action_type, state.last_attempt_at, state.last_confirmed_at
        FROM action_group_action_state state
        JOIN actions a ON state.action_id = a.id
        WHERE a.account_id = '696505809372'
        ORDER BY state.last_attempt_at DESC NULLS LAST
        LIMIT 5
    """)
    res = conn.execute(stalled_states_sql)
    for row in res:
        print(row)
