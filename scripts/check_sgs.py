import boto3

def check_sgs():
    print("Using local AWS credentials to check SGs...")
    ec2 = boto3.client("ec2", region_name="eu-north-1")
    try:
        res = ec2.describe_security_groups(GroupIds=["sg-0ef32ca8805a55a8b", "sg-06f6252fa8a95b61d"])
        for sg in res.get("SecurityGroups", []):
            print(f"\nSG ID: {sg['GroupId']}, Name: {sg.get('GroupName')}")
            print(f"  Ingress Rules: {sg.get('IpPermissions')}")
    except Exception as e:
        print(f"Error describing SGs: {e}")

if __name__ == "__main__":
    check_sgs()
