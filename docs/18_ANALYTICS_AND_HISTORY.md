# Analytics and history

SQLite finalized sessions, segments, distractions, recovery audit rows, devices, categories, and
historical goals are the only analytics inputs. Statistics and Session History are read-only.
Temporary intentions are never persisted, queried, displayed, or exported.

## Metric dictionary

- **Focus:** confirmed planned focus plus confirmed overtime. Pause, sleep, unknown recovery gaps,
  and discarded sessions are excluded. Recovered confirmed focus is included unless filtered out.
- **Daily focus:** focus segments split at local-midnight boundaries using their stored timezone.
- **Active day:** a local date with at least one confirmed focus second.
- **Goal progress/met day:** daily focus divided by the goal effective on that historical date; met
  means focus is at least the goal. Progress may exceed 100%.
- **Session completion rate:** completed or completed-with-overtime sessions divided by included
  finalized sessions. Recovered and stopped-early sessions remain visible but are not completions.
- **Planned/completed/stopped/overtime:** the stored timer plan, confirmed planned portion, unfilled
  planned portion, and explicit confirmed overtime.
- **Continuous block:** the sum of focus segments sharing a continuity group. A pause of ten seconds
  or less preserves continuity; longer pauses and system sleep break it.
- **Pause metrics:** stored pause duration/count, short and long classifications, with system-sleep
  pauses also reported separately.
- **Distraction metrics:** simple marker count, sessions with markers, and markers per focus hour.
  There are no distraction types.
- **Category/device metrics:** the same confirmed focus and session rules grouped by persisted IDs;
  historical device identity is preserved.

All durations are integer elapsed seconds. Ratios with no valid denominator are shown as unavailable,
not zero. Axes start at zero and empty ranges remain empty.

## Ranges, filters, charts, and history

Statistics supports Today, Last 7 Days, This/Last Week, Last 30 Days, This/Last Month, This Year,
and custom local dates. Filters cover category, status, device, overtime, recovered sessions, and
minimum focus. Qt-native charts show daily focus, Monday-based weekly comparison, categories,
planned versus actual, pause/distraction trends, continuous-block distribution, and a correctly
aligned leap-year-aware calendar heatmap with absolute/goal mode.

Session History supports full-ID/category search, date/category/status/device filters, overtime or
distraction presence, min/max focus, five sorts, and 50-row pages. Details are read-only and include
aggregates, segments, continuity, pause classifications, distractions, recovery audit, and portable
sync paths/checksums. Only the full session ID can be copied.

## Cache, indexes, and performance

Analytics caches by filters plus `analytics_revision`. Database triggers increment that revision for
canonical session, segment, distraction, recovery, and goal changes. Range/status analytics indexes
and session foreign-key indexes prevent N+1 queries. The disposable five-year benchmark contains
10,000 sessions, 50,000 segments, and 20,000 distractions; the acceptance run completed analytics in
2.60 seconds and the first history page in 5.44 ms. Query-plan review confirmed indexed session range
search. Performance varies by storage and machine.

## Export versus portable data

Statistics export is an explicit, atomic UTF-8 daily-summary CSV written to a user-selected location
outside `portable_data`. It never runs automatically and is not a synchronization format. Portable
CSV remains the lossless raw interchange contract for devices, finalized sessions, segments,
distractions, goals, categories, and quotes.
