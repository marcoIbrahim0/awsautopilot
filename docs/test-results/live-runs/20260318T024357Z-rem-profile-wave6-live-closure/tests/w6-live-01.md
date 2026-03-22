# Test 01 - EC2.53 grouped executable live rerun

- Wave: `Wave 6`
- Date (UTC): `2026-03-18T02:57:25Z`
- Tester: `Codex`
- Backend URL during execution: `http://127.0.0.1:18020`
- Branch tested: `master`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Disposable runtime bootstrapped under [`../evidence/runtime/runtime-bootstrap.json`](../evidence/runtime/runtime-bootstrap.json).
- Action group `f29f469e-710a-4f4a-8db1-c4a3ae21705a` existed for `EC2.53`.
- Executable candidate action: `d740b079-2fe0-40ec-baa0-efe3e0e01a2b` on `sg-06f6252fa8a95b61d`.
- Manual candidate action: `0d5b9a29-bd79-4454-a9c4-c0a5c62479e0` on `sg-0ef32ca8805a55a8b`.
- Pre-apply AWS state for both retained fixture security groups exposed public `22/3389`; see [`../evidence/aws/w6-live-01-ec253-pre-security-groups.json`](../evidence/aws/w6-live-01-ec253-pre-security-groups.json).

## Steps Executed

1. Reviewed the grouped EC2.53 action group detail and both standalone previews.
2. Generated the supported customer-run grouped bundle and inspected the extracted layout plus contract metadata.
3. Ran `AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh` from the grouped bundle root.
4. Verified the post-apply AWS state for both security groups.
5. Ran `terraform destroy -auto-approve` inside the executable action folder.
6. Verified the post-rollback AWS state and confirmed the executable fixture security group no longer had any ingress rules.
7. Restored the executable fixture security group manually to the captured pre-apply public `22/3389` state and verified final cleanup.

## Key Evidence

- Standalone executable preview: [`../evidence/api/w6-live-01-ec253-exec-preview.json`](../evidence/api/w6-live-01-ec253-exec-preview.json)
- Standalone manual preview: [`../evidence/api/w6-live-02-ec253-manual-preview.json`](../evidence/api/w6-live-02-ec253-manual-preview.json)
- Group bundle contract check: [`../evidence/api/w6-live-01-ec253-bundle-contract-check.json`](../evidence/api/w6-live-01-ec253-bundle-contract-check.json)
- Group bundle tree: [`../evidence/bundles/w6-live-01-ec253-group-tree.txt`](../evidence/bundles/w6-live-01-ec253-group-tree.txt)
- Group runs after apply: [`../evidence/api/w6-live-01-ec253-group-runs-after-apply.json`](../evidence/api/w6-live-01-ec253-group-runs-after-apply.json)
- Grouped apply log: [`../evidence/bundles/w6-live-01-ec253-run_all-apply.log`](../evidence/bundles/w6-live-01-ec253-run_all-apply.log)
- Terraform destroy log: [`../evidence/bundles/w6-live-01-ec253-terraform-destroy.log`](../evidence/bundles/w6-live-01-ec253-terraform-destroy.log)
- Generated rollback guidance and Terraform source:
  - [`../evidence/bundles/w6-live-01-ec253-group/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-d740b079/README.txt`](../evidence/bundles/w6-live-01-ec253-group/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-d740b079/README.txt)
  - [`../evidence/bundles/w6-live-01-ec253-group/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-d740b079/sg_restrict_public_ports.tf`](../evidence/bundles/w6-live-01-ec253-group/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-d740b079/sg_restrict_public_ports.tf)
- AWS state snapshots:
  - pre-apply: [`../evidence/aws/w6-live-01-ec253-pre-security-groups.json`](../evidence/aws/w6-live-01-ec253-pre-security-groups.json)
  - post-apply: [`../evidence/aws/w6-live-01-ec253-post-apply-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-apply-security-groups.json)
  - post-rollback: [`../evidence/aws/w6-live-01-ec253-post-rollback-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-rollback-security-groups.json)
  - post-manual-restore: [`../evidence/aws/w6-live-01-ec253-post-manual-restore-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-manual-restore-security-groups.json)
- Manual cleanup proof: [`../evidence/aws/w6-live-01-ec253-manual-restore.log`](../evidence/aws/w6-live-01-ec253-manual-restore.log)
- Cleanup summary: [`../notes/aws-cleanup-summary.md`](../notes/aws-cleanup-summary.md)

## Assertions

- The supported grouped customer-run bundle now preserves the executable EC2.53 branch:
  - bundle contract reported `runnable_action_count = 1`
  - the extracted bundle contained both one executable action folder and one manual-guidance action folder
- The grouped executable apply path is truthful:
  - `run_all.sh` completed successfully
  - the grouped run reached `finished`
  - `sg-06f6252fa8a95b61d` replaced public `22/3389` with restricted `10.0.0.0/8` rules
  - `sg-0ef32ca8805a55a8b` stayed unchanged and public
- The generated rollback path is not exact:
  - `terraform destroy` removed the managed restricted rules
  - the original public `22/3389` rules were not recreated
  - `sg-06f6252fa8a95b61d` was left with no ingress rules after destroy
- Manual cleanup restored the retained fixture to its pre-apply state by re-authorizing the original public `22/3389` rules with the captured descriptions.

## Result

- Status: `FAIL`
- Severity: `HIGH`
- Tracker mapping: `W6-LIVE-01`

## Notes

- This rerun closes the March 16 grouped-tier defect: the supported bundle is executable again and the AWS apply path is proven.
- The remaining blocker is rollback exactness, not executable selection.
- The authoritative outcome for apply/destroy is the bundle log plus the AWS state snapshots. The helper exit-code text files were normalized after local zsh wrapper issues that occurred after the underlying commands had already completed.
