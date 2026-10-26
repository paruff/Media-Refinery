---
version: alpha
name: Media Refinery Console
description: Calm, dense operations console for reviewing and approving media normalization plans.
colors:
  primary: "#1F5FAD"
  primary-hover: "#174C8C"
  on-primary: "#FFFFFF"
  secondary: "#5B6472"
  neutral: "#F6F7F9"
  surface: "#FFFFFF"
  surface-sunken: "#EEF0F3"
  on-surface: "#1B1F24"
  on-surface-muted: "#4E5662"
  border: "#D5D9E0"
  success: "#1E7A46"
  warning: "#8A5A00"
  error: "#B42318"
  on-status: "#FFFFFF"
  music: "#6B3FA0"
  audiobook: "#8A4B12"
  video: "#1F5FAD"
  ebook: "#0F6E6E"
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.3
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.35
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0.02em
  mono-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
rounded:
  none: 0px
  sm: 4px
  md: 6px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  sidebar: 224px
  content-max: 1280px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 8px
    height: 32px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 8px
    height: 32px
  button-danger:
    backgroundColor: "{colors.error}"
    textColor: "{colors.on-status}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 8px
    height: 32px
  chip-state:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 4px
  chip-error:
    backgroundColor: "{colors.error}"
    textColor: "{colors.on-status}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 4px
  table-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-sm}"
    height: 40px
  diff-panel:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.on-surface}"
    typography: "{typography.mono-md}"
    rounded: "{rounded.md}"
    padding: 16px
  input-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.sm}"
    padding: 8px
    height: 32px
  page:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.on-surface}"
  table-cell-meta:
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.body-sm}"
  divider:
    backgroundColor: "{colors.border}"
    height: 1px
  chip-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.on-status}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 4px
  chip-warning:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.on-status}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 4px
  row-edge-music:
    backgroundColor: "{colors.music}"
    width: 3px
  row-edge-audiobook:
    backgroundColor: "{colors.audiobook}"
    width: 3px
  row-edge-video:
    backgroundColor: "{colors.video}"
    width: 3px
  row-edge-ebook:
    backgroundColor: "{colors.ebook}"
    width: 3px
---

# Media Refinery Console

## Overview

A self-hosted operations console used by one technical owner (and occasionally a
household member) to watch the refinery queue and approve normalization plans before
files are published to Plex/Jellyfin, Music Assistant, Audiobookshelf and Calibre.

The feel is **calm, precise and dense** — closer to a well-made admin tool than a media
app. The media servers are where artwork shines; here the job is judging a plan quickly
and safely. Information density beats decoration: tables, diffs and status chips carry
the interface. Nothing destructive happens without an explicit, clearly labelled action.

Primary task: the **Review** screen — see a before→after diff (path, container, codecs,
tags, cover) and approve or reject it, singly or in bulk.

## Colors

A neutral, cool-grey foundation with one blue accent for action, plus status and
media-type hues used only as small signals (chips, row edges), never as large fills.

- **Primary (#1F5FAD):** Refinery Blue — the only colour for primary actions (Approve,
  Run) and focus rings.
- **Secondary (#5B6472):** Slate — secondary text, icons, inactive navigation.
- **Neutral (#F6F7F9):** Page background; **Surface (#FFFFFF)** for cards and tables;
  **Surface-sunken (#EEF0F3)** for diffs, code and chips.
- **On-surface (#1B1F24)** body text; **On-surface-muted (#4E5662)** metadata.
- **Status:** Success green (#1E7A46) validated, Warning amber (#8A5A00) needs review,
  Error red (#B42318) failed/quarantined. All meet 4.5:1 against white.
- **Media types:** Music violet (#6B3FA0), Audiobook umber (#8A4B12), Video blue
  (#1F5FAD), Ebook teal (#0F6E6E) — only as a 3px left row edge or chip.

## Typography

**Inter** for all interface text, **JetBrains Mono** for paths, codecs, hashes, ffmpeg
arguments and log lines — anything a user might copy or compare character by character.

- **Headlines:** Inter Semi-Bold, 24px page titles, 18px section titles.
- **Body:** Inter Regular 14px; tables use 13px for density.
- **Labels:** Inter Semi-Bold 12px with slight tracking for chips, column headers and
  buttons. Sentence case, not all-caps.
- **Mono:** 13px for diff panels and logs; long paths wrap at `/`, never truncate silently.

## Layout

Fixed left sidebar (224px) with the five views: Queue, Review, Quarantine, Summary,
plus Item detail reached from any row. Content area fluid up to 1280px.

An 8px spacing scale with a 4px half-step. Tables are the main layout primitive; the
Review screen is a two-column before/after diff above an action bar that stays visible.
At widths under 768px the sidebar collapses to a top bar and diffs stack vertically.

## Elevation & Depth

Flat. Hierarchy comes from tonal layers (neutral page → white surface → sunken diff) and
1px `border` (#D5D9E0) dividers, not shadows. The only shadow is on the sticky action
bar and modal confirmation dialogs, to show they float above scrolling content.

## Shapes

Restrained: 4px radius on buttons and inputs, 6px on panels and cards, fully rounded
chips. No mixed radii within one component.

## Components

- **Buttons:** Primary (Approve/Run) filled Refinery Blue; Secondary white with border;
  Danger filled red, used only for Reject-and-quarantine and Purge. 32px tall. One primary
  button per view.
- **State chips:** pill chips for pipeline state (`pending`, `planned`, `validated`,
  `error`…); colour only reinforces the text label, never replaces it.
- **Tables:** 40px rows, sticky header, sortable columns, row checkbox for bulk actions,
  media-type colour as a 3px left edge.
- **Diff panel:** sunken mono block, before on the left, after on the right; changed
  values highlighted with a background tint plus a `→` marker (not colour alone).
- **Verification list:** each check as a row with ✓/✗ icon + text result + measured value
  (e.g. `VMAF 95.2 ≥ 93`).
- **Input fields:** 32px, 1px border, 2px primary focus ring.
- **Confirm dialog:** required for destructive or bulk actions; restates the count and
  the effect ("Approve 24 items → publish to Music").

## Do's and Don'ts

- Do keep one primary action per screen; Approve is the hero on Review.
- Do pair every status colour with an icon or text label (colour-blind safe).
- Do show full paths in mono; let them wrap instead of truncating.
- Do maintain WCAG AA: 4.5:1 for text, visible 2px focus ring on all interactive elements,
  full keyboard operation (j/k to move, a to approve, r to reject on Review).
- Don't use media artwork as decoration or background — covers appear only in the diff
  as the thing being reviewed.
- Don't use large coloured fills or gradients; status hues stay small.
- Don't hide destructive actions behind hover-only controls.
- Don't auto-refresh a list the user is selecting in; show a "new items" notice instead.
