import boto3
from backend.workers.services.inventory_reconcile import _collect_ec2_security_groups

def test_deleted_sg():
    class SessionMock:
        def client(self, service_name, region_name):
            return boto3.client(service_name, region_name=region_name)

    print("Calling _collect_ec2_security_groups for missing SG...")
    snapshots = _collect_ec2_security_groups(
        session_boto=SessionMock(),
        region="eu-north-1",
        resource_ids=["sg-06f6252fa8a95b61d"],
        max_resources=10
    )
    
    for snap in snapshots:
        print(f"Snapshot resource_id={snap.resource_id}")
        for eval in snap.evaluations:
            print(f"  Eval control={eval.control_id} status={eval.status} reason={eval.status_reason}")

if __name__ == "__main__":
    test_deleted_sg()
