---
Test 03 — Landing Page Check
Run date: 2026-02-28
Status: FAIL

ENVIRONMENT VALUES
FRONTEND_URL=https://dev.valensjewelry.com
BACKEND_API_URL=https://api.valensjewelry.com
TEST_EMAIL=maromaher54@gmail.com
---

| Test | Expected | Actual | Pass/Fail |
|------|---------|--------|-----------|
| 3.1 Page loads without errors | no red errors in console | No errors (except expected 401 on `/api/auth/me` guest check) | PASS |
| 3.2 No placeholder content visible | no placeholders, no "Lorem ipsum" | Found `https://calendly.com/placeholder` on primary CTA | FAIL |
| 3.3 Hero headline is correct | matches rewritten headline | Headline is: "500 findings. 20 actions. Every fix attached." | PASS |
| 3.4 Primary CTA works | navigates to correct destination | Navigates to a Calendly placeholder for "Bits In Glass" | FAIL |
| 3.5 No broken footer links | no 404s, no placeholder links | LinkedIn link points to private admin dashboard | FAIL |
| 3.6 "Hybrid Redemption" typo is fixed | reads "Hybrid Remediation" | "Redemption" not found. Reads "Hybrid Remediation" | PASS |
| 3.7 Page is responsive | no horizontal scroll, text readable | Mobile view scales correctly, no scroll issues | PASS |

### Failed Tests:
* **Test 3.2**: Found placeholder Calendly link used for the main button.
* **Test 3.4**: CTA navigates to incorrect Calendly page (`calendly.com/placeholder`).
* **Test 3.5**: Footer LinkedIn link goes to `https://www.linkedin.com/company/111719210/admin/dashboard/` instead of the public profile page.

*(Note: Test executed via automated browser checks. Visual screenshots were omitted but verification on dev domain confirmed the active placeholder texts.)*
