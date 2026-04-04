#!/usr/bin/env bash
set +e

REPORT_URL=https://api.ocypheris.com/api/internal/group-runs/report
REPORT_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI0ZjU2NTQzNC1lZWIyLTQyYjYtOTdmOS0zY2VlMTZmYjk1MzUiLCJncm91cF9pZCI6IjlhOTA0ZTZhLTNhYjgtNGVjYS1iZTkyLWI3MjdiMGFhY2Y2NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJlZTA5YjM2Yy0zM2FkLTRhZjktOGZhYS05Mjc5NGZjN2ViYzEiLCJjOGQ0OTZmZS0zNDMxLTRhNDQtYmMwOC03NDY0NmI1ZjI1NzIiLCIwNDk5NjI2OS05MjJlLTQ1M2UtOWFhOS1hYWMyMTM2NmUyNGIiLCIzM2VkMzc3Ni0wMGYwLTRkOTktYjNhZC0zMTZmOTdjMDhhMWEiLCI3NDdlNmE5ZS1lYWQ5LTRlNjAtODEwZi1mZGY2YjNmN2VmMmQiLCI2Y2IwNzY5ZS01YmQyLTQ4Y2YtYTRjOC0wZWEwMDY4NGY0NGQiLCJkMTA4ZGQyOS1hODlkLTQ1ZDMtYjJkNS05Njg5ZDk2OTlkNWUiLCI0Yjk3Y2Y5YS1mNTE0LTQwMzMtYjU0ZS1kZDY3OWM0MjdjZDkiLCJkYTlkODcxMy0zODNkLTQxNWUtYjJmYS03YjBiNTAzOWZmOTQiLCI1NGIwZDU4NC1kNjBhLTQwOWQtODZlMy01NDU4YmQ4MDU0YjEiLCI4ZWRlYjdmNi01NTZlLTQxMmMtOWY1OS05MDVjOGE4M2Y0NTIiLCI5NzEwMDJmZi1mNzBiLTRmNjQtYmMxZi04YWU5YzFmOWY2MDAiLCI4YWRhNjJjOC0zNmUxLTRmOTAtYWZiYi0zYWI4OWIxODA5NmUiLCJiYTA5ZmViZi0zMzg1LTQwZWMtYTExYi03MDdjZDA4MmI3OTgiLCI4YWIyOTk5Ny1iYjZjLTQxZmUtYmEwYy0yNmYwMzUyM2YwZWQiLCJjYmUwZDJjMy1jNjA5LTRhYTItYTEyZi02YWZiMzM2Y2Q1MDciLCJkZWI3MWU3ZC0xZmM5LTQxMDgtYTQ2Ni04NTlmZTUxYzUyZWYiLCIxNzZjMjllZC1mY2VjLTQ5MzQtYTFhYi0zNDRiYjRiNmY0NDQiLCJhOWU1YTk4OS0zZGJhLTQxMTQtYWVhZi0yZGRhYzEyMGFjMGMiLCIzN2UwZjcxZC00ODA1LTQ2ZDAtOWY5Zi1iZjQzNDJkN2U2M2MiLCJhYmFhOWRlNy1hYzA4LTRiN2MtODY2MC05MzY5NWU5OTJjMWEiLCI4ZDllOGNjMS05NDlhLTQxMmQtOGRiMC05ODkyM2I1MTM1MTgiLCJkMzQxOWNiOC05ODRiLTRjOTUtODE3ZC04M2RkM2IzOTRiOTgiLCI1M2MwNzI1My1hOWIxLTQwNDQtOTJmOS03NTAwNjNkMzBiNTkiXSwianRpIjoiMmU1NGMwMDgtZTcwMy00NjgwLTg0NjgtZjVjNWFlYWUyNjM2IiwiaWF0IjoxNzc1MDA0MTMxLCJleHAiOjE3NzUwOTA1MzF9.8vMQrHvsaXujoJNgfvpDBKocHNZTqZT4EytTNWeMyNQ
STARTED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI0ZjU2NTQzNC1lZWIyLTQyYjYtOTdmOS0zY2VlMTZmYjk1MzUiLCJncm91cF9pZCI6IjlhOTA0ZTZhLTNhYjgtNGVjYS1iZTkyLWI3MjdiMGFhY2Y2NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJlZTA5YjM2Yy0zM2FkLTRhZjktOGZhYS05Mjc5NGZjN2ViYzEiLCJjOGQ0OTZmZS0zNDMxLTRhNDQtYmMwOC03NDY0NmI1ZjI1NzIiLCIwNDk5NjI2OS05MjJlLTQ1M2UtOWFhOS1hYWMyMTM2NmUyNGIiLCIzM2VkMzc3Ni0wMGYwLTRkOTktYjNhZC0zMTZmOTdjMDhhMWEiLCI3NDdlNmE5ZS1lYWQ5LTRlNjAtODEwZi1mZGY2YjNmN2VmMmQiLCI2Y2IwNzY5ZS01YmQyLTQ4Y2YtYTRjOC0wZWEwMDY4NGY0NGQiLCJkMTA4ZGQyOS1hODlkLTQ1ZDMtYjJkNS05Njg5ZDk2OTlkNWUiLCI0Yjk3Y2Y5YS1mNTE0LTQwMzMtYjU0ZS1kZDY3OWM0MjdjZDkiLCJkYTlkODcxMy0zODNkLTQxNWUtYjJmYS03YjBiNTAzOWZmOTQiLCI1NGIwZDU4NC1kNjBhLTQwOWQtODZlMy01NDU4YmQ4MDU0YjEiLCI4ZWRlYjdmNi01NTZlLTQxMmMtOWY1OS05MDVjOGE4M2Y0NTIiLCI5NzEwMDJmZi1mNzBiLTRmNjQtYmMxZi04YWU5YzFmOWY2MDAiLCI4YWRhNjJjOC0zNmUxLTRmOTAtYWZiYi0zYWI4OWIxODA5NmUiLCJiYTA5ZmViZi0zMzg1LTQwZWMtYTExYi03MDdjZDA4MmI3OTgiLCI4YWIyOTk5Ny1iYjZjLTQxZmUtYmEwYy0yNmYwMzUyM2YwZWQiLCJjYmUwZDJjMy1jNjA5LTRhYTItYTEyZi02YWZiMzM2Y2Q1MDciLCJkZWI3MWU3ZC0xZmM5LTQxMDgtYTQ2Ni04NTlmZTUxYzUyZWYiLCIxNzZjMjllZC1mY2VjLTQ5MzQtYTFhYi0zNDRiYjRiNmY0NDQiLCJhOWU1YTk4OS0zZGJhLTQxMTQtYWVhZi0yZGRhYzEyMGFjMGMiLCIzN2UwZjcxZC00ODA1LTQ2ZDAtOWY5Zi1iZjQzNDJkN2U2M2MiLCJhYmFhOWRlNy1hYzA4LTRiN2MtODY2MC05MzY5NWU5OTJjMWEiLCI4ZDllOGNjMS05NDlhLTQxMmQtOGRiMC05ODkyM2I1MTM1MTgiLCJkMzQxOWNiOC05ODRiLTRjOTUtODE3ZC04M2RkM2IzOTRiOTgiLCI1M2MwNzI1My1hOWIxLTQwNDQtOTJmOS03NTAwNjNkMzBiNTkiXSwianRpIjoiMmU1NGMwMDgtZTcwMy00NjgwLTg0NjgtZjVjNWFlYWUyNjM2IiwiaWF0IjoxNzc1MDA0MTMxLCJleHAiOjE3NzUwOTA1MzF9.8vMQrHvsaXujoJNgfvpDBKocHNZTqZT4EytTNWeMyNQ","event":"started","reporting_source":"bundle_callback"}'
FINISHED_SUCCESS_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI0ZjU2NTQzNC1lZWIyLTQyYjYtOTdmOS0zY2VlMTZmYjk1MzUiLCJncm91cF9pZCI6IjlhOTA0ZTZhLTNhYjgtNGVjYS1iZTkyLWI3MjdiMGFhY2Y2NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJlZTA5YjM2Yy0zM2FkLTRhZjktOGZhYS05Mjc5NGZjN2ViYzEiLCJjOGQ0OTZmZS0zNDMxLTRhNDQtYmMwOC03NDY0NmI1ZjI1NzIiLCIwNDk5NjI2OS05MjJlLTQ1M2UtOWFhOS1hYWMyMTM2NmUyNGIiLCIzM2VkMzc3Ni0wMGYwLTRkOTktYjNhZC0zMTZmOTdjMDhhMWEiLCI3NDdlNmE5ZS1lYWQ5LTRlNjAtODEwZi1mZGY2YjNmN2VmMmQiLCI2Y2IwNzY5ZS01YmQyLTQ4Y2YtYTRjOC0wZWEwMDY4NGY0NGQiLCJkMTA4ZGQyOS1hODlkLTQ1ZDMtYjJkNS05Njg5ZDk2OTlkNWUiLCI0Yjk3Y2Y5YS1mNTE0LTQwMzMtYjU0ZS1kZDY3OWM0MjdjZDkiLCJkYTlkODcxMy0zODNkLTQxNWUtYjJmYS03YjBiNTAzOWZmOTQiLCI1NGIwZDU4NC1kNjBhLTQwOWQtODZlMy01NDU4YmQ4MDU0YjEiLCI4ZWRlYjdmNi01NTZlLTQxMmMtOWY1OS05MDVjOGE4M2Y0NTIiLCI5NzEwMDJmZi1mNzBiLTRmNjQtYmMxZi04YWU5YzFmOWY2MDAiLCI4YWRhNjJjOC0zNmUxLTRmOTAtYWZiYi0zYWI4OWIxODA5NmUiLCJiYTA5ZmViZi0zMzg1LTQwZWMtYTExYi03MDdjZDA4MmI3OTgiLCI4YWIyOTk5Ny1iYjZjLTQxZmUtYmEwYy0yNmYwMzUyM2YwZWQiLCJjYmUwZDJjMy1jNjA5LTRhYTItYTEyZi02YWZiMzM2Y2Q1MDciLCJkZWI3MWU3ZC0xZmM5LTQxMDgtYTQ2Ni04NTlmZTUxYzUyZWYiLCIxNzZjMjllZC1mY2VjLTQ5MzQtYTFhYi0zNDRiYjRiNmY0NDQiLCJhOWU1YTk4OS0zZGJhLTQxMTQtYWVhZi0yZGRhYzEyMGFjMGMiLCIzN2UwZjcxZC00ODA1LTQ2ZDAtOWY5Zi1iZjQzNDJkN2U2M2MiLCJhYmFhOWRlNy1hYzA4LTRiN2MtODY2MC05MzY5NWU5OTJjMWEiLCI4ZDllOGNjMS05NDlhLTQxMmQtOGRiMC05ODkyM2I1MTM1MTgiLCJkMzQxOWNiOC05ODRiLTRjOTUtODE3ZC04M2RkM2IzOTRiOTgiLCI1M2MwNzI1My1hOWIxLTQwNDQtOTJmOS03NTAwNjNkMzBiNTkiXSwianRpIjoiMmU1NGMwMDgtZTcwMy00NjgwLTg0NjgtZjVjNWFlYWUyNjM2IiwiaWF0IjoxNzc1MDA0MTMxLCJleHAiOjE3NzUwOTA1MzF9.8vMQrHvsaXujoJNgfvpDBKocHNZTqZT4EytTNWeMyNQ","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"c8d496fe-3431-4a44-bc08-74646b5f2572","execution_status":"success"},{"action_id":"ee09b36c-33ad-4af9-8faa-92794fc7ebc1","execution_status":"success"},{"action_id":"04996269-922e-453e-9aa9-aac21366e24b","execution_status":"success"},{"action_id":"33ed3776-00f0-4d99-b3ad-316f97c08a1a","execution_status":"success"},{"action_id":"6cb0769e-5bd2-48cf-a4c8-0ea00684f44d","execution_status":"success"},{"action_id":"747e6a9e-ead9-4e60-810f-fdf6b3f7ef2d","execution_status":"success"},{"action_id":"d108dd29-a89d-45d3-b2d5-9689d9699d5e","execution_status":"success"},{"action_id":"4b97cf9a-f514-4033-b54e-dd679c427cd9","execution_status":"success"},{"action_id":"da9d8713-383d-415e-b2fa-7b0b5039ff94","execution_status":"success"},{"action_id":"54b0d584-d60a-409d-86e3-5458bd8054b1","execution_status":"success"},{"action_id":"8edeb7f6-556e-412c-9f59-905c8a83f452","execution_status":"success"},{"action_id":"971002ff-f70b-4f64-bc1f-8ae9c1f9f600","execution_status":"success"},{"action_id":"8ada62c8-36e1-4f90-afbb-3ab89b18096e","execution_status":"success"},{"action_id":"ba09febf-3385-40ec-a11b-707cd082b798","execution_status":"success"},{"action_id":"8ab29997-bb6c-41fe-ba0c-26f03523f0ed","execution_status":"success"},{"action_id":"deb71e7d-1fc9-4108-a466-859fe51c52ef","execution_status":"success"},{"action_id":"176c29ed-fcec-4934-a1ab-344bb4b6f444","execution_status":"success"},{"action_id":"a9e5a989-3dba-4114-aeaf-2ddac120ac0c","execution_status":"success"},{"action_id":"37e0f71d-4805-46d0-9f9f-bf4342d7e63c","execution_status":"success"},{"action_id":"abaa9de7-ac08-4b7c-8660-93695e992c1a","execution_status":"success"},{"action_id":"8d9e8cc1-949a-412d-8db0-98923b513518","execution_status":"success"},{"action_id":"d3419cb8-984b-4c95-817d-83dd3b394b98","execution_status":"success"},{"action_id":"53c07253-a9b1-4044-92f9-750063d30b59","execution_status":"success"}],"non_executable_results":[{"action_id":"cbe0d2c3-c609-4aa2-a12f-6afb336cd507","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]}]}'
FINISHED_FAILED_TEMPLATE='{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJlNGUwN2FhOC1iOGVhLTRjMWQtOWZkNy00MzYyYTJmYzExOTUiLCJncm91cF9ydW5faWQiOiI0ZjU2NTQzNC1lZWIyLTQyYjYtOTdmOS0zY2VlMTZmYjk1MzUiLCJncm91cF9pZCI6IjlhOTA0ZTZhLTNhYjgtNGVjYS1iZTkyLWI3MjdiMGFhY2Y2NyIsImFsbG93ZWRfYWN0aW9uX2lkcyI6WyJlZTA5YjM2Yy0zM2FkLTRhZjktOGZhYS05Mjc5NGZjN2ViYzEiLCJjOGQ0OTZmZS0zNDMxLTRhNDQtYmMwOC03NDY0NmI1ZjI1NzIiLCIwNDk5NjI2OS05MjJlLTQ1M2UtOWFhOS1hYWMyMTM2NmUyNGIiLCIzM2VkMzc3Ni0wMGYwLTRkOTktYjNhZC0zMTZmOTdjMDhhMWEiLCI3NDdlNmE5ZS1lYWQ5LTRlNjAtODEwZi1mZGY2YjNmN2VmMmQiLCI2Y2IwNzY5ZS01YmQyLTQ4Y2YtYTRjOC0wZWEwMDY4NGY0NGQiLCJkMTA4ZGQyOS1hODlkLTQ1ZDMtYjJkNS05Njg5ZDk2OTlkNWUiLCI0Yjk3Y2Y5YS1mNTE0LTQwMzMtYjU0ZS1kZDY3OWM0MjdjZDkiLCJkYTlkODcxMy0zODNkLTQxNWUtYjJmYS03YjBiNTAzOWZmOTQiLCI1NGIwZDU4NC1kNjBhLTQwOWQtODZlMy01NDU4YmQ4MDU0YjEiLCI4ZWRlYjdmNi01NTZlLTQxMmMtOWY1OS05MDVjOGE4M2Y0NTIiLCI5NzEwMDJmZi1mNzBiLTRmNjQtYmMxZi04YWU5YzFmOWY2MDAiLCI4YWRhNjJjOC0zNmUxLTRmOTAtYWZiYi0zYWI4OWIxODA5NmUiLCJiYTA5ZmViZi0zMzg1LTQwZWMtYTExYi03MDdjZDA4MmI3OTgiLCI4YWIyOTk5Ny1iYjZjLTQxZmUtYmEwYy0yNmYwMzUyM2YwZWQiLCJjYmUwZDJjMy1jNjA5LTRhYTItYTEyZi02YWZiMzM2Y2Q1MDciLCJkZWI3MWU3ZC0xZmM5LTQxMDgtYTQ2Ni04NTlmZTUxYzUyZWYiLCIxNzZjMjllZC1mY2VjLTQ5MzQtYTFhYi0zNDRiYjRiNmY0NDQiLCJhOWU1YTk4OS0zZGJhLTQxMTQtYWVhZi0yZGRhYzEyMGFjMGMiLCIzN2UwZjcxZC00ODA1LTQ2ZDAtOWY5Zi1iZjQzNDJkN2U2M2MiLCJhYmFhOWRlNy1hYzA4LTRiN2MtODY2MC05MzY5NWU5OTJjMWEiLCI4ZDllOGNjMS05NDlhLTQxMmQtOGRiMC05ODkyM2I1MTM1MTgiLCJkMzQxOWNiOC05ODRiLTRjOTUtODE3ZC04M2RkM2IzOTRiOTgiLCI1M2MwNzI1My1hOWIxLTQwNDQtOTJmOS03NTAwNjNkMzBiNTkiXSwianRpIjoiMmU1NGMwMDgtZTcwMy00NjgwLTg0NjgtZjVjNWFlYWUyNjM2IiwiaWF0IjoxNzc1MDA0MTMxLCJleHAiOjE3NzUwOTA1MzF9.8vMQrHvsaXujoJNgfvpDBKocHNZTqZT4EytTNWeMyNQ","event":"finished","reporting_source":"bundle_callback","action_results":[{"action_id":"c8d496fe-3431-4a44-bc08-74646b5f2572","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"ee09b36c-33ad-4af9-8faa-92794fc7ebc1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"04996269-922e-453e-9aa9-aac21366e24b","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"33ed3776-00f0-4d99-b3ad-316f97c08a1a","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"6cb0769e-5bd2-48cf-a4c8-0ea00684f44d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"747e6a9e-ead9-4e60-810f-fdf6b3f7ef2d","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d108dd29-a89d-45d3-b2d5-9689d9699d5e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"4b97cf9a-f514-4033-b54e-dd679c427cd9","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"da9d8713-383d-415e-b2fa-7b0b5039ff94","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"54b0d584-d60a-409d-86e3-5458bd8054b1","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8edeb7f6-556e-412c-9f59-905c8a83f452","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"971002ff-f70b-4f64-bc1f-8ae9c1f9f600","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8ada62c8-36e1-4f90-afbb-3ab89b18096e","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"ba09febf-3385-40ec-a11b-707cd082b798","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8ab29997-bb6c-41fe-ba0c-26f03523f0ed","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"deb71e7d-1fc9-4108-a466-859fe51c52ef","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"176c29ed-fcec-4934-a1ab-344bb4b6f444","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"a9e5a989-3dba-4114-aeaf-2ddac120ac0c","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"37e0f71d-4805-46d0-9f9f-bf4342d7e63c","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"abaa9de7-ac08-4b7c-8660-93695e992c1a","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"8d9e8cc1-949a-412d-8db0-98923b513518","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"d3419cb8-984b-4c95-817d-83dd3b394b98","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"},{"action_id":"53c07253-a9b1-4044-92f9-750063d30b59","execution_status":"failed","execution_error_code":"bundle_runner_failed","execution_error_message":"run_actions.sh exited non-zero"}],"non_executable_results":[{"action_id":"cbe0d2c3-c609-4aa2-a12f-6afb336cd507","support_tier":"manual_guidance_only","profile_id":"s3_enable_abort_incomplete_uploads","strategy_id":"s3_enable_abort_incomplete_uploads","reason":"manual_guidance_metadata_only","blocked_reasons":["Lifecycle preservation evidence is missing for additive merge review."]}]}'
REPLAY_DIR="./.bundle-callback-replay"
RUNNER="./run_actions.sh"
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
  local finished_at payload
  if [ "$FINISH_SENT" -eq 1 ]; then
    return 0
  fi
  FINISH_SENT=1
  finished_at="$(iso_now)"
  if [ "$exit_code" -eq 0 ]; then
    payload="$(inject_timestamp "$FINISHED_SUCCESS_TEMPLATE" "finished_at" "$finished_at")"
  else
    payload="$(inject_timestamp "$FINISHED_FAILED_TEMPLATE" "finished_at" "$finished_at")"
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
