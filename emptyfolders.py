import argparse
import os
import sys
import time
import logging
from pathlib import Path

VERSION = "2.2"
SCRIPT_NAME = "emptyfolders.py"
ALLOWED_FILES = {"thumbs.db", ".ds_store", ".localized"}
# Lower-case names of system folders that are skipped entirely (Windows
# recycle bin and System Volume Information; macOS trash folders)
IGNORED_DIRS = {"$recycle.bin", "system volume information", ".trash", ".trashes"}

EMPTY_FILE = "empty-folders.txt"
ISSUES_FILE = "folders-with-issues.txt"
SCAN_LOG = "scan.log"
ERROR_LOG = "errors.log"

DELETE_NONE = 0
DELETE_PROMPT = 1
DELETE_FORCE = 2

log = logging.getLogger("emptyfolders")


class CountingHandler(logging.Handler):
    """Counts warnings/errors raised during this run."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.count = 0

    def emit(self, record):
        self.count += 1


problems = CountingHandler()


EPILOG = f"""\
what counts as an empty folder:
  * a folder with no content at all
  * a folder containing only Thumbs.db, .DS_Store and/or .localized
  * a folder containing only such empty folders (nested), reported
    bottom-up, so a whole empty tree is listed from the leaves upwards
Symbolic links are never followed and never treated as empty.
System folders are skipped: $RECYCLE.BIN and System Volume Information
(Windows), .Trash and .Trashes (macOS). A folder containing one is not empty.
The folder you start in is never reported or deleted.

output files (written in the current folder):
  {EMPTY_FILE:<22} always written; one empty folder per line
  {ISSUES_FILE:<22} only created if folders could not be read
  {ERROR_LOG:<22} only created if warnings/errors occurred (appended to)
  {SCAN_LOG:<22} only created with -l/--log (appended to)

deleting:
  Without -dp/-df nothing is changed: the script only lists empty folders.
  With deletion, only Thumbs.db, .DS_Store and .localized are removed from a
  folder before it is removed; any other content aborts that folder's
  deletion and is logged as an error. Deleted folders cannot be restored.
  Run without a delete switch first and review {EMPTY_FILE}.

switches are case-insensitive: -DP == -dp == -Dp, --LOG == --log.

exit status: 0 success, 1 some folders could not be read, 2 bad usage.

examples:
  python {SCRIPT_NAME}                 list empty folders only
  python {SCRIPT_NAME} --delete-prompt confirm each deletion
  python {SCRIPT_NAME} -DF -L          delete without asking and keep a full log
"""


def case_variants(option):
    """-DP -> -DP, -dP, -Dp, -dp (argparse options are case-sensitive)."""
    letters = option[1:]
    variants = {option}
    for i, ch in enumerate(letters):
        variants |= {v[:i + 1] + ch.swapcase() + v[i + 2:] for v in set(variants)}
    return sorted(variants)


def normalize_argv(argv):
    """Lower-case long options so --DELETE-FORCE works like --delete-force."""
    result = []
    for token in argv:
        if token.startswith("--") and token != "--":
            name, sep, value = token.partition("=")
            token = name.lower() + sep + value
        result.append(token)
    return result


def parse_args(argv):
    """Return (delete_mode, write_log)."""
    parser = argparse.ArgumentParser(
        prog=SCRIPT_NAME,
        description="Find (and optionally delete) empty folders below the current folder.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        allow_abbrev=False,
    )
    parser.add_argument("-h", "-H", "-?", "--help", action="help",
                        help="show this detailed help and exit")
    parser.add_argument("-v", "-V", "--version", action="version",
                        version=f"emptyfolders {VERSION}",
                        help="show version and exit")
    parser.add_argument("-l", "-L", "--log", dest="log", action="store_true",
                        help=f"write a full activity log to {SCAN_LOG}")

    delete = parser.add_mutually_exclusive_group()
    delete.add_argument(*case_variants("-dp"), "--delete-prompt", "--prompt",
                        dest="delete_mode", action="store_const", const=DELETE_PROMPT,
                        help="delete empty folders, asking for each one")
    delete.add_argument(*case_variants("-df"), "--delete-force", "--force",
                        dest="delete_mode", action="store_const", const=DELETE_FORCE,
                        help="delete empty folders without asking")
    parser.set_defaults(delete_mode=DELETE_NONE)

    args = parser.parse_args(normalize_argv(argv))
    return args.delete_mode, args.log


def setup_logging(write_log):
    """Errors always go to ERROR_LOG (created lazily on first record).
    The full activity log is only written when requested."""
    log.setLevel(logging.INFO)
    log.propagate = False
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    err = logging.FileHandler(ERROR_LOG, encoding="utf-8", delay=True)
    err.setLevel(logging.WARNING)
    err.setFormatter(fmt)
    log.addHandler(err)
    log.addHandler(problems)

    if write_log:
        full = logging.FileHandler(SCAN_LOG, encoding="utf-8")
        full.setFormatter(fmt)
        log.addHandler(full)


class LazyFile:
    """Text file that is only created when the first line is written."""

    def __init__(self, path):
        self.path = path
        self.handle = None

    def write_line(self, text):
        if self.handle is None:
            self.handle = open(self.path, "w", encoding="utf-8")
        self.handle.write(text + "\n")

    def close(self):
        if self.handle:
            self.handle.close()


def delete_folder(path, mode):
    """Delete a folder that only holds allowed files. Returns True if removed."""
    try:
        if mode == DELETE_PROMPT:
            answer = input(f"Delete folder '{path}'? (y/n): ").strip().lower()
            if answer != "y":
                return False

        with os.scandir(path) as it:
            leftovers = list(it)
        for entry in leftovers:
            # Only ever remove files from the allowed list
            if entry.is_dir(follow_symlinks=False) or entry.name.lower() not in ALLOWED_FILES:
                raise OSError(f"unexpected content: {entry.name}")
            os.remove(entry.path)

        os.rmdir(path)
        print(f"Deleted: {path}")
        log.info(f"Deleted: {path}")
        return True

    except Exception as e:
        log.error(f"Failed deleting {path}: {e}")
        print(f"Failed deleting {path}: {e}")
        return False


def main():
    delete_mode, write_log = parse_args(sys.argv[1:])
    start_path = Path.cwd()
    setup_logging(write_log)

    empty_output = LazyFile(EMPTY_FILE)
    issues_output = LazyFile(ISSUES_FILE)
    # empty-folders.txt is a result file: create it even when nothing is found
    empty_output.handle = open(EMPTY_FILE, "w", encoding="utf-8")

    print(f"Starting scan in: {start_path}")
    log.info(f"Scan started in {start_path}")

    total_scanned = 0
    empty_found = 0
    issues_found = 0
    start_time = time.time()
    empty_dirs = set()  # folders that are (or, once deleted, were) empty

    def on_walk_error(e):
        # os.walk silently skips unreadable folders unless told otherwise
        nonlocal issues_found
        issues_output.write_line(str(e.filename))
        issues_found += 1
        log.warning(f"Issue accessing {e.filename}: {e}")

    # Top-down scan so system folders can be pruned (a bottom-up walk would
    # enter them and report access errors for e.g. System Volume Information)
    scanned = []  # (root, all subfolder names, files), parents before children
    for root, dirs, files in os.walk(start_path, onerror=on_walk_error):
        scanned.append((root, list(dirs), files))
        for d in [d for d in dirs if d.lower() in IGNORED_DIRS]:
            log.info(f"Ignored system folder: {os.path.join(root, d)}")
        dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS]
        total_scanned += 1

        if total_scanned % 100 == 0:
            elapsed = time.time() - start_time
            rate = total_scanned / elapsed if elapsed > 0 else 0
            print(f"Scanned: {total_scanned} folders | {rate:.1f} folders/sec")

    # Evaluate bottom-up (important for deletion and nested empty folders).
    # Ignored folders stay in `dirs` but never enter empty_dirs, so a folder
    # that contains one is never considered empty.
    for root, dirs, files in reversed(scanned):
        # Never report or delete the folder the scan was started from
        if Path(root) == start_path:
            continue

        only_allowed_files = all(f.lower() in ALLOWED_FILES for f in files)
        only_empty_subdirs = all(os.path.join(root, d) in empty_dirs for d in dirs)
        if not (only_allowed_files and only_empty_subdirs):
            continue

        empty_output.write_line(root)
        empty_found += 1
        log.info(f"Empty: {root}")

        if delete_mode == DELETE_NONE:
            empty_dirs.add(root)
        elif delete_folder(root, delete_mode):
            empty_dirs.add(root)

    empty_output.close()
    issues_output.close()

    elapsed = time.time() - start_time

    print("\n--- Scan Complete ---")
    print(f"Total folders scanned: {total_scanned}")
    print(f"Empty folders found: {empty_found}")
    print(f"Folders with issues: {issues_found}")
    print(f"Time elapsed: {elapsed:.2f} seconds")
    log.info(f"Scan complete: {total_scanned} scanned, {empty_found} empty, {issues_found} issues")

    if issues_found:
        print(f"See {ISSUES_FILE} and {ERROR_LOG}")
    elif problems.count:
        print(f"Errors occurred, see {ERROR_LOG}")

    logging.shutdown()
    return 1 if issues_found else 0


if __name__ == "__main__":
    sys.exit(main())
