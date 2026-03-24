import sys
from sqlalchemy import create_engine, text
from backend.config import settings

db_url = settings.DATABASE_URL_SYNC
engine = create_engine(db_url)

with engine.connect() as conn:
    print("--- Findings for Stalled Actions ---")
    findings_sql = text("""
        SELECT a.id as action_id, a.action_type, f.id as finding_id, f.status, 
               f.shadow_status_normalized, f.shadow_last_observed_event_time, 
               f.last_observed_at, f.canonical_control_id, f.resource_key, f.source
        FROM action_group_action_state state
        JOIN actions a ON state.action_id = a.id
        JOIN action_findings af ON a.id = af.action_id
        JOIN findings f ON af.finding_id = f.id
        WHERE state.latest_run_status_bucket = 'run_successful_pending_confirmation'
          AND a.account_id = '696505809372'
    """)
    res = conn.execute(findings_sql)
    for row in res:
        print(row)
        
    print("\n--- Recent Reconcile Shard Runs for EC2 ---")
    shard_sql = text("""
        SELECT id, tenant_id, service, status, created_at, finished_at, error_message
        FROM tenant_reconcile_run_shards
        WHERE service = 'ec2' 
        ORDER BY created_at DESC
        LIMIT 5
    """)
    for row in conn.execute(shard_sql):
        print(row)
