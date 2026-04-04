# Decision Log

## 1. S3 general purpose buckets should block public write access
- Action ID: 19337c80-843c-40fb-b35c-fd561406009f
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private_manual_preservation
- Summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Existing bucket policy preservation evidence is missing for CloudFront + OAC migration. Missing bucket identifier for access-path validation. Run creation did not require additional risk-only acceptance.

## 2. S3 general purpose buckets should block public access
- Action ID: da0d429e-6f16-461e-be2f-09ea7997e30a
- Tier: manual_guidance/actions
- Outcome: manual_guidance_metadata_only
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private_manual_preservation
- Summary: Family resolver downgraded strategy 's3_migrate_cloudfront_oac_private' to manual S3.2 preservation profile 's3_migrate_cloudfront_oac_private_manual_preservation'. Bucket is still configured for S3 website hosting with a public website-read policy, and BlockPublicPolicy would reject preserving that public statement. Use the website-specific CloudFront cutover path or manual review instead of the generic CloudFront + OAC migration. Run creation did not require additional risk-only acceptance.

## 3. S3 general purpose buckets should block public write access
- Action ID: 0ca962a2-1dee-421e-88fc-e3be9af0b56d
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 4. S3 general purpose buckets should block public read access
- Action ID: 0dc8756d-3d23-4945-a66a-b425bf315fb1
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 5. S3 general purpose buckets should block public write access
- Action ID: 0ff2bc8f-d6f6-483b-adca-30619d4ac208
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 6. S3 general purpose buckets should block public write access
- Action ID: 1dc66e7e-efe9-4fd6-9335-3197211b289f
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 7. S3 general purpose buckets should block public write access
- Action ID: 21c09e7f-7b0c-4be5-9bed-981fa8f01907
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 8. S3 general purpose buckets should block public write access
- Action ID: 2c8ba273-6902-4f19-afeb-9e6d6a523aa1
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 9. S3 general purpose buckets should block public access
- Action ID: 3ae05cd4-4f24-4371-ad5d-63e2ae01d341
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 10. S3 general purpose buckets should block public write access
- Action ID: 3ce30a5c-4f48-44e0-877a-ee3bdc641a27
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 11. S3 general purpose buckets should block public write access
- Action ID: 496f8cc3-f3c0-4587-becf-6ec0d5b68d61
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 12. S3 general purpose buckets should block public write access
- Action ID: 499adc8a-c56c-4782-ad28-127a69cf241e
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 13. S3 general purpose buckets should block public read access
- Action ID: 4c631219-af57-4aad-af2e-a1add122aff2
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 14. S3 general purpose buckets should block public write access
- Action ID: 51f0f65a-8f13-44b1-b889-1243080bd069
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 15. S3 general purpose buckets should block public write access
- Action ID: 5b77d9d9-fa33-4435-b70b-0e8a1cde7682
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 16. S3 general purpose buckets should block public write access
- Action ID: 7f361ff6-fb26-4207-9cf7-92ca0dcb3460
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 17. S3 general purpose buckets should block public access
- Action ID: 8f162041-8712-4a78-a757-a6f8b7a33129
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 18. S3 general purpose buckets should block public write access
- Action ID: 9fa9f7b4-ac06-497e-bf34-ba31b8c98d51
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' because Terraform can merge the current bucket policy at apply time. Runtime capture failed (AccessDenied), so the customer-run Terraform bundle must fetch the live bucket policy. Run creation did not require additional risk-only acceptance.

## 19. S3 general purpose buckets should block public write access
- Action ID: a76d1974-0643-4780-8689-91a23075fb83
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 20. S3 general purpose buckets should block public read access
- Action ID: a781c11d-f7fe-4ff4-a9e1-8ba921068654
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 21. S3 general purpose buckets should block public write access
- Action ID: ad9bdd8f-7b30-4d58-9599-85fa6673edd2
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 22. S3 general purpose buckets should block public read access
- Action ID: d03ad604-a057-4677-8c12-0934a27317ea
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 23. S3 general purpose buckets should block public write access
- Action ID: d3cf0cc7-e545-4151-818c-18f8d806c919
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 24. S3 general purpose buckets should block public write access
- Action ID: dda812ab-15c2-482f-8782-ffef1ab0a60d
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 25. S3 general purpose buckets should block public write access
- Action ID: dedc7b1c-0300-4a28-8806-6735354facba
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 26. S3 general purpose buckets should block public read access
- Action ID: deff1612-54f9-4b10-85ae-afc1e557e571
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 27. S3 general purpose buckets should block public read access
- Action ID: dfdf129a-d3ea-4821-8074-e060d7dd92f6
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 28. S3 general purpose buckets should block public write access
- Action ID: e7f23835-5d6e-410f-8ccd-27a0c268c546
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 29. S3 general purpose buckets should block public write access
- Action ID: ed8274a5-f821-4036-95c7-7079cd6553ec
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 30. S3 general purpose buckets should block public write access
- Action ID: fb27abe2-d234-4627-9ee2-6227b8447efd
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 31. S3 general purpose buckets should block public write access
- Action ID: fddd2631-0898-48d7-8bf8-5e638c4ac493
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 32. S3 general purpose buckets should block public access
- Action ID: abf5eb48-ea9b-48d0-a534-236cf8818bf9
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

## 33. S3 general purpose buckets should block public access
- Action ID: f497bc0c-ddcb-4191-8fa5-c6ed21bbe134
- Tier: executable/actions
- Outcome: executable_bundle_generated
- Strategy/Profile: s3_migrate_cloudfront_oac_private / s3_migrate_cloudfront_oac_private
- Summary: Family resolver kept executable S3.2 profile 's3_migrate_cloudfront_oac_private' for strategy 's3_migrate_cloudfront_oac_private'. Run creation did not require additional risk-only acceptance.

