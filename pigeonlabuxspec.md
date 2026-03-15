# PigeonLab: User Experience Design Specification

## Companion Document to the Platform Architecture Spec

---

## The Design Problem

PigeonLab must serve three very different people at the same desk:

| User | Comfort Level | What They Need | What Scares Them |
|------|--------------|----------------|------------------|
| **PI / Lead Researcher** | Technically literate, data-focused | Publication-quality exports, full control over analysis parameters, reproducibility manifests | Nothing — they want power |
| **PhD / Lab Members** | Moderate comfort, learns fast | Efficient daily workflows, behavior labeling, identity review, spatial analysis | Poorly organized interfaces, ambiguous system state |
| **Undergraduate / Visitor** | Uses phone for everything, minimal computer experience | Simple tasks: "process these videos," "check if pigeons are labeled correctly," "show me the heatmap" | Anything that looks like a terminal, spreadsheet, or settings panel |

### The Core UX Principle

**One app, progressive complexity.** The undergraduate sees a simple, friendly interface. The PhD student discovers more tools as they need them. The PI can access everything. Nobody sees complexity they don't need yet.

This is not three different apps. It's one app with **three layers of depth**:

```
Surface:     Big buttons, plain language, visual feedback
             (undergrad can do everything here)
                          │
                          ▼
Standard:    Tables, filters, batch operations, configuration
             (PhD students live here)
                          │
                          ▼
Advanced:    Training pipeline, benchmarks, raw SQL, API access
             (PI and power users)
```

---

## Visual Design Language

### Style: Clean Modern + Scientific Warmth

The aesthetic should feel like a mix of **Notion** (clean, modern, breathing room) and **a well-designed lab notebook** (data-dense when needed but never cluttered).

| Design Element | Choice | Why |
|----------------|--------|-----|
| Font | Inter (UI), JetBrains Mono (data/code) | Clean, highly readable at all sizes |
| Colors | Soft neutrals (warm grays, off-white) with one accent color (teal #0D9488) | Non-intimidating, professional, not "techy dark mode" |
| Icons | Lucide icon set | Simple, friendly, consistent |
| Spacing | Generous whitespace, 16px base grid | Reduces visual overwhelm |
| Cards | Rounded corners (8px), subtle shadows | Modern, approachable |
| Data tables | Alternating row shading, sticky headers | Readable even with lots of data |
| Charts | Soft colors, clear labels, hover tooltips | Accessible to non-data people |
| Empty states | Friendly illustrations + "here's what to do next" | Never a blank screen |
| Loading states | Skeleton screens, not spinners | Feels faster, less anxious |
| Error states | Plain language, suggested fix, no stack traces | "We couldn't find any pigeons in this video. Try a different one?" |

### Color Palette

```
Background:     #FAFAF9 (warm off-white)
Surface:        #FFFFFF (cards, panels)
Border:         #E7E5E4 (subtle warm gray)
Text Primary:   #1C1917 (near-black, warm)
Text Secondary: #78716C (warm gray)
Accent:         #0D9488 (teal — friendly, scientific, not corporate)
Success:        #16A34A (green)
Warning:        #F59E0B (amber)
Error:          #DC2626 (red, used sparingly)
Pigeon Overlay: #6366F1 (indigo, distinct from background in video)
```

### Typography Scale

```
Page Title:     24px / 700 weight
Section Title:  18px / 600 weight
Card Title:     16px / 600 weight
Body:           14px / 400 weight
Caption:        12px / 400 weight
Data/Mono:      13px / 400 weight (JetBrains Mono)
Button:         14px / 500 weight
```

---

## Navigation: Task-Oriented, Not Layer-Oriented

### What The Architecture Spec Had (Wrong for Users)

```
Ingestion | Review | Analysis | Training | Export
```

This is organized by system layer. A user doesn't think "I need to go to the Review module." They think "I need to check if the system got the pigeons right in today's videos."

### What Users Actually Need

The navigation is organized around **what the user wants to accomplish**:

```
┌──────────────────────────────────────────────────┐
│  🏠 Home     📹 Videos     🐦 Pigeons     📊 Insights  │
│                                                          │
│  (visible to everyone)                                   │
│                                                          │
│  ⚙️ Lab Setup  (visible in settings menu)                │
│  🧪 Training   (visible to advanced users)               │
└──────────────────────────────────────────────────┘
```

### Navigation Structure

| Tab | What It Does | Who Uses It | Complexity |
|-----|-------------|-------------|------------|
| **Home** | Dashboard: today's status, recent activity, things that need attention | Everyone | Surface |
| **Videos** | Add videos, see processing status, watch with overlays | Everyone | Surface → Standard |
| **Pigeons** | See all known pigeons, their profiles, identity management | Everyone (view) / PhD+ (edit) | Surface → Standard |
| **Insights** | Heatmaps, behavior timelines, zone analysis, droppings maps, exports | Everyone (view) / PhD+ (configure) | Surface → Advanced |
| **Lab Setup** | Arena zones, camera config, behavior rules, thresholds | PI / PhD | Standard → Advanced |
| **Training** | Clip library, labeling, model training, benchmarks | PI / Advanced PhD | Advanced |

---

## Screen-by-Screen Design

### Home (The First Thing Everyone Sees)

This is the most important screen. If this feels friendly, the whole app feels friendly.

```
┌─────────────────────────────────────────────────────────┐
│  🏠 Good morning, Lab                                    │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │  📹 12 videos   │  │  🐦 4 pigeons    │               │
│  │  processed today │  │  tracked         │               │
│  └─────────────────┘  └─────────────────┘               │
│                                                          │
│  ⚡ Needs Your Attention (3)                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │  🟡 2 videos have unconfirmed pigeon identities   │   │
│  │     [Review Now →]                                │   │
│  │                                                    │   │
│  │  🟡 5 frames flagged for quality check             │   │
│  │     [Check Frames →]                              │   │
│  │                                                    │   │
│  │  🟢 Droppings detection ready for benchmarking     │   │
│  │     [Run Benchmark →]                             │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  📊 Quick Stats This Week                               │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Alpha: 68% feeder area, 12% perch               │   │
│  │  Beta:  45% open floor, 30% nesting corner        │   │
│  │  [See Full Insights →]                            │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  🕐 Recent Activity                                     │
│  │  10:32 AM  Processed overhead_session12.mp4  ✅      │
│  │  10:28 AM  Processed side_session12.mp4      ✅      │
│  │   9:15 AM  You confirmed Beta's identity     ✅      │
│  │  Yesterday  Trained behavior model v3        ✅      │
└─────────────────────────────────────────────────────────┘
```

#### Design Notes

- **"Needs Your Attention"** is the most important element. It tells the user exactly what to do next. An undergraduate can follow these links without understanding the system architecture.
- **No jargon.** "Unconfirmed pigeon identities" not "placeholder assignments pending review." "Quality check" not "QC flags."
- **Color-coded status dots.** 🟡 = needs action, 🟢 = ready/info, 🔴 = problem.
- **Quick Stats** gives the PI a reason to glance at the home screen daily.

---

### Videos Tab

#### Simple View (What the Undergraduate Sees)

```
┌─────────────────────────────────────────────────────────┐
│  📹 Videos                              [+ Add Videos]   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  🔍 Search videos...                              │   │
│  │                                                    │   │
│  │  Today                                            │   │
│  │  ┌────────────────────────────────────────────┐   │   │
│  │  │ 🎬 overhead_session12.mp4                   │   │   │
│  │  │    4 pigeons found · 503 frames · ✅ Done   │   │   │
│  │  │    [Watch ▶]  [See Pigeons]                 │   │   │
│  │  └────────────────────────────────────────────┘   │   │
│  │  ┌────────────────────────────────────────────┐   │   │
│  │  │ 🎬 side_session12.mp4                       │   │   │
│  │  │    4 pigeons found · 510 frames · 🟡 Review │   │   │
│  │  │    [Watch ▶]  [Review Identity]             │   │   │
│  │  └────────────────────────────────────────────┘   │   │
│  │                                                    │   │
│  │  Yesterday                                        │   │
│  │  ┌────────────────────────────────────────────┐   │   │
│  │  │ 🎬 overhead_session11.mp4                   │   │   │
│  │  │    4 pigeons · 498 frames · ✅ Approved     │   │   │
│  │  │    [Watch ▶]  [See Pigeons]                 │   │   │
│  │  └────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

#### Add Videos Flow (Guided, Non-Intimidating)

```
Step 1 of 3: Choose Videos
┌──────────────────────────────────────────────────┐
│                                                    │
│     📁 Drag videos here, or click to browse        │
│                                                    │
│     Supports: MP4, AVI, MOV                        │
│                                                    │
└──────────────────────────────────────────────────┘
   3 videos selected

Step 2 of 3: Which camera?
┌──────────────────────────────────────────────────┐
│  overhead_session13.mp4    →  [Overhead ▾]        │
│  side_session13.mp4        →  [Side ▾]            │
│  corner_session13.mp4      →  [Corner ▾]          │
└──────────────────────────────────────────────────┘
   PigeonLab guessed the cameras from the filenames.
   Fix any that are wrong.

Step 3 of 3: How many pigeons?
┌──────────────────────────────────────────────────┐
│  How many pigeons should we look for?             │
│                                                    │
│     [ 4 ]  (same as last time)                    │
│                                                    │
│  What should we call them?                        │
│     🐦 pigeon  (you can change this later)        │
└──────────────────────────────────────────────────┘

                              [Process Videos →]
```

#### Video Player (With Overlays)

```
┌─────────────────────────────────────────────────────────┐
│  📹 overhead_session12.mp4                               │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │                                                    │   │
│  │            [Video frame with colored                │   │
│  │             mask overlays on each pigeon            │   │
│  │             and name labels: Alpha, Beta,           │   │
│  │             Gamma, Delta]                           │   │
│  │                                                    │   │
│  ├──────────────────────────────────────────────────┤   │
│  │  ◀ ▶  ││  ───●─────────────────── 2:34 / 5:12  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  Frame 152 of 503                                        │
│                                                          │
│  Pigeons in this frame:                                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                   │
│  │Alpha │ │Beta  │ │Gamma │ │Delta │                    │
│  │feeder│ │floor │ │perch │ │corner│                    │
│  │moving│ │still │ │still │ │moving│                    │
│  └──────┘ └──────┘ └──────┘ └──────┘                   │
│                                                          │
│  🟡 Frame 152: Possible overlap between Alpha and Beta  │
│     [Looks Fine]  [Fix This]                            │
└─────────────────────────────────────────────────────────┘
```

---

### Pigeons Tab

#### Gallery View (Default — Friendly)

```
┌─────────────────────────────────────────────────────────┐
│  🐦 Your Pigeons                       [+ Register New]  │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐                       │
│  │             │  │             │                        │
│  │  [Photo     │  │  [Photo     │                        │
│  │   crop of   │  │   crop of   │                        │
│  │   Alpha]    │  │   Beta]     │                        │
│  │             │  │             │                        │
│  │  Alpha      │  │  Beta       │                        │
│  │  Red band L │  │  Blue band L│                        │
│  │  Seen: 47   │  │  Seen: 43   │                        │
│  │  sessions   │  │  sessions   │                        │
│  │             │  │             │                        │
│  │  Favorite:  │  │  Favorite:  │                        │
│  │  feeder     │  │  open floor │                        │
│  │  (68%)      │  │  (45%)      │                        │
│  └─────────────┘  └─────────────┘                       │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐                       │
│  │  [Gamma]    │  │  [Delta]    │                        │
│  │  Green R    │  │  No marker  │                        │
│  │  38 sessions│  │  41 sessions│                        │
│  │  perch 52%  │  │  nesting 39%│                        │
│  └─────────────┘  └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

#### Pigeon Profile (Click into a pigeon)

```
┌─────────────────────────────────────────────────────────┐
│  🐦 Alpha                                [Edit Profile]  │
│  Red leg band, left leg                                  │
│                                                          │
│  ┌─ Where Alpha Spends Time ──────────────────────┐     │
│  │                                                  │     │
│  │    [Heatmap of arena with Alpha's position       │     │
│  │     density shown as warm colors]                │     │
│  │                                                  │     │
│  │  feeder ████████████████████░░░░ 68%              │     │
│  │  perch  ████████░░░░░░░░░░░░░░░ 18%              │     │
│  │  floor  ████░░░░░░░░░░░░░░░░░░░  9%              │     │
│  │  other  ██░░░░░░░░░░░░░░░░░░░░░  5%              │     │
│  └──────────────────────────────────────────────────┘     │
│                                                          │
│  ┌─ What Alpha Does ─────────────────────────────┐      │
│  │                                                 │      │
│  │  [Behavior timeline — horizontal bars showing   │      │
│  │   feeding, resting, walking episodes over time] │      │
│  │                                                 │      │
│  │  Feeding:   12.3 min avg/session                │      │
│  │  Resting:   8.1 min avg/session                 │      │
│  │  Walking:   4.2 min avg/session                 │      │
│  │  Near Beta: 2.8 min avg/session                 │      │
│  └─────────────────────────────────────────────────┘      │
│                                                          │
│  ┌─ Identity Confidence ─────────────────────────┐      │
│  │  Confirmed in 42 of 47 sessions (89%)          │      │
│  │  5 sessions still unconfirmed                   │      │
│  │  [Review Unconfirmed →]                         │      │
│  └─────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

---

### Insights Tab

#### Overview (Default View)

```
┌─────────────────────────────────────────────────────────┐
│  📊 Insights                                             │
│                                                          │
│  ┌─ Time Range ──────────────────────────────────┐      │
│  │  [This Week ▾]   [All Cameras ▾]              │      │
│  └────────────────────────────────────────────────┘      │
│                                                          │
│  ┌─ Zone Heatmap ────────────────────────────────┐      │
│  │                                                 │      │
│  │  [Arena diagram with combined pigeon density    │      │
│  │   shown as heat colors. Zone boundaries drawn.  │      │
│  │   Click a zone to see which pigeons use it.]    │      │
│  │                                                 │      │
│  │  [Alpha ●] [Beta ●] [Gamma ●] [Delta ●] [All] │      │
│  └─────────────────────────────────────────────────┘      │
│                                                          │
│  ┌─ Behavior Summary ───────────────────────────┐       │
│  │                                                │       │
│  │  [Stacked bar chart: time spent in each        │       │
│  │   behavior per pigeon this week]               │       │
│  │                                                │       │
│  └────────────────────────────────────────────────┘       │
│                                                          │
│  ┌─ Social Map ──────────────────────────────────┐      │
│  │                                                 │      │
│  │  [Network diagram: pigeons as nodes, line       │      │
│  │   thickness = time spent near each other]       │      │
│  │                                                 │      │
│  │  Alpha ←——thick——→ Beta                         │      │
│  │  Gamma ←——thin——→ Delta                         │      │
│  └─────────────────────────────────────────────────┘      │
│                                                          │
│  ┌─ Droppings Map ───────────────────────────────┐      │
│  │  [Arena with droppings density overlay]         │      │
│  │  Most droppings: nesting corner (34%)           │      │
│  │  ⚠️ Not yet benchmarked — treat as preliminary  │      │
│  └─────────────────────────────────────────────────┘      │
│                                                          │
│  [Export This View as PDF]  [Export Data as CSV]         │
└─────────────────────────────────────────────────────────┘
```

---

### Identity Review Flow (The Most Important Review Task)

This is the task that replaces EZannot for identity confirmation. It must be dead simple.

```
┌─────────────────────────────────────────────────────────┐
│  🐦 Confirm Pigeon Identities                            │
│  side_session12.mp4 · 4 pigeons detected                │
│                                                          │
│  We found 4 pigeons in this video. Please confirm       │
│  which pigeon is which.                                  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │                                                    │   │
│  │  [Video frame showing pigeon #1 highlighted       │   │
│  │   with a colored outline]                          │   │
│  │                                                    │   │
│  │  ◀  Pigeon 1 of 4  ▶                              │   │
│  │                                                    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  This pigeon is:                                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │  Alpha   │  │  Beta    │  │  Gamma   │  │ Delta  │  │
│  │  Red L   │  │  Blue L  │  │  Green R │  │ None   │  │
│  │  [crop]  │  │  [crop]  │  │  [crop]  │  │ [crop] │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                                                          │
│  Not sure? [Skip for Now]   [This is a New Pigeon]      │
│                                                          │
│  ─────────────────────────────────────────────           │
│  Already confirmed:                                      │
│  ✅ Pigeon 2 → Beta                                     │
│  ✅ Pigeon 3 → Gamma                                    │
│  ⬜ Pigeon 4 → (not yet confirmed)                      │
│                                                          │
│                                    [Done with this Video] │
└─────────────────────────────────────────────────────────┘
```

#### Why This Works for Non-Technical Users

- **One pigeon at a time.** Not a grid of 4 pigeons with dropdown menus.
- **Visual matching.** Show the pigeon from the video next to reference photos of known pigeons.
- **Plain language.** "This pigeon is:" not "Assign persistent cross-session identity."
- **Easy escape hatches.** "Skip for Now" and "This is a New Pigeon" handle uncertainty without forcing a wrong choice.
- **Progress indicator.** "Pigeon 1 of 4" and checkmarks below show what's done.

---

### QC Flag Review (Simplified)

The engineering term "QC flag" becomes "Needs Your Attention" in the UI.

```
┌─────────────────────────────────────────────────────────┐
│  ⚡ Needs Your Attention                                 │
│  5 items across 2 videos                                │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  🟡 Pigeon might have been lost                    │   │
│  │     overhead_session12.mp4 · Frame 234             │   │
│  │     We found 3 pigeons instead of 4                │   │
│  │                                                    │   │
│  │  [Video frame with 3 highlighted pigeons]          │   │
│  │                                                    │   │
│  │  What happened?                                    │   │
│  │  [Pigeon is hidden]  [Pigeon left frame]           │   │
│  │  [System made a mistake]  [I'm not sure]           │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  🟡 Two pigeons might be overlapping               │   │
│  │     overhead_session12.mp4 · Frame 287             │   │
│  │                                                    │   │
│  │  [Video frame with overlapping masks]              │   │
│  │                                                    │   │
│  │  [Looks correct]  [Fix the masks]                  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

#### Translation Table: Engineering → User Language

| Engineering Term | User-Facing Language |
|------------------|---------------------|
| QC flag | "Needs your attention" |
| count_mismatch (HIGH) | "Pigeon might have been lost" |
| mask_overlap (HIGH) | "Two pigeons might be overlapping" |
| area_jump (MEDIUM) | "A pigeon's outline changed suddenly" |
| centroid_jump (MEDIUM) | "A pigeon might have jumped unexpectedly" |
| mask_disappearance (HIGH) | "A pigeon disappeared" |
| border_clipping (LOW) | "A pigeon is at the edge of the frame" |
| area_too_small (MEDIUM) | "A detection looks too small to be a pigeon" |
| area_too_large (MEDIUM) | "A detection looks too large" |
| placeholder identity | "Unconfirmed pigeon" |
| review_status: raw | "Not yet checked" |
| review_status: reviewed | "Checked" |
| review_status: approved | "Confirmed" |
| confidence threshold | "How sure the system needs to be" |
| re-inference | "Apply to all videos" |
| behavior classifier | "Behavior model" |
| benchmark | "Accuracy check" |

---

## Progressive Disclosure: How Complexity Is Revealed

### Level 1: Surface (Everyone)

Accessible from the main navigation with no clicks into settings.

| Feature | How It Appears |
|---------|---------------|
| Watch a video with pigeon overlays | Big "Watch ▶" button on every video card |
| See where pigeons spend time | Heatmap on pigeon profile, one click from Pigeons tab |
| Confirm pigeon identity | Guided flow from "Needs Your Attention" or video card |
| Check flagged frames | "Needs Your Attention" cards with plain language and buttons |
| See quick stats | Home dashboard |
| Add new videos | [+ Add Videos] button with drag-and-drop wizard |

### Level 2: Standard (PhD Students)

Accessible from within Surface features via "Show More" or filter/sort controls.

| Feature | How It Appears |
|---------|---------------|
| Filter videos by session, camera, status | Filter bar at top of Videos tab |
| Compare sessions side-by-side | "Compare" button in Insights tab |
| View detailed behavior timelines | Click into a behavior bar on pigeon profile |
| Export CSV / COCO / overlay videos | "Export" buttons within each Insights view |
| Edit arena zones | Settings → Lab Setup → Arena Configuration |
| Adjust behavior thresholds | Settings → Lab Setup → Behavior Rules |
| Review all QC flags (not just highlights) | "See All" link at bottom of Needs Attention |

### Level 3: Advanced (PI / Power Users)

Accessible from Settings menu or dedicated Training tab.

| Feature | How It Appears |
|---------|---------------|
| Clip library and behavior labeling | Training tab in navigation |
| Train behavior classifier | Training → Launch Training |
| Compare model versions | Training → Model History |
| Apply model to archive | Training → Apply to All Videos |
| Run benchmarks | Settings → Benchmarks |
| View benchmark results | Settings → Benchmarks → Results |
| Edit camera configurations | Settings → Lab Setup → Cameras |
| View raw database queries | Settings → Advanced → Database Browser |
| Download reproducibility manifest | Export → Reproducibility Manifest |

---

## Onboarding: First-Time Experience

When PigeonLab is opened for the first time, the user sees a guided setup wizard — not the empty Home dashboard.

### Welcome Flow

```
Screen 1: Welcome
┌──────────────────────────────────────────────────┐
│                                                    │
│        🐦 Welcome to PigeonLab                     │
│                                                    │
│   Let's set up your lab so PigeonLab              │
│   can start analyzing your pigeon videos.          │
│                                                    │
│   This will take about 5 minutes.                  │
│                                                    │
│              [Get Started →]                        │
│                                                    │
└──────────────────────────────────────────────────┘

Screen 2: Register Your Pigeons
┌──────────────────────────────────────────────────┐
│  How many pigeons do you have?                     │
│                                                    │
│         [ 4 ]                                      │
│                                                    │
│  Give each one a name:                             │
│  🐦 1: [Alpha    ]  Markings: [Red band, left  ]  │
│  🐦 2: [Beta     ]  Markings: [Blue band, left ]  │
│  🐦 3: [Gamma    ]  Markings: [Green band, right]  │
│  🐦 4: [Delta    ]  Markings: [No marker       ]  │
│                                                    │
│  You can always add or change pigeons later.       │
│                                                    │
│         [← Back]           [Next →]                │
└──────────────────────────────────────────────────┘

Screen 3: Describe Your Arena
┌──────────────────────────────────────────────────┐
│  Where are things in your arena?                   │
│                                                    │
│  [Interactive rectangle representing the arena.    │
│   User drags to create named zones:                │
│   "Feeder," "Water," "Perch," "Nesting Corner."   │
│   Zones get auto-colored.]                         │
│                                                    │
│  Click and drag to mark areas.                     │
│  Name each area so PigeonLab knows what's where.   │
│                                                    │
│  ✅ Feeder area (green)                            │
│  ✅ Water area (blue)                              │
│  ✅ Perch (orange)                                 │
│  [+ Add another area]                              │
│                                                    │
│         [← Back]           [Next →]                │
└──────────────────────────────────────────────────┘

Screen 4: Add Your First Videos
┌──────────────────────────────────────────────────┐
│  Drop some pigeon videos here to get started.      │
│                                                    │
│     📁 Drag videos here, or click to browse        │
│                                                    │
│  PigeonLab will find the pigeons, track them,      │
│  and start building your lab's dataset.             │
│                                                    │
│  You can always add more videos later.             │
│                                                    │
│         [← Back]        [Start Processing →]       │
└──────────────────────────────────────────────────┘

Screen 5: Processing
┌──────────────────────────────────────────────────┐
│  🎉 PigeonLab is analyzing your videos!             │
│                                                    │
│  overhead_session01.mp4  ████████████░░░  78%      │
│  side_session01.mp4      ████░░░░░░░░░░  32%      │
│                                                    │
│  This might take a few minutes.                    │
│  We'll let you know when it's ready.               │
│                                                    │
│  What's happening:                                 │
│  ✅ Finding pigeons in each frame                  │
│  🔄 Tracking pigeons through the video             │
│  ⬜ Checking for problems                          │
│  ⬜ Computing positions and zones                  │
│                                                    │
│         [Go to Home — we'll notify you]            │
└──────────────────────────────────────────────────┘
```

---

## Accessibility & Usability Details

### For the Phone-Primary User

| Challenge | Solution |
|-----------|----------|
| Not used to desktop apps | Large click targets (minimum 44px), generous spacing |
| Intimidated by data tables | Default to card views and visual summaries; tables are opt-in |
| Won't read documentation | Every feature has inline help tooltips (hover on desktop, tap on ?) |
| Confused by status systems | Color-coded dots with plain text: 🟢 Done, 🟡 Needs attention, 🔴 Problem |
| Afraid of breaking things | All destructive actions require confirmation ("Are you sure you want to remove this?") |
| Doesn't know keyboard shortcuts | Everything is mouse/click accessible; shortcuts are bonus, not required |

### For the PhD Researcher

| Challenge | Solution |
|-----------|----------|
| Needs efficient batch workflows | Multi-select in video list, batch approve/reject |
| Wants keyboard shortcuts | Documented in Settings → Keyboard Shortcuts |
| Needs export flexibility | Export button on every view with format options |
| Wants to configure thresholds | Lab Setup section with sliders and live preview |
| Needs reproducibility | Every export includes a manifest of settings used |

### For the PI

| Challenge | Solution |
|-----------|----------|
| Needs publication-quality outputs | High-resolution heatmap export, customizable color scales |
| Wants to see lab-wide trends | Session comparison in Insights tab |
| Needs to audit what happened | Activity log on Home, review history on every entity |
| Wants to train custom models | Full Training tab with readiness checks and evaluation reports |

---

## Error Handling: Always Friendly

Every error message follows this template:

```
What happened (plain language)
Why it might have happened (one sentence)
What to do next (one clear action)
```

### Examples

```
❌ We couldn't find any pigeons in this video.
   The video might be too dark or the camera angle might be unusual.
   [Try a Different Video]  [Adjust Settings]

❌ Processing failed for side_session12.mp4.
   The video file might be corrupted or in an unsupported format.
   [Try Again]  [Skip This Video]  [Get Help]

⚠️ We're not very confident about this pigeon's identity.
   This pigeon doesn't look much like any of your registered pigeons.
   [Confirm Anyway]  [This is a New Pigeon]  [Skip for Now]

⚠️ The droppings detector hasn't been tested on your videos yet.
   Results might not be accurate until you run an accuracy check.
   [Run Accuracy Check]  [Show Results Anyway (Preliminary)]
```

---

## Implementation Notes for Developers

### Frontend Stack

| Component | Technology |
|-----------|-----------|
| Framework | React 18+ with TypeScript |
| Styling | Tailwind CSS (utility-first, matches design tokens above) |
| Components | shadcn/ui (clean, accessible, customizable) |
| Charts | Recharts (simple) + Plotly (heatmaps) |
| Video | HTML5 video with custom controls for frame scrubbing |
| State | React Query for server state, Zustand for UI state |
| Routing | React Router |
| Build | Vite |

### Backend API Structure

The FastAPI backend exposes clean REST endpoints that the frontend consumes. The frontend never touches SQLite directly.

```
GET  /api/videos                    → List all videos with status
POST /api/videos/process            → Start processing a video
GET  /api/videos/{id}               → Video details + frame list
GET  /api/videos/{id}/frame/{n}     → Frame image with optional overlay

GET  /api/pigeons                   → List all pigeons with profiles
GET  /api/pigeons/{id}              → Pigeon profile with stats
PUT  /api/pigeons/{id}              → Update pigeon profile

GET  /api/insights/heatmap          → Heatmap data for specified pigeons/timerange
GET  /api/insights/behaviors        → Behavior summary data
GET  /api/insights/pairwise         → Pairwise distance/interaction data
GET  /api/insights/droppings        → Droppings heatmap data

GET  /api/review/attention          → Items needing attention (QC flags + unconfirmed IDs)
POST /api/review/identity           → Confirm/reject/reassign identity
POST /api/review/qc-flag            → Resolve a QC flag
POST /api/review/behavior           → Confirm/reject a behavior event

GET  /api/training/clips            → Clip library
POST /api/training/label            → Label a clip
POST /api/training/start            → Launch training run
GET  /api/training/models           → Model registry

GET  /api/export/{format}           → Generate export in specified format
```

---

## Summary: The Design Principles

1. **Task-oriented, not architecture-oriented.** Users think in tasks, not system layers.
2. **Progressive disclosure.** Simple by default, powerful on demand.
3. **Plain language everywhere.** No jargon in the UI. Engineering terms stay in the code.
4. **One pigeon at a time.** Review flows handle one item at a time, not overwhelming grids.
5. **Always show what to do next.** Home dashboard and "Needs Your Attention" queue.
6. **Never a blank screen.** Empty states have helpful illustrations and next-step guidance.
7. **Friendly error messages.** What happened, why, what to do.
8. **Visual-first, data-on-demand.** Heatmaps and timelines first, raw numbers available when asked.
9. **Safe to explore.** Nothing breaks from clicking around. All destructive actions need confirmation.
10. **Works for the person who only knows TikTok AND the person writing the paper.**
