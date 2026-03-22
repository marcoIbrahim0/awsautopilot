# Test 01 - EC2.53 grouped executable live rerun

- Wave: `Wave 6`
- Date (UTC): `2026-03-18T03:23:59Z`
- Tester: `Codex`
- Backend URL during execution: `http://127.0.0.1:18022`
- Branch tested: `master`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- AWS Account: `696505809372`
- Region(s): `eu-north-1`

## Preconditions

- Disposable runtime bootstrapped under [`../evidence/runtime/runtime-bootstrap.json`](../evidence/runtime/runtime-bootstrap.json).
- Action group `848668f2-5f24-4637-aeaa-6b7e5f9a0271` existed for `EC2.53`.
- Executable candidate action: `ad9328e1-faf2-4fd4-9885-c7f8c50c7d14` on `sg-06f6252fa8a95b61d`.
- Manual candidate action: `2a1c9d2f-b05d-48b3-bcec-d7645c5fd017` on `sg-0ef32ca8805a55a8b`.
- Pre-apply AWS state for both retained fixture security groups exposed public `22/3389`; see [`../evidence/aws/w6-live-01-ec253-pre-security-groups-patched.json`](../evidence/aws/w6-live-01-ec253-pre-security-groups-patched.json).

## Steps Executed

1. Patched the generated EC2.53 bundle helpers so `sg_capture_state.py` fetches SG rules by `group-id`, filters `IsEgress` client-side, preserves ingress-rule descriptions, and updates rollback guidance to the real bundle-local capture/restore flow.
2. Re-ran focused generator/worker regression coverage and regenerated a fresh grouped bundle for the same EC2.53 action group.
3. Verified the regenerated bundle contract: one executable `close_and_revoke` action, one manual `ssm_only` action, and a non-null bundle-local rollback command for the executable branch.
4. Captured live pre-state with `SECURITY_GROUP_ID=sg-06f6252fa8a95b61d REGION=eu-north-1 python3 scripts/sg_capture_state.py` and saved the exact rollback snapshot.
5. Ran `AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh` from the grouped bundle root.
6. Verified the post-apply AWS state:
   - `sg-06f6252fa8a95b61d` removed public `22/3389` and added restricted `10.0.0.0/8`
   - `sg-0ef32ca8805a55a8b` stayed unchanged and public
   - the group run reached `finished`
7. Ran `terraform destroy -auto-approve` inside the executable action folder, then ran `python3 rollback/sg_restore.py`.
8. Verified the executable fixture security group returned to exact pre-apply ingress, including the original rule descriptions, and confirmed the manual fixture security group still matched baseline.
9. Deleted temporary SaaS-account queues and stopped the disposable local API, worker, and Postgres runtime.

## Key Evidence

- Bundle contract check: [`../evidence/api/w6-live-01-ec253-bundle-contract-check.json`](../evidence/api/w6-live-01-ec253-bundle-contract-check.json)
- Group bundle tree: [`../evidence/bundles/w6-live-01-ec253-group-patched-tree.txt`](../evidence/bundles/w6-live-01-ec253-group-patched-tree.txt)
- Generated helper and rollback guidance:
  - [`../evidence/bundles/w6-live-01-ec253-group-patched/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-ad9328e1/scripts/sg_capture_state.py`](../evidence/bundles/w6-live-01-ec253-group-patched/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-ad9328e1/scripts/sg_capture_state.py)
  - [`../evidence/bundles/w6-live-01-ec253-group-patched/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-ad9328e1/rollback/sg_restore.py`](../evidence/bundles/w6-live-01-ec253-group-patched/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-ad9328e1/rollback/sg_restore.py)
  - [`../evidence/bundles/w6-live-01-ec253-group-patched/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-ad9328e1/README.txt`](../evidence/bundles/w6-live-01-ec253-group-patched/executable/actions/02-arn-aws-ec2-eu-north-1-696505809372-security-gro-ad9328e1/README.txt)
- Pre-apply exact-state capture:
  - [`../evidence/aws/w6-live-01-ec253-pre-capture-output.txt`](../evidence/aws/w6-live-01-ec253-pre-capture-output.txt)
  - [`../evidence/aws/w6-live-01-ec253-pre-capture-snapshot.json`](../evidence/aws/w6-live-01-ec253-pre-capture-snapshot.json)
- Grouped apply log and status:
  - [`../evidence/bundles/w6-live-01-ec253-group-patched-run_all-apply.log`](../evidence/bundles/w6-live-01-ec253-group-patched-run_all-apply.log)
  - [`../evidence/api/w6-live-01-ec253-group-runs-post-apply-patched.json`](../evidence/api/w6-live-01-ec253-group-runs-post-apply-patched.json)
- AWS state comparisons:
  - post-apply: [`../evidence/aws/w6-live-01-ec253-post-apply-compare.json`](../evidence/aws/w6-live-01-ec253-post-apply-compare.json)
  - post-rollback: [`../evidence/aws/w6-live-01-ec253-post-rollback-compare.json`](../evidence/aws/w6-live-01-ec253-post-rollback-compare.json)
- Rollback execution:
  - [`../evidence/bundles/w6-live-01-ec253-group-patched-terraform-destroy.log`](../evidence/bundles/w6-live-01-ec253-group-patched-terraform-destroy.log)
  - [`../evidence/bundles/w6-live-01-ec253-group-patched-sg-restore.log`](../evidence/bundles/w6-live-01-ec253-group-patched-sg-restore.log)
- Cleanup summary: [`../notes/aws-cleanup-summary.md`](../notes/aws-cleanup-summary.md)

## Assertions

- The supported grouped customer-run bundle preserves the executable EC2.53 branch truthfully:
  - `runnable_action_count = 1`
  - the executable action remained `close_and_revoke` with `support_tier = deterministic_bundle`
  - the manual action remained `ssm_only` with `support_tier = manual_guidance_only`
- The bundle-local rollback contract is now truthful:
  - pre-apply capture succeeded before AWS mutation
  - the captured snapshot preserved the original public `22/3389` CIDRs and descriptions
  - the executable bundle shipped a bundle-local restore command at `rollback/sg_restore.py`
- The grouped executable apply path is truthful:
  - `run_all.sh` completed successfully
  - the group run reached `finished`
  - `sg-06f6252fa8a95b61d` replaced public `22/3389` with restricted `10.0.0.0/8`
  - `sg-0ef32ca8805a55a8b` stayed unchanged and public
- The grouped rollback path is now exact:
  - `terraform destroy` removed the managed restricted rules
  - `python3 rollback/sg_restore.py` restored the original public `22/3389` rules
  - the executable security group matched the pre-apply baseline exactly, including rule descriptions
  - the manual security group also matched the pre-apply baseline exactly

## Result

- Status: `PASS`
- Severity: `NONE`
- Tracker mapping: `W6-LIVE-01`

## Notes

- This rerun closes the March 18 rollback defect for `EC2.53` on current `master`.
- The root cause was bundle-local rollback asymmetry in the `close_and_revoke` Terraform path, not resolver selection or grouped-tier preservation.
