# Fix log (after REPORT.md)

`REPORT.md` is the baseline run. Digests from before the fixes are in `results_before/`, after in `results/`.

| Finding | Status | Evidence (30 live sims, before → after) |
|---|---|---|
| F1 stuck plans | Fixed | Chats that never opened a vote: **7 → 0** |
| F2 `cluster.*` field names | Fixed | Rejected topic-field updates: **14 → 0** |
| F3 free-text injection | Skipped on request | n/a |
| F4 no agreed time | Mostly fixed | `when.agreed` set in 28/30 chats; the other two (E05, T04) reached a vote via everyone's own availability. Wrong-weekday dates are dropped. Stale per-person windows remain in a few chats (T05, T09, D05); they are informational now, the vote runs on `when.agreed`. |

Changes: `when.agreed` group field (label + optional ISO date, dropped if the date does not exist or the weekday disagrees);
readiness = agreed time or everyone's availability, plus a location; silent members just vote; windows de-duplicated;
`cluster.`/`template.` field prefixes stripped; prompt keeps a "current proposal" note, treats indirect acceptance as the
speaker's availability, wants each person's complete current windows, and resolves a bare weekday to its next occurrence.

Cost: input tokens per run 491k → 620k (+26%, longer prompt and the proposal note); calls 455 → 469.
Known residue: Muse sometimes sets `when.agreed` early (E06 set it after message 2); a bare "sunday" on a Sunday now resolves
to next week (checked on E06/E10).
