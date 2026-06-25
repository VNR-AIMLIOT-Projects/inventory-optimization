# Replenix — UX Revamp Specification

> **Version**: 1.0  
> **Date**: 2026-06-25  
> **Status**: Draft — Awaiting Review  
> **Scope**: Full UX overhaul of all pages and components  
> **Constraint**: No major tech stack changes. React + Vite + shadcn/ui + Tailwind + Recharts + wouter remain.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Diagnosis](#2-current-state-diagnosis)
3. [Design Philosophy](#3-design-philosophy)
4. [Global Design System Changes](#4-global-design-system-changes)
5. [Page-by-Page Revamp](#5-page-by-page-revamp)
6. [Component-Level Fixes](#6-component-level-fixes)
7. [Interaction & Motion Design](#7-interaction--motion-design)
8. [Copilot Redesign](#8-copilot-redesign)
9. [Display Strategy: Desktop-First with Mobile Fallback](#9-display-strategy-desktop-first-with-mobile-fallback)
10. [Implementation Order](#10-implementation-order)

---

## 1. Executive Summary

Replenix is a powerful multi-echelon inventory optimization platform with a 6-step pipeline: Upload → Modify → Preview → Train → Evaluate → Deploy. It has deep functionality including DQN training with live WebSocket updates, multi-SKU evaluation, human-in-the-loop deployment simulation, an AI copilot on every page, and a real-time notification system.

**The problem**: Despite strong functionality, the UX feels overwhelming, visually heavy, and unmistakably AI-generated. A new user looking at any page would struggle to understand what to do first. The visual language — while technically competent — relies on patterns that are hallmarks of AI-generated code: excessive glassmorphism, uniform card layouts, overuse of uppercase tracking-widest labels, and a "command center" aesthetic that prioritizes looking impressive over being usable.

**The goal**: Make every page feel like it was designed by a senior product designer at a company like Linear, Stripe, or Vercel. The UX should be so intuitive that the user barely notices the design — they just *flow* through the pipeline.

---

## 2. Current State Diagnosis

### 2.1 What's Actually Good (Keep These)
- **Pipeline concept**: The 6-step sequential flow is sound and maps cleanly to the actual workflow.
- **Sidebar navigation**: Collapsible sidebar with step descriptions is well-structured.
- **AI Copilot**: Having per-page context-aware AI assistance is a genuine differentiator.
- **Real-time training updates**: WebSocket-based live charts during training are impressive.
- **Dark/light mode**: Having both modes is the right call for enterprise users.
- **Typography choices**: Inter + Space Grotesk + JetBrains Mono is a strong stack.

### 2.2 Core UX Problems

#### Problem 1: "Everything is Important" Syndrome
Every page screams for attention equally. Cards have shadows, glows, gradients, badges, icons, and borders all competing. When everything is emphasized, nothing is.

**Examples**:
- `Stage1Data.tsx`: Upload zone, generate zone, SKU selector, data table, upload history, success banner, and StageNav all appear at once with equal visual weight.
- `DeploymentDashboard.tsx`: 7 KPI blocks + SKU list + detail panel + ledger + charts + controls — all visible simultaneously.

#### Problem 2: AI-Generated Visual Fingerprints
These patterns are dead giveaways:
- `glass` utility class used on everything (header, sidebar, popover, dropdown, notification panel).
- `tracking-widest uppercase text-[10px]` on virtually every label.
- `rounded-3xl` on containers that don't need aggressive rounding.
- `shadow-2xl shadow-primary/5` scattered everywhere.
- Gradient backgrounds (`bg-gradient-to-br from-card to-muted/20`) on cards that don't need them.
- Military/sci-fi copy: "SYS.ONLINE", "SYSTEM.LOG", "Operator Login", "Initialize Record", "Commence Pipeline", "Access Level: root", "Establish secure link".

#### Problem 3: Cognitive Overload on Data Pages
- **Training page** (`Stage2Training.tsx` — 1,177 lines): Configuration panel + sweep mode + progress bars + per-SKU status dots + live chart + training history + loaded runs — all packed into a single scrollable view.
- **Deployment Dashboard** (`DeploymentDashboard.tsx` — 1,053 lines): KPI bar + SKU list + override controls + ledger table + sparklines + action buttons — the user needs a manual just to understand the terminology.
- **Modify page** (`ModifyDemand.tsx` — 574 lines): Three collapsible param sections + preview graph + comparison + SKU selector + reset dialog — feels like a control panel, not a tool.

#### Problem 4: Lack of Progressive Disclosure
All controls are always visible regardless of state. For example:
- Training config shows "Sensitivity Sweep Mode" toggle before the user has even run a single training.
- Deployment shows "Export" and "New Session" buttons even when no session exists.
- Modify page shows all parameter sections expanded with every input field visible.

#### Problem 5: Inconsistent Information Hierarchy
- Page titles sometimes appear in the header, sometimes in a `border-l-2` block.
- Some pages have `StageNav`, some don't (HomeDashboard, LandingPage).
- Card styling varies: some use `bg-card/50`, some `bg-gradient-to-br`, some just `bg-card`.

#### Problem 6: The Landing Page Doesn't Sell
The landing page is generic: one headline, one paragraph, three feature cards. For an enterprise product handling real inventory decisions, this is underwhelming. There's no social proof, no product screenshot, no demo, no pricing — just "Start Managing".

---

## 3. Design Philosophy

### Guiding Principles

1. **"Calm Technology"**: The interface should be quiet by default and loud only when something needs attention. Inspired by Linear's restraint.

2. **"Progressive Disclosure"**: Show what's needed now, reveal more as the user progresses. A first-time user uploading data should see 3 things maximum, not 12.

3. **"Clear Hierarchy"**: Every page should answer: What am I looking at? What should I do? What are my options? — in that order, through visual hierarchy alone.

4. **"Data Density Without Clutter"**: The deployment dashboard *needs* to show lots of data. The solution isn't hiding it, but organizing it with proper spatial grouping, consistent metrics formatting, and contextual emphasis.

5. **"Human Copy"**: Replace all militaristic/sci-fi language with clear, warm, professional copy that a supply chain manager would understand.

---

## 4. Global Design System Changes

### 4.0 CRITICAL: Fix "Everything Is Too Big" (The Zoom Problem)

The user currently has to press `Ctrl+-` two to three times (zooming to ~67-75%) for the UI to feel right. This means **the default UI is 25-33% oversized**. This is not a browser quirk — it's a compound problem with multiple root causes that must all be fixed:

#### Root Cause 1: Bloated Card Component (`card.tsx`)
The `Card` component base class is:
```
rounded-[2rem] glass text-card-foreground shadow-2xl hover:shadow-primary/5
```
- `rounded-[2rem]` = 32px border radius — absurdly large. This forces huge internal padding to avoid content clipping the corners.
- `glass` = `bg-background/80 backdrop-blur-md border border-white/10` — applied to EVERY card, not just floating elements.
- `shadow-2xl` = the heaviest possible shadow on every single card.
- `CardHeader` has `p-6` (24px padding) and `CardContent` has `p-6 pt-0` (24px sides/bottom).
- `CardTitle` is `text-2xl` (24px) by default — far too large for most card titles.

**Fix**:
```tsx
// Card: reduce rounding, remove glass, lighten shadow
"rounded-xl border border-border bg-card text-card-foreground shadow-sm"

// CardHeader: tighter padding
"flex flex-col space-y-1 p-4"        // was p-6

// CardContent: tighter padding
"p-4 pt-0"                            // was p-6 pt-0

// CardTitle: smaller default size
"text-base font-semibold leading-none tracking-tight"  // was text-2xl
```

#### Root Cause 2: Oversized Page-Level Elements
| Element | Current | Should Be |
|---------|---------|----------|
| Header bar height | `h-16` (64px) | `h-12` (48px) |
| Primary CTA buttons | `h-12` (48px) + `text-lg` | `h-9` (36px) + `text-sm` |
| Page titles | `text-4xl` / `text-5xl` / `text-7xl` | `text-2xl` / `text-3xl` max |
| Sidebar padding | `p-6` (24px) | `p-4` (16px) |
| Sidebar width | `w-64` (256px) = 16rem expanded | `w-56` (224px) = 14rem |
| Sidebar collapsed margin offset | `lg:ml-[112px]` / `lg:ml-[288px]` | `lg:ml-[88px]` / `lg:ml-[240px]` |
| Nav items | `py-3 px-3` + description text | `py-2 px-2.5` |
| Chart heights | `h-[380px]` / `h-[500px]` | `h-[280px]` / `h-[360px]` |
| Empty state icons | `w-16 h-16` / `w-12 h-12` | `w-10 h-10` / `w-8 h-8` |
| Copilot FAB | `h-14 w-14` (56px) | `h-11 w-11` (44px) |
| KPI blocks (Deploy) | `px-4 py-3` + `text-lg` values | `px-3 py-2` + `text-sm` values |

#### Root Cause 3: HTML Font Bloat (`index.html`)
The `index.html` loads **30+ Google Font families** in a single massive `<link>` tag — including Playfair Display, Libre Baskerville, Architects Daughter, DM Sans, Geist, IBM Plex, Lora, Merriweather, Montserrat, Open Sans, Outfit, Oxanium, Poppins, Roboto, and more. **Only 3 are actually used** (Inter, Space Grotesk, JetBrains Mono).

**Fix**: Strip the `<link>` tag down to only the 3 fonts that are referenced in `tailwind.config.ts` and `index.css`. The current tag is ~1.6KB of URL alone and triggers dozens of unnecessary network requests on page load, which can cause a visible font-swap flash that makes the initial render feel janky and oversized (FOUT — Flash of Unstyled Text).

#### Root Cause 4: No Content Max-Width
On a large monitor (e.g., 27" 2560px), card grids stretch to fill the entire viewport minus the sidebar. A 3-column card grid at full width means each card is ~600px+ wide with `p-6` internal padding — hence everything feels enormous.

**Fix**: Add `max-w-screen-xl mx-auto` (1280px max) to page content containers. On smaller laptops this changes nothing; on large monitors it prevents the layout from stretching into unreadable widths.

#### Root Cause 5: Aggressive Rounding Creates Wasted Space
`rounded-3xl` (24px) and `rounded-[2rem]` (32px) on cards, sidebar, and header force large internal margins to prevent content from visually colliding with the rounded corners. This cascading whitespace inflates every element.

**Fix**: Use `rounded-lg` (8px) on cards, `rounded-xl` (12px) maximum on containers like sidebar. Reserve `rounded-2xl` only for the floating copilot panel.

#### Compound Effect
These issues multiply: a Card with 32px rounding + 24px padding + 24px title text + glass blur + 2xl shadow inside a full-width grid on a 1920px screen = each card feels like a billboard. When 6-8 such cards appear on the training or deploy page, the user drowns in oversized UI chrome.

**Target**: After the fix, the UI should feel comfortable at **100% browser zoom on a 14" 1920×1080 laptop** with no need to zoom out. On larger displays, the max-width constraint prevents stretching.

### 4.1 Color Palette Refinement

**Light Mode** (current values are close but need warming):
```css
:root {
  --background: 0 0% 99%;         /* Slightly off-white, less sterile */
  --foreground: 222 47% 11%;
  --card: 0 0% 100%;
  --card-foreground: 222 47% 11%;
  --muted: 220 14% 96%;
  --muted-foreground: 220 9% 46%;
  --primary: 221 83% 53%;         /* Richer blue, less navy */
  --primary-foreground: 210 40% 98%;
  --border: 220 13% 91%;
  --radius: 0.5rem;               /* Currently 0rem — add subtle rounding */
}
```

**Dark Mode** (current is too deep/cold — warm it up):
```css
.dark {
  --background: 224 47% 7%;       /* Slightly warmer dark */
  --foreground: 213 31% 91%;
  --card: 224 47% 9%;             /* Distinct from background */
  --muted: 224 30% 13%;
  --border: 224 20% 16%;
  --primary: 217 91% 60%;         /* Brighter primary for contrast */
}
```

**Semantic Status Colors** (define once, use everywhere):
```css
:root {
  --success: 142 71% 45%;
  --warning: 38 92% 50%;
  --danger: 0 84% 60%;
  --info: 217 91% 60%;
}
```

### 4.2 Typography Scale

Remove the overuse of `text-[10px] uppercase tracking-widest`. Establish a clear scale:
- **Page title**: `text-2xl font-semibold tracking-tight` (Space Grotesk)
- **Section heading**: `text-lg font-medium` (Space Grotesk)
- **Card title**: `text-base font-medium` (Inter)
- **Body**: `text-sm` (Inter)
- **Caption/metadata**: `text-xs text-muted-foreground` (Inter) — *not uppercase*
- **Data/monospace**: `text-sm font-mono` (JetBrains Mono)
- **Badge/label**: `text-xs font-medium` — uppercase only when truly a label (e.g., "SKU", "STATUS")

### 4.3 Spacing & Layout

> **⚠️ Important**: The primary issue is that everything is TOO BIG, not too cramped. Do NOT increase padding/spacing from current values — reduce them.

- **Page padding**: `px-5 py-4` (currently `px-6 pb-6 pt-2` — the horizontal is fine but reduce slightly for density).
- **Card internal padding**: `p-4` everywhere (currently `p-6` = 24px which is excessive for most cards).
- **Card gaps**: `gap-4` consistently between cards (currently varies between `gap-4`, `gap-6`, `gap-8`).
- **Max content width**: `max-w-screen-xl mx-auto` (1280px) on all internal page content — prevents stretching on large monitors.
- **Section spacing**: `space-y-5` between major sections (currently `space-y-4` is actually fine — the problem is component SIZE, not spacing between them).

### 4.4 Card & Container Style

**Stop doing**:
- `glass` on everything. Reserve glassmorphism for exactly 2 elements: the sidebar and the copilot panel.
- `shadow-2xl` on regular cards. Use `shadow-sm` by default, `shadow-md` for elevated elements.
- `rounded-3xl` on content containers. Use `rounded-xl` maximum.
- `bg-card/50 backdrop-blur-sm` on cards — just use solid `bg-card`.

**Start doing**:
- Cards: `bg-card border border-border rounded-xl shadow-sm`
- Elevated cards (interactive): add `hover:shadow-md transition-shadow`
- Header bar: `bg-card border-b border-border` — clean and grounded, not floating.

### 4.5 Remove Sci-Fi Copy

| Current | Replacement |
|---------|-------------|
| SYS.ONLINE / SYS.OFFLINE | "Backend connected" / "Backend offline" |
| SYSTEM.LOG | "Notifications" |
| Operator Login | "Sign in" |
| Initialize Record | "Create account" |
| Commence Pipeline | "Start pipeline" |
| Access Level: root | (Remove entirely) |
| Confirm identity to proceed | "Enter your email and password" |
| Establish secure link | "Sign in to your account" |
| Deployment Engine Offline | "No active simulation" |
| Operator Provisioning | "Create your account" |
| Disconnect | "Sign out" |
| Authorization Required | (Remove entirely) |
| Control Center | "Dashboard" |

---

## 5. Page-by-Page Revamp

### 5.1 Landing Page (`LandingPage.tsx`)

**Current issues**: Generic hero, no product screenshots, no social proof, no explanation of what the pipeline does, feature cards are abstract.

**Revamp**:
- **Hero**: Keep the headline structure but make it warmer: "Smart inventory decisions, powered by reinforcement learning." Remove "automated by AI" — it's vague.
- **Add a product screenshot**: Show the deployment dashboard in action (dark mode, real data). This immediately communicates what the product does.
- **Feature section**: Replace abstract cards with a visual pipeline walkthrough. Show the 6 steps as a horizontal timeline with micro-illustrations or icons, each with a one-sentence description.
- **Add credibility**: "Built with PyTorch DQN agents" / "Multi-SKU parallel training" / "Human-in-the-loop deployment" — technical proof points that enterprise users care about.
- **CTA**: Change "Start Managing" to "Get Started" or "Try the Pipeline".
- **Remove the floating badge**: "The Future of Inventory" adds nothing.

### 5.2 Auth Page (`AuthPage.tsx`)

**Current issues**: Split-screen layout is fine but the left panel copy is sci-fi ("Authorization Required", "Authenticate to manage policies..."). The form cards use `backdrop-blur-md` creating a frosted-glass effect that feels gimmicky.

**Revamp**:
- **Left panel**: Show a simplified product visual (e.g., a stylized chart or the pipeline steps) instead of text-heavy branding.
- **Form copy**: "Sign in to Replenix" / "Create your account". Remove "Operator Login", "Operator Provisioning", "Initialize Record", "Establish secure link".
- **Form cards**: Solid background, no blur. Clean inputs with consistent spacing.
- **Tab labels**: "Sign in" / "Create account" (not "Login" / "Register").

### 5.3 Home Dashboard (`HomeDashboard.tsx`)

**Current issues**: The pipeline steps are shown as a vertical timeline with hover effects, but there's no actionable information. It's a pretty diagram that tells you what you already know from the sidebar.

**Revamp**:
- **Replace the pipeline diagram with a status overview**: Show the *current state* of the user's pipeline. Which step have they completed? Is there data uploaded? Is there a trained model? This makes the homepage actually useful.
- **Quick actions**: Instead of a single "Commence Pipeline" button, show contextual next-step buttons:
  - If no data: "Upload your first dataset" (big, prominent)
  - If data uploaded but not trained: "Your data is ready → Start training"
  - If model trained: "You have a trained model → View evaluation"
  - If evaluated: "Ready to deploy → Launch simulation"
- **Recent activity**: Show last 3 actions (uploaded file, training run, evaluation result).
- **Title**: "Dashboard" not "Control Center".

### 5.4 Stage 1: Upload Data (`Stage1Data.tsx`)

**Current issues**: Too much on screen — upload zone, generate zone (tabs), data preview table, upload history cards, success banner, StageNav, copilot. A new user is overwhelmed.

**Revamp — Progressive Disclosure**:
- **Phase 1 (no data)**: Show only the upload dropzone and a "Generate sample data" link (not a full tab with 4 config inputs). Make the dropzone large and inviting. Show the template download as a small link below, not a full-width button.
- **Phase 2 (data uploaded)**: The upload zone shrinks. The data preview appears prominently. The SKU selector appears if multiple SKUs exist. Upload history slides into a collapsible section.
- **Data preview**: Instead of a raw table showing 50 rows, show:
  - A summary card: "365 days · 4 SKUs · Jan 2025 – Dec 2025 · Summer pattern detected"
  - A small sparkline chart for quick visual confirmation
  - A "View full data" expandable for the table

### 5.5 Stage 2: Modify Demand (`ModifyDemand.tsx`)

**Current issues**: Three collapsible parameter sections (Baseline, Seasonal, Festival) with 10+ number inputs visible simultaneously. The preview graph takes up 2/3 width but the controls are cramped in 1/3.

**Revamp**:
- **Split the cognitive load**: Instead of showing all parameter groups at once, show them as a stepped wizard within the page:
  - Show the detected summary first: "We detected a summer pattern with baseline demand of ~150 units/day"
  - Let the user choose which parameters to adjust (most won't touch Festival params)
  - Each parameter group opens in-place with a clear visual before/after impact
- **Preview graph**: Keep it prominent (2/3 width) but add an overlay that highlights what changed when parameters are modified (e.g., shade the seasonal periods differently).
- **Copy**: "What is this page?" explainer is good — keep it but make it always visible as a subtle subtitle, not a collapsible.
- **Save flow**: Auto-save with a debounce instead of requiring an explicit "Save Changes" button. Show a small "Saved ✓" indicator.

### 5.6 Stage 3: Preview Demand (`PreviewDemand.tsx`)

**Current issues**: This page feels redundant. It shows the same graph from Modify plus a data table plus "Brownian Motion Variations". The user might wonder: "Didn't I just see this?"

**Revamp**:
- **Differentiate from Modify**: This page should focus on *validation and confidence*. Frame it as "Review your demand profile before training."
- **Key information**: Show a clear summary: "Your demand data is ready for training. Here's what the model will learn from."
- **Variations section**: Keep it but explain it better. Instead of "Brownian Motion Variations", say "Possible demand scenarios — the model will train against these variations."
- **Clear call-to-action**: A prominent "Looks good → Start Training" button at the bottom (not just the StageNav arrow).

### 5.7 Stage 4: Train (`Stage2Training.tsx`)

**Current issues**: The most complex page (1,177 lines). Training config + sweep mode + per-SKU status + live chart + training history — all in one view. The advanced settings are hidden behind a collapsible but sweep mode is exposed at the same level.

**Revamp — Three-State Layout**:

**State 1: Pre-training**
- Show only: Episode count input + a "Start Training" button. Defaults should be good enough.
- "Advanced Settings" stays collapsed. Move "Sweep Mode" inside Advanced — it's a power-user feature.
- Training history appears below if past runs exist, but is clearly secondary.

**State 2: Training in progress**
- The config panel becomes read-only.
- The live chart becomes the hero element — full width.
- Per-SKU progress appears as a compact progress bar row below the chart (not a separate panel).
- WebSocket status indicator is a small dot in the corner, not a prominent badge.

**State 3: Training complete**
- Show a results summary: "Training complete — best reward: X, avg: Y"
- Clear CTA: "Evaluate results →"
- Training history updates with the new run.

### 5.8 Stage 5: Evaluate (`Stage3Deployment.tsx`)

**Current issues**: Two different layouts depending on whether a historical model is loaded vs. batch evaluation. The dual-mode causes confusion.

**Revamp**:
- **Unified layout**: Whether viewing a loaded run or batch results, use the same visual structure:
  - Left: Model selector (loaded runs or batch SKUs)
  - Center: Three reward comparison cards (RL vs Oracle vs Rule-Based)
  - Right/Below: Evaluation graph + training curve
- **Simplify the "Deploy" card**: Currently a full Card with a rocket icon, description, and button. Make it a prominent inline button at the top: "Deploy this model →".
- **Oracle % metric**: Make this THE hero number. "Your RL agent achieves 94.2% of optimal" should be the first thing the user sees.

### 5.9 Stage 6: Deploy (`DeploymentDashboard.tsx`)

**Current issues**: The most information-dense page. 7 KPI blocks + SKU list + detail panel with override inputs, ledger table, and sparklines. The terminology is confusing (Inv, Inv $, RL, Ovr, Act).

**Revamp**:

- **KPI bar**: Reduce from 7 blocks to 4 primary KPIs: Day Progress, Net Profit, Stockout Days, SKU Count. The rest (Revenue, Cost, Inventory Value) move to an expandable "Details" row.
- **SKU list**: Add a search/filter if more than 5 SKUs. Add a mini health bar (colored bar showing green/yellow/red distribution) at the top of the list.
- **Detail panel**: 
  - Split into tabs: "Overview" (current state + sparkline) | "Ledger" (history table) | "Override" (manual control)
  - The override input should be more prominent with a clear explanation: "The AI recommends ordering 45 units. You can override this."
- **Ledger table**: Add column headers that are self-explanatory. Replace abbreviations: "Inv" → "Inventory", "Ovr" → "Override". Use color coding for overridden rows.
- **Auto-run**: Add a speed selector (1x / 5x / 10x) instead of just on/off.

### 5.10 Profile Page (`ProfilePage.tsx`)

**Current issues**: Over-designed for a simple form. The "Operator Identity" heading with border-left accent is unnecessarily dramatic.

**Revamp**: 
- Simple page title: "Profile"
- Clean form with name fields and email (read-only)
- Add a "Change Password" section
- Remove the sci-fi copy

---

## 6. Component-Level Fixes

### 6.1 Header (`Header.tsx`)

**Current**: Floating glass bar with rounded-3xl, system status dot, notification popover with "SYSTEM.LOG" header, user dropdown with "Access Level: root".

**Revamp**:
- **Remove floating/glass**: Make it a standard top bar with `bg-card border-b border-border`.
- **Status indicator**: Small dot next to the logo area. Green = connected, red = disconnected. Tooltip on hover for details.
- **Notifications**: Clean dropdown. Title: "Notifications". Use standard list items, not monospace terminal-style entries.
- **User menu**: Show avatar + name. Dropdown: "Profile", "Settings" (if applicable), "Sign out". Remove "Access Level: root".

### 6.2 Sidebar (`Sidebar.tsx`)

**Current**: Floating glass sidebar with rounded-3xl, offset from edges. Navigation items have complex active states with gradient overlays.

**Revamp**:
- **Keep the floating style** but simplify: Remove `shadow-2xl`. Use `border border-border bg-card`. Keep `rounded-2xl`.
- **Navigation items**: Simplify active state to a clean left border accent (`border-l-2 border-primary`) + subtle background. Remove gradient overlays.
- **Branding**: Keep the logo and "Replenix" text. Change "Intelligent Inventory" subtitle to "Inventory Optimization" (clearer).
- **Add step indicators**: Show completion status per step (empty circle → checkmark) based on pipeline state.

### 6.3 StageNav (`StageNav.tsx`)

**Current**: Glass bar with dot indicators and prev/next buttons. Appears on all pipeline pages.

**Revamp**:
- **Simplify**: Replace dots with a horizontal stepper showing step names: "Upload → Modify → Preview → Train → Evaluate → Deploy" with the current step highlighted.
- **Show completion**: Completed steps get a subtle checkmark.
- **Remove glass**: Use `bg-muted/50 rounded-lg`.

### 6.4 Charts (Recharts usage)

**Current**: Hardcoded colors (`#8b5cf6`, `#334155`), inconsistent tooltip styles, some charts use theme variables and some don't.

**Revamp**:
- Define a `chartTheme` object that all charts reference.
- Tooltip: Use `bg-card border-border rounded-lg shadow-md` consistently.
- Grid: Very subtle, `opacity-0.08`.
- Colors: Use CSS variables so they adapt to light/dark mode automatically.
- Axis labels: `text-xs text-muted-foreground`.

---

## 7. Interaction & Motion Design

### 7.1 Page Transitions
- Current: `animate-in fade-in duration-500` on page content.
- Keep but add a subtle slide-up: `animate-in fade-in slide-in-from-bottom-2 duration-300`.

### 7.2 Loading States
- Replace all `<Loader2 className="animate-spin" />` with skeleton screens for data-loading states.
- Keep spinner only for action buttons (Submit, Train, Evaluate).

### 7.3 Toast Notifications
- Current toasts are fine functionally. Add auto-dismiss after 4 seconds (if not already).
- Use semantic colors: success = green border-left, error = red, info = blue.

### 7.4 Hover & Focus States
- Cards: `hover:shadow-md transition-shadow duration-200`
- Buttons: Keep existing hover states but ensure consistent focus rings: `focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2`.
- Inputs: `focus:border-primary focus:ring-1 focus:ring-primary/30`.

### 7.5 Empty States
- Every section that can be empty should have a clear, friendly empty state:
  - Upload: "Drop your CSV here to get started"
  - Training history: "No training runs yet. Start your first one above."
  - Notifications: "You're all caught up" (not "System nominal. No events.")

---

## 8. Copilot Redesign

The floating AI Copilot is a genuine differentiator and should be elevated, not just styled.

### 8.1 Current Issues
- The FAB (floating action button) animation is complex but the actual chat panel is basic.
- Chat bubbles are tiny (11px text).
- Quick actions are plain text buttons that look like form labels.
- The streaming text animation adds character but the overall panel feels like a prototype.

### 8.2 Revamp Plan
- **FAB**: Simplify the expansion animation. Resting state: a clean circle with a sparkle icon. Hover: gentle scale-up (1.05x). No text expansion on hover — it's distracting and jumpy.
- **Panel**: Increase width from 360px to 400px. Increase height from 520px to 560px.
- **Chat text**: Increase from 11px to 13px for readability.
- **Quick actions**: Style as pill buttons with subtle borders: `rounded-full border bg-muted/50 px-4 py-2 hover:bg-primary/10 hover:border-primary/30`.
- **Header**: Show the page context more prominently: "Data Assistant · 4 SKUs loaded" instead of just a status dot.
- **Input area**: Increase input height to 44px. Rounder design.
- **Unread indicator**: Keep the ping animation but make the badge a number (e.g., "2") instead of just a dot.

---

## 9. Display Strategy: Desktop-First with Mobile Fallback

> **Priority**: The primary use case is laptops (14"-16") and desktop monitors (24"-32"). Mobile is a secondary nice-to-have, not a design target. All design decisions should optimize for the desktop experience first.

### 9.1 The Primary Target: Laptops & Monitors

The UI must feel right at **100% browser zoom** across these common resolutions:
- **1366×768** (older/smaller laptops) — must be usable, no horizontal scroll
- **1920×1080** (standard laptop/monitor) — the primary design target
- **2560×1440** (QHD monitors) — should look clean, not stretched
- **3840×2160** (4K monitors) — max-width constraint prevents billboard effect
- **Ultra-wide monitors** (3440×1440, etc.) — content stays centered, sidebar + content area is capped

**Key fix**: The `max-w-screen-xl` (1280px) content constraint is the single most impactful change. It ensures that on any screen wider than ~1500px, the content area stops growing and stays centered. This prevents the "everything is enormous" feeling on large displays.

### 9.2 Sidebar Margin Bug
- `DeploymentDashboard.tsx` hardcodes `lg:ml-[320px]` instead of using the `isCollapsed` state.
- After the sidebar width reduction (256px → 224px), all pages should use: `isCollapsed ? "lg:ml-[88px]" : "lg:ml-[240px]"`.

### 9.3 Mobile (Secondary Priority)
Mobile is not a primary use case for an inventory optimization platform with complex charts, ledgers, and training controls. However, basic usability should be maintained:
- Sidebar hides on mobile, replaced by sheet (hamburger menu) — **already works, keep it**.
- Layouts stack to single column on mobile via existing `grid-cols-1 lg:grid-cols-3` — **already works**.
- Charts use `<ResponsiveContainer>` — **already works, verified**.
- KPI bar on deployment: stack to 2 columns on tablet, single on mobile.
- Copilot: On mobile (< 768px), make the panel full-width, slide up from bottom.
- **Do NOT compromise desktop density to make mobile work better**. If a trade-off exists, optimize for desktop.

---

## 10. Implementation Order

Break the revamp into 5 phases to avoid a risky big-bang rewrite:

### Phase 1: Design System Foundation — Fix the Zoom Problem (1-2 days)
> This phase alone should eliminate the need to `Ctrl+-` zoom out. Every subsequent phase builds on these foundations.

- [ ] **`card.tsx`**: Reduce rounding `rounded-[2rem]` → `rounded-xl`, remove `glass`, reduce `shadow-2xl` → `shadow-sm`, reduce padding `p-6` → `p-4`, reduce title `text-2xl` → `text-base`
- [ ] **`index.html`**: Strip the Google Fonts `<link>` tag from 30+ families down to only Inter, Space Grotesk, JetBrains Mono
- [ ] **`index.css`**: Update color variables (light + dark), set `--radius: 0.5rem` (from `0rem`)
- [ ] **`tailwind.config.ts`**: Verify refined tokens match the new color palette
- [ ] **Add `max-w-screen-xl mx-auto`** to page content containers in all page components
- [ ] Create/update shared utility classes (remove `glass` overuse — keep only on sidebar + copilot)
- [ ] Fix all hardcoded chart colors to use CSS variables

### Phase 2: Shell Components (1-2 days)
- [ ] Revamp `Header.tsx` — remove glass, fix copy, clean notifications
- [ ] Revamp `Sidebar.tsx` — simplify active states, add step completion indicators
- [ ] Revamp `StageNav.tsx` — horizontal stepper with step names
- [ ] Fix `DeploymentDashboard` sidebar margin bug
- [ ] Audit and fix all sci-fi copy across all pages (see Section 4.5 table)

### Phase 3: Landing + Auth (1 day)
- [ ] Revamp `LandingPage.tsx` — add product visual, pipeline walkthrough, credibility points
- [ ] Revamp `AuthPage.tsx` — clean form, human copy, remove excess decoration
- [ ] Revamp `ProfilePage.tsx` — simplify

### Phase 4: Pipeline Pages — Data Flow (2-3 days)
- [ ] `Stage1Data.tsx` — progressive disclosure, summary card, simplified upload
- [ ] `ModifyDemand.tsx` — summary-first, auto-save, parameter grouping
- [ ] `PreviewDemand.tsx` — differentiate from Modify, add CTA

### Phase 5: Pipeline Pages — ML Flow (2-3 days)
- [ ] `Stage2Training.tsx` — three-state layout, simplify sweep mode
- [ ] `Stage3Deployment.tsx` (Evaluate) — unified layout, hero Oracle %
- [ ] `DeploymentDashboard.tsx` — reduce KPIs, tab-based detail panel, clear terminology
- [ ] `PageCopilot.tsx` — FAB simplification, panel size/readability, quick action pills

---

## Appendix A: File Inventory

| File | Lines | Complexity | Priority |
|------|-------|------------|----------|
| `Stage2Training.tsx` | 1,177 | Very High | P1 |
| `DeploymentDashboard.tsx` | 1,053 | Very High | P1 |
| `Stage3Deployment.tsx` | 644 | High | P1 |
| `ModifyDemand.tsx` | 574 | High | P2 |
| `Stage1Data.tsx` | 507 | High | P2 |
| `PageCopilot.tsx` | 374 | Medium | P2 |
| `PreviewDemand.tsx` | 252 | Medium | P3 |
| `DataUpload.tsx` | 212 | Medium | P3 |
| `Header.tsx` | 203 | Medium | P1 |
| `Sidebar.tsx` | 146 | Low | P1 |
| `AuthPage.tsx` | 145 | Low | P2 |
| `ProfilePage.tsx` | 120 | Low | P3 |
| `index.css` | 117 | Low | P0 |
| `LandingPage.tsx` | 106 | Low | P2 |
| `HomeDashboard.tsx` | 104 | Low | P2 |
| `App.tsx` | 74 | Low | — |
| `StageNav.tsx` | 49 | Low | P1 |

## Appendix B: Tech Stack Reference

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 18.3.1 |
| Bundler | Vite | 7.3.0 |
| Styling | Tailwind CSS | 3.4.17 |
| Components | shadcn/ui (Radix) | Various |
| Routing | Wouter | 3.3.5 |
| State | TanStack Query | 5.60.5 |
| Charts | Recharts | 2.15.4 |
| Animation | Framer Motion | 11.18.2 (installed but underused) |
| Icons | Lucide React | 0.453.0 |
| Forms | React Hook Form + Zod | Latest |
| Real-time | Socket.io Client | 4.8.3 |
| Backend (RL) | FastAPI + PyTorch | — |
| Backend (App) | Express 5 + Drizzle ORM | — |
| Database | PostgreSQL | — |
| Queue | RabbitMQ + amqplib | — |

## Appendix C: What NOT to Change

- **Routing structure**: Keep all current routes (`/upload`, `/modify`, `/train`, etc.).
- **API contracts**: No changes to API calls or data shapes.
- **State management**: Keep TanStack Query + local state pattern.
- **Backend**: Zero backend changes.
- **Functionality**: Every feature that exists today must continue to work.
- **Framer Motion**: It's installed but barely used — leverage it more for page transitions and micro-interactions during the revamp, but don't add it as a hard dependency for basic functionality.
