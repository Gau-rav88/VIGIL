# FRONTEND — Project VIGIL
### Full UI/UX design specification and implementation guide

| Field | Value |
|---|---|
| Document version | 1.0.0 |
| Companions | `PRD.md` (FR-UI-*), `ARCHITECTURE.md` (API §8, tree §10), `FLOW.md` (what each screen reacts to) |
| Stack | Next.js 14 (App Router), TypeScript 5, Tailwind CSS 3.4, Recharts 2, Cytoscape.js 3 (+ fcose), TanStack Query 5, TanStack Table 8, Zustand 4 |
| Supersedes | The `frontend/` subtree in `ARCHITECTURE.md` §10 (this document extends it; §16 lists the final tree) |

> **Instructions to the code generator.** (1) Implement tokens (§3) first, then the shell (§5), then pages in the order of §18. (2) Do not substitute fonts, palette values, radii, or component behavior without a written reason. (3) Copy strings come from `src/lib/copy.ts` (§15); never inline UI text in components. (4) Every interactive component needs a visible keyboard focus state and an accessible name. (5) Pages that need data not yet in `ARCHITECTURE.md` §8 use the **backend additions** in §12.4; implement those API routes too.

---

## 1. Design Brief

**Subject.** VIGIL is a forensic workbench. Its users decide whether a pattern of trades and chat messages is market manipulation, and their conclusions may end up in front of a judge.

**Audiences and their primary jobs**

| Audience | Primary job on screen | Session shape |
|---|---|---|
| Forensic investigator | Understand *why* a case was flagged, test the attribution, and challenge it | Long, focused, desktop, two monitors |
| Compliance officer | Judge a finished dossier and sign off | Short, reading-heavy, desktop and tablet, sometimes phone |
| Surveillance desk operator | Watch the market for emerging risk | All day, wall display or second screen |
| Counsel / court clerk | Verify a bundle independently | One-off, any browser |

**What the interface must make obvious**
1. *Is this real?* Evidence and its integrity are always one glance away.
2. *How sure are we?* Confidence is shown wherever a conclusion is shown.
3. *What came first?* Time order of social triggers and market moves is the spine of the product.
4. *What is a finding and what is only a lead?* The UI never lets an inference pass as a fact.

---

## 2. Design Plan (token system, layout concept, principles)

### 2.1 Direction in one paragraph
A **light-table evidence workbench**. Cool daylight surfaces, graphite ink, hairline structure, and four semantic hues that each mean exactly one thing: *evidence* (marker yellow), *inference* (ultraviolet), *integrity* (verified teal), *danger* (seal red). The one memorable thing is the **Tape**: a shared-time two-track strip where social triggers sit above market volume and a **lag bracket** measures the delay between them, with the portion of volume traced to the ring shaded in ultraviolet. Everything else is quiet and disciplined so the Tape and the evidence markers carry the personality.

### 2.2 Palette (named values)

| Name | Hex | Role |
|---|---|---|
| Lightbox | `#F3F5F6` | App background |
| Graphite | `#1F2B33` | Text, market track, primary controls |
| Evidence tag | `#F2B705` | Numbered evidence markers and citations only |
| Ultraviolet | `#5B3FD4` | Inferred links, ring-attributed volume, focus ring |
| Verified teal | `#0F7B6C` | Signature, ledger, and hash checks that passed |
| Seal red | `#B3261E` | Failed checks, tamper, critical severity, destructive actions |

Supporting values: social-track blue `#2563C9` (data series only), raised surface `#FFFFFF`, sunken surface `#E8ECEE`, hairline `#CBD3D8`, strong hairline `#9AA7AF`, muted ink `#51616B`.
A second theme, **Deep bench** (dark), exists for wall displays (§3.1).

### 2.3 Type
| Role | Family | Use |
|---|---|---|
| Interface and numbers | **Public Sans** (variable, 400 to 700) | All UI, tables, charts, numerals with `tabular-nums` |
| Documents and narrative | **Source Serif 4** (variable) | Dossier body, case summary paragraph, page titles on the dossier and case pages |
| Hashes, IDs, pseudonyms | System monospace stack (not loaded) | Only for strings that must be compared character by character |
| Devanagari social text | **Noto Sans Devanagari** (fallback for message text) | Hinglish and Hindi messages in evidence views |

Why this pair: Public Sans comes from government design work, reads clearly at small sizes in dense tables, and feels institutional without being cold. Source Serif carries the register of a legal document where the reader slows down. The two are clearly different in structure, so the shift from "operating the tool" to "reading the record" is felt.

Scale (base 15 px, ratio about 1.2):

| Token | Size / line | Weight | Used for |
|---|---|---|---|
| `text-xs` | 12 / 16 | 500 | Axis ticks, table meta |
| `text-sm` | 13 / 18 | 400/500 | Table cells, inspector rows |
| `text-base` | 15 / 22 | 400 | Body UI text |
| `text-md` | 18 / 26 | 600 | Panel titles |
| `text-lg` | 22 / 30 | 600 | Page titles (sans pages) |
| `text-xl` | 28 / 36 | 600 serif | Case and dossier titles |
| `text-2xl` | 36 / 42 | 600 serif | Dossier cover only |

Line length: maximum 68 characters for dossier prose (`max-w-[68ch]`), 80 for any other paragraph. Serif body uses line-height 1.65, sans body 1.45.

### 2.4 Shape, depth, and spacing
- Spacing: 4 px base unit (`1=4px`).
- Radii express hierarchy: **2 px** for data cells, inputs, and chips inside tables; **6 px** for panels and drawers; **999 px** for status chips only. Nothing else is rounded.
- Depth: separate surfaces with hairlines and background shade, not shadows. The only shadow in the product is `--shadow-pop` on popovers, menus, and modals.
- Density: tables use 32 px rows by default, 40 px in comfortable mode (user setting).

### 2.5 Layout concept
A left **rail** (navigation), a thin **top bar** (global status), and, inside a case, a **case bar** that stays pinned and tells you where the case is in its life. Content aligns left; numbers align right in tables; the Tape and graph use the full width.

```
┌──────┬──────────────────────────────────────────────────────────────┐
│ VIGIL│ top bar:  search          Live, 120 ms behind    IST | UTC  ⓘ │
│      ├──────────────────────────────────────────────────────────────┤
│ Live │ case bar: ZENITHSME  Awaiting review   confidence 0.87  v1   │
│ Cases│           window 04:20 to 04:37 UTC     [Adjust analysis]    │
│ Ver- ├──────────────────────────────────────────────────────────────┤
│ ify  │                                                              │
│ Sim  │                  page content                                │
│ Admin│                                                              │
└──────┴──────────────────────────────────────────────────────────────┘
```

### 2.6 Principles
1. **Four meanings, four hues.** Yellow is evidence, ultraviolet is inference, teal is integrity, red is danger. No other use of these colors anywhere.
2. **Time is the spine.** Any chart with time shares the same x-axis conventions, crosshair behavior, and event markers as the Tape.
3. **Structure encodes information.** Borders, numbering, and dividers appear only where the content has that structure: stage numbers for the case stepper (a real sequence), evidence numbers for citations (a real index).
4. **Show uncertainty in the same place as the claim.** Every score has its basis one click away. Every inferred link looks different (dashed, ultraviolet) from an observed one (solid, graphite).
5. **Spend boldness once.** The Tape is the bold element; chrome stays plain.
6. **The interface never accuses.** Copy says "linked", "consistent with", "lead"; it never says "guilty", "criminal", or "fraudster".

### 2.7 Review of the plan against the generic defaults (what was changed and why)

| First instinct | Why it was rejected | Final choice |
|---|---|---|
| Near-black surveillance dashboard with a single neon accent | Reads as a generic security-tool look and tires eyes in long reading sessions; the product's credibility comes from being a document-grade record | Light default; dark "Deep bench" only as a wall-display theme, built on a blue-green slate, with four meaningful hues |
| Cream paper background with serif headings and clay accent | Another default look, and warm cream tints charts and evidence yellow | Cool daylight surface; serif only where people read legal prose |
| Grid of identical rounded cards for tickers and cases | Hides ranking and makes every item feel equal | Ranked **watch ladder** (rows with proportional bars) and dense tables |
| Heatmap tiles with gradient washes | Gradient meaning is hard to read and fails color-blind users | MRS drawn as bar length plus a number; three tiers named in text |
| All-caps tracked labels above every section, mono micro-labels, middle-dot meta strings, arrows on links | Template chrome that adds noise | Sentence-case headings, no eyebrow labels, meta shown as short sentences, links are plain underlined text |
| Fade-and-slide entrance on every section | Decorative motion | One orchestrated moment: the lag bracket drawing on first view of a case. Everything else moves only in response to a click or an incoming alert |
| Pie or donut for "illicit share of volume" | Poor comparison | Stacked volume bars in the Tape, ring share in ultraviolet |

---

## 3. Design Tokens (implementation)

### 3.1 `src/styles/tokens.css`

```css
:root {
  /* surfaces */
  --bg-base:#F3F5F6; --bg-raised:#FFFFFF; --bg-sunken:#E8ECEE;
  /* ink */
  --ink:#1F2B33; --ink-muted:#51616B; --ink-faint:#6C7B85;           /* faint: large or decorative only */
  /* structure */
  --line:#CBD3D8; --line-strong:#9AA7AF;
  /* meaning */
  --tag:#F2B705;  --tag-ink:#3D2E00;  --tag-wash:#FFF4CC;
  --uv:#5B3FD4;   --uv-wash:#ECE8FB;
  --verified:#0F7B6C; --verified-wash:#E2F3F0;
  --seal:#B3261E; --seal-wash:#FBE9E7;
  /* data series */
  --social:#2563C9; --market:#1F2B33; --price:#51616B;
  /* focus */
  --focus:#5B3FD4;
  /* shape */
  --r-cell:2px; --r-panel:6px; --r-chip:999px;
  /* depth */
  --shadow-pop:0 8px 24px rgba(20,35,44,.18);
  /* rhythm */
  --rail-w:216px; --rail-w-collapsed:56px; --topbar-h:48px; --casebar-h:56px;
  --row-h:32px;
}
:root[data-density="comfortable"] { --row-h:40px; }

/* Deep bench: wall display theme, built on blue-green slate */
:root[data-theme="floor"] {
  --bg-base:#14232C; --bg-raised:#1B2E39; --bg-sunken:#0F1B22;
  --ink:#E6ECEF; --ink-muted:#A3B3BC; --ink-faint:#7F919B;
  --line:#2F4654; --line-strong:#4A6677;
  --tag:#F2B705; --tag-ink:#1F1700; --tag-wash:#3A3210;
  --uv:#A593FF; --uv-wash:#2A2550;
  --verified:#4FD1B8; --verified-wash:#143B38;
  --seal:#FF8A80; --seal-wash:#44211F;
  --social:#7FB0FF; --market:#E6ECEF; --price:#A3B3BC;
  --focus:#F2B705;
  --shadow-pop:0 8px 24px rgba(0,0,0,.45);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration:.001ms !important; animation-iteration-count:1 !important; transition-duration:.001ms !important; scroll-behavior:auto !important; }
}
:focus-visible { outline:2px solid var(--focus); outline-offset:2px; border-radius:var(--r-cell); }
body { background:var(--bg-base); color:var(--ink); font-family:var(--font-sans); font-size:15px; line-height:1.45; font-variant-numeric:tabular-nums; }
.doc-prose { font-family:var(--font-serif); line-height:1.65; max-width:68ch; }
.hash { font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:12.5px; letter-spacing:0; word-break:break-all; }
```

Contrast notes (verified against WCAG 2.2 AA for normal text on `--bg-raised`): Graphite 14.6:1, muted ink 6.6:1, ultraviolet 6.9:1, verified teal 5.4:1, seal red 6.8:1. `--ink-faint` (about 4.6:1 on raised) is for non-essential text only. Evidence tag yellow is **only** used as a fill with `--tag-ink` text (10.7:1).

### 3.2 `tailwind.config.ts`

```ts
import type { Config } from "tailwindcss";
const v = (n: string) => `var(--${n})`;
export default {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="floor"]'],
  theme: {
    extend: {
      colors: {
        bg: { base: v("bg-base"), raised: v("bg-raised"), sunken: v("bg-sunken") },
        ink: { DEFAULT: v("ink"), muted: v("ink-muted"), faint: v("ink-faint") },
        line: { DEFAULT: v("line"), strong: v("line-strong") },
        tag: { DEFAULT: v("tag"), ink: v("tag-ink"), wash: v("tag-wash") },
        uv: { DEFAULT: v("uv"), wash: v("uv-wash") },
        verified: { DEFAULT: v("verified"), wash: v("verified-wash") },
        seal: { DEFAULT: v("seal"), wash: v("seal-wash") },
        social: v("social"), market: v("market"),
      },
      borderRadius: { cell: v("r-cell"), panel: v("r-panel"), chip: v("r-chip") },
      boxShadow: { pop: v("shadow-pop") },
      fontFamily: { sans: ["var(--font-sans)", "system-ui", "sans-serif"], serif: ["var(--font-serif)", "Georgia", "serif"] },
      fontSize: {
        xs: ["12px", "16px"], sm: ["13px", "18px"], base: ["15px", "22px"],
        md: ["18px", "26px"], lg: ["22px", "30px"], xl: ["28px", "36px"], "2xl": ["36px", "42px"],
      },
      spacing: { rail: v("rail-w"), "rail-c": v("rail-w-collapsed"), topbar: v("topbar-h"), casebar: v("casebar-h"), row: v("row-h") },
      maxWidth: { prose: "68ch" },
    },
  },
  plugins: [],
} satisfies Config;
```

### 3.3 Fonts (`src/app/layout.tsx`)

```tsx
import { Public_Sans, Source_Serif_4, Noto_Sans_Devanagari } from "next/font/google";
import "@/styles/tokens.css"; import "./globals.css";
const sans  = Public_Sans({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], variable: "--font-serif", display: "swap", axes: ["opsz"] });
const deva  = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--font-deva", display: "swap" });
export const metadata = { title: "VIGIL", description: "Market manipulation investigation workbench" };
export default function Root({ children }: { children: React.ReactNode }) {
  return (<html lang="en" className={`${sans.variable} ${serif.variable} ${deva.variable}`}>
    <body><a href="#main" className="sr-only focus:not-sr-only">Skip to content</a>{children}</body></html>);
}
```
Social message text uses `font-family: var(--font-sans), var(--font-deva)` so Hinglish renders with correct glyphs.

### 3.4 Semantic styling rules (binding)

| Meaning | Color | Never also use for |
|---|---|---|
| Evidence reference or citation | `--tag` fill, `--tag-ink` text | Warnings, highlights |
| Inferred or probabilistic link, ring-attributed share | `--uv` | Selection, branding |
| Integrity passed (hash, Merkle, ledger, signature) | `--verified` | Generic success toasts |
| Failed check, tamper, critical severity, destructive confirm | `--seal` | Emphasis, errors that are not integrity or severity |
| Social series | `--social` | Anything outside chart series |

Severity (anomaly) is communicated by **text label and shape**, with color as a third channel: Low (hollow circle), Medium (filled circle), High (filled triangle), Critical (filled triangle with seal-red outline and the word "Critical").

---

## 4. Brand mark and tone

- **Wordmark:** "VIGIL" in Public Sans 700, letter-spacing 0.02em, with a small bracket glyph before it (an open horizontal bracket `⎴` drawn as inline SVG, 14 px, `--ink`), echoing the lag bracket. Collapsed rail shows only the glyph.
- **Voice:** plain, precise, neutral. Sentence case everywhere. Active verbs. Errors state what happened and what to do. Never apologetic, never accusatory (§15).

---

## 5. App Shell and Navigation

### 5.1 Components
| Component | Spec |
|---|---|
| `AppShell` | CSS grid: `grid-template-columns: var(--rail-w) 1fr`, rail collapsible to `--rail-w-collapsed` (persisted in `localStorage` under `vigil.rail`) |
| `Rail` | Items (icon + label): Live, Cases, Verify, Simulator (dev only), Admin (admin only). Active item has a 2 px left bar in `--ink` and bold label. Icons: `lucide-react` 18 px, stroke 1.75 |
| `TopBar` | Height `--topbar-h`. Left: global search (`/` focuses). Center-right: connection status. Right: timezone switch (`Exchange time` or `UTC`), theme toggle (`Standard` or `Deep bench`), density toggle, user menu |
| `ConnectionStatus` | Live: "Live, {lag} ms behind" with a filled circle in `--verified`; degraded: "Behind by {n} s" (hollow circle); offline: "Reconnecting in {n} s" (seal red outline). Text always present |
| `CaseBar` | Only under `/cases/[caseId]/*`. Pinned below the top bar. Contents in §5.2 |
| `Toaster` | Bottom-right, max 3, 5 s, never covers the case bar. Uses same verbs as the triggering action (§15) |
| `Drawer` | Right-side, 480 px, used for evidence viewing; closes with `Esc` |

### 5.2 Case bar contents
```
ZENITHSME  NSE SME      [ Awaiting review ]     Confidence 0.87   Completeness 100%    Dossier v1  ✓ Verified
Window 04:20 to 04:37 UTC (IST 09:50 to 10:07)      ① Detect ─ ② Align ─ ③ Attribute ─ ④ Assess ─ ⑤ Draft and sign ─ ⑥ Review
                                                    [Adjust analysis ▾]   [Open dossier]
```
The six-step stepper is a real sequence (numbers are justified). It maps backend stages to user language:

| Step | Backend stages |
|---|---|
| 1 Detect | `OPENED` |
| 2 Align | `ENRICHING`, `ALIGNED` |
| 3 Attribute | `ATTRIBUTING` |
| 4 Assess | `ASSESSING` |
| 5 Draft and sign | `DRAFTING`, `VALIDATING`, `SIGNING` |
| 6 Review | `PENDING_REVIEW`, `APPROVED`, `PUBLISHED`, `REJECTED`, `REWORK` |

Terminal non-linear states (`WATCHLIST`, `CLOSED_NO_ACTION`, `FAILED`) replace the stepper with a one-line explanation and the relevant action.

Flags from the backend appear as inline notices under the bar, never as hidden badges: `PARTIAL_ATTRIBUTION`, `ATTRIBUTION_SQL_ONLY`, `MISSING_MARKET_SLICE`, `MISSING_SOCIAL_SLICE`, `LLM_UNAVAILABLE`, `NEW_EVIDENCE_AVAILABLE` (see §6.3).

### 5.3 Role gating (UI)

| Capability | investigator | compliance_officer | admin | auditor_readonly |
|---|---|---|---|---|
| View live, cases, graph, dossier | yes | yes | yes | yes |
| Adjust analysis (directives), mark links | yes | yes | no | no |
| Submit for review | yes | no | no | no |
| Approve, rework, reject | no | yes | no | no |
| Reveal an account | no | yes | no | no |
| Download evidence and bundle | evidence only | both | both | no |
| Simulator, admin health, ledger verify | no | no | yes | ledger verify only |

Controls a role cannot use are **not rendered** (not merely disabled), except where seeing a disabled control teaches the workflow (the review panel for investigators shows read-only text: "Compliance officers decide on this dossier").

---

## 6. Screens

All wireframes are ASCII. `[ ]` is a button, `( )` a radio, `▾` a menu, `░` a bar, `▲` evidence/anomaly markers.

### 6.1 `/live` — Watch floor
**Job:** see which tickers are heating up and whether a case already exists.
**Data:** WebSocket topics `heatmap`, `anomalies`, `cases`; `GET /symbols/heatmap` on first paint; `GET /symbols/{symbol}/series` for the selected ticker.

```
┌ Watch ladder (ranked by risk) ─────────────┐ ┌ ZENITHSME ─────────────────────────────────┐ ┌ Alerts ──────────────────┐
│ Ticker       Risk                Hype  Vol z│ │ Mini tape, last 60 minutes                │ │ 04:32:56  Case opened    │
│ ZENITHSME    ░░░░░░░░░░░░░░░ 86   88    9.7 │ │  hype ╱‾╲   ▲ burst                       │ │   ZENITHSME, aligned     │
│  Case open ▸ Awaiting review                │ │  vol  ▁▁▁▁▂▅█████                         │ │ 04:32:45  Volume spike   │
│ NOVAPHARMA   ░░░░░░░░░░ 54      61    3.1   │ │  <──149 s──>                              │ │   ZENITHSME, high        │
│ KAVERISOFT   ░░░░░ 33           22    1.2   │ │ Hype 88   Volume z 9.7   Spread 2.3×      │ │ 04:30:47  Hype burst     │
│ …                                           │ │ [Open case]                               │ │   3 channels, score 81   │
└─────────────────────────────────────────────┘ └────────────────────────────────────────────┘ └──────────────────────────┘
```
- **Watch ladder row:** ticker (semibold), proportional risk bar (length = MRS, fill graphite below 40, a tag-yellow outline between 40 and 70, seal red at 70 or more; the tier is also stated in the row's accessible name: "Risk 86, high"), MRS number, hype, volume z. Rows reorder at most every 5 s with a 150 ms position transition (response to data, only when order changes); the selected row keeps its position until you deselect.
- If a case exists: second line "Case open, {stage label}" as a text link.
- **Mini tape:** the Tape component (§7) in compact mode (single column, no brush).
- **Alert feed:** newest first, 200 max, each item is a link to the anomaly or case. New items flash `--tag-wash` for 600 ms (attention to real incoming information). `aria-live="polite"`, rate-limited to one announcement per 5 s ("3 new alerts").
- **Deep bench mode:** hides the mini tape panel, enlarges ladder type to `text-md`, and runs full-bleed for wall displays. Toggle in the top bar or press `f`.
- **States:** loading (skeleton rows, 8), empty ("No tickers are being tracked. Start a scenario in Simulator or connect a market feed."), degraded feed (banner "Market feed is behind by {n} s. Scores may be late.").

### 6.2 `/cases` — Case queue
**Job:** find the case that needs you.
**Data:** `GET /cases?status&symbol&min_mrs&limit&cursor`.

```
Saved views:  (•) Awaiting review   ( ) Needs rework   ( ) Open   ( ) Watching   ( ) All     Search ticker…   Min risk [  ]

Ticker      Status             Risk  Confidence  Complete  Window               Opened       Notices
ZENITHSME   Awaiting review     86     0.87       100%     04:20–04:37 UTC       10 min ago   New activity
NOVAPHARMA  Tracing accounts    54     —           —       09:12–09:40 IST       2 min ago
…
```
- TanStack Table with server pagination (cursor), sortable columns, sticky header, row height `--row-h`.
- Row emphasis: rows in the active saved view's "needs you" state are semibold; no zebra stripes.
- Status is a chip with text (never color only). `Awaiting review` chip: `--tag-wash` fill, `--tag-ink` text is **not** allowed (yellow is reserved for evidence); use neutral `--bg-sunken` fill with ink text and a leading small stage glyph. Integrity or danger states use teal or seal outlines only when they refer to integrity or danger (for example `Failed`).
- Keyboard: `j`/`k` move, `Enter` open, `x` select, `/` filter focus.
- **Empty:** "No cases match these filters. Clear filters or widen the risk threshold."

### 6.3 `/cases/[caseId]` — Case workbench (the main screen)
**Job:** understand the case in one screen, then dig.
**Data:** `GET /cases/{id}`, `GET /cases/{id}/series` (§12.4), `GET /cases/{id}/timeline`, `GET /cases/{id}/evidence`, WebSocket `cases` filtered by id.

```
[ case bar ]
[ new-activity notice, if any:  New activity since version 1.  [Regenerate dossier] ]
┌ Summary (serif) ─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Chatter led trading by 149 seconds. Accounts linked to one ring made 45% of volume while price rose 38%.   ¹ ²  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ Tape ────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Social   hype ▁▁▂▅██▇▅▃▂   ┃ call-to-action stems                                                             │
│ ─ lag ──────────┣━━━━━━━ 149 s (p 0.002) ━━━━━━━┫───────────────────────────────────────────────────────────  │
│ Market   volume ▁▁▁▁▁▁▃▆██▇▆▄    ░ ring share (violet)  ─ price                                              │
│ Evidence ①    ②         ③       ④                                         [View as table]  [Zoom ▾]         │
│ 04:25         04:30       04:35      04:40      04:45                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ What the system found ─────────────┐ ┌ Accounts ─────────────────────────┐ ┌ Evidence ──────────────────────┐
│ Social                             │ │ Ring 1  ring score 0.93           │ │ ① Trade slice      f10c22a9…   │
│  Hype burst  high  04:30:47        │ │  19 accounts, 3 brokers, 5 devices│ │ ② Social slice     7bd3e1c0…   │
│  3 near-duplicate campaigns        │ │ Top accounts by volume            │ │ ③ Graph export     3a91c0e7…   │
│ Market                             │ │  Zx9f…  8.1%  BRK-07              │ │ ④ Timeline chart   a07cd2f4…   │
│  Volume spike  high  04:32:45      │ │  Aq2m…  7.4%  BRK-07              │ │ [View in drawer]               │
│  Wash cycle ×6 (2 to 4 accounts)   │ │ Leads (not findings)  1 ▾         │ │                                │
│ Graph                              │ │ [Open graph]                      │ │                                │
│  Ring detected, 19 of 20 linked    │ │                                   │ │                                │
└────────────────────────────────────┘ └───────────────────────────────────┘ └────────────────────────────────┘
```
- **Summary** is a one-paragraph generated sentence from deterministic template with numbered evidence tags (clickable). It is not LLM-only text (FLOW invariant 6).
- **Adjust analysis** menu (investigator or compliance): "Widen window to ±2 h", "Exclude an account…", "Re-run attribution". Each opens a small confirm popover stating its effect ("Attribution re-runs and creates a new dossier version. The current version stays available.").
- **New activity notice** appears when flag `NEW_EVIDENCE_AVAILABLE` is set. Action label: **Regenerate dossier** (posts directive `FORCE_REATTRIBUTION` with `params.window_end=now`); success toast "Regenerating dossier"; when done "Dossier v2 ready".
- **Evidence list** is the index for all numbered tags in the page; selecting an item opens the evidence drawer.
- **Evidence drawer** (480 px): for slices shows paged raw rows (virtualized) with the original columns; for social shows original text (Devanagari-safe font), channel, pseudonymous author, `raw_sha256`; always shows full SHA-256 in `.hash` style with a Copy action and the line "Hash computed at capture, recorded in the ledger as entry {id}".
- **Loading:** Tape skeleton with axis only. **Error:** "Couldn't load the timeline. Try again" with Retry button. **Failed case:** the case bar explains the reason and shows "Retry" (admin) or "Contact an administrator".

**The one orchestrated moment.** First time a case opens in a session, the lag bracket draws over 900 ms: guides drop at the first coordinated message, the bar extends to the first suspect volume rise, and the label appears. Stored in `sessionStorage` (`vigil.bracket.{caseId}`); never repeats; skipped under reduced motion.

### 6.4 `/cases/[caseId]/graph` — Graph explorer
**Job:** test the attribution; challenge any link.
**Data:** `GET /cases/{id}/graph?max_nodes=500&min_conf=0.6`; `POST /cases/{id}/links/feedback`.

```
┌ Filters ──────────────┐ ┌ Canvas ─────────────────────────────────────────────────┐ ┌ Inspector ─────────────────┐
│ Link confidence 0.60  │ │                                                          │ │ Link: Zx9f… to Aq2m…       │
│ ──●───────            │ │        ○──○        ⬡ BRK-07                              │ │ Confidence 0.96  (inferred)│
│ Show                  │ │      ○╌╌╌○╌╌○     ▭ device Dv3a…                         │ │ Basis                      │
│ [x] Trades            │ │        ○◄━━○◄━━○  (cycle in red)                         │ │  Shared device    0.90 × 1 │
│ [x] Inferred links    │ │                                                          │ │  Circular cycle   0.85 × 1 │
│ [x] Brokers           │ │  Zoom + − fit   Layout ▾   Trace cycle ▸                 │ │  Synchronized     0.70 × .9│
│ [ ] Devices           │ │                                                          │ │ Combined 1−Π(1−w·s) = 0.96 │
│ [ ] Channels          │ │                                                          │ │ Evidence ② ③               │
│ Cycles (6)            │ └──────────────────────────────────────────────────────────┘ │ [Mark as false positive]   │
│  4 accounts, 1,000 sh │ [View as table]                                              │ [Confirm link]             │
│  …                    │                                                              │                            │
└───────────────────────┘                                                              └────────────────────────────┘
```
- **Visual encoding** (full stylesheet in §9): Trader = circle sized by log volume; Broker = hexagon; Device = rounded rectangle; Network fingerprint = tag shape; Channel = diamond; Handle = triangle; Entity = dashed compound container around its traders.
- **Edges:** observed trade = solid graphite with arrowhead (direction of share flow), width by log quantity; inferred link = **dashed ultraviolet**, width by confidence, label shows confidence on hover or select; cycle edges = seal-red, 3 px, only while cycle is highlighted; device/broker/channel edges = thin, `--ink-faint`.
- **Cluster color** for entity fills uses a color-blind-safe set (Okabe-Ito subset `#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00`) at 18 % opacity so ultraviolet links remain visible on top. (This is categorical identity, not a semantic hue.)
- **Interactions:** click selects; double-click expands neighbors; box select; `Trace cycle` (user-triggered) animates the path over 1.2 s; layout menu: `Clusters` (fcose, default), `Brokers` (concentric), `Time` (x by first trade).
- **Link feedback flow:** "Mark as false positive" opens a popover: comment (optional), button **Mark as false positive**. On success: toast "Link marked as false positive"; edge shows struck style (dotted, `--ink-faint`), the entity and ring score refresh from the server (`ATTRIBUTION_DONE` event). "Confirm link" works the same with toast "Link confirmed". Both are reversible by repeating with the other action (the original record stays in the audit trail).
- **Accessible alternative:** `View as table` shows nodes and edges in two tables (same filters), with row actions mirroring the inspector. The canvas has `role="img"` plus an `aria-label` summary, and nodes are reachable by `Tab` (focus proxy list) with arrow keys moving between neighbors.
- **Performance:** at 500 nodes, hide labels below zoom 0.6, `textureOnViewport: true`, `hideEdgesOnViewport: true` while panning, `pixelRatio: 1.5` on low-power devices. Target ≥ 30 fps (AC-UI-02).
- **Empty:** "No linked accounts at this confidence. Lower the threshold to see weaker links."
- **Offline fallback:** when the API flags `ATTRIBUTION_SQL_ONLY`, banner: "Graph store is offline. Showing links found from trade records only; devices and brokers are unavailable."

### 6.5 `/cases/[caseId]/timeline` — Chronology
A vertical, two-lane list (left lane Social, right lane Market, center spine times) for reading a case as a story or exporting it. Each entry: time, one sentence, numbered evidence tags. Filters: lane, severity, text search. Uses the same data as the dossier timeline. Print stylesheet produces a clean A4 page.

### 6.6 `/dossiers/[dossierId]` — Dossier viewer
**Job:** read the record, check its integrity, decide.
**Data:** `GET /dossiers/{id}`, `GET /dossiers/{id}/verify`, `GET /cases/{caseId}/dossiers`, `/pdf`, `/bundle`, `POST /cases/{caseId}/review`.

```
┌ Contents ─────┐ ┌ Document (serif, 68ch) ────────────────────────────┐ ┌ Integrity ─────────────────┐
│ Summary       │ │ Forensic dossier                                    │ │ Version  v1 ▾  (v3 latest) │
│ Timeline      │ │ ZENITHSME, 14 March 2026                            │ │ ✓ Schema valid             │
│ Market        │ │                                                     │ │ ✓ Evidence hashes (14)     │
│ Social        │ │ Summary                                             │ │ ✓ Merkle root              │
│ Attribution   │ │ Chatter in three public channels preceded a surge   │ │ ✓ Ledger chain (37)        │
│ Clauses       │ │ in volume by 149 seconds. Nineteen linked accounts  │ │ ✓ Signature  dev-2026-01   │
│ Confidence    │ │ accounted for 45% of volume. ¹ ²                    │ │ ○ Human review  not yet    │
│ Limitations   │ │                                                     │ │ [Download PDF] [Bundle]    │
│ Evidence      │ │ Timeline … Market … Social … Attribution …          │ │ [Verify again]             │
└───────────────┘ │                                                     │ ├────────────────────────────┤
                  │ Clauses (advisory, legal review required)           │ │ Decision (officers)        │
                  │ …                                                   │ │ ( ) Approve and sign       │
                  │                                                     │ │ ( ) Request rework         │
                  └─────────────────────────────────────────────────────┘ │ ( ) Reject                 │
                                                                          │ Comment [            ]     │
                                                                          │ [Record decision]          │
                                                                          └────────────────────────────┘
```
- **Document column** uses `.doc-prose`. Section titles are serif `text-xl`. The cover (first screen) uses `text-2xl` with the case window and the integrity line "Signed {date} with key {key_id}".
- **Citations** appear as superscript numbered tags (yellow fill, `--tag-ink` number, 2 px radius, min 24 px hit area). Hover or focus: popover with evidence type, short hash, capture time, **Open evidence**. Numbers are assigned in order of first appearance and map to the Evidence section at the end.
- **Attribution section:** ring table (accounts, methods, ring score as number + 5-segment meter, cycle count, volume share). **Leads (not findings)** is a collapsed subsection titled exactly that, with the sentence "These links rely on one weak signal and are not part of the findings."
- **Clauses section** always begins with a bordered note: "These mappings are advisory. Legal review is required before any enforcement use." Each clause lists regime, clause, rationale text, and finding types.
- **Confidence and limitations:** the four component scores as plain rows with value and one-line explanation; limitations as a bulleted list including active flags in plain language ("Parsed in rules-only mode for part of the period").
- **Integrity panel** (sticky): check rows show icon + word + detail; passed rows use teal check, failed rows use seal-red cross with the exact failed check named and an expandable "What this means" text. `Human review` row is hollow until approval, then teal with reviewer and time. If any check fails the entire panel gets a seal-red header "This record failed verification" and the Decision controls are replaced by "Review is blocked until the record verifies."
- **Version selector** lists all versions with created time, reviewer, status. Older versions show a banner "This is an earlier version. Version {n} is current." Published versions are read-only and carry "Published" in the header.
- **Decision panel** (compliance only): the radio options are labeled **Approve and sign**, **Request rework**, **Reject**. Comment is required for rework and reject (min 10 characters, helper text "Say what needs to change" / "Say why this case is closed"). Button label changes to match: **Approve and sign**, **Request rework**, **Reject case**. A confirm dialog states consequences:
  - Approve: "This signs version {n+1} with your name and the current time. Signed versions can't be edited. Later changes create a new version."
  - Rework: "The case returns to analysis. The current dossier stays available."
  - Reject: "The case closes. This can't be undone, and the record stays in the ledger."
  Success toasts reuse the verbs: "Dossier approved and signed", "Rework requested", "Case rejected".
- **Print:** `@media print` shows only the document column, with a footer carrying dossier id, version, digest first 16 characters, and page numbers.
- **Mobile (≤ 640 px):** contents rail becomes a dropdown, integrity panel becomes a sticky bottom summary ("Verified, 6 of 6 checks") that opens a sheet, decision panel becomes a bottom sheet. Officers can review and decide on a phone.

### 6.7 `/entities/[entityId]` — Entity profile
Header: ring score (number + meter), member count, volume share, linked cases. Tables: accounts (pseudonym, broker, device count, role in cycles), brokers and gateways, shared devices and networks (each with the accounts sharing it), reaction behavior (median latency to calls vs random baseline). Actions: **Open in graph**, **Reveal account** (compliance only; opens a confirm dialog "Revealing links this pseudonym to a real account. This action is recorded.").
Data: `GET /entities/{id}` (§12.4).

### 6.8 `/verify` — Independent verifier
**Job:** let anyone check a bundle without trusting VIGIL.

```
Drop a bundle (.zip) here, or [Choose file]            Public key (optional) [Choose file]  (bundle key used if empty)
(•) Check in this browser      ( ) Check on the server

Checks
 ✓ Schema valid
 ✓ Evidence hashes   14 of 14 match
 ✓ Merkle root       c41e…  matches dossier
 ✓ Ledger chain      37 entries, linked
 ✓ Signature         Ed25519, key dev-2026-01
 ✓ Human review      approved by arjun.m, 14 Mar 2026 04:52 UTC
Result: Valid
```
- Browser mode: `jszip`, `@noble/hashes/sha256`, `@noble/ed25519`, `canonicalize` (RFC 8785). Streams large files through hashing in chunks; progress bar per check. Copy under the mode toggle: "Files stay in this browser." (shown only in browser mode).
- Failure display names the exact problem and file: "Evidence file `EV-TRADE_SLICE-f10c…` does not match its recorded hash. Expected 3a91…, got 77d0…" (expected and actual in `.hash` style, copyable). Overall result in seal red: "Not valid".
- Server mode posts the ZIP to `POST /verify`.
- Accessible: results are an ordered list (a real sequence of checks) with `aria-live="polite"` announcing completion.

### 6.9 `/simulator` — Scenarios (dev and demo only, admin)
List of scenarios with description, expected outcome, parameters (speed, seed), and **Start scenario** / **Stop scenario**. Status panel shows simulated clock, event rate, and open cases. After a run, **Compare with ground truth** shows precision and recall for ring accounts, cycles, spoofers, and alignment lag error against acceptance thresholds (pass or fail in words and teal or seal-red outline). Hidden when `ENV=prod`.

### 6.10 `/admin/health` — System health (admin)
Service table (status, version, readiness, last event time), consumer lag per group, ingest latency chart with a 200 ms threshold line (p50, p95, p99), parser mode ratio (rules vs LLM), signer status and key id, ledger head and last anchor time, **Verify ledger range** (calls `GET /ledger/verify`). Alerts shown as sentences: "Ingest p99 is 240 ms, above the 200 ms target since 10:41."

### 6.11 `/login` (dev) and OIDC (prod)
Dev: choose a role, receive a token from `/auth/dev-token`, session stored in memory plus `sessionStorage`. Prod: OIDC authorization code with PKCE (`next-auth` v5 OIDC provider); token refresh handled silently; on 401 the app preserves the URL and returns after sign-in. Copy: "Sign in to continue" (not "Welcome back").

---

## 7. Signature Component: the Tape

### 7.1 Anatomy (rows share one x-scale and one plot margin)
1. **Social row** (height 140): hype score area (`--social`, 1.5 px line, 12 % fill); call-to-action stems rising from the baseline, height by `log(views+1)`, **shape by class** (circle: buy call, square: hold/pump, triangle: coordination timing, diamond: target price, cross: exit) with class named in tooltip; `HYPE_BURST` band as a light `--social` wash with its label.
2. **Lag lane** (height 40): the bracket from `t_social` (first coordinated message) to `t_market` (first suspect volume rise), vertical hairline guides extending through both rows, label "{n} s later" centered with "p {value}" in smaller text. Tooltip explains the test in plain words: "Trading rose {n} seconds after the first coordinated message. A shuffle test says a gap this consistent would occur by chance about {p×100}% of the time."
3. **Market row** (height 160): volume bars in `--market` for organic share and `--uv` for the ring-attributed share (stacked), price line (`--price`, right axis, thin), anomaly markers on the baseline (shape by type: triangle volume spike, diamond price jump, square wash cycle, circle sync orders, bar spoofing).
4. **Evidence row** (height 28): yellow numbered tags at the time each evidence object relates to; clicking opens the drawer.
5. **Axis:** shared time axis, 5-minute major ticks adaptive to zoom, local exchange time by default with a `UTC` toggle; the pair is always visible in the tooltip.
6. **Navigator:** Recharts `Brush` (height 24) under the axis for zoom; `Zoom` menu: 15 min, 1 h, Case window, All.

### 7.2 Behavior
- **Crosshair:** moves across all rows together; tooltip shows time (both zones), hype score, volume (organic + ring), price, and the nearest events within 5 s.
- **Keyboard:** `←` `→` move crosshair by one bin, `Shift` + arrow by 10 bins, `[` and `]` jump to previous or next event, `Enter` opens the focused event or evidence, `v` toggles table view, `Esc` clears focus.
- **View as table:** replaces the chart with a table of 1-minute rows (time, hype, volume, ring volume, price, events) plus an events table. This is the accessible alternative and also the copy/paste source.
- **Downsampling:** LTTB to at most 1,200 points per row for series above that size.
- **Compact mode** (used on `/live`): single column, no evidence row, no brush, no lag lane label (bracket shown thin).
- **Reduced motion:** the bracket appears fully drawn.
- **Accessible summary:** `aria-label` on the wrapper: "Timeline for {symbol}. Hype rose at {t1}; trading rose {n} seconds later; {k} evidence items." Markers are focusable buttons inside a `role="list"`.

### 7.3 Implementation skeleton (`src/components/Tape/Tape.tsx`)

```tsx
"use client";
import { useMemo, useRef, useState, useLayoutEffect } from "react";
import { scaleTime } from "d3-scale";
import { ComposedChart, Area, Bar, Line, XAxis, YAxis, Tooltip, Brush, ReferenceArea } from "recharts";
import { LagLane } from "./LagLane";
import { EvidenceRow } from "./EvidenceRow";
import { useTapeStore } from "@/state/useTapeStore";
import type { CaseSeries } from "@/lib/types";

export const PLOT_MARGIN = { left: 56, right: 56, top: 8, bottom: 0 }; // identical for every row

export function Tape({ series, compact = false }: { series: CaseSeries; compact?: boolean }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(960);
  useLayoutEffect(() => {
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(480, Math.floor(e.contentRect.width))));
    if (wrap.current) ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);

  const { zoom, scrubberTs, setScrubber } = useTapeStore();
  const [t0, t1] = zoom ?? [series.window.start, series.window.end];
  const x = useMemo(() => scaleTime().domain([t0, t1]).range([PLOT_MARGIN.left, width - PLOT_MARGIN.right]), [t0, t1, width]);
  const xTicks = useMemo(() => x.ticks(width > 900 ? 10 : 5).map(d => +d), [x, width]);
  const common = {
    width, margin: PLOT_MARGIN, syncId: "tape",
    onMouseMove: (s: any) => s?.activeLabel && setScrubber(Number(s.activeLabel)),
  };
  const xAxis = <XAxis dataKey="t" type="number" scale="time" domain={[+t0, +t1]} ticks={xTicks} hide />;

  return (
    <div ref={wrap} role="group" aria-label={series.a11ySummary} className="relative bg-bg-raised border border-line rounded-panel">
      {/* Social row */}
      <ComposedChart {...common} height={compact ? 96 : 140} data={series.hype}>
        {xAxis}<YAxis width={0} domain={[0, 100]} hide />
        <Area dataKey="hype" stroke="var(--social)" strokeWidth={1.5} fill="var(--social)" fillOpacity={0.12} isAnimationActive={false} />
        {series.bursts.map(b => <ReferenceArea key={b.id} x1={+new Date(b.start)} x2={+new Date(b.end)} fill="var(--social)" fillOpacity={0.08} />)}
        {/* CTA stems rendered by <CtaStems/> via recharts <Customized/> using shared x-scale */}
      </ComposedChart>

      {/* Lag lane: pure SVG sharing x-scale and margins */}
      <LagLane x={x} width={width} height={compact ? 24 : 40} lag={series.lag} animateOnce={!compact} caseId={series.caseId} />

      {/* Market row: organic + ring-attributed stacked volume, price on right axis */}
      <ComposedChart {...common} height={compact ? 110 : 160} data={series.bars}>
        {xAxis}
        <YAxis yAxisId="v" width={0} hide /><YAxis yAxisId="p" orientation="right" width={0} hide domain={["auto", "auto"]} />
        <Bar yAxisId="v" dataKey="organic" stackId="v" fill="var(--market)" isAnimationActive={false} />
        <Bar yAxisId="v" dataKey="ring" stackId="v" fill="var(--uv)" isAnimationActive={false} />
        <Line yAxisId="p" dataKey="price" stroke="var(--price)" strokeWidth={1} dot={false} isAnimationActive={false} />
        <Tooltip content={<TapeTooltip />} cursor={{ stroke: "var(--ink)", strokeWidth: 1 }} />
        {!compact && <Brush dataKey="t" height={24} stroke="var(--line-strong)" travellerWidth={8} />}
      </ComposedChart>

      {!compact && <EvidenceRow x={x} width={width} items={series.evidence} />}
      <TimeAxis x={x} width={width} ticks={xTicks} />
    </div>
  );
}
```

`LagLane` (excerpt):
```tsx
export function LagLane({ x, width, height, lag, animateOnce, caseId }: Props) {
  const [drawn, setDrawn] = useState(() => !animateOnce || sessionStorage.getItem(`vigil.bracket.${caseId}`) === "1"
    || matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => { if (!drawn) { const id = requestAnimationFrame(() => { setDrawn(true); sessionStorage.setItem(`vigil.bracket.${caseId}`, "1"); }); return () => cancelAnimationFrame(id); } }, [drawn, caseId]);
  const xs = x(new Date(lag.tSocial)), xm = x(new Date(lag.tMarket));
  return (
    <svg width={width} height={height} role="img" aria-label={`Trading rose ${lag.seconds} seconds after the first coordinated message`}>
      <line x1={xs} x2={xs} y1={0} y2={height} stroke="var(--ink)" strokeDasharray="2 3" />
      <line x1={xm} x2={xm} y1={0} y2={height} stroke="var(--ink)" strokeDasharray="2 3" />
      <path d={`M${xs},${height/2 - 5} v10 M${xs},${height/2} H${drawn ? xm : xs} M${xm},${height/2 - 5} v10`}
            stroke="var(--ink)" strokeWidth={1.5} fill="none" style={{ transition: "d 900ms cubic-bezier(.2,.7,.2,1)" }} />
      <text x={(xs + xm) / 2} y={height / 2 - 8} textAnchor="middle" className="fill-ink text-sm" opacity={drawn ? 1 : 0} style={{ transition: "opacity 300ms 700ms" }}>
        {lag.seconds} s later
      </text>
      <text x={(xs + xm) / 2} y={height / 2 + 18} textAnchor="middle" className="fill-ink-muted text-xs">p {lag.pValue.toFixed(3)}</text>
    </svg>
  );
}
```
(If the browser does not animate the SVG `d` property, animate `strokeDashoffset` on a pre-drawn path instead; the result must be the same visual.)

---

## 8. Data Layer

### 8.1 Types
Generate types at build time:
- `openapi-typescript` from `/api/v1/openapi.json` → `src/lib/api-types.ts`.
- `json-schema-to-typescript` from `libs/vigil_common/schemas/*.schema.json` → `src/lib/schema-types.ts` (dossier, anomaly, signal, trade).
- Hand-written view models in `src/lib/types.ts` (`CaseSeries`, `LagInfo`, `GraphElements`).

### 8.2 API client (`src/lib/api.ts`)
- `fetch` wrapper adding `Authorization: Bearer`, JSON handling, and RFC 7807 `problem+json` parsing into `ApiError {status, title, detail, type}`.
- On 401 → trigger re-auth; on 403 → toast "You don't have permission for this action"; on 5xx → inline error state with Retry.
- Timestamps remain **strings** in view models; convert to `Date` only for display or scale math. Nanosecond precision strings are preserved for evidence displays.

### 8.3 TanStack Query keys and policies

| Key | Endpoint | Stale time | Notes |
|---|---|---|---|
| `['heatmap']` | `/symbols/heatmap` | 0 (WS-updated) | Seeded by WS frames via `setQueryData` |
| `['series', symbol, from, to, res]` | `/symbols/{symbol}/series` | 5 s | |
| `['cases', filters]` | `/cases` | 5 s | Invalidated by WS `cases` frames |
| `['case', id]` | `/cases/{id}` | 2 s | Invalidated by WS frames with `case_id` |
| `['case-series', id]` | `/cases/{id}/series` | 10 s | |
| `['timeline', id]` | `/cases/{id}/timeline` | 10 s | |
| `['graph', id, minConf, maxNodes]` | `/cases/{id}/graph` | 30 s | `keepPreviousData` |
| `['evidence', id]` | `/cases/{id}/evidence` | 60 s | |
| `['dossier', id]` | `/dossiers/{id}` | ∞ (immutable per id) | |
| `['verify', id]` | `/dossiers/{id}/verify` | 0 | Refetch on mount and on **Verify again** |
| `['entity', id]` | `/entities/{id}` | 30 s | |

Mutations (`directives`, `links/feedback`, `review`, `submit`) use optimistic UI only for link feedback (edge style flips immediately, rolls back on error). All mutations disable their trigger while pending and show a spinner **inside the button**; labels do not change meaning while pending ("Recording decision…").

### 8.4 WebSocket hook (`src/state/useStream.ts`)

```ts
"use client";
import { create } from "zustand";
import { useEffect } from "react";
import { queryClient } from "@/lib/queryClient";

type Conn = "live" | "behind" | "reconnecting" | "offline";
type Frame = { topic: string; ts: string; data: any };
interface StreamState { conn: Conn; lagMs: number; alerts: Frame[]; heatmap: Record<string, any>; push: (f: Frame[]) => void; set: (p: Partial<StreamState>) => void; }
export const useStreamStore = create<StreamState>((set, get) => ({
  conn: "offline", lagMs: 0, alerts: [], heatmap: {},
  push: (frames) => set(s => {
    let heatmap = s.heatmap, alerts = s.alerts;
    for (const f of frames) {
      if (f.topic === "heatmap") heatmap = { ...heatmap, ...Object.fromEntries(f.data.map((r: any) => [r.symbol, r])) };
      else if (f.topic === "anomalies" || f.topic === "cases") alerts = [f, ...alerts].slice(0, 200);
      if (f.topic === "cases") queryClient.invalidateQueries({ queryKey: ["case", f.data.case_id] }), queryClient.invalidateQueries({ queryKey: ["cases"] });
    }
    return { heatmap, alerts };
  }),
  set: (p) => set(p),
}));

export function useStream(topics: string[]) {
  useEffect(() => {
    let ws: WebSocket | null = null, stop = false, attempt = 0, watchdog: any, buf: Frame[] = [], raf = 0;
    const flush = () => { raf = 0; if (buf.length) { useStreamStore.getState().push(buf); buf = []; } };
    const connect = () => {
      useStreamStore.getState().set({ conn: attempt ? "reconnecting" : "offline" });
      ws = new WebSocket(`${process.env.NEXT_PUBLIC_WS_BASE}/stream?topics=${topics.join(",")}&token=${getToken()}`);
      ws.onopen = () => { attempt = 0; useStreamStore.getState().set({ conn: "live" }); arm(); };
      ws.onmessage = (m) => {
        arm(); const f = JSON.parse(m.data) as Frame; if (f.topic === "heartbeat") return;
        useStreamStore.getState().set({ lagMs: Date.now() - Date.parse(f.ts) });
        buf.push(f); if (!raf) raf = window.setTimeout(flush, 250);            // render at most 4 times per second
      };
      ws.onclose = () => { if (!stop) setTimeout(connect, Math.min(15000, 1000 * 2 ** attempt++)); };
    };
    const arm = () => { clearTimeout(watchdog); watchdog = setTimeout(() => ws?.close(), 30000); };   // no heartbeat for 30 s
    connect();
    return () => { stop = true; clearTimeout(watchdog); ws?.close(); };
  }, [topics.join(",")]);
}
```
Backoff: 1, 2, 4, 8, then 15 s. After reconnect, queries for heatmap and cases are refetched to close any gap. `conn` becomes `behind` when `lagMs > 2000`.

### 8.5 Other stores
- `useTapeStore`: `zoom`, `scrubberTs`, `tz: 'exchange'|'utc'`, `setZoom`, `setScrubber`.
- `useGraphStore`: `selection`, `filters {minConf, show{trades,inferred,brokers,devices,channels}}`, `layout`, `tracedCycleId`, `vetoed` (set of pair ids, optimistic).
- `useUiStore` (persisted): `railCollapsed`, `theme`, `density`.

### 8.6 Time handling
Utility `fmtTime(ts, {tz, withSeconds, withMs})` uses `Intl.DateTimeFormat` with `Asia/Kolkata` for `NSE`/`BSE`, `America/New_York` for `NASDAQ`/`NYSE`, `UTC` for `SYNTH` and for the UTC toggle. Evidence and verification contexts always show UTC alongside the chosen zone.

---

## 9. Graph Styling (`src/components/Graph/style.ts`)

```ts
import type cytoscape from "cytoscape";
const CLUSTER = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"];
export const graphStyle = (): cytoscape.Stylesheet[] => [
  { selector: "node", style: { "font-family": "Public Sans, sans-serif", "font-size": 10, color: "#1F2B33", "text-valign": "bottom", "text-margin-y": 4,
      "border-width": 1, "border-color": "#1F2B33", "background-color": "#FFFFFF", label: "data(label)", "min-zoomed-font-size": 9 } },
  { selector: "node[type = 'Trader']",  style: { shape: "ellipse", width: "mapData(volume, 0, 100000, 14, 44)", height: "mapData(volume, 0, 100000, 14, 44)",
      "background-color": (e: any) => CLUSTER[e.data("cluster") % CLUSTER.length], "background-opacity": 0.18 } },
  { selector: "node[type = 'Broker']",  style: { shape: "hexagon", width: 28, height: 28, "background-color": "#E8ECEE" } },
  { selector: "node[type = 'Device']",  style: { shape: "round-rectangle", width: 24, height: 16, "background-color": "#E8ECEE" } },
  { selector: "node[type = 'NetworkFingerprint']", style: { shape: "tag", width: 24, height: 16, "background-color": "#E8ECEE" } },
  { selector: "node[type = 'Channel']", style: { shape: "diamond", width: 26, height: 26, "background-color": "#FFFFFF", "border-color": "#2563C9" } },
  { selector: "node[type = 'Handle']",  style: { shape: "triangle", width: 18, height: 18, "border-color": "#2563C9" } },
  { selector: ":parent", style: { shape: "round-rectangle", "background-opacity": 0.04, "border-style": "dashed", "border-color": "#9AA7AF", "border-width": 1, "padding": "14px",
      label: "data(label)", "text-valign": "top", "text-halign": "center", "text-margin-y": -4 } },
  { selector: "edge", style: { width: 1, "curve-style": "bezier", "line-color": "#6C7B85", "target-arrow-color": "#6C7B85", opacity: 0.9 } },
  { selector: "edge[type = 'TRADED_WITH']", style: { "target-arrow-shape": "triangle", "line-color": "#1F2B33", "target-arrow-color": "#1F2B33", width: "mapData(qty, 0, 20000, 1, 5)" } },
  { selector: "edge[type = 'LINKED']", style: { "line-style": "dashed", "line-dash-pattern": [6, 4], "line-color": "#5B3FD4", width: "mapData(confidence, 0.6, 1, 1.5, 4.5)" } },
  { selector: "edge[type = 'REACTED_TO']", style: { "line-color": "#2563C9", "target-arrow-shape": "vee", "target-arrow-color": "#2563C9" } },
  { selector: "edge.cycle", style: { "line-color": "#B3261E", "target-arrow-color": "#B3261E", width: 3 } },
  { selector: "edge.vetoed", style: { "line-style": "dotted", "line-color": "#6C7B85", opacity: 0.5 } },
  { selector: ":selected", style: { "border-width": 3, "border-color": "#5B3FD4", "overlay-opacity": 0 } },
  { selector: ".dim", style: { opacity: 0.18 } },
];
export const layoutFcose = { name: "fcose", quality: "default", randomize: false, animate: true, animationDuration: 400,
  nodeRepulsion: 6500, idealEdgeLength: 90, nodeSeparation: 75, packComponents: true } as const;
```
Notes: theme variants (`floor`) swap hex values via a `useTheme` hook that rebuilds the stylesheet (Cytoscape does not read CSS variables). Load Cytoscape with `next/dynamic(..., { ssr: false })`.

---

## 10. Accessibility, Responsiveness, Performance

### 10.1 Accessibility (WCAG 2.2 AA)
- Every state is conveyed by text or shape in addition to color (severity labels, check icons with words, status chips with text).
- Focus: 2 px `--focus` outline with 2 px offset on all interactive elements; in Deep bench the focus color is evidence yellow. Focus order follows visual order; drawers trap focus and restore it on close.
- Target size at least 24 × 24 px (citation tags and Tape markers get invisible hit-area padding).
- Live regions: alert feed (`polite`, max one announcement per 5 s), verification results (`polite`), toasts (`status`).
- Charts: summary label, table alternative (`v`), focusable markers; graph: table alternative and focus proxy list.
- Forms: visible labels, error text tied by `aria-describedby`, required comment fields marked in words ("Required").
- Reduced motion: all non-essential motion removed; bracket shown drawn; list reorder transitions disabled.
- Language: `lang="en"`; social message text carries `lang` from the payload when present (`hi`, `en`).
- Automated checks: `@axe-core/playwright` on every route in CI must report zero serious or critical violations.

### 10.2 Responsive behavior

| Width | Behavior |
|---|---|
| ≥ 1280 | Full layouts as drawn |
| 1024 to 1279 | Right-hand panels (inspector, integrity, alerts) become collapsible drawers; rail collapsed by default |
| 640 to 1023 | Single column. Case page: summary, Tape (simplified two rows), then tabs (Findings, Accounts, Evidence). Graph: table view by default with an "Open canvas" button |
| < 640 | Supported: `/cases`, `/cases/[id]` summary and findings, `/dossiers/[id]` read and decide, `/verify`. Not optimized: graph canvas, simulator, admin (show "Open on a larger screen") |

### 10.3 Performance budgets
- Largest Contentful Paint < 2.5 s on broadband for `/cases` and `/live`.
- Initial JS per route ≤ 180 KB gzip; Cytoscape, Recharts, `jszip`, and noble libraries load only on routes that need them (dynamic import).
- Live ladder renders at most 4 times per second; rows memoized by symbol; virtualized with `@tanstack/react-virtual` above 60 rows.
- Evidence drawer tables virtualized; page size 200 rows via cursor.
- Tape series memoized; downsampled to ≤ 1,200 points per row.
- Fonts: `display: swap`, subsets only, Devanagari loaded only when a message with that script is displayed.

---

## 11. Security and Privacy in the UI
- Tokens kept in memory and `sessionStorage` (dev) or httpOnly session cookie via `next-auth` (prod). Never in `localStorage`.
- All pseudonymous identifiers are shown as shortened pseudonyms (`Zx9f…`) with a Copy action for the full value. Real identities appear only after **Reveal account**, which requires confirmation, is compliance-only, and inserts an audit entry; the revealed value stays on screen for 60 s then masks again.
- Social message text is rendered as plain text with HTML escaped; URLs are shown as text with a "Open in new tab" action that adds `rel="noopener noreferrer"` (message content is untrusted).
- CSP: `default-src 'self'; connect-src 'self' {API} {WS}; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'`.
- Downloads use presigned URLs from the API, opened in a new tab; the UI never proxies evidence bytes.

---

## 12. Routing, Contracts, and Backend Additions

### 12.1 Route map

| Route | Roles | Data sources | FR |
|---|---|---|---|
| `/` | all | redirect to `/live` | |
| `/login` | public (dev) | `/auth/dev-token` | FR-API-02 |
| `/live` | all | WS + heatmap + series | FR-UI-01 |
| `/cases` | all | `/cases` | FR-UI-02 |
| `/cases/[caseId]` | all | case, series, timeline, evidence | FR-UI-03 |
| `/cases/[caseId]/graph` | all | graph, feedback | FR-UI-04 |
| `/cases/[caseId]/timeline` | all | timeline | FR-UI-03 |
| `/dossiers/[dossierId]` | all | dossier, verify, review | FR-UI-05 |
| `/entities/[entityId]` | all | entity | FR-GRA-08 |
| `/verify` | all (public path allowed) | local or `/verify` | FR-UI-06 |
| `/simulator` | admin (dev) | `/sim/*` | FR-UI-07 |
| `/admin/health` | admin, investigator (read) | `/admin/health`, `/ledger/verify` | FR-UI-08 |

### 12.2 Route guards
`middleware.ts` reads the session role and redirects to `/live` with toast "You don't have access to that page" if the role is not allowed. Client components re-check via `useRole()` for conditional rendering.

### 12.3 URL state
Filters live in the URL (`/cases?status=PENDING_REVIEW&symbol=…`); graph filters in query (`?minConf=0.6&show=trades,inferred`); Tape zoom in hash (`#t=04:25..04:45`). Links are shareable between colleagues.

### 12.4 Backend additions required by the UI (implement in `services/api`)

| Method and path | Roles | Response shape |
|---|---|---|
| `GET /cases/{case_id}/series?res=5s` | I,C,A,R | `{ "caseId", "window":{"start","end"}, "hype":[{"t":ms,"hype":0..100}], "bars":[{"t":ms,"organic":int,"ring":int,"price":number}], "bursts":[{"id","start","end","score"}], "ctaStems":[{"t":ms,"cls","views","messageId","evidenceId"}], "markers":[{"t":ms,"type","severity","anomalyId"}], "lag":{"tSocial","tMarket","seconds","pValue","xcorrPeak"}, "evidence":[{"n":1,"t":ms,"evidenceId","type","sha256"}], "a11ySummary":"…" }` |
| `GET /cases/{case_id}/accounts?limit&cursor` | I,C,A,R | `{items:[{accountId, shortId, brokerId, volumeShare, deviceCount, entityId, inCycles}]}` |
| `GET /entities/{entity_id}` | I,C,A,R | `{entityId, ringScore, memberCount, volumeShare, accounts[], brokers[], sharedDevices[], sharedNetworks[], reaction:{medianLatencyMs, nullMedianLatencyMs, pValue}, cases[]}` |
| `GET /cases/{case_id}/flags` | I,C,A,R | `{flags:[{flag, since, explanation}]}` (plain-language explanation strings come from the backend `config/flag_text.yaml` or fall back to `copy.ts`) |
| `POST /cases/{case_id}/directives` with `type: "FORCE_REATTRIBUTION"` and `params.window_end` | I,C | `202 {directiveId}` (extends the existing endpoint) |

`ring` volume in `bars` is the volume traded by accounts that belong to any entity of the case with `ring_score ≥ 0.60` (FLOW §4 numbers).

---

## 13. Testing

| Layer | Tooling | What |
|---|---|---|
| Unit | Vitest + Testing Library | `fmtTime`, color/semantic helpers, copy keys, LTTB, reducer for stream store |
| Component | Storybook 8 (with a11y addon) | Tape (baseline, ring, no ring, compact, failed), WatchLadder, IntegrityPanel (all pass, one fail), ReviewPanel (each role), GraphCanvas (fixtures) |
| Contract | MSW + generated types | Mock server serves fixtures from the simulator ground truth (`frontend/e2e/fixtures/pump_dump_ring_01/*.json`) |
| E2E | Playwright | `live.spec.ts`, `case.spec.ts` (Tape renders, lag label equals fixture, evidence tag opens drawer), `graph.spec.ts` (filter, select edge, mark as false positive, toast text), `dossier.spec.ts` (verify badge, decision confirm text per outcome, 409 handling), `verify.spec.ts` (valid bundle, tampered bundle names the failed check) |
| Accessibility | `@axe-core/playwright` | Zero serious/critical on every route, both themes |
| Visual | Playwright screenshots | Tape and dossier cover in both themes (mask time-varying text) |
| Performance | Lighthouse CI | LCP and JS budgets (§10.3) |

`data-testid` convention: `{component}-{element}` in kebab case, for example `tape-lag-label`, `integrity-check-signature`, `review-decision-approve`, `graph-edge-inspector`.

---

## 14. Keyboard Map

| Keys | Action | Where |
|---|---|---|
| `g` then `l` / `c` / `v` | Go to Live / Cases / Verify | Global |
| `/` | Focus search | Global |
| `?` | Show shortcuts | Global |
| `t` | Toggle exchange time and UTC | Global |
| `f` | Toggle Deep bench wall mode | `/live` |
| `j` / `k`, `Enter`, `x` | Move, open, select row | Tables and ladder |
| `←` `→`, `Shift` + arrows | Move crosshair | Tape |
| `[` `]` | Previous or next event | Tape |
| `v` | Toggle chart or table | Tape, graph |
| `Esc` | Close drawer, popover, or clear selection | Global |
| `a` / `r` | Open review panel on Approve / Rework | `/dossiers/[id]` (officers) |

All shortcuts are listed in a help dialog and disabled while typing in inputs.

---

## 15. Content and Microcopy

### 15.1 Rules
- Sentence case. Plain verbs. One idea per string. Active voice.
- An action keeps the same name through the flow: button, confirm title, toast.
- Errors say what happened and what to do next; they do not apologize.
- Empty states tell the user what to do next.
- Never use "guilty", "criminal", "fraudster", "suspect" for people. Use "linked accounts", "ring", "consistent with", "lead".
- Show confidence as a number (0.00 to 1.00) with a plain-language band: Low (< 0.40), Moderate (0.40 to 0.59), Strong (0.60 to 0.79), Very strong (0.80 or more).

### 15.2 `src/lib/copy.ts` (excerpt, normative keys)

```ts
export const copy = {
  stage: { OPENED:"Opened", ENRICHING:"Gathering data", ALIGNED:"Aligned", ATTRIBUTING:"Tracing accounts", ASSESSING:"Assessing confidence",
    DRAFTING:"Drafting dossier", VALIDATING:"Checking citations", SIGNING:"Signing", PENDING_REVIEW:"Awaiting review", APPROVED:"Approved",
    PUBLISHED:"Published", REJECTED:"Rejected", REWORK:"Needs rework", WATCHLIST:"Watching", CLOSED_NO_ACTION:"Closed, no action", FAILED:"Failed" },
  flags: {
    PARTIAL_ATTRIBUTION:"Account tracing timed out. Showing the links found so far.",
    ATTRIBUTION_SQL_ONLY:"The graph store was offline. Links come from trade records only; devices and brokers are unavailable.",
    MISSING_MARKET_SLICE:"Market data for this window couldn't be collected. Confidence is lower.",
    MISSING_SOCIAL_SLICE:"Social data for this window couldn't be collected. Confidence is lower.",
    LLM_UNAVAILABLE:"Some messages were parsed with rules only. Wording in the dossier uses the standard template.",
    NEW_EVIDENCE_AVAILABLE:"New activity since this dossier was signed.",
  },
  action: { regenerate:"Regenerate dossier", adjust:"Adjust analysis", widen:"Widen window to ±2 h", exclude:"Exclude an account", rerun:"Re-run attribution",
    approve:"Approve and sign", rework:"Request rework", reject:"Reject case", markFalse:"Mark as false positive", confirmLink:"Confirm link",
    verifyAgain:"Verify again", downloadPdf:"Download PDF", downloadBundle:"Download bundle", openGraph:"Open graph", openDossier:"Open dossier",
    startScenario:"Start scenario", stopScenario:"Stop scenario", retry:"Try again" },
  toast: { approved:"Dossier approved and signed", rework:"Rework requested", rejected:"Case rejected", falsePositive:"Link marked as false positive",
    linkConfirmed:"Link confirmed", regenerating:"Regenerating dossier", regenerated:(v:number)=>`Dossier v${v} ready`, noPermission:"You don't have permission for this action" },
  confirm: {
    approve:(n:number)=>`This signs version ${n} with your name and the current time. Signed versions can't be edited. Later changes create a new version.`,
    rework:"The case returns to analysis. The current dossier stays available.",
    reject:"The case closes. This can't be undone, and the record stays in the ledger.",
    reveal:"Revealing links this pseudonym to a real account. This action is recorded." },
  empty: { live:"No tickers are being tracked. Start a scenario in Simulator or connect a market feed.",
    cases:"No cases match these filters. Clear filters or widen the risk threshold.",
    graph:"No linked accounts at this confidence. Lower the threshold to see weaker links.",
    leads:"No leads. Every attributed account is part of a finding." },
  error: { load:(what:string)=>`Couldn't load ${what}. Try again.`, offline:"Reconnecting. Live data may be late.",
    verifyFail:"This record failed verification. Don't rely on it until the failed check is resolved." },
  integrity: { SCHEMA_VALID:"Schema valid", EVIDENCE_HASHES:"Evidence hashes", MERKLE_ROOT:"Merkle root", LEDGER_CHAIN:"Ledger chain", SIGNATURE:"Signature", HUMAN_REVIEW_PRESENT:"Human review" },
  clausesNote:"These mappings are advisory. Legal review is required before any enforcement use.",
  leadsNote:"These links rely on one weak signal and are not part of the findings.",
} as const;
```

### 15.3 Plain-language explanations for technical items (tooltips and "What this means")

| Item | Explanation |
|---|---|
| Risk score | "A 0 to 100 score combining chatter, trading volume, timing, linked accounts, price move, and order-book signs." |
| Hype burst | "Many accounts posting calls to buy about the same ticker, close together, across several channels." |
| Lag | "How long after the first coordinated message trading rose." |
| p value | "How often a gap this consistent would show up by chance if chatter and trading were unrelated." |
| Ring score | "How strongly the evidence suggests these accounts act as one group." |
| Wash cycle | "Shares that pass between linked accounts and return to where they started." |
| Merkle root | "A single fingerprint of all evidence files. Changing any file changes it." |
| Ledger chain | "A log where each entry includes the fingerprint of the one before it, so edits to history are detectable." |

---

## 16. Final Frontend Directory Tree

```
frontend/
├── package.json
├── pnpm-lock.yaml
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── tsconfig.json
├── playwright.config.ts
├── vitest.config.ts
├── .storybook/{main.ts,preview.ts}
├── middleware.ts
├── scripts/gen-types.mjs                 # openapi-typescript + json-schema-to-typescript
├── e2e/
│   ├── live.spec.ts  case.spec.ts  graph.spec.ts  dossier.spec.ts  verify.spec.ts  a11y.spec.ts
│   ├── mocks/handlers.ts                 # MSW
│   └── fixtures/pump_dump_ring_01/{case.json,series.json,graph.json,dossier.json,bundle_valid.zip,bundle_tampered.zip}
├── public/{favicon.svg,logo-glyph.svg}
└── src/
    ├── styles/{tokens.css,globals.css}
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx                              # redirect /live
    │   ├── login/page.tsx
    │   ├── live/page.tsx
    │   ├── cases/page.tsx
    │   ├── cases/[caseId]/layout.tsx             # renders CaseBar
    │   ├── cases/[caseId]/page.tsx
    │   ├── cases/[caseId]/graph/page.tsx
    │   ├── cases/[caseId]/timeline/page.tsx
    │   ├── dossiers/[dossierId]/page.tsx
    │   ├── entities/[entityId]/page.tsx
    │   ├── verify/page.tsx
    │   ├── simulator/page.tsx
    │   ├── admin/health/page.tsx
    │   └── api/auth/[...nextauth]/route.ts       # prod OIDC
    ├── components/
    │   ├── shell/{AppShell.tsx,Rail.tsx,TopBar.tsx,ConnectionStatus.tsx,CaseBar.tsx,Stepper.tsx,Toaster.tsx,Drawer.tsx,ShortcutHelp.tsx}
    │   ├── ui/{Button.tsx,Chip.tsx,Meter.tsx,Table.tsx,Popover.tsx,Dialog.tsx,EmptyState.tsx,ErrorState.tsx,Skeleton.tsx,CopyHash.tsx,EvidenceTag.tsx}
    │   ├── Tape/{Tape.tsx,LagLane.tsx,EvidenceRow.tsx,CtaStems.tsx,TimeAxis.tsx,TapeTooltip.tsx,TapeTable.tsx}
    │   ├── live/{WatchLadder.tsx,LadderRow.tsx,AlertFeed.tsx}
    │   ├── cases/{CaseTable.tsx,SummaryLine.tsx,FindingsList.tsx,AccountsPanel.tsx,EvidenceList.tsx,EvidenceDrawer.tsx,AdjustMenu.tsx,FlagNotices.tsx}
    │   ├── Graph/{GraphCanvas.tsx,style.ts,layouts.ts,FiltersPanel.tsx,Inspector.tsx,CyclesList.tsx,GraphTables.tsx,FeedbackPopover.tsx}
    │   ├── dossier/{DossierDocument.tsx,Citation.tsx,IntegrityPanel.tsx,VersionSelect.tsx,ReviewPanel.tsx,ClauseSection.tsx,AttributionSection.tsx}
    │   ├── verify/{Dropzone.tsx,CheckList.tsx,verifyBundle.ts}   # client verifier
    │   └── admin/{ServiceTable.tsx,LatencyChart.tsx,LedgerVerify.tsx,ScenarioList.tsx,GroundTruthTable.tsx}
    ├── lib/{api.ts,api-types.ts,schema-types.ts,types.ts,queryClient.ts,auth.ts,format.ts,time.ts,copy.ts,lttb.ts,roles.ts}
    └── state/{useStream.ts,useTapeStore.ts,useGraphStore.ts,useUiStore.ts}
```

`package.json` dependencies (pin exact versions in the lockfile): `next@14`, `react@18`, `react-dom@18`, `typescript@5`, `tailwindcss@3.4`, `recharts@2`, `d3-scale`, `cytoscape@3`, `cytoscape-fcose`, `@tanstack/react-query@5`, `@tanstack/react-table@8`, `@tanstack/react-virtual@3`, `zustand@4`, `lucide-react`, `next-auth@5`, `jszip`, `@noble/hashes`, `@noble/ed25519`, `canonicalize`; dev: `vitest`, `@testing-library/react`, `@playwright/test`, `@axe-core/playwright`, `storybook@8`, `msw`, `openapi-typescript`, `json-schema-to-typescript`, `eslint`, `prettier`.

---

## 17. Definition of Done (frontend)

1. Every route in §12.1 renders in both themes with no console errors, driven by the simulator ground-truth fixtures and by the live stack.
2. The Tape shows organic vs ring volume, the lag bracket, call-to-action stems, evidence tags, and a working table alternative; bracket animation plays once per case per session and not under reduced motion.
3. The graph explorer renders 500 nodes at ≥ 30 fps, distinguishes observed (solid) from inferred (dashed ultraviolet) links, highlights cycles, and completes the false-positive flow with the exact toast text from `copy.ts`.
4. The dossier viewer shows live six-check integrity, renders numbered citations that open evidence, blocks decisions when verification fails, and requires a comment for rework or reject.
5. `/verify` verifies a valid bundle in the browser, rejects a tampered bundle naming the failed check and file, and matches server-side results.
6. Colors with semantic meaning (yellow, ultraviolet, teal, seal red) are used only as defined in §3.4 (checked by a lint rule that forbids raw hex outside `tokens.css` and `style.ts`).
7. Axe reports zero serious or critical issues on every route; keyboard-only use completes the investigator and officer journeys.
8. All UI strings come from `copy.ts`; no string uses "guilty", "criminal", or "fraud" about people.
9. Performance budgets in §10.3 pass in Lighthouse CI.
10. Playwright suite and Storybook a11y checks pass in CI.

---

## 18. Build Order

1. **Foundations:** `tokens.css`, Tailwind config, fonts, `copy.ts`, `format.ts`/`time.ts`, `api.ts`, query client, auth, `AppShell`.
2. **UI primitives:** Button, Chip, Meter, Table, Popover, Dialog, Drawer, Toaster, CopyHash, EvidenceTag, Skeleton, empty and error states.
3. **Cases list** and **CaseBar** (stepper, flags).
4. **Tape** (static data first, then live), then the **case workbench**.
5. **Stream store and `/live`** (ladder, alert feed, mini tape).
6. **Graph explorer** (style, layouts, inspector, feedback, table alternative).
7. **Dossier viewer** (document, citations, integrity panel, review panel, print styles).
8. **Verify page** (client verifier, server mode).
9. **Entities, timeline page, simulator, admin health.**
10. **Hardening:** Axe, keyboard map, responsive behavior, performance budgets, Storybook, Playwright, visual baselines.
