---
name: minimal-design
description: Design direction for this project's frontend. Use whenever building, restyling, or refactoring any UI (pages, components, layouts, CSS/Tailwind). Enforces a modern, sleek, Vercel/Geist-style minimal look with very restrained effects and motion.
---

# Vercel-style minimal design direction

## Priority

The `frontend-design` skill has HIGHER priority. Follow its process and quality
bar. This skill only fixes the aesthetic direction it should pursue:
"refined minimalism, Vercel/Geist style". Where the two conflict, frontend-design
wins, but still choose this direction rather than a bold/maximalist one.

## Principles

1. Content first. Hierarchy comes from type size, weight, spacing, and
   contrast, not from decoration.
2. Neutral palette, one accent at most. Color is for state (success/error/link),
   not decoration.
3. 1px borders define structure. Avoid heavy shadows.
4. Generous whitespace, consistent 4/8px spacing scale.
5. Almost no motion. If in doubt, don't animate.

## Tokens (define as CSS variables, support light + dark)

- Font: Geist Sans for UI, Geist Mono for code/numbers/IDs
  (fallback: system-ui stack). No decorative or display fonts.
- Light: background #ffffff, subtle surface #fafafa, border #eaeaea,
  text #171717, muted text #666666
- Dark: background #000000, surface #0a0a0a, border #333333,
  text #ededed, muted text #a1a1a1
- Accent: a single blue (#0070f3) for links/focus/primary highlights only
- Radius: 6px for inputs/buttons, 8-12px for cards/modals. Never fully
  pill-shaped unless it's a badge.
- Type scale: 12 / 14 / 16 / 20 / 24 / 32 / 48. Body 14-16px.
  Headings: weight 600, tight letter-spacing (-0.02em), no all-caps.
- Shadows: none by default. At most one very soft shadow
  (0 1px 2px rgba(0,0,0,0.05)) on floating elements (menus, modals).

## Components

- Buttons: primary = solid foreground color (black on light, white on dark),
  inverse text. Secondary = transparent with 1px border. Height 32-40px.
  No gradients, no glow.
- Inputs: 1px border, same radius as buttons, visible focus ring
  (2px, accent or foreground color). Never remove focus outlines.
- Cards: surface background + 1px border. Hover: border color change only.
- Navigation: simple, flat, sticky top bar with a 1px bottom border.
  Optional subtle backdrop blur only on the sticky header.
- Tables/lists: hairline dividers, no zebra striping, no heavy row cards.
- Badges/status: small, subtle tinted background, 12px text.
- Icons: one consistent outline set (lucide), 16-20px, 1.5px stroke.

## Motion (strict budget)

- Allowed: 100-150ms ease transitions on color, background, border-color,
  opacity. Optional gentle fade-in (<=200ms) for modals/menus.
- Forbidden: parallax, scroll-triggered animations, bouncing/spring effects,
  animated gradients, glow, floating/pulsing elements, large staggered reveals,
  custom cursors.
- Respect `prefers-reduced-motion`.

## Never

- Gradients as backgrounds, glassmorphism, neon glows, colored shadows
- Emoji as UI icons, decorative illustrations
- More than one accent color
- Inconsistent radii, spacing, or border colors across components

## Refactor workflow

1. Audit: list current colors, fonts, radii, shadows, and animations in use.
2. Create/replace global tokens (CSS variables or Tailwind theme) with the
   values above. Do this first, in one place.
3. Refactor shared primitives (Button, Input, Card, Nav, Badge) before pages.
4. Update pages to use primitives and tokens; delete hard-coded one-off styles.
5. Remove excess animations/effects per the Motion section.
6. Check light and dark mode, focus states, responsive layout, and contrast.
7. Summarize what changed. Do not change logic, routes, or data fetching.

## Final checklist

- [ ] All colors/spacing/radii come from tokens, none hard-coded
- [ ] Only one accent color, used sparingly
- [ ] Borders instead of shadows for structure
- [ ] Motion limited to short color/opacity transitions
- [ ] Looks clean in both light and dark mode
