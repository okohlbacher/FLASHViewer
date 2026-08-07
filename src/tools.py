"""Per-tool facts, and the pure helpers that read a workspace.

Deliberately free of Streamlit *and* of the parsers: `src/parse/*` pull in
pyopenms via `src/masstable.py`, and keeping this module importable without
either is what lets the plain-python test suite exercise it. Same split as
`src/presets.py` (pure) vs `src/preset_page.py` (Streamlit).
"""
import json
import os
import time
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


def missing_references(files_dir):
    """Referenced paths recorded in external_files.txt that no longer exist.

    input_listing() *drops* these, which is right for "what can I run?" and
    useless for "is anything broken?". A separate function rather than a third
    return value, because upload_widget and tests/test_input_listing.py both
    unpack the existing two-tuple.
    """
    index = Path(files_dir, "external_files.txt")
    if not index.exists():
        return []
    with open(index) as fh:
        return [line for line in fh.read().splitlines()
                if line and not os.path.exists(line)]


# ------------------------------------------------------------ recorded intent

_INTENT_STEPS = ("data", "method")


def _intent_path(workflow_dir, step):
    if step not in _INTENT_STEPS:
        raise ValueError(f"unknown intent step: {step!r}")
    return Path(workflow_dir, "intent", f"{step}.json")


def record_intent(workflow_dir, step, **fields):
    """Record that the user did something deliberate.

    Ownership must be a recorded property, never inferred — the two data-loss
    bugs in HANDOFF.md section 2 are both that mistake. The same applies to
    intent: `upload_widget` auto-copies the example files whenever its
    directory is empty, and `save_parameters()` runs on every widget render, so
    both naive signals are already true before the user has done anything.

    Call this ONLY from a branch a user action actually reached:
      - the upload form's submit branch           source="upload"
      - desktop_file_picker's non-empty return    source="reference"
      - the Load example data button              source="example"
      - save_parameters(), only when the dict differs from the one on disk
    """
    path = _intent_path(workflow_dir, step)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    payload.update(fields)
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_intent(workflow_dir, step):
    """The recorded intent, or None if there is none.

    None means UNKNOWN, not "no". Existing workspaces are deliberately not
    migrated, so one made before this existed has files and no marker — the UI
    must say "added earlier" rather than claim the user chose them, or claim
    there is nothing there.
    """
    path = _intent_path(workflow_dir, step)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
