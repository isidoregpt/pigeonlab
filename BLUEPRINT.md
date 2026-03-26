# PigeonLab Blueprint

## Error Catalog

### BUG-001 — Export URL bypasses Vite dev proxy
**Status:** RESOLVED
Export downloads used `window.open()` which bypassed the Vite dev proxy, causing 404s in development. Fixed by using a temporary `<a>` element click with a relative URL, which correctly routes through the proxy.

### BUG-002 — Missing video features endpoint
**Status:** RESOLVED
The `/api/videos/{video_id}/frame/{frame_num}/features` endpoint now exists in `backend/routers/videos.py` and returns per-pigeon feature data for the requested frame.

### BUG-003 — Missing video track-edits endpoint
**Status:** RESOLVED
The `/api/videos/{video_id}/track-edits` endpoint now exists in `backend/routers/videos.py` and returns the edit history for a given video.

### BUG-004 — Review queue links to video_id=0
**Status:** RESOLVED
The review queue now uses `getNextVideoForIdentityReview()` to fetch the actual next video needing review. VideoCard review buttons link to `/review?type=identity&video_id={actual_id}`.

### INC-004 — Attention count doesn't include behaviors
**Status:** RESOLVED
The `/api/review/attention/count` endpoint now includes pending behavior reviews in its total, matching the sidebar badge and TopBar notification count.

---

## Appendix A — Seed Data Summary

The `backend/seed_data.py` script creates the following sample data for development:

| Entity             | Count   | Notes                                           |
|--------------------|---------|------------------------------------------------|
| Pigeons            | 4       | Alpha, Beta, Gamma, Delta with physical markers |
| Videos             | 4       | 2 sessions, mixed cameras, all status=completed |
| Video assignments  | 16      | 4 pigeons x 4 videos, status=raw               |
| QC flags           | 4       | 1 per video, mixed severity, status=pending     |
| Features           | ~varies | Per-pigeon per-frame tracking data              |
| Behavior records   | ~varies | Aggregated behavior observations                |
| Pairwise records   | ~varies | Inter-pigeon distance measurements              |
| Droppings          | 15-20   | Randomly distributed across videos              |
| Clips              | 10      | Extracted segments with varied reasons           |
| Behavior labels    | 5       | 5 of 10 clips labeled with behavior classes     |
| Model registry     | 1       | Single baseline behavior classifier             |
