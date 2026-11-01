# CLAUDE.md

Single-file Python 3 CLI (`emptyfolders.py`, stdlib only) that lists and optionally deletes empty folders.
Docs: `README.md`, man page `emptyfolders.1`, and `--help` (text in `EPILOG`). Keep all three in sync when changing options or behaviour.

## Conventions
- Every switch must work in upper and lower case. Short options are registered in all case variants via `case_variants`; long options are lower-cased by `normalize_argv`.
- Each option has a Unix-style long alias (`--delete-prompt`, `--delete-force`, `--log`, `--help`, `--version`).
- Logging: the `emptyfolders` logger. `errors.log` (WARNING+) uses a delayed `FileHandler` so it exists only if something went wrong; `scan.log` only with `-l`. `folders-with-issues.txt` uses `LazyFile` for the same reason. `empty-folders.txt` is the one result file that is always written.
- `os.walk` hides unreadable folders unless `onerror` is passed, so access problems are recorded in `on_walk_error`. Do not remove it.
- Deletion removes only `ALLOWED_FILES` and must never touch other content. The start folder is never reported or deleted.
- Emptiness is computed bottom-up from walk results plus the `empty_dirs` set (folders deleted or, without deletion, found empty).
- Cross-platform; no shell calls.

## Testing
No test suite. Test in a scratch directory: nested empty folders, a folder with only `Thumbs.db`, a folder with real files, and an unreadable folder (simulate by patching `os.scandir` to raise `PermissionError`). Check that `errors.log` and `folders-with-issues.txt` appear only when expected.
