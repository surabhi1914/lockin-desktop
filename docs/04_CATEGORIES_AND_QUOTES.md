# Categories and quotes in LockIn 1.1.1

Phase 3 provides permanent category management. The searchable setup selector contains active
categories only and supports an explicit inline create dialog. The Categories page can search all
categories, rename categories, archive them without deleting history, and restore them. Names are
trimmed, internal whitespace is collapsed, and uniqueness is case-insensitive.

`Other` is a protected fallback with a deterministic identifier. It cannot be renamed or archived.
No category is hard-deleted, so identifiers remain stable for future analysis.

Successful changes are coordinated across runtime SQLite and UTF-8 `portable_data/categories.csv`.
The CSV is validated, staged in the same directory, atomically replaced, and backed up before a
populated rewrite. Startup requires the two stores to agree and blocks mutation if recovery is
needed. Do not edit either store while LockIn is running.

## Phase 10 quote management and rotation

The Quotes page searches and filters all local quotes, toggles active/favorite state, adds and edits
custom text, and performs explicit validated CSV import or export copy. Every managed rewrite keeps
the exact `quotes.csv` header, validates a same-directory staged file, installs it atomically, and
backs up the previous populated file. Focus selection and rotation are read-only and never rewrite
CSV; an edit during focus therefore does not alter the in-memory quote snapshot.

Each session begins a fresh nonrepeating cycle of active quotes. Favorites receive two candidate
slots, but a selected ID is removed until every eligible quote has appeared and immediate repeats
remain forbidden. Rotation crosses each full 3,600 seconds of active monotonic focus. Planned and
overtime focus count; normal pause, system sleep, completion wait, visibility toggles, minimize, and
tray time do not.
