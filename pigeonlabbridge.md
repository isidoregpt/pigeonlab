# PigeonLab: Implementation Bridge

## Reconciling Architecture + UX into a Buildable Specification

### Companion to: Platform Architecture Spec + UX Design Spec

---

## Purpose of This Document

The architecture spec defines **what the system is**. The UX spec defines **how humans use it**. This document bridges the two by defining:

1. Role model and permissions
2. UX-to-database state mappings
3. Mask/track correction workflow (full screen-level spec)
4. Batch workflows
5. Comparison workflows
6. API contracts per screen
7. Implementation priority order

---

## 1. Role Model & Permissions

### Visibility vs Permission

PigeonLab uses a two-axis model: **visibility** (what you can see) and **permission** (what you can change). These are separate concerns.

| Axis | What It Controls | How It's Set |
|------|-----------------|-------------|
| Visibility | Which UI sections and features appear | Role-based: assigned per user account |
| Permission | Which actions the user can perform | Role-based: destructive actions require higher roles |

### Roles

| Role | Visibility Level | Who Gets It | Can View | Can Edit | Can Delete | Can Train Models |
|------|-----------------|-------------|----------|----------|------------|-----------------|
| **Viewer** | Surface | Undergrads, visitors, external collaborators | All videos, pigeons, insights, exports | Nothing | Nothing | No |
| **Reviewer** | Surface + Standard | Lab members, PhD students | Everything Viewer can + review queues, batch tools, lab setup | Confirm identities, resolve QC flags, label clips, approve behaviors | Reject detections (soft delete) | No |
| **Admin** | Surface + Standard + Advanced | PI, lead researcher, senior PhD | Everything | Everything Reviewer can + edit arena config, camera config, behavior rules, thresholds | Hard delete videos, reset identities, remove pigeons | Yes |

### Permission Matrix

| Action | Viewer | Reviewer | Admin |
|--------|--------|----------|-------|
| Watch videos with overlays | ✅ | ✅ | ✅ |
| View pigeon profiles | ✅ | ✅ | ✅ |
| View heatmaps and insights | ✅ | ✅ | ✅ |
| Export data (CSV, COCO, etc.) | ✅ | ✅ | ✅ |
| Add new videos for processing | ❌ | ✅ | ✅ |
| Confirm/reject pigeon identities | ❌ | ✅ | ✅ |
| Resolve QC flags | ❌ | ✅ | ✅ |
| Correct masks and tracks | ❌ | ✅ | ✅ |
| Label behavior clips | ❌ | ✅ | ✅ |
| Approve videos (final sign-off) | ❌ | ❌ | ✅ |
| Edit arena zones | ❌ | ❌ | ✅ |
| Edit behavior rule thresholds | ❌ | ❌ | ✅ |
| Register/remove pigeons | ❌ | ❌ | ✅ |
| Train behavior models | ❌ | ❌ | ✅ |
| Apply models to archive | ❌ | ❌ | ✅ |
| Run benchmarks | ❌ | ❌ | ✅ |
| Delete videos | ❌ | ❌ | ✅ |

### Implementation Note

For Phase 1-3 (local single-user or small lab), roles can be a simple config flag in `config/default.yaml` rather than a full authentication system:

```yaml
# config/default.yaml
users:
  default_role: "admin"          # Single-user labs: everyone is admin
  # For multi-user labs:
  # accounts:
  #   - name: "Dr. Smith"
  #     role: "admin"
  #   - name: "Alex (PhD)"
  #     role: "reviewer"
  #   - name: "Jordan (undergrad)"
  #     role: "viewer"
```

Full authentication (OAuth, lab SSO) is a Phase 4+ feature if needed.

---

## 2. UX-to-Database State Mappings

### Canonical Mapping

Every UI label maps to exactly one database value. This table is the single source of truth for frontend and backend developers.

#### Review Status

Every reviewable entity follows the same lifecycle:

```
RAW → REVIEWED → APPROVED
                ↘ REJECTED
```

| UI Label | UI Color | Database Value | Column | Meaning |
|----------|----------|----------------|--------|---------|
| Not yet checked | ⚪ Gray dot | `raw` | `review_status` | Model output, no human has looked at it |
| Checked | 🔵 Blue dot | `reviewed` | `review_status` | A human looked at it but didn't formally approve or reject |
| Confirmed | 🟢 Green dot | `approved` | `review_status` | A human confirmed this is correct |
| Rejected | 🔴 Red dot | `rejected` | `review_status` | A human marked this as wrong — excluded from downstream analysis |
| Needs attention | 🟡 Amber dot | `pending` | `review_tasks.status` | QC rule flagged this for human review |

**Downstream rule:** Any query that powers reports, exports, or insights must filter to `review_status = 'approved'` by default. `rejected` items are excluded from all analytics unless the user explicitly requests "include rejected."

**QC flag status is a separate enum.** The `qc_flags.review_status` column uses a QC workflow lifecycle (`pending` → `acknowledged` → `resolved`), not the entity review lifecycle (`raw` → `reviewed` → `approved` → `rejected`). These are different state machines:

| Enum | Used On | Values | Purpose |
|------|---------|--------|---------|
| Entity review status | Identities, behaviors, droppings, videos | `raw`, `reviewed`, `approved`, `rejected` | Tracks human trust level for this data |
| QC flag status | QC flags only | `pending`, `acknowledged`, `resolved` | Tracks whether the flagged issue has been addressed |
| Review task status | Review task queue | `pending`, `in_progress`, `completed` | Tracks work item progress |

Do not conflate these three enums in code. They serve different purposes even though some value names overlap.

#### Identity Status

| UI Label | Database Value | Column | Meaning |
|----------|---------------|--------|---------|
| Unconfirmed pigeon | `placeholder` | `video_assignments.match_method` | Auto-assigned, not yet human-verified |
| Confirmed | `manual` or `marker` or `appearance` with `review_status = approved` | | Human verified this identity |
| Suggested match | Any `match_method` with `confidence >= 0.85` and `review_status = raw` | | System is fairly sure but hasn't been confirmed |
| Unknown pigeon | `placeholder` with no known pigeon match | | System found a pigeon but doesn't know who it is |

#### Video Status

Videos have **two independent status fields** because processing and review are separate concerns. A video can fail processing (processing_status = `failed`) but still have no review status. A video can be successfully processed (processing_status = `completed`) but not yet reviewed (review_status = `raw`).

**Processing Status** (set by the pipeline, not by humans):

| UI Label | UI Badge | Database Column | Database Value | Meaning |
|----------|----------|-----------------|----------------|---------|
| Queued | ⏳ Clock | `processing_status` | `queued` | Waiting to be processed |
| Processing | 🔄 Spinner | `processing_status` | `processing` | SAM3 is running |
| Processed | ✅ Check | `processing_status` | `completed` | Pipeline finished successfully |
| Failed | 🔴 Red | `processing_status` | `failed` | Pipeline error — see logs |

**Review Status** (set by humans, independent of processing):

| UI Label | UI Badge | Database Column | Database Value | Meaning |
|----------|----------|-----------------|----------------|---------|
| Not yet checked | ⚪ Gray | `review_status` | `raw` | No human has reviewed this video |
| Checked | 🔵 Blue | `review_status` | `reviewed` | Someone looked at it |
| Approved | 🟢 Green | `review_status` | `approved` | PI/admin signed off |
| Rejected | 🔴 Red | `review_status` | `rejected` | Marked as unusable (bad video, wrong setup, etc.). Rejecting a video excludes it from default analytics and training eligibility but does not delete its raw artifacts. Admins can view and restore rejected videos. |

**Combined UI Badge:** The video card shows a composite badge:
- Processing not done → show processing status
- Processing done → show review status
- Processing failed → show "Failed" regardless of review status

**Database change required:** The `videos` table in the architecture spec needs `processing_status` added alongside the existing `review_status`:

```sql
-- Updated videos table (change from architecture spec)
ALTER TABLE videos ADD COLUMN processing_status TEXT DEFAULT 'queued';
-- Existing review_status column remains unchanged
```

#### Behavior Events

| UI Label | Database `source` | Database `review_status` |
|----------|------------------|-------------------------|
| Detected (rule) | `rule_engine` | `raw` |
| Detected (model) | `learned_model` | `raw` |
| Confirmed | Any | `approved` |
| Rejected | Any | `rejected` |

#### Droppings

| UI Label | Database `review_status` | Database `detection_method` |
|----------|-------------------------|----------------------------|
| Detected (preliminary) | `raw` | `sam3_text` |
| Confirmed | `approved` | Any |
| Rejected | `rejected` | Any |
| Not yet tested | N/A | Benchmark not yet run |

### Soft Delete Rule

This rule applies uniformly across all reviewable entities: detections, identities, behavior events, droppings, and videos.

| Principle | Behavior |
|-----------|----------|
| Soft delete never removes source data | The record stays in the database; raw masks/frames stay on disk |
| Soft delete sets `review_status = 'rejected'` | This is the only mechanism for "removing" an item from active use |
| Rejected items are excluded by default | Default insights, exports, and training queries filter to `approved` only |
| Rejected items are viewable by Reviewers and Admins | A filter toggle "Show rejected" reveals them in any list view |
| Admins can restore rejected items | Change `review_status` back to `reviewed` for re-evaluation |
| Hard delete is Admin-only | Limited to deleting entire videos or explicit cleanup actions |
| Hard delete is irreversible | Requires a confirmation dialog: "This will permanently remove the video and all associated data" |

**Why this matters:** In research, "wrong" data is still data. A rejected video might turn out to be useful later (different analysis, different question). Soft delete preserves the option to reconsider without risking accidental data loss.

### UI Label Convention: "Confirmed" vs "Approved"

Both words map to `review_status = 'approved'` in the database. The UI uses different words depending on context to feel natural:

| Context | UI Label | Database Value | Why This Word |
|---------|----------|----------------|---------------|
| Identity assignment | **Confirmed** | `approved` | "I confirmed this is Alpha" feels natural |
| Behavior event | **Confirmed** | `approved` | "I confirmed this is feeding" feels natural |
| Droppings detection | **Confirmed** | `approved` | "I confirmed this is a dropping" feels natural |
| Video (final sign-off) | **Approved** | `approved` | "I approved this video" implies authority |

**Implementation rule:** The database always stores `approved`. The frontend maps it to "Confirmed" or "Approved" based on the entity type. Do not create separate database values for these — they are the same state with different display labels.

### Frontend Implementation Rule

```
// The frontend NEVER shows raw database values to users.
// Always map through the canonical translation layer.

function getStatusLabel(review_status: string): string {
  const map = {
    'raw': 'Not yet checked',
    'reviewed': 'Checked',
    'approved': 'Confirmed',
    'rejected': 'Rejected',
    'pending': 'Needs attention',
    'processing': 'Processing',
    'failed': 'Failed'
  };
  return map[review_status] || review_status;
}

function getStatusColor(review_status: string): string {
  const map = {
    'raw': 'gray',
    'reviewed': 'blue',
    'approved': 'green',
    'rejected': 'red',
    'pending': 'amber',
    'processing': 'blue',
    'failed': 'red'
  };
  return map[review_status] || 'gray';
}
```

---

## 3. Mask/Track Correction Workflow (Full Spec)

This is the core EZannot replacement. It must be specified at the same level of detail as the identity review flow.

### When This Flow Is Triggered

- User clicks "Fix This" on a QC flag showing a mask problem
- User clicks "Fix Masks" while watching a video
- User clicks "Correct Track" on a pigeon profile
- Reviewer opens the review queue and selects a mask/track task

### Screen Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  🔧 Fix Masks & Tracks                                          │
│  overhead_session12.mp4 · Frame 234 of 503                      │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │              [Main video frame display]                    │  │
│  │              [Pigeon masks shown as colored overlays]      │  │
│  │              [Selected pigeon has highlighted border]      │  │
│  │              [Cursor changes based on active tool]         │  │
│  │                                                            │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  ◀◀  ◀  Frame 234  ▶  ▶▶    ───●──────────── 234/503    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Context Frames ─────────────────────────────────────────┐   │
│  │  [Frame 232] [Frame 233] [Frame 234*] [Frame 235] [236]  │   │
│  │  (thumbnail strip for quick visual context)               │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ Tools ───────────────┐  ┌─ Selected Pigeon ─────────────┐  │
│  │                        │  │                                │  │
│  │  [👆 Select] (default) │  │  🐦 Alpha (unconfirmed)       │  │
│  │  [✏️ Draw mask]        │  │  Area: 4,231 px               │  │
│  │  [🧹 Erase mask]      │  │  Zone: feeder area             │  │
│  │  [🔗 Merge tracks]    │  │  Confidence: 0.87              │  │
│  │  [✂️ Split track]     │  │                                │  │
│  │  [🗑️ Delete detection]│  │  [Change Identity ▾]           │  │
│  │                        │  │                                │  │
│  │  [↩️ Undo last edit]  │  │  Other pigeons in frame:       │  │
│  │  [↪️ Redo]            │  │  🐦 Beta  🐦 Gamma  🐦 Delta  │  │
│  │                        │  │                                │  │
│  └────────────────────────┘  └────────────────────────────────┘  │
│                                                                  │
│  ┌─ Edit History (this session) ────────────────────────────┐   │
│  │  1. Drew mask addition on frame 234 for Alpha             │   │
│  │  2. Erased overlap region on frame 234                    │   │
│  │  [↩️ Undo All]                                            │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  [Cancel (discard changes)]            [Save as Checked ✓]      │
│                                        [Save as Confirmed ✓✓]   │
└─────────────────────────────────────────────────────────────────┘
```

### Tool Behaviors

#### Select Tool (Default)

| Action | Result |
|--------|--------|
| Click on a pigeon mask | Select that pigeon — shows its info in the right panel |
| Click on empty area | Deselect all |
| Arrow keys left/right | Step one frame backward/forward |
| Scroll wheel | Zoom in/out on the frame |

#### Draw Mask Tool

| Action | Result |
|--------|--------|
| Click + drag on frame | Paint new mask pixels for the selected pigeon |
| Brush size | Adjustable via slider or `[` / `]` keys |
| Visual feedback | Green overlay appears where you paint |
| Constraint | Only paints on the currently selected pigeon's layer |

#### Erase Mask Tool

| Action | Result |
|--------|--------|
| Click + drag on frame | Remove mask pixels from the selected pigeon |
| Brush size | Adjustable via slider or `[` / `]` keys |
| Visual feedback | Red overlay appears where you erase |

#### Merge Tracks

```
Merge two pigeons' tracks into one.

Trigger: Select "Merge tracks" tool, then click two pigeons in the frame.

┌──────────────────────────────────────────────────┐
│  Merge Tracks                                      │
│                                                    │
│  Merge [Pigeon 3 (unconfirmed)] into [Alpha]?     │
│                                                    │
│  This will combine their masks from this frame     │
│  onward. Use this when the system accidentally     │
│  split one pigeon into two tracks.                 │
│                                                    │
│  [Cancel]                    [Merge →]             │
└──────────────────────────────────────────────────┘
```

#### Split Track

```
Split one pigeon's track into two at the current frame.

Trigger: Select "Split track" tool, then click a pigeon.

┌──────────────────────────────────────────────────┐
│  Split Track                                       │
│                                                    │
│  Split [Alpha]'s track at frame 234?               │
│                                                    │
│  Before frame 234: stays as Alpha                  │
│  From frame 234 onward: becomes a new              │
│  unconfirmed pigeon                                │
│                                                    │
│  Use this when the system accidentally merged      │
│  two different pigeons into one track.             │
│                                                    │
│  [Cancel]                    [Split →]             │
└──────────────────────────────────────────────────┘
```

#### Delete Detection

```
Remove a detection from this frame.

Trigger: Select "Delete detection" tool, then click a pigeon.

┌──────────────────────────────────────────────────┐
│  Remove Detection                                  │
│                                                    │
│  Remove this detection from frame 234?             │
│                                                    │
│  This is probably not a real pigeon. Removing it   │
│  will mark it as a false detection.                │
│                                                    │
│  [Cancel]                    [Remove]              │
└──────────────────────────────────────────────────┘
```

### Keyboard Shortcuts (for PhD/Power Users)

| Key | Action |
|-----|--------|
| `S` | Select tool |
| `D` | Draw mask tool |
| `E` | Erase mask tool |
| `[` / `]` | Decrease / increase brush size |
| `←` / `→` | Previous / next frame |
| `Shift + ←` / `→` | Jump 10 frames |
| `Ctrl + Z` | Undo |
| `Ctrl + Shift + Z` | Redo |
| `1-9` | Select pigeon 1-9 |
| `Space` | Toggle mask overlay visibility |
| `Enter` | Save as Checked |

### Audit Trail

Every edit is recorded in `track_edits`:

```json
{
  "edit_type": "draw_mask",
  "video_id": 12,
  "frame_idx": 234,
  "old_obj_id": 1,
  "editor": "Alex (PhD)",
  "edited_at": "2025-03-15T14:22:00",
  "details": {
    "pixels_added": 342,
    "tool": "draw",
    "brush_size": 12
  }
}
```

**Architecture spec change required:** The `track_edits` table needs a `details TEXT` column (JSON) to store tool-specific metadata like brush size, pixel counts, and merge/split parameters:

```sql
-- Add to track_edits table in architecture spec
ALTER TABLE track_edits ADD COLUMN details TEXT;  -- JSON: tool-specific edit metadata
```

---

## 4. Batch Workflows

PhD users need efficient bulk operations. These are accessible from the Standard visibility level.

### Batch Identity Confirmation

```
┌──────────────────────────────────────────────────────────┐
│  🐦 Batch Confirm Identities                              │
│  12 videos with unconfirmed pigeons                       │
│                                                            │
│  The system is fairly confident about these matches.       │
│  Review and confirm in bulk.                               │
│                                                            │
│  ☑️ session_10 overhead: Pigeon 1 → Alpha (92%)           │
│  ☑️ session_10 overhead: Pigeon 2 → Beta (89%)            │
│  ☑️ session_10 overhead: Pigeon 3 → Gamma (91%)           │
│  ☐  session_10 overhead: Pigeon 4 → Delta (78%) ⚠️       │
│  ☑️ session_11 overhead: Pigeon 1 → Alpha (95%)           │
│  ...                                                       │
│                                                            │
│  ☑️ Select all above 85% confidence                        │
│                                                            │
│  [Confirm Selected (8)]           [Review One by One]      │
└──────────────────────────────────────────────────────────┘
```

### Batch QC Resolution

```
┌──────────────────────────────────────────────────────────┐
│  ⚡ Batch Resolve: Border Clipping (Low Severity)         │
│  23 items across 8 videos                                 │
│                                                            │
│  These are all "pigeon near edge of frame" flags.         │
│  For most lab setups, these are normal and can be          │
│  acknowledged in bulk.                                     │
│                                                            │
│  ☑️ Select all 23 items                                    │
│                                                            │
│  [Acknowledge All (normal behavior)]                       │
│  [Review Individually]                                     │
└──────────────────────────────────────────────────────────┘
```

### Batch Export

```
┌──────────────────────────────────────────────────────────┐
│  📥 Export Data                                            │
│                                                            │
│  What to export:                                           │
│  ☑️ Spatial features (positions, velocities, zones)        │
│  ☑️ Behavior events                                        │
│  ☐  Raw masks (COCO format)                                │
│  ☐  Overlay videos                                         │
│  ☑️ Droppings data                                         │
│                                                            │
│  Which videos:                                             │
│  ● Confirmed videos only (recommended)                     │
│  ○ All processed videos (includes unreviewed)              │
│  ○ Selected sessions: [Choose ▾]                           │
│                                                            │
│  Which pigeons:                                            │
│  ● Confirmed identities only (recommended)                 │
│  ○ Include unconfirmed (placeholder IDs will be flagged)   │
│                                                            │
│  Format: [CSV ▾]                                           │
│                                                            │
│  ☑️ Include reproducibility manifest                        │
│                                                            │
│  [Export →]                                                │
└──────────────────────────────────────────────────────────┘
```

### Batch Clip Labeling

```
┌──────────────────────────────────────────────────────────┐
│  🏷️ Label Clips                                           │
│  47 unlabeled clips in library                            │
│                                                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│  │ [Clip ▶]   │  │ [Clip ▶]   │  │ [Clip ▶]   │          │
│  │ Alpha      │  │ Beta       │  │ Gamma      │          │
│  │ feeder     │  │ open floor │  │ perch      │          │
│  │            │  │            │  │            │          │
│  │ [Feeding▾] │  │ [Resting▾] │  │ [Preening▾]│          │
│  └────────────┘  └────────────┘  └────────────┘          │
│                                                            │
│  Quick label mode: click a clip, press a number key        │
│  1=Feeding  2=Resting  3=Walking  4=Preening               │
│  5=Courtship  6=Aggression  7=Other  0=Skip                │
│                                                            │
│  Progress: 12 of 47 labeled                                │
│  [Save and Continue Later]                                 │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Comparison Workflows

Research requires comparison. These views live in the Insights tab at the Standard visibility level.

### Session vs Session

```
┌──────────────────────────────────────────────────────────┐
│  📊 Compare Sessions                                       │
│                                                            │
│  [Session 10 (Mar 12) ▾]  vs  [Session 12 (Mar 14) ▾]    │
│                                                            │
│  ┌─ Zone Occupancy ──────────────────────────────────┐    │
│  │  Alpha:  feeder 68% → 52%  ⬇️ -16%                │    │
│  │  Beta:   floor  45% → 61%  ⬆️ +16%                │    │
│  │  Gamma:  perch  52% → 48%  ─  stable              │    │
│  │  Delta:  nest   39% → 42%  ─  stable              │    │
│  └────────────────────────────────────────────────────┘    │
│                                                            │
│  ┌─ Behavior Comparison ─────────────────────────────┐    │
│  │  [Side-by-side stacked bar charts:                 │    │
│  │   Session 10 behaviors vs Session 12 behaviors]    │    │
│  └────────────────────────────────────────────────────┘    │
│                                                            │
│  ┌─ Heatmap Comparison ──────────────────────────────┐    │
│  │  [Session 10 heatmap]    [Session 12 heatmap]      │    │
│  │  [Difference heatmap: what changed]                │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### Pigeon vs Pigeon

```
┌──────────────────────────────────────────────────────────┐
│  📊 Compare Pigeons                                        │
│                                                            │
│  [Alpha ▾]  vs  [Beta ▾]                                  │
│                                                            │
│  ┌─ Zone Preferences ───────────────────────────────┐     │
│  │  [Two heatmaps side by side]                      │     │
│  │  Alpha prefers feeder (68%) vs Beta's floor (45%) │     │
│  └───────────────────────────────────────────────────┘     │
│                                                            │
│  ┌─ Activity Levels ────────────────────────────────┐     │
│  │  Alpha: 14.2 mm/s avg velocity                    │     │
│  │  Beta:   8.7 mm/s avg velocity                    │     │
│  │  Alpha is 63% more active than Beta               │     │
│  └───────────────────────────────────────────────────┘     │
│                                                            │
│  ┌─ Time Near Each Other ───────────────────────────┐     │
│  │  [Timeline showing proximity events]              │     │
│  │  Average: 2.8 min/session within 100mm            │     │
│  └───────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────┘
```

### Model Version vs Model Version

```
┌──────────────────────────────────────────────────────────┐
│  🧪 Compare Behavior Models                                │
│                                                            │
│  [Model v1 (Mar 10) ▾]  vs  [Model v2 (Mar 14) ▾]       │
│                                                            │
│  ┌─ Overall Accuracy ───────────────────────────────┐     │
│  │  v1: 72.3%    →    v2: 81.6%    ⬆️ +9.3%         │     │
│  └───────────────────────────────────────────────────┘     │
│                                                            │
│  ┌─ Per-Class F1 ───────────────────────────────────┐     │
│  │  Feeding:    0.85 → 0.91  ⬆️                      │     │
│  │  Resting:    0.79 → 0.84  ⬆️                      │     │
│  │  Preening:   0.61 → 0.73  ⬆️                      │     │
│  │  Courtship:  0.42 → 0.55  ⬆️                      │     │
│  └───────────────────────────────────────────────────┘     │
│                                                            │
│  ┌─ Confusion Matrices ─────────────────────────────┐     │
│  │  [v1 confusion matrix]  [v2 confusion matrix]     │     │
│  └───────────────────────────────────────────────────┘     │
│                                                            │
│  [Set v2 as Active Model]   [Apply v2 to All Videos]      │
└──────────────────────────────────────────────────────────┘
```

### Pre-Review vs Approved Comparison

```
┌──────────────────────────────────────────────────────────┐
│  📊 Review Impact: session_12                              │
│                                                            │
│  How much did human review change the results?             │
│                                                            │
│  Identities changed:     2 of 4 (50%)                     │
│  Masks corrected:        3 frames                          │
│  Behaviors changed:      1 event rejected                  │
│  Droppings confirmed:    12 of 18 (67%)                    │
│                                                            │
│  This tells you how reliable the automated pipeline is.    │
│  Over time, this number should decrease as models improve. │
└──────────────────────────────────────────────────────────┘
```

---

## 6. API Contracts Per Screen

Every screen in the UX spec needs specific backend endpoints. This table maps screens to the API calls they require.

### Home Dashboard

| UI Element | API Call | Response |
|-----------|---------|----------|
| Video count today | `GET /api/stats/today` | `{videos_processed: 12, pigeons_tracked: 4}` |
| Needs attention count | `GET /api/review/attention/count` | `{total: 3, identity: 2, qc: 5, droppings: 1}` |
| Needs attention items | `GET /api/review/attention?limit=5` | List of attention items with type, description, link |
| Quick stats | `GET /api/stats/summary?period=week` | Per-pigeon zone occupancy percentages |
| Recent activity | `GET /api/activity?limit=10` | List of recent events with timestamps |

### Videos Tab

| UI Element | API Call | Response |
|-----------|---------|----------|
| Video list | `GET /api/videos?sort=date&page=1` | Paginated video list with status badges |
| Video detail | `GET /api/videos/{id}` | Video metadata + pigeon count + status |
| Video frame | `GET /api/videos/{id}/frame/{n}?overlay=true` | JPEG with mask overlays |
| Add videos | `POST /api/videos/process` | Job ID, processing starts async |
| Processing status | `GET /api/videos/{id}/status` | `{status: "processing", progress: 78}` |

### Pigeons Tab

| UI Element | API Call | Response |
|-----------|---------|----------|
| Pigeon gallery | `GET /api/pigeons` | List with name, markers, session count, top zone |
| Pigeon profile | `GET /api/pigeons/{id}` | Full profile with stats |
| Pigeon heatmap | `GET /api/pigeons/{id}/heatmap?period=week` | 2D density array |
| Pigeon behaviors | `GET /api/pigeons/{id}/behaviors?period=week` | Behavior summary with durations |
| Pigeon identity confidence | `GET /api/pigeons/{id}/identity-status` | Confirmed vs unconfirmed session counts |

### Insights Tab

| UI Element | API Call | Response |
|-----------|---------|----------|
| Combined heatmap | `GET /api/insights/heatmap?pigeons=all&period=week` | 2D density array |
| Behavior summary | `GET /api/insights/behaviors?period=week` | Per-pigeon behavior durations |
| Social map | `GET /api/insights/pairwise?period=week` | Pairwise proximity durations |
| Droppings map | `GET /api/insights/droppings?period=week` | Droppings density + zone counts |
| Session comparison | `GET /api/insights/compare?a=session_10&b=session_12` | Side-by-side stats |

### Review Screens

| UI Element | API Call | Response |
|-----------|---------|----------|
| Identity review | `GET /api/review/identities?video_id=12` | Unconfirmed assignments with reference crops |
| Confirm identity | `POST /api/review/identity` | `{assignment_id, pigeon_id, action: "confirm"}` |
| QC flag list | `GET /api/review/qc-flags?status=pending` | Flagged frames with descriptions |
| Resolve QC flag | `POST /api/review/qc-flag` | `{flag_id, action: "acknowledged"}` |
| Mask correction save | `POST /api/review/mask-edit` | `{video_id, frame_idx, pigeon_id, mask_data}` |
| Track merge | `POST /api/review/track-merge` | `{video_id, obj_a, obj_b, from_frame}` |
| Track split | `POST /api/review/track-split` | `{video_id, obj_id, at_frame}` |

### Training Tab

| UI Element | API Call | Response |
|-----------|---------|----------|
| Clip library | `GET /api/training/clips?labeled=false` | Paginated clip list with metadata |
| Label clip | `POST /api/training/label` | `{clip_id, behavior_class, split}` |
| Training readiness | `GET /api/training/readiness` | Per-class counts vs minimums |
| Start training | `POST /api/training/start` | Job ID, training starts async |
| Training status | `GET /api/training/status/{job_id}` | `{epoch: 5, loss: 0.23, val_acc: 0.81}` |
| Model registry | `GET /api/training/models` | List of trained models with metrics |
| Set active model | `POST /api/training/models/{id}/activate` | Confirms activation |
| Re-inference | `POST /api/training/reinfer?model_version=v2` | Job ID |

### Export

| UI Element | API Call | Response |
|-----------|---------|----------|
| Export data | `POST /api/export` | `{format, filters, include_manifest}` → download link |

### Example Request Bodies for Major Write Endpoints

These examples define the contract between frontend and backend for every destructive or state-changing operation.

#### Process Videos

```json
POST /api/videos/process
{
  "video_paths": ["data/videos/overhead_session13.mp4", "data/videos/side_session13.mp4"],
  "camera_assignments": {
    "overhead_session13.mp4": "overhead",
    "side_session13.mp4": "side"
  },
  "text_prompt": "pigeon",
  "expected_pigeon_count": 4,
  "session_id": "session_13"
}

Response 200:
{
  "job_id": "proc_20250315_142200",
  "videos_queued": 2,
  "status": "processing"
}
```

#### Confirm Identity

```json
POST /api/review/identity
{
  "assignment_id": 47,
  "action": "confirm",
  "pigeon_id": "Alpha",
  "reviewer": "Alex"
}

Response 200:
{
  "assignment_id": 47,
  "review_status": "approved",
  "pigeon_id": "Alpha"
}
```

#### Reject Identity (Reassign)

```json
POST /api/review/identity
{
  "assignment_id": 48,
  "action": "reassign",
  "old_pigeon_id": "Beta",
  "new_pigeon_id": "Gamma",
  "reviewer": "Alex"
}

Response 200:
{
  "assignment_id": 48,
  "review_status": "approved",
  "pigeon_id": "Gamma",
  "old_pigeon_id": "Beta"
}
```

#### Resolve QC Flag

```json
POST /api/review/qc-flag
{
  "flag_id": 112,
  "action": "acknowledged",
  "resolved_action": "accepted",
  "reviewer": "Alex",
  "notes": "Pigeon was temporarily hidden behind feeder, normal behavior"
}

Response 200:
{
  "flag_id": 112,
  "qc_status": "resolved"
}
```

#### Save Mask Edit

```json
POST /api/review/mask-edit
{
  "video_id": 12,
  "frame_idx": 234,
  "pigeon_id": "Alpha",
  "edit_type": "draw_mask",
  "mask_data": "<base64-encoded binary mask PNG>",
  "editor": "Alex",
  "details": {
    "tool": "draw",
    "brush_size": 12,
    "pixels_added": 342
  }
}

Response 200:
{
  "edit_id": 89,
  "video_id": 12,
  "frame_idx": 234,
  "saved": true
}
```

#### Merge Tracks

```json
POST /api/review/track-merge
{
  "video_id": 12,
  "source_obj_id": 3,
  "target_obj_id": 1,
  "from_frame": 234,
  "editor": "Alex",
  "notes": "System split Alpha into two tracks at frame 234, merging back"
}

Response 200:
{
  "edit_id": 90,
  "merged": true,
  "source_obj_id": 3,
  "target_obj_id": 1,
  "frames_affected": 269
}
```

#### Split Track

```json
POST /api/review/track-split
{
  "video_id": 12,
  "obj_id": 1,
  "at_frame": 287,
  "editor": "Alex",
  "notes": "Two pigeons were merged into one track, splitting at frame 287"
}

Response 200:
{
  "edit_id": 91,
  "original_obj_id": 1,
  "new_obj_id": 5,
  "split_at_frame": 287
}
```

#### Label a Clip

```json
POST /api/training/label
{
  "clip_id": 203,
  "behavior_class": "preening",
  "split": "train",
  "labeler": "Alex",
  "notes": ""
}

Response 200:
{
  "label_id": 445,
  "clip_id": 203,
  "behavior_class": "preening"
}
```

#### Start Training

```json
POST /api/training/start
{
  "behavior_classes": ["feeding", "resting", "preening", "courtship"],
  "backbone": "r3d_18",
  "epochs": 50,
  "batch_size": 16,
  "learning_rate": 0.001,
  "freeze_backbone": true,
  "augmentations": ["horizontal_flip", "color_jitter", "time_crop"]
}

Response 200:
{
  "job_id": "train_20250315_143000",
  "status": "started",
  "estimated_duration_minutes": 45   // nullable — null when unknown
}
```

#### Re-Inference Across Archive

```json
POST /api/training/reinfer
{
  "model_version": "v20250315_143000",
  "scope": "eligible",
  "skip_already_inferred": true,
  "skip_failed_videos": true,
  "only_approved_videos": false
}

Response 200:
{
  "job_id": "reinfer_20250315_150000",
  "videos_eligible": 87,
  "videos_skipped": 13,
  "status": "started"
}
```

#### Export

```json
POST /api/export
{
  "format": "csv",
  "include": ["features", "behaviors", "droppings"],
  "filters": {
    "review_status": "approved",
    "identity_status": "confirmed_only",
    "sessions": null,
    "pigeons": null
  },
  "include_manifest": true
}

Response 200:
{
  "download_url": "/api/export/download/export_20250315_151000.zip",
  "files_included": ["features.csv", "behaviors.csv", "droppings.csv", "manifest.json"],
  "rows_exported": 142837
}
```

---

## 7. Implementation Priority Order

### What Must Be Polished First to Replace EZannot

| Priority | Feature | Why First |
|----------|---------|-----------|
| 1 | Video player with mask overlays | Users must see what the system produced |
| 2 | Identity review flow | Most common review task, most impactful for data quality |
| 3 | QC flag review ("Needs Attention") | Catches problems before they propagate |
| 4 | Mask/track correction tools | Core annotation correction — the EZannot replacement |
| 5 | Add videos wizard | Users must be able to feed new data in |

### What Must Be Polished First to Replace LabGym

| Priority | Feature | Why First |
|----------|---------|-----------|
| 6 | Clip extraction (automatic from behavior events) | Creates the raw material for labeling |
| 7 | Clip labeling interface | Users must be able to assign behavior classes |
| 8 | Training pipeline with readiness check | Must know when enough data exists |
| 9 | Model evaluation with confusion matrix | Must prove the model works |
| 10 | Re-inference across archive | Closes the train → apply loop |

### What Can Be Built Later

| Feature | When | Why Later |
|---------|------|-----------|
| Batch workflows | After core review flows work | Optimization, not foundation |
| Comparison views | After data accumulates | Needs multiple sessions to be useful |
| Benchmark modules | After ground truth is collected | Needs labeled test data |
| Role-based permissions | After multi-user need arises | Single-user labs don't need it |
| Session comparison | After 10+ sessions processed | Not useful with small datasets |

---

## Summary: How the Three Documents Fit Together

| Document | Defines | Audience |
|----------|---------|----------|
| **Architecture Spec** | What the system is — layers, database, algorithms, data flow | Backend developers, system architects |
| **UX Design Spec** | How humans use it — screens, navigation, visual design, language | Frontend developers, designers |
| **Implementation Bridge** (this doc) | How architecture and UX connect — roles, state mappings, API contracts, build order | Full-stack developers, project leads |

### The Build Sequence

```
1. Architecture Spec → Build database + SAM3 wrappers + tracking + QC rules
2. UX Design Spec → Build Home dashboard + Video player + Identity review
3. Implementation Bridge → Wire API endpoints, implement mask correction,
                           add batch workflows, comparison views
4. Iterate → Process real pigeon videos, collect feedback, refine
```

### The Single Test for Completeness

> Can a researcher who has never used PigeonLab before sit down, add pigeon videos, review the results, correct mistakes, view spatial insights, label behavior clips, train a classifier, and export publication-ready data — all without touching a terminal, reading documentation, or asking for help?

When the answer is yes, PigeonLab is complete.
