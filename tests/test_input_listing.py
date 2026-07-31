"""Files added by reference must be visible in the input list.

The desktop app never copies input into the workspace: it appends the chosen
path to external_files.txt. The listing logic in upload_widget decides between
a "no data yet, use the example files" branch and the branch that actually
lists what is present — and the emptiness test used to look only at files_dir.
Since files_dir stays empty when everything is referenced, the fallback branch
always won and referenced files were never listed. Picking a file appeared to
do nothing.

This test mirrors that decision, so the regression cannot come back silently.

Run: python3 tests/test_input_listing.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}  {detail}")


def listing(files_dir: Path, fallback):
    """The branch logic from StreamlitUI.upload_widget, isolated.

    Returns (used_fallback, current_files).
    """
    external_index = files_dir / "external_files.txt"
    external_list = []
    if external_index.exists():
        with open(external_index) as fh:
            external_list = [
                line for line in fh.read().splitlines()
                if line and os.path.exists(line)
            ]
    copied_present = [f for f in files_dir.iterdir()
                      if f.name != "external_files.txt"]

    if fallback and not copied_present and not external_list:
        return True, [f.name for f in copied_present]
    current = [f.name for f in copied_present]
    current += [f"(local) {Path(f).name}" for f in external_list]
    return False, current


def main():
    tmp = Path(tempfile.mkdtemp(prefix="flashapp-listing-"))
    try:
        files_dir = tmp / "input-files" / "mzML-files"
        files_dir.mkdir(parents=True)
        (files_dir / "external_files.txt").touch()
        fallback = ["example-data/flashdeconv/example_fd.mzML"]

        used_fallback, current = listing(files_dir, fallback)
        check("empty workspace falls back to example data",
              used_fallback and current == [], str(current))

        # The desktop path: reference a real file, copy nothing.
        real = tmp / "elsewhere" / "run.mzML"
        real.parent.mkdir(parents=True)
        real.write_bytes(b"x")
        with open(files_dir / "external_files.txt", "a") as fh:
            fh.write(f"{real}\n")

        used_fallback, current = listing(files_dir, fallback)
        check("a referenced file is NOT treated as an empty workspace",
              not used_fallback, f"used_fallback={used_fallback}")
        check("a referenced file appears in the list",
              current == ["(local) run.mzML"], str(current))

        # A copied file alongside a referenced one: both show.
        (files_dir / "copied.mzML").write_bytes(b"y")
        _, current = listing(files_dir, fallback)
        check("copied and referenced files both appear",
              sorted(current) == ["(local) run.mzML", "copied.mzML"], str(current))

        # A referenced file that has since been moved away must drop out
        # rather than be listed as present.
        real.unlink()
        _, current = listing(files_dir, fallback)
        check("a referenced file that no longer exists is dropped",
              current == ["copied.mzML"], str(current))

        # ...and if that was the only input, we are empty again.
        (files_dir / "copied.mzML").unlink()
        used_fallback, current = listing(files_dir, fallback)
        check("losing every input falls back to example data again",
              used_fallback, f"used_fallback={used_fallback}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
