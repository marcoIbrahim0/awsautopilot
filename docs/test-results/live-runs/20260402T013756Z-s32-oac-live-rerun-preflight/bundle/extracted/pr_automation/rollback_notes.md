# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## S3 general purpose buckets should block public write access
- Action ID: `19337c80-843c-40fb-b35c-fd561406009f`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket 696505809372|eu-north-1|AWS::::Account:696505809372|S3.2`

## S3 general purpose buckets should block public write access
- Action ID: `0ca962a2-1dee-421e-88fc-e3be9af0b56d`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r222018|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372-r222018`

## S3 general purpose buckets should block public read access
- Action ID: `0dc8756d-3d23-4945-a66a-b425bf315fb1`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r222018-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372-r222018-access-logs`

## S3 general purpose buckets should block public write access
- Action ID: `0ff2bc8f-d6f6-483b-adca-30619d4ac208`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372`

## S3 general purpose buckets should block public write access
- Action ID: `1dc66e7e-efe9-4fd6-9335-3197211b289f`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-dev-serverless-src-696505809372-eu-north-1|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-dev-serverless-src-696505809372-eu-north-1`

## S3 general purpose buckets should block public write access
- Action ID: `21c09e7f-7b0c-4be5-9bed-981fa8f01907`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi7-seed-696505809372-20260328205857-access-logs`

## S3 general purpose buckets should block public write access
- Action ID: `2c8ba273-6902-4f19-afeb-9e6d6a523aa1`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket ocypheris-live-ct-20260328t181200z-eu-north-1-access-logs`

## S3 general purpose buckets should block public access
- Action ID: `3ae05cd4-4f24-4371-ad5d-63e2ae01d341`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi7-seed-696505809372-20260328205857|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi7-seed-696505809372-20260328205857`

## S3 general purpose buckets should block public write access
- Action ID: `3ce30a5c-4f48-44e0-877a-ee3bdc641a27`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::wi1-noncurrent-lifecycle-696505809372-2026033000365-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket wi1-noncurrent-lifecycle-696505809372-2026033000365-access-logs`

## S3 general purpose buckets should block public write access
- Action ID: `496f8cc3-f3c0-4587-becf-6ec0d5b68d61`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r94854|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372-r94854`

## S3 general purpose buckets should block public write access
- Action ID: `499adc8a-c56c-4782-ad28-127a69cf241e`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket phase2-wi1-lifecycle-696505809372-20260329004157-access-logs`

## S3 general purpose buckets should block public read access
- Action ID: `4c631219-af57-4aad-af2e-a1add122aff2`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372-r221001-access-logs`

## S3 general purpose buckets should block public write access
- Action ID: `51f0f65a-8f13-44b1-b889-1243080bd069`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi5-site-696505809372-20260328t164043z`

## S3 general purpose buckets should block public write access
- Action ID: `5b77d9d9-fa33-4435-b70b-0e8a1cde7682`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-dev-serverless-src-696505809372-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-dev-serverless-src-696505809372-access-logs`

## S3 general purpose buckets should block public write access
- Action ID: `7f361ff6-fb26-4207-9cf7-92ca0dcb3460`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-website-a1-696505809372-eu-north-1-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket arch1-bucket-website-a1-696505809372-eu-north-1-access-logs`

## S3 general purpose buckets should block public access
- Action ID: `8f162041-8712-4a78-a757-a6f8b7a33129`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket phase2-wi1-lifecycle-696505809372-20260328224331`

## S3 general purpose buckets should block public write access
- Action ID: `9fa9f7b4-ac06-497e-bf34-ba31b8c98d51`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r221001|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372-r221001`

## S3 general purpose buckets should block public write access
- Action ID: `a76d1974-0643-4780-8689-91a23075fb83`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi5-site-696505809372-20260328t164043z-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi5-site-696505809372-20260328t164043z-access-logs`

## S3 general purpose buckets should block public read access
- Action ID: `a781c11d-f7fe-4ff4-a9e1-8ba921068654`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260328224331-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket phase2-wi1-lifecycle-696505809372-20260328224331-access-logs`

## S3 general purpose buckets should block public write access
- Action ID: `ad9bdd8f-7b30-4d58-9599-85fa6673edd2`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi13-14-nopolicy-696505809372-20260328201935-access-logs`

## S3 general purpose buckets should block public read access
- Action ID: `d03ad604-a057-4677-8c12-0934a27317ea`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::ocypheris-live-ct-20260328t181200z-eu-north-1|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket ocypheris-live-ct-20260328t181200z-eu-north-1`

## S3 general purpose buckets should block public write access
- Action ID: `d3cf0cc7-e545-4151-818c-18f8d806c919`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::sa-wi13-14-nopolicy-696505809372-20260328201935|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket sa-wi13-14-nopolicy-696505809372-20260328201935`

## S3 general purpose buckets should block public write access
- Action ID: `da0d429e-6f16-461e-be2f-09ea7997e30a`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-website-a1-696505809372-eu-north-1|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket arch1-bucket-website-a1-696505809372-eu-north-1`

## S3 general purpose buckets should block public write access
- Action ID: `dda812ab-15c2-482f-8782-ffef1ab0a60d`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-s9fix1|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372-s9fix1`

## S3 general purpose buckets should block public write access
- Action ID: `dedc7b1c-0300-4a28-8806-6735354facba`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::wi1-noncurrent-lifecycle-696505809372-20260330003655|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket wi1-noncurrent-lifecycle-696505809372-20260330003655`

## S3 general purpose buckets should block public read access
- Action ID: `deff1612-54f9-4b10-85ae-afc1e557e571`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-access-logs-696505809372-r94854-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-access-logs-696505809372-r94854-access-logs`

## S3 general purpose buckets should block public read access
- Action ID: `dfdf129a-d3ea-4821-8074-e060d7dd92f6`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329004157|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket phase2-wi1-lifecycle-696505809372-20260329004157`

## S3 general purpose buckets should block public write access
- Action ID: `e7f23835-5d6e-410f-8ccd-27a0c268c546`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329002042-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket phase2-wi1-lifecycle-696505809372-20260329002042-access-logs`

## S3 general purpose buckets should block public write access
- Action ID: `ed8274a5-f821-4036-95c7-7079cd6553ec`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-evidence-b1-696505809372-eu-north-1-access-logs|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket arch1-bucket-evidence-b1-696505809372-eu-north-1-access-logs`

## S3 general purpose buckets should block public write access
- Action ID: `fb27abe2-d234-4627-9ee2-6227b8447efd`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::phase2-wi1-lifecycle-696505809372-20260329002042|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket phase2-wi1-lifecycle-696505809372-20260329002042`

## S3 general purpose buckets should block public write access
- Action ID: `fddd2631-0898-48d7-8bf8-5e638c4ac493`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::arch1-bucket-evidence-b1-696505809372-eu-north-1|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket arch1-bucket-evidence-b1-696505809372-eu-north-1`

## S3 general purpose buckets should block public access
- Action ID: `abf5eb48-ea9b-48d0-a534-236cf8818bf9`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s311-review-696505809372`

## S3 general purpose buckets should block public access
- Action ID: `f497bc0c-ddcb-4191-8fa5-c6ed21bbe134`
- Control ID: `S3.2`
- Target: `696505809372|eu-north-1|arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372|S3.2`
- Rollback command: `aws s3api delete-public-access-block --bucket security-autopilot-w6-envready-s315-exec-696505809372`
