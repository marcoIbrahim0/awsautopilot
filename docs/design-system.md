# Design system – locked base theme (dark-first)

**Lock the base theme:** black + one blue (#0A71FF) as foundation. Everything else is supportive. No freestyle.

---

## 1. Core palette

| Role | Hex | Notes |
|------|-----|--------|
| **Background** | `#000000` | Main app background |
| **Section cards / panels** | `#0B0B0B` or `#111111` | Depth without new colors |
| **Dividers** | `#1A1A1A` | Borders / dividers |
| **Text (primary)** | `#FFFFFF` | Headings, primary text |
| **Text (muted)** | `#B3B3B3` | Secondary, body-like |
| **Primary brand blue** | `#0A71FF` | **Only** for CTAs, links, active nav, key highlights |

---

## 2. Use #0A71FF only for

- Primary CTA buttons  
- Links  
- Active states (current nav item)  
- Key highlights (icons, accents)  

Everything else stays neutral.

---

## 3. Button system

**Primary button**

- Background: `#0A71FF`
- Text: `#FFFFFF`
- Hover: `#085ACC`
- Active: `#053577`

**Secondary button**

- Background: transparent
- Border: `1px solid #0A71FF`
- Text: `#0A71FF`
- Hover bg: `rgba(10,113,255,0.08)`

---

## 4. Sections & layout

- Main background: `#000000`
- Section cards / panels: `#0B0B0B` or `#111111`
- Dividers: `#1A1A1A`

---

## 5. Typography

- **Headings:** white
- **Body text:** slightly muted white `rgba(255,255,255,0.85)` or `#B3B3B3`
- **Links inline:** blue, no underline until hover
- Avoid blue headings unless it’s a CTA.

---

## 6. Optional gradient

Use once or twice max (e.g. hero, pricing CTA):

```css
background: linear-gradient(135deg, #0A71FF 0%, #0F2E9B 100%);
```

---

## 7. Accessibility

- White on black ✅ excellent
- Blue #0A71FF on black ✅ good
- Blue text on white ❌ avoid (use darker blue if needed)
- Palette is **dark-first**. If you add light sections, confirm first.

---

## 8. What NOT to do

- ❌ Don’t introduce random blues
- ❌ Don’t use gradients everywhere
- ❌ Don’t color long paragraphs blue
- ❌ Don’t mix gray-blue text (kills contrast)

---

## CSS variables (`.dark` theme in `frontend/src/app/globals.css`)

```css
.dark {
  --bg: #000000;
  --surface: #0B0B0B;
  --surface-alt: #111111;
  --border: #1A1A1A;
  --text: #FFFFFF;
  --text-muted: #B3B3B3;
  --text-body: rgba(255,255,255,0.85);
  --accent: #0A71FF;
  --accent-hover: #085ACC;
  --accent-active: #053577;
  --focus-ring: #0A71FF;
  --primary-btn-bg: #0A71FF;
  --primary-btn-hover: #085ACC;
  --primary-btn-active: #053577;
  --secondary-btn-hover-bg: rgba(10,113,255,0.08);
}
```

Component rules: Primary button uses `--primary-btn-*`; secondary uses transparent + border accent + `--secondary-btn-hover-bg`. Cards/panels use `--surface` or `--surface-alt`.
