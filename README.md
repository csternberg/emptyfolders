# emptyfolders

Find, and optionally delete, empty folders below the current directory.
Pure Python 3 standard library; works on Windows, Linux and macOS.

A folder counts as empty when it:

* has no content at all, or
* contains only `Thumbs.db`, `.DS_Store` and/or `.localized`, or
* contains only folders that are themselves empty (nested empty trees).

Symbolic links are never followed or treated as empty, and the folder you start in is never reported or deleted.

## Usage

```
python emptyfolders.py [-h] [-v] [-l] [-dp | -df]
```

| Short | Long                             | Description                                  |
|-------|----------------------------------|----------------------------------------------|
| `-dp` | `--delete-prompt`, `--prompt`    | Delete empty folders, asking for each        |
| `-df` | `--delete-force`, `--force`      | Delete empty folders without asking          |
| `-l`  | `--log`                          | Write a full activity log to `scan.log`      |
| `-h`, `-?` | `--help`                    | Show detailed help                           |
| `-v`  | `--version`                      | Show version                                 |

All switches are case-insensitive (`-DP` = `-dp` = `-Dp`, `--LOG` = `--log`).
`-dp` and `-df` are mutually exclusive. Without a delete switch nothing is changed.

## Output files

Written in the current directory:

| File                      | Created                                        |
|---------------------------|------------------------------------------------|
| `empty-folders.txt`       | Always; one empty folder per line              |
| `folders-with-issues.txt` | Only if folders could not be read              |
| `errors.log`              | Only if warnings/errors occurred (appended)    |
| `scan.log`                | Only with `-l`/`--log` (appended)              |

## Deleting

Only `Thumbs.db`, `.DS_Store` and `.localized` are removed from a folder before it is deleted.
If anything else is found, that folder is kept and the problem is written to `errors.log`.
Deleted folders cannot be restored, so run without a delete switch first and review `empty-folders.txt`.

## Exit status

`0` success, `1` some folders could not be read, `2` invalid usage.

## Man page

`emptyfolders.1` is included; view with `man ./emptyfolders.1`.
