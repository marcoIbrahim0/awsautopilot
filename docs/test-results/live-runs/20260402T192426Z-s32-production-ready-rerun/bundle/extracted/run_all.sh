#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI5N2ZkMWU3Ni0wZmVlLTRhOTgtOTNjNi1mNWI2YzAyOGU5ZDIiLCJncm91cF9pZCI6IjkyMDBiNmQ1LWIyMDktNDQzZi05ZDc4LTI4YTRlNjBmNmZiMSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxOTMzN2M4MC04NDNjLTQwZmItYjM1Yy1mZDU2MTQwNjAwOWYiLCJkYTBkNDI5ZS02ZjE2LTQ2MWUtYmUyZi0wOWVhNzk5N2UzMGEiLCIwY2E5NjJhMi0xZGVlLTQyMWUtODhmYy1lM2JlOWFmMGI1NmQiLCIzYWUwNWNkNC00ZjI0LTQzNzEtYWQ1ZC02M2UyYWUwMWQzNDEiLCI0YzYzMTIxOS1hZjU3LTRhYWQtYWYyZS1hMWFkZDEyMmFmZjIiLCJkMDNhZDYwNC1hMDU3LTQ2NzctOGMxMi0wOTM0YTI3MzE3ZWEiLCJmYjI3YWJlMi1kMjM0LTQ2MjctOWVlMi02MjI3Yjg0NDdlZmQiLCJmZGRkMjYzMS0wODk4LTQ4ZDctOGJmOC01ZTYzOGM0YWM0OTMiLCIwZGM4NzU2ZC0zZDIzLTQ5NDUtYTY2YS1iNDI1YmYzMTVmYjEiLCIwZmYyYmM4Zi1kNmY2LTQ4M2ItYWRjYS0zMDYxOWQ0YWMyMDgiLCIxZGM2NmU3ZS1lZmU5LTRmZDYtOTMzNS0zMTk3MjExYjI4OWYiLCIyMWMwOWU3Zi03YjBjLTRiZTUtOWJlZC05ODFmYThmMDE5MDciLCIyYzhiYTI3My02OTAyLTRmMTktYWZlYi05ZTZkNmE1MjNhYTEiLCIzY2UzMGE1Yy00ZjQ4LTQ0ZTAtODc3YS1lZTNiZGM2NDFhMjciLCI0OTZmOGNjMy1mM2MwLTQ1ODctYmVjZi02ZWMwZDViNjhkNjEiLCI1Yjc3ZDlkOS1mYTMzLTQ0MzUtYjcwYi0wZThhMWNkZTc2ODIiLCI3ZjM2MWZmNi1mYjI2LTQyMDctOWNmNy05MmNhMGRjYjM0NjAiLCI4ZjE2MjA0MS04NzEyLTRhNzgtYTc1Ny1hNmY4YjdhMzMxMjkiLCI5ZmE5ZjdiNC1hYzA2LTQ5N2UtYmYzNC1iYTMxYjhjOThkNTEiLCJhNzZkMTk3NC0wNjQzLTQ3ODAtODY4OS05MWEyMzA3NWZiODMiLCJhNzgxYzExZC1mN2ZlLTRmZjQtYTllMS04YmE5MjEwNjg2NTQiLCI1MWYwZjY1YS04ZjEzLTQ0YjEtYjg4OS0xMjQzMDgwYmQwNjkiLCI0OTlhZGM4YS1jNTZjLTQ3ODItYWQyOC0xMjdhNjljZjI0MWUiLCJlN2YyMzgzNS01ZDZlLTQxMGYtOGNjZC0yN2EwYzI2OGM1NDYiLCJlZDgyNzRhNS1mODIxLTQwMzYtOTVjNy03MDc5Y2Q2NTUzZWMiLCJhZDliZGQ4Zi03YjMwLTRkNTgtOTU5OS04NWZhNjY3M2VkZDIiLCJkM2NmMGNjNy1lNTQ1LTQxNTEtODE4Yy0xOGY4ZDgwNmM5MTkiLCJkZGE4MTJhYi0xNWMyLTQ4MmYtODc4Mi1mZmVmMWFiMGE2MGQiLCJkZWRjN2IxYy0wMzAwLTRhMjgtODgwNi02NzM1MzU0ZmFjYmEiLCJkZWZmMTYxMi01NGY5LTRiMTAtODVhZS1hZmMxZTU1N2U1NzEiLCJkZmRmMTI5YS1kM2VhLTQ4MjEtODA3NC1lMDYwZDdkZDkyZjYiLCJhYmY1ZWI0OC1lYTliLTQ4ZDAtYTUzNC0yMzZjZjg4MThiZjkiLCJmNDk3YmMwYy1kZGNiLTQxOTEtOGZhNS1jNmVkMjFiYmUxMzQiXSwianRpIjoiMzVjMGVkNmUtMmM1YS00ZWNlLTg2YTItNDk4MTQwYjVkNmNkIiwiaWF0IjoxNzc1MTU5NDcwLCJleHAiOjE3NzUyNDU4NzB9.KAiD1G1-34O8vmXeqUHiYLj0R5eCJQtOujwkJfhyO3I
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI5N2ZkMWU3Ni0wZmVlLTRhOTgtOTNjNi1mNWI2YzAyOGU5ZDIiLCJncm91cF9pZCI6IjkyMDBiNmQ1LWIyMDktNDQzZi05ZDc4LTI4YTRlNjBmNmZiMSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxOTMzN2M4MC04NDNjLTQwZmItYjM1Yy1mZDU2MTQwNjAwOWYiLCJkYTBkNDI5ZS02ZjE2LTQ2MWUtYmUyZi0wOWVhNzk5N2UzMGEiLCIwY2E5NjJhMi0xZGVlLTQyMWUtODhmYy1lM2JlOWFmMGI1NmQiLCIzYWUwNWNkNC00ZjI0LTQzNzEtYWQ1ZC02M2UyYWUwMWQzNDEiLCI0YzYzMTIxOS1hZjU3LTRhYWQtYWYyZS1hMWFkZDEyMmFmZjIiLCJkMDNhZDYwNC1hMDU3LTQ2NzctOGMxMi0wOTM0YTI3MzE3ZWEiLCJmYjI3YWJlMi1kMjM0LTQ2MjctOWVlMi02MjI3Yjg0NDdlZmQiLCJmZGRkMjYzMS0wODk4LTQ4ZDctOGJmOC01ZTYzOGM0YWM0OTMiLCIwZGM4NzU2ZC0zZDIzLTQ5NDUtYTY2YS1iNDI1YmYzMTVmYjEiLCIwZmYyYmM4Zi1kNmY2LTQ4M2ItYWRjYS0zMDYxOWQ0YWMyMDgiLCIxZGM2NmU3ZS1lZmU5LTRmZDYtOTMzNS0zMTk3MjExYjI4OWYiLCIyMWMwOWU3Zi03YjBjLTRiZTUtOWJlZC05ODFmYThmMDE5MDciLCIyYzhiYTI3My02OTAyLTRmMTktYWZlYi05ZTZkNmE1MjNhYTEiLCIzY2UzMGE1Yy00ZjQ4LTQ0ZTAtODc3YS1lZTNiZGM2NDFhMjciLCI0OTZmOGNjMy1mM2MwLTQ1ODctYmVjZi02ZWMwZDViNjhkNjEiLCI1Yjc3ZDlkOS1mYTMzLTQ0MzUtYjcwYi0wZThhMWNkZTc2ODIiLCI3ZjM2MWZmNi1mYjI2LTQyMDctOWNmNy05MmNhMGRjYjM0NjAiLCI4ZjE2MjA0MS04NzEyLTRhNzgtYTc1Ny1hNmY4YjdhMzMxMjkiLCI5ZmE5ZjdiNC1hYzA2LTQ5N2UtYmYzNC1iYTMxYjhjOThkNTEiLCJhNzZkMTk3NC0wNjQzLTQ3ODAtODY4OS05MWEyMzA3NWZiODMiLCJhNzgxYzExZC1mN2ZlLTRmZjQtYTllMS04YmE5MjEwNjg2NTQiLCI1MWYwZjY1YS04ZjEzLTQ0YjEtYjg4OS0xMjQzMDgwYmQwNjkiLCI0OTlhZGM4YS1jNTZjLTQ3ODItYWQyOC0xMjdhNjljZjI0MWUiLCJlN2YyMzgzNS01ZDZlLTQxMGYtOGNjZC0yN2EwYzI2OGM1NDYiLCJlZDgyNzRhNS1mODIxLTQwMzYtOTVjNy03MDc5Y2Q2NTUzZWMiLCJhZDliZGQ4Zi03YjMwLTRkNTgtOTU5OS04NWZhNjY3M2VkZDIiLCJkM2NmMGNjNy1lNTQ1LTQxNTEtODE4Yy0xOGY4ZDgwNmM5MTkiLCJkZGE4MTJhYi0xNWMyLTQ4MmYtODc4Mi1mZmVmMWFiMGE2MGQiLCJkZWRjN2IxYy0wMzAwLTRhMjgtODgwNi02NzM1MzU0ZmFjYmEiLCJkZWZmMTYxMi01NGY5LTRiMTAtODVhZS1hZmMxZTU1N2U1NzEiLCJkZmRmMTI5YS1kM2VhLTQ4MjEtODA3NC1lMDYwZDdkZDkyZjYiLCJhYmY1ZWI0OC1lYTliLTQ4ZDAtYTUzNC0yMzZjZjg4MThiZjkiLCJmNDk3YmMwYy1kZGNiLTQxOTEtOGZhNS1jNmVkMjFiYmUxMzQiXSwianRpIjoiMzVjMGVkNmUtMmM1YS00ZWNlLTg2YTItNDk4MTQwYjVkNmNkIiwiaWF0IjoxNzc1MTU5NDcwLCJleHAiOjE3NzUyNDU4NzB9.KAiD1G1-34O8vmXeqUHiYLj0R5eCJQtOujwkJfhyO3I","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI5N2ZkMWU3Ni0wZmVlLTRhOTgtOTNjNi1mNWI2YzAyOGU5ZDIiLCJncm91cF9pZCI6IjkyMDBiNmQ1LWIyMDktNDQzZi05ZDc4LTI4YTRlNjBmNmZiMSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxOTMzN2M4MC04NDNjLTQwZmItYjM1Yy1mZDU2MTQwNjAwOWYiLCJkYTBkNDI5ZS02ZjE2LTQ2MWUtYmUyZi0wOWVhNzk5N2UzMGEiLCIwY2E5NjJhMi0xZGVlLTQyMWUtODhmYy1lM2JlOWFmMGI1NmQiLCIzYWUwNWNkNC00ZjI0LTQzNzEtYWQ1ZC02M2UyYWUwMWQzNDEiLCI0YzYzMTIxOS1hZjU3LTRhYWQtYWYyZS1hMWFkZDEyMmFmZjIiLCJkMDNhZDYwNC1hMDU3LTQ2NzctOGMxMi0wOTM0YTI3MzE3ZWEiLCJmYjI3YWJlMi1kMjM0LTQ2MjctOWVlMi02MjI3Yjg0NDdlZmQiLCJmZGRkMjYzMS0wODk4LTQ4ZDctOGJmOC01ZTYzOGM0YWM0OTMiLCIwZGM4NzU2ZC0zZDIzLTQ5NDUtYTY2YS1iNDI1YmYzMTVmYjEiLCIwZmYyYmM4Zi1kNmY2LTQ4M2ItYWRjYS0zMDYxOWQ0YWMyMDgiLCIxZGM2NmU3ZS1lZmU5LTRmZDYtOTMzNS0zMTk3MjExYjI4OWYiLCIyMWMwOWU3Zi03YjBjLTRiZTUtOWJlZC05ODFmYThmMDE5MDciLCIyYzhiYTI3My02OTAyLTRmMTktYWZlYi05ZTZkNmE1MjNhYTEiLCIzY2UzMGE1Yy00ZjQ4LTQ0ZTAtODc3YS1lZTNiZGM2NDFhMjciLCI0OTZmOGNjMy1mM2MwLTQ1ODctYmVjZi02ZWMwZDViNjhkNjEiLCI1Yjc3ZDlkOS1mYTMzLTQ0MzUtYjcwYi0wZThhMWNkZTc2ODIiLCI3ZjM2MWZmNi1mYjI2LTQyMDctOWNmNy05MmNhMGRjYjM0NjAiLCI4ZjE2MjA0MS04NzEyLTRhNzgtYTc1Ny1hNmY4YjdhMzMxMjkiLCI5ZmE5ZjdiNC1hYzA2LTQ5N2UtYmYzNC1iYTMxYjhjOThkNTEiLCJhNzZkMTk3NC0wNjQzLTQ3ODAtODY4OS05MWEyMzA3NWZiODMiLCJhNzgxYzExZC1mN2ZlLTRmZjQtYTllMS04YmE5MjEwNjg2NTQiLCI1MWYwZjY1YS04ZjEzLTQ0YjEtYjg4OS0xMjQzMDgwYmQwNjkiLCI0OTlhZGM4YS1jNTZjLTQ3ODItYWQyOC0xMjdhNjljZjI0MWUiLCJlN2YyMzgzNS01ZDZlLTQxMGYtOGNjZC0yN2EwYzI2OGM1NDYiLCJlZDgyNzRhNS1mODIxLTQwMzYtOTVjNy03MDc5Y2Q2NTUzZWMiLCJhZDliZGQ4Zi03YjMwLTRkNTgtOTU5OS04NWZhNjY3M2VkZDIiLCJkM2NmMGNjNy1lNTQ1LTQxNTEtODE4Yy0xOGY4ZDgwNmM5MTkiLCJkZGE4MTJhYi0xNWMyLTQ4MmYtODc4Mi1mZmVmMWFiMGE2MGQiLCJkZWRjN2IxYy0wMzAwLTRhMjgtODgwNi02NzM1MzU0ZmFjYmEiLCJkZWZmMTYxMi01NGY5LTRiMTAtODVhZS1hZmMxZTU1N2U1NzEiLCJkZmRmMTI5YS1kM2VhLTQ4MjEtODA3NC1lMDYwZDdkZDkyZjYiLCJhYmY1ZWI0OC1lYTliLTQ4ZDAtYTUzNC0yMzZjZjg4MThiZjkiLCJmNDk3YmMwYy1kZGNiLTQxOTEtOGZhNS1jNmVkMjFiYmUxMzQiXSwianRpIjoiMzVjMGVkNmUtMmM1YS00ZWNlLTg2YTItNDk4MTQwYjVkNmNkIiwiaWF0IjoxNzc1MTU5NDcwLCJleHAiOjE3NzUyNDU4NzB9.KAiD1G1-34O8vmXeqUHiYLj0R5eCJQtOujwkJfhyO3I","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"0ca962a2-1dee-421e-88fc-e3be9af0b56d","execution_status":"success"},{"action_id":"0dc8756d-3d23-4945-a66a-b425bf315fb1","execution_status":"success"},{"action_id":"0ff2bc8f-d6f6-483b-adca-30619d4ac208","execution_status":"success"},{"action_id":"1dc66e7e-efe9-4fd6-9335-3197211b289f","execution_status":"success"},{"action_id":"21c09e7f-7b0c-4be5-9bed-981fa8f01907","execution_status":"success"},{"action_id":"2c8ba273-6902-4f19-afeb-9e6d6a523aa1","execution_status":"success"},{"action_id":"3ae05cd4-4f24-4371-ad5d-63e2ae01d341","execution_status":"success"},{"action_id":"3ce30a5c-4f48-44e0-877a-ee3bdc641a27","execution_status":"success"},{"action_id":"496f8cc3-f3c0-4587-becf-6ec0d5b68d61","execution_status":"success"},{"action_id":"499adc8a-c56c-4782-ad28-127a69cf241e","execution_status":"success"},{"action_id":"4c631219-af57-4aad-af2e-a1add122aff2","execution_status":"success"},{"action_id":"51f0f65a-8f13-44b1-b889-1243080bd069","execution_status":"success"},{"action_id":"5b77d9d9-fa33-4435-b70b-0e8a1cde7682","execution_status":"success"},{"action_id":"7f361ff6-fb26-4207-9cf7-92ca0dcb3460","execution_status":"success"},{"action_id":"8f162041-8712-4a78-a757-a6f8b7a33129","execution_status":"success"},{"action_id":"9fa9f7b4-ac06-497e-bf34-ba31b8c98d51","execution_status":"success"},{"action_id":"a76d1974-0643-4780-8689-91a23075fb83","execution_status":"success"},{"action_id":"a781c11d-f7fe-4ff4-a9e1-8ba921068654","execution_status":"success"},{"action_id":"ad9bdd8f-7b30-4d58-9599-85fa6673edd2","execution_status":"success"},{"action_id":"d03ad604-a057-4677-8c12-0934a27317ea","execution_status":"success"},{"action_id":"d3cf0cc7-e545-4151-818c-18f8d806c919","execution_status":"success"},{"action_id":"dda812ab-15c2-482f-8782-ffef1ab0a60d","execution_status":"success"},{"action_id":"dedc7b1c-0300-4a28-8806-6735354facba","execution_status":"success"},{"action_id":"deff1612-54f9-4b10-85ae-afc1e557e571","execution_status":"success"},{"action_id":"dfdf129a-d3ea-4821-8074-e060d7dd92f6","execution_status":"success"},{"action_id":"e7f23835-5d6e-410f-8ccd-27a0c268c546","execution_status":"success"},{"action_id":"ed8274a5-f821-4036-95c7-7079cd6553ec","execution_status":"success"},{"action_id":"fb27abe2-d234-4627-9ee2-6227b8447efd","execution_status":"success"},{"action_id":"fddd2631-0898-48d7-8bf8-5e638c4ac493","execution_status":"success"},{"action_id":"abf5eb48-ea9b-48d0-a534-236cf8818bf9","execution_status":"success"},{"action_id":"f497bc0c-ddcb-4191-8fa5-c6ed21bbe134","execution_status":"success"}],"non_executable_results":[{"action_id":"19337c80-843c-40fb-b35c-fd561406009f","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Existing bucket policy preservation evidence is missing for CloudFront + OAC migration.","Missing bucket identifier for access-path validation."]},{"action_id":"da0d429e-6f16-461e-be2f-09ea7997e30a","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Bucket is still configured for S3 website hosting with a public website-read policy, and BlockPublicPolicy would reject preserving that public statement. Use the website-specific CloudFront cutover path or manual review instead of the generic CloudFront + OAC migration."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiI5Zjc2MTZkOC1hZjA0LTQzY2EtOTljZC03MTM2MjUzNTdiNzAiLCJncm91cF9ydW5faWQiOiI5N2ZkMWU3Ni0wZmVlLTRhOTgtOTNjNi1mNWI2YzAyOGU5ZDIiLCJncm91cF9pZCI6IjkyMDBiNmQ1LWIyMDktNDQzZi05ZDc4LTI4YTRlNjBmNmZiMSIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyIxOTMzN2M4MC04NDNjLTQwZmItYjM1Yy1mZDU2MTQwNjAwOWYiLCJkYTBkNDI5ZS02ZjE2LTQ2MWUtYmUyZi0wOWVhNzk5N2UzMGEiLCIwY2E5NjJhMi0xZGVlLTQyMWUtODhmYy1lM2JlOWFmMGI1NmQiLCIzYWUwNWNkNC00ZjI0LTQzNzEtYWQ1ZC02M2UyYWUwMWQzNDEiLCI0YzYzMTIxOS1hZjU3LTRhYWQtYWYyZS1hMWFkZDEyMmFmZjIiLCJkMDNhZDYwNC1hMDU3LTQ2NzctOGMxMi0wOTM0YTI3MzE3ZWEiLCJmYjI3YWJlMi1kMjM0LTQ2MjctOWVlMi02MjI3Yjg0NDdlZmQiLCJmZGRkMjYzMS0wODk4LTQ4ZDctOGJmOC01ZTYzOGM0YWM0OTMiLCIwZGM4NzU2ZC0zZDIzLTQ5NDUtYTY2YS1iNDI1YmYzMTVmYjEiLCIwZmYyYmM4Zi1kNmY2LTQ4M2ItYWRjYS0zMDYxOWQ0YWMyMDgiLCIxZGM2NmU3ZS1lZmU5LTRmZDYtOTMzNS0zMTk3MjExYjI4OWYiLCIyMWMwOWU3Zi03YjBjLTRiZTUtOWJlZC05ODFmYThmMDE5MDciLCIyYzhiYTI3My02OTAyLTRmMTktYWZlYi05ZTZkNmE1MjNhYTEiLCIzY2UzMGE1Yy00ZjQ4LTQ0ZTAtODc3YS1lZTNiZGM2NDFhMjciLCI0OTZmOGNjMy1mM2MwLTQ1ODctYmVjZi02ZWMwZDViNjhkNjEiLCI1Yjc3ZDlkOS1mYTMzLTQ0MzUtYjcwYi0wZThhMWNkZTc2ODIiLCI3ZjM2MWZmNi1mYjI2LTQyMDctOWNmNy05MmNhMGRjYjM0NjAiLCI4ZjE2MjA0MS04NzEyLTRhNzgtYTc1Ny1hNmY4YjdhMzMxMjkiLCI5ZmE5ZjdiNC1hYzA2LTQ5N2UtYmYzNC1iYTMxYjhjOThkNTEiLCJhNzZkMTk3NC0wNjQzLTQ3ODAtODY4OS05MWEyMzA3NWZiODMiLCJhNzgxYzExZC1mN2ZlLTRmZjQtYTllMS04YmE5MjEwNjg2NTQiLCI1MWYwZjY1YS04ZjEzLTQ0YjEtYjg4OS0xMjQzMDgwYmQwNjkiLCI0OTlhZGM4YS1jNTZjLTQ3ODItYWQyOC0xMjdhNjljZjI0MWUiLCJlN2YyMzgzNS01ZDZlLTQxMGYtOGNjZC0yN2EwYzI2OGM1NDYiLCJlZDgyNzRhNS1mODIxLTQwMzYtOTVjNy03MDc5Y2Q2NTUzZWMiLCJhZDliZGQ4Zi03YjMwLTRkNTgtOTU5OS04NWZhNjY3M2VkZDIiLCJkM2NmMGNjNy1lNTQ1LTQxNTEtODE4Yy0xOGY4ZDgwNmM5MTkiLCJkZGE4MTJhYi0xNWMyLTQ4MmYtODc4Mi1mZmVmMWFiMGE2MGQiLCJkZWRjN2IxYy0wMzAwLTRhMjgtODgwNi02NzM1MzU0ZmFjYmEiLCJkZWZmMTYxMi01NGY5LTRiMTAtODVhZS1hZmMxZTU1N2U1NzEiLCJkZmRmMTI5YS1kM2VhLTQ4MjEtODA3NC1lMDYwZDdkZDkyZjYiLCJhYmY1ZWI0OC1lYTliLTQ4ZDAtYTUzNC0yMzZjZjg4MThiZjkiLCJmNDk3YmMwYy1kZGNiLTQxOTEtOGZhNS1jNmVkMjFiYmUxMzQiXSwianRpIjoiMzVjMGVkNmUtMmM1YS00ZWNlLTg2YTItNDk4MTQwYjVkNmNkIiwiaWF0IjoxNzc1MTU5NDcwLCJleHAiOjE3NzUyNDU4NzB9.KAiD1G1-34O8vmXeqUHiYLj0R5eCJQtOujwkJfhyO3I","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"0ca962a2-1dee-421e-88fc-e3be9af0b56d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0dc8756d-3d23-4945-a66a-b425bf315fb1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"0ff2bc8f-d6f6-483b-adca-30619d4ac208","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"1dc66e7e-efe9-4fd6-9335-3197211b289f","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"21c09e7f-7b0c-4be5-9bed-981fa8f01907","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"2c8ba273-6902-4f19-afeb-9e6d6a523aa1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"3ae05cd4-4f24-4371-ad5d-63e2ae01d341","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"3ce30a5c-4f48-44e0-877a-ee3bdc641a27","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"496f8cc3-f3c0-4587-becf-6ec0d5b68d61","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"499adc8a-c56c-4782-ad28-127a69cf241e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4c631219-af57-4aad-af2e-a1add122aff2","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"51f0f65a-8f13-44b1-b889-1243080bd069","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"5b77d9d9-fa33-4435-b70b-0e8a1cde7682","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"7f361ff6-fb26-4207-9cf7-92ca0dcb3460","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8f162041-8712-4a78-a757-a6f8b7a33129","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"9fa9f7b4-ac06-497e-bf34-ba31b8c98d51","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"a76d1974-0643-4780-8689-91a23075fb83","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"a781c11d-f7fe-4ff4-a9e1-8ba921068654","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"ad9bdd8f-7b30-4d58-9599-85fa6673edd2","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d03ad604-a057-4677-8c12-0934a27317ea","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d3cf0cc7-e545-4151-818c-18f8d806c919","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"dda812ab-15c2-482f-8782-ffef1ab0a60d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"dedc7b1c-0300-4a28-8806-6735354facba","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"deff1612-54f9-4b10-85ae-afc1e557e571","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"dfdf129a-d3ea-4821-8074-e060d7dd92f6","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"e7f23835-5d6e-410f-8ccd-27a0c268c546","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"ed8274a5-f821-4036-95c7-7079cd6553ec","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"fb27abe2-d234-4627-9ee2-6227b8447efd","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"fddd2631-0898-48d7-8bf8-5e638c4ac493","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"abf5eb48-ea9b-48d0-a534-236cf8818bf9","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"f497bc0c-ddcb-4191-8fa5-c6ed21bbe134","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"19337c80-843c-40fb-b35c-fd561406009f","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Existing bucket policy preservation evidence is missing for CloudFront + OAC migration.","Missing bucket identifier for access-path validation."]},{"action_id":"da0d429e-6f16-461e-be2f-09ea7997e30a","support_tier":"manual_guidance_only","profile_id":"s3_migrate_cloudfront_oac_private_manual_preservation","strategy_id":"s3_migrate_cloudfront_oac_private","reason":"manual_guidance_metadata_only","blocked_reasons":["Bucket is still configured for S3 website hosting with a public website-read policy, and BlockPublicPolicy would reject preserving that public statement. Use the website-specific CloudFront cutover path or manual review instead of the generic CloudFront + OAC migration."]}]}'
REPLAY_DIR="./.bundle-callback-replay"
RUNNER="./run_actions.sh"
SUMMARY_PATH="${BUNDLE_EXECUTION_SUMMARY_PATH:-./.bundle-execution-summary.json}"
RUN_RC=1
FINISH_SENT=0

mkdir -p "$REPLAY_DIR"

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

inject_timestamp() {
  local template_json="$1"
  local field_name="$2"
  local field_value="$3"
  python3 - "$template_json" "$field_name" "$field_value" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
payload[str(sys.argv[2])] = str(sys.argv[3])
print(json.dumps(payload, separators=(",", ":")))
PY
}

inject_execution_summary() {
  local template_json="$1"
  local summary_path="$2"
  local finished_at="$3"
  python3 - "$template_json" "$summary_path" "$finished_at" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(sys.argv[1])
summary_path = Path(sys.argv[2])
finished_at = str(sys.argv[3])

if summary_path.is_file():
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        summary = {}
    if isinstance(summary.get("action_results"), list):
        payload["action_results"] = summary["action_results"]

payload["finished_at"] = finished_at
print(json.dumps(payload, separators=(",", ":")))
PY
}

post_payload() {
  local payload="$1"
  if [ -z "$REPORT_URL" ] || [ -z "$REPORT_TOKEN" ]; then
    return 1
  fi
  if command -v curl >/dev/null 2>&1; then
    local response_file http_code rc
    response_file=$(mktemp)
    http_code=$(curl -sS       --connect-timeout 5       --max-time 20       --retry 4       --retry-delay 2       --retry-all-errors       -o "$response_file"       -w "%{http_code}"       -X POST "$REPORT_URL"       -H "Content-Type: application/json"       -d "$payload")
    rc=$?
    if [ "$rc" -ne 0 ]; then
      rm -f "$response_file"
      return "$rc"
    fi
    rm -f "$response_file"
    case "$http_code" in
      2??)
        return 0
        ;;
    esac
    return 1
  fi
  return 1
}

persist_replay() {
  local suffix="$1"
  local payload="$2"
  local file="$REPLAY_DIR/${suffix}-$(date +%s).json"
  printf '%s\n' "$payload" > "$file"
}

emit_finished_callback() {
  local exit_code="$1"
  local finished_at payload template_json
  if [ "$FINISH_SENT" -eq 1 ]; then
    return 0
  fi
  FINISH_SENT=1
  finished_at="$(iso_now)"
  if [ "$exit_code" -eq 0 ]; then
    template_json="$FINISHED_SUCCESS_TEMPLATE"
  else
    template_json="$FINISHED_FAILED_TEMPLATE"
  fi
  if [ -f "$SUMMARY_PATH" ]; then
    if ! payload="$(inject_execution_summary "$template_json" "$SUMMARY_PATH" "$finished_at")"; then
      payload="$(inject_timestamp "$template_json" "finished_at" "$finished_at")"
    fi
  else
    payload="$(inject_timestamp "$template_json" "finished_at" "$finished_at")"
  fi
  if ! post_payload "$payload"; then
    persist_replay "finished" "$payload"
  fi
}

handle_exit() {
  local exit_code="$1"
  emit_finished_callback "$exit_code"
  exit "$exit_code"
}

STARTED_AT="$(iso_now)"
START_PAYLOAD="$(inject_timestamp "$STARTED_TEMPLATE" "started_at" "$STARTED_AT")"
if ! post_payload "$START_PAYLOAD"; then
  persist_replay "started" "$START_PAYLOAD"
fi

trap 'handle_exit $?' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

chmod +x "$RUNNER"
"$RUNNER"
RUN_RC=$?
exit "$RUN_RC"
