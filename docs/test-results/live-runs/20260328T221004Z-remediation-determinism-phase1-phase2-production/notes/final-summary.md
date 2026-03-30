# Final Summary

This retained run executed the Phase 2 production-only handoff on `master` and proved the live AWS-side correctness of `WI-2` `ssm_only`, `WI-8` `bastion_sg_reference`, and one grouped mixed-tier Phase 2 S3.11 run. The gate still ends `BLOCKED` because `WI-1` additive merge could not be proven truthfully on production, and the broader production-ready decision remains `NO-GO` because `WI-12` plus the post-apply lag bug remain open retained blockers.

## WI Table

| WI | Scope | Status | Retained outcome |
| --- | --- | --- | --- |
| WI-1 | S3.11 additive lifecycle merge | BLOCKED | Seeded bucket `phase2-wi1-lifecycle-696505809372-20260328224331` had a real renderable lifecycle config, but production never surfaced a truthful action for that bucket after ingest plus scoped recompute. |
| WI-2 | EC2.53 `ssm_only` | PASS | Action `58a22607-666e-4016-8fe3-4ce62a235a6e` generated a deterministic bundle, Terraform validated and applied, AWS removed public `22/3389` without adding replacement ingress, and rollback restored the original public rules. |
| WI-8 | EC2.53 `bastion_sg_reference` | PASS | Action `dfa0a526-87b8-4670-92d7-401a611f58f5` resolved `approved_bastion_security_group_ids=["sg-085d69a76707542b2"]`, Terraform validated and applied, AWS replaced public `22/3389` with SG-source rules from the approved bastion SG, and rollback restored the original public rules. |
| WI-7 | S3 family `resource_id` fallback | WAIVED / DEFERRED | Retained prior authoritative March 28 production-path investigation; not a required pass item for this run. |
| WI-12 | Config.1 auto scope | BLOCKED | Still no truthful production candidate. |
| WI-13 | S3.2 OAC zero-policy | PASS | Already proven live in the earlier March 28 Phase 1 candidate rerun. |
| WI-14 | S3.5 empty-policy | PASS | Already proven live in the earlier March 28 Phase 1 candidate rerun. |

## Key Production Facts

- Gate 2A reran unchanged and passed across all eight focused local Phase 2 commands.
- Production auth, `/health`, `/ready`, tenant/account resolution, and action discovery all worked on the real production surface.
- The tenant remediation settings path for `WI-8` is proven live:
  - initial settings had no approved bastion SG IDs
  - a real canary bastion SG was created and patched into `/api/users/me/remediation-settings`
  - the `WI-8` preview and run resolution reflected that approved bastion SG ID
  - the settings were restored after the proof completed
- The grouped Phase 2 proof is retained:
  - action group `9a904e6a-3ab8-4eca-be92-b727b0aacf67`
  - group run `cfe0eaa2-0be2-4ff9-a907-2f56aaf336b0`
  - remediation run `864fe109-17e9-4e3b-b752-5bc31de86957`
  - `run_all.sh` executed the two executable S3.11 members and finalized through the callback contract with five `manual_guidance_only` siblings

## Retained Risks / Blockers

- `WI-1` is still blocked on truthful candidate materialization. The live dataset exposed deterministic S3.11 candidates only for buckets with no lifecycle config, and the seeded additive-merge bucket never surfaced as a production action.
- Post-apply production lag reproduced again:
  - `WI-2` action stayed `open` after completed ingest despite AWS already being remediated
  - `WI-8` action still stayed `open` after later scoped recompute despite AWS already being remediated
  - the grouped executable S3.11 actions also stayed `open` after scoped recompute despite AWS already being remediated
- Because `WI-12` is still unproven and the lag bug remains open, the overall Phase 1 + Phase 2 production-ready decision is still `NO-GO`.
