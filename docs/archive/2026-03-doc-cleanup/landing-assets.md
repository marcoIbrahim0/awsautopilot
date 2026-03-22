# Landing Page – Image & Video Placeholders

Use this doc to know **where** images/videos are wired and **what to add later**. The logo is already in use; other slots use placeholders or no asset yet.

---

## Logo (in use)

- **Nav:** `public/logo/logo-light.svg` (dark background).
- **Footer (Centered With Logo):** `public/logo/logo-light.svg`.
- **Replace later:** Swap for your final product logo (SVG or PNG). Keep light variant for dark theme; add `logo-dark.svg` if you add a light landing variant.

---

## Hero (right-side “report” preview)

- **Current:** Static mock (BrowserWindowMock) with text only – no image.
- **Add later (optional):**
  - **Image:** Screenshot of the actual “Baseline Report” (Executive Summary + Top Risks) – e.g. `public/landing/hero-report-preview.png`.
  - **Video:** Short loop (e.g. 10–15 s) of the report opening or scrolling – e.g. `public/landing/hero-report-demo.mp4`. Use `<video autoPlay loop muted playsInline />` in `BrowserWindowMock` or a wrapper.

---

## Problem / Focus cards (Why AWS-first SMBs stall)

- **Current:** FocusCards with title + description only; no images.
- **Add later (optional):** One image per card to reinforce “Implementation / Operational / Compliance” gap:
  - **Image:** Icons or illustrations (e.g. “implementation gap”, “flood of findings”, “audit evidence”) – e.g. `public/landing/card-implementation.png`, `card-operational.png`, `card-compliance.png`. Wire via `FocusCards` `cards[].image`.

---

## Report section (CometCard tiles)

- **Current:** CometCard with title + description only; `image` is `undefined`.
- **Add later (optional):** One image per tile (Executive summary, Top risks, Recommendations):
  - **Image:** Icons or small illustrations – e.g. `public/landing/report-executive.png`, `report-risks.png`, `report-recommendations.png`. Set `BENTO_TILES[].image` in `ReportBentoSection.tsx`.

---

## Differentiator / outcomes section

- **Current:** Text + Dynamic Island pill + GlowingEffect box; no media.
- **Add later (optional):**
  - **Image:** Product UI showing “Baseline → Fixes → Evidence” (e.g. dashboard or workflow).
  - **Video:** Short clip of the product (e.g. connecting account → report → actions). Prefer muted, looped, subtle.

---

## Secondary CTA band (“Ready to see your baseline?”)

- **Current:** Gradient background only; no image/video.
- **Add later (optional):**
  - **Background video:** Very subtle loop (e.g. particles, grid) – e.g. `public/landing/cta-bg-loop.mp4`. Keep opacity low so text stays readable.

---

## Footer

- **Current:** Logo from `public/logo/logo-light.svg` (Centered With Logo).
- **Add later:** Same as logo – use final brand logo; optional favicon or small icon set for social/legal links if you add them.

---

## Summary table

| Location              | Current              | Add later (suggested)                          |
|-----------------------|----------------------|-------------------------------------------------|
| Nav                   | Logo image           | Final product logo (light for dark theme)      |
| Hero right            | Text mock            | Report screenshot or short demo video          |
| Problem cards         | No image             | 3 illustrations/icons (one per gap)           |
| Report tiles          | No image             | 3 icons/illustrations (one per tile)           |
| Differentiator        | No media             | Product UI image or short product video       |
| Secondary CTA band    | Gradient only        | Optional subtle background video               |
| Footer                | Logo image           | Final logo; optional social/legal icons        |

All paths above are relative to `public/` (e.g. `public/landing/hero-report-preview.png` → use `/landing/hero-report-preview.png` in `src`).
