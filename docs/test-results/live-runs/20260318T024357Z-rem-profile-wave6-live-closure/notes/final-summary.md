# Remediation-profile Wave 6 EC2.53 focused live rerun summary

- Wave: `Wave 6 focused EC2.53 rerun`
- Date (UTC): `2026-03-18T02:57:25Z`
- Environment used: `local master against an isolated runtime on 127.0.0.1:18020`
- Branch tested: `master`
- Exact HEAD tested: `e9a362b3f543154838a72665dcd2866919b5089b`
- AWS accounts and regions:
  - SaaS queue/runtime account `029037611564` in `eu-north-1`
  - isolated AWS test account `696505809372` in `eu-north-1`
- Supported execution model exercised: `customer-run PR bundles only`
- Action group: `f29f469e-710a-4f4a-8db1-c4a3ae21705a`
- Remediation run: `21f55c01-de18-4ef5-bc75-29fc6be3ee48`
- Group run: `fa386bc6-6fb4-48ed-a806-13eefcc2b040`

## Outcome

| Check | Result | Evidence |
|---|---|---|
| Grouped executable contract | `PASS` | [`../evidence/api/w6-live-01-ec253-bundle-contract-check.json`](../evidence/api/w6-live-01-ec253-bundle-contract-check.json) |
| Grouped executable apply | `PASS` | [`../evidence/bundles/w6-live-01-ec253-run_all-apply.log`](../evidence/bundles/w6-live-01-ec253-run_all-apply.log), [`../evidence/aws/w6-live-01-ec253-post-apply-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-apply-security-groups.json) |
| Grouped run terminal reporting | `PASS` | [`../evidence/api/w6-live-01-ec253-group-runs-after-apply.json`](../evidence/api/w6-live-01-ec253-group-runs-after-apply.json) |
| Manual/downgrade branch truthfulness | `PASS` | [`../evidence/api/w6-live-02-ec253-manual-preview.json`](../evidence/api/w6-live-02-ec253-manual-preview.json), [`../evidence/bundles/w6-live-01-ec253-group-tree.txt`](../evidence/bundles/w6-live-01-ec253-group-tree.txt) |
| Automatic rollback exactness | `FAIL` | [`../evidence/bundles/w6-live-01-ec253-terraform-destroy.log`](../evidence/bundles/w6-live-01-ec253-terraform-destroy.log), [`../evidence/aws/w6-live-01-ec253-post-rollback-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-rollback-security-groups.json) |
| Final environment restoration | `PASS_WITH_MANUAL_CLEANUP` | [`../evidence/aws/w6-live-01-ec253-manual-restore.log`](../evidence/aws/w6-live-01-ec253-manual-restore.log), [`./aws-cleanup-summary.md`](./aws-cleanup-summary.md) |

## Highest-Severity Finding

| Test / Family | Severity | Issue | Evidence |
|---|---|---|---|
| `W6-LIVE-01` / `EC2.53` | `HIGH` | The March 16 grouped-tier fix is effective and the supported customer-run bundle now applies truthfully, but the generated rollback path is not exact: `terraform destroy` removes the restricted rules and leaves the executable fixture security group without any ingress instead of restoring the original public `22/3389` rules. Manual AWS CLI cleanup was required to return the fixture to pre-state. | [`../tests/w6-live-01.md`](../tests/w6-live-01.md), [`../evidence/aws/w6-live-01-ec253-post-rollback-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-rollback-security-groups.json), [`../evidence/aws/w6-live-01-ec253-post-manual-restore-security-groups.json`](../evidence/aws/w6-live-01-ec253-post-manual-restore-security-groups.json) |

## Key Takeaways

- The supported grouped customer-run execution model is now truthful for the executable EC2.53 branch on current `master`.
- The executable fixture security group moved from public `22/3389` ingress to restricted `10.0.0.0/8` ingress exactly as intended during apply.
- The grouped run reporting callback completed successfully and persisted a `finished` state for the group run.
- The remaining defect is rollback symmetry inside the generated bundle. The artifact's Terraform and `README` only support revoking/re-authorizing ingress operationally; they do not encode exact pre-state restoration.

## Recommended Gate Decision

- Recommended gate decision: `W6-LIVE-01 = FAIL`
- Rationale:
  - executable grouped apply proof is now present
  - manual/downgrade proof remains present
  - exact rollback still requires manual intervention, so the family cannot yet be claimed as fully live-proofed

## Related Notes

- Detailed test note: [`../tests/w6-live-01.md`](../tests/w6-live-01.md)
- Cleanup note: [`./aws-cleanup-summary.md`](./aws-cleanup-summary.md)
