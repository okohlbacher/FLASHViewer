"""Per-tool facts, and the pure helpers that read a workspace.

Deliberately free of Streamlit *and* of the parsers: `src/parse/*` pull in
pyopenms via `src/masstable.py`, and keeping this module importable without
either is what lets the plain-python test suite exercise it. Same split as
`src/presets.py` (pure) vs `src/preset_page.py` (Streamlit).
"""
import os
from pathlib import Path


def input_listing(files_dir):
    """Split a tool's input directory into (copied files, referenced paths).

    Files added by reference are recorded as one absolute path per line in
    external_files.txt, not placed in the directory — so anything deciding
    "is there input here?" has to consult both. A referenced file that has
    since been moved away is dropped rather than reported as present.

    This is the single implementation; `StreamlitUI.upload_widget` calls it, so
    a test that exercises it is testing the shipping code rather than a mirror
    of it.
    """
    files_dir = Path(files_dir)
    if not files_dir.exists():
        return [], []

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
    return copied_present, external_list


def has_input(files_dir):
    """Does this tool have any input at all, copied or referenced?"""
    copied, external = input_listing(files_dir)
    return bool(copied or external)
