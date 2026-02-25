---
Compiled deployment scripts, teardown scripts, and coverage matrix 
for AWS security test environment across two architectures.

RapidClaims Telehealth Evidence Pipeline: 18 resources deployed across Groups A, B, C.
RapidRad Teleradiology Exchange Platform: 18 resources deployed across Groups A, B, C.
All 6 adversarial resources (A1, A2, A3, B1, B2, B3) scripted 
with reset commands.
6 teardown scripts written (3 per architecture).

Changed files:
* docs/prod-readiness/08-deployment-scripts.md
* docs/prod-readiness/08-teardown-scripts.md
* docs/prod-readiness/08-coverage-matrix.md

Source task files compiled:
* 08-task2-deploy-arch1.sh
* 08-task3-deploy-arch2.sh
* 08-task4-reset-arch1.sh
* 08-task5-reset-arch2.sh
* 08-task6-teardown-arch1-groupA.sh
* 08-task6-teardown-arch1-groupB.sh
* 08-task6-teardown-arch1-full.sh
* 08-task7-teardown-arch2-groupA.sh
* 08-task7-teardown-arch2-groupB.sh
* 08-task7-teardown-arch2-full.sh
* 08-task8-coverage-matrix.md

Coverage counts:
* Total controls covered: 26
* Controls with adversarial validation: 10
* Controls with basic coverage only: 16
* Coverage gaps: 16 (S3.1, SecurityHub.1, GuardDuty.1, S3.4, CloudTrail.1, Config.1, SSM.7, EC2.182, EC2.7, S3.9, S3.11, S3.15, RDS.PUBLIC_ACCESS, RDS.ENCRYPTION, EKS.PUBLIC_ENDPOINT, ARC-008)
* PR proof targets PASSING: 0 of 4
* PR proof targets FAILING: 4 (arch1_sg_dependency_a2, arch1_bucket_evidence_b1, arch2_shared_compute_role_a3, arch2_mixed_policy_role_b3)

Remaining risks:
* Coverage gaps remain for 16 controls listed in 08-task8-coverage-matrix.md.
* All 4 PR proof targets have MISSING fields (C1-C4 for A-series; C1-C5 for B-series).
* arch2_root_credentials_state_c cannot be fully scripted with AWS CLI v2 because root-principal state is manual-gate only.
* Reset flow still requires manual steps for root credentials and may require manual RDS instance recreation to restore unencrypted state.
---
