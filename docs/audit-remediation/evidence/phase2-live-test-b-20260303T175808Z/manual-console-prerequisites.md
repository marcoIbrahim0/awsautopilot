# Manual-console prerequisites (Live Test B)

1. B1 (MFA=0 hard block): Requires an account where root MFA is actually disabled (`AccountMFAEnabled=0`) if executed fully live.
2. Connected tenant-linked accounts in this environment did not expose an MFA-disabled root account at run time.
3. Therefore B1 was executed through the approved staging/test path by injecting runtime signal `iam_root_account_mfa_enrolled=false` in API test harness, while preserving gate logic and safety controls.
4. B2 uses the connected live account context with `AccountMFAEnabled=1` (captured in `b2-account-summary.json`).
5. B3 is a worker simulation path (no manual console interaction required) validating fail-closed transition behavior.
