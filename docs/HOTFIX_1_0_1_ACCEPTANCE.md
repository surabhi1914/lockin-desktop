# LockIn v1.0.1 window-flicker hotfix acceptance

## Scope and diagnosis

- Symptom: a small blank window flashed during normal UI interaction in both source and packaged
  v1.0.0 builds.
- Classification: transient Qt top-level/native widgets; not a child process, console, main-window
  reconstruction, theme reload, or PyInstaller-only behavior.
- Exact object: parentless `QPushButton` instances for Rename and Archive in `CategoryRow`.
- Trigger: `CategoriesPage.refresh()` during startup, Categories navigation, search/filter changes,
  and category service updates.
- v1.0.0 source: `app/ui/pages/categories_page.py`, original lines 56 and 57 called
  `setVisible(True)` before lines 62–64 added the buttons to the row layout.
- Why brief: Qt showed each parentless visible button as a native top-level window, then hid and
  recreated it as a child when the layout assigned its parent. Measured lifetime was 31–32 ms.
- Why one action appeared severe: every refresh rebuilt every visible category row, creating two
  transient native windows per active category.

Before-trace excerpt (privacy-safe):

```text
class=QPushButton event=Show parent=null native_id=9438058
stack=...categories_page.py:158:refresh -> categories_page.py:56:__init__
class=QPushButton event=Hide parent=null lifetime_ms=31.0
process-launch records=0
```

Reproduction: run `.\.venv\Scripts\python.exe main.py`, select Categories, then repeat navigation or
change its search/filter. With `LOCKIN_TRACE_TRANSIENT_WINDOWS=1`, v1.0.0 logged parentless native
button Show/Hide events for each reconstructed row.

## Root fix and diagnostics

`CategoryRow` and its three action buttons now receive explicit parents. Buttons are inserted into
the row layout before visibility is assigned, and each row is parented to the page's rows container.
Legitimate dialogs, popups, tooltips, tray behavior, and error reporting are unchanged.

Development-only diagnostics are opt-in through `LOCKIN_TRACE_PROCESS_LAUNCHES=1` and
`LOCKIN_TRACE_TRANSIENT_WINDOWS=1`. They log process API/command/flags/application stack and Qt
widget class, parent, flags, modality, geometry, native ID, lifecycle, active windows, and application
stack without logging environment variables or personal data. Normal launches install no tracing.

## Acceptance evidence

- Baseline before modification: 406 tests passed; Ruff, formatting, mypy, session integrity,
  portable sync, and analytics were healthy.
- Hotfix development regression: 410 tests passed, including process-blocking, widget ownership,
  top-level/native-ID stability, and page-reuse tests.
- Before trace: 40 parentless button Show events across startup and one Categories navigation; no
  interaction-time process launches.
- After trace: zero parentless button Shows, zero unexpected visible top-level Shows, and zero
  process launches across repeated Categories/Home/Statistics/Settings navigation.
- Diagnostics-disabled development launch used disposable runtime/portable/settings paths, visited
  all seven shell pages, retained exactly one LockIn window, and showed no click-time process.
- Session integrity, portable synchronization, and analytics verification passed unchanged.
- Combined branch coverage reached the required 90.00%; Ruff, formatting, and strict mypy passed.
- Frozen v1.0.1 health passed with Unicode/space-containing disposable roots. Packaged navigation
  retained one LockIn window and logged zero process launches or unexpected top-level Shows.
- The real per-user v1.0.0 installation upgraded to v1.0.1. SHA-256 snapshots of all eight files in
  the runtime/default portable roots remained identical through upgrade, uninstall, reinstall, and
  isolated health checks. The final installed product is v1.0.1.
- The post-build checker validated version consistency, sanitized resources, the onedir bundle,
  installer/ZIP checksums, privacy exclusions, private-repository visibility, and the unchanged
  v1.0.0 tag plus exact original asset sizes/digests.
- No schema, migration, portable contract, feature, or personal-data change is present.

Windows CI and post-publication checks remain required before publication is considered complete.
The release identity is commit `fix: eliminate transient window flicker`, annotated tag `v1.0.1`,
and private GitHub Release `LockIn v1.0.1`. The v1.0.0 tag, Release, and assets must remain
byte-for-byte unchanged.
