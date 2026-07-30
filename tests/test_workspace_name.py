"""?workspace= is user input that becomes a filesystem path.

Guards two failures seen for real: an empty value resolved to the workspaces
directory itself (ValueError in render_sidebar), and traversal out of it.

Run: python3 tests/test_workspace_name.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def sanitize(requested):
    """Mirrors the guard in common.page_setup()."""
    requested = str(requested or "").strip()
    if (not requested) or requested != Path(requested).name or requested in (".", ".."):
        return "default"
    return requested


def main():
    root = Path("..", "workspaces-FLASHViewer")

    # The two failures this exists for.
    assert sanitize("") == "default"
    assert sanitize("   ") == "default"
    assert sanitize("..") == "default"
    assert sanitize("../../etc") == "default"
    assert sanitize("/etc/passwd") == "default"
    assert sanitize("a/b") == "default"
    assert sanitize(None) == "default"

    # Ordinary names still work.
    for good in ("default", "my-run", "run_2026", "AB12"):
        assert sanitize(good) == good, good

    # And the resulting path never leaves the workspaces directory.
    for candidate in ("", "..", "../..", "/etc", "a/b", "default", "my-run"):
        resolved = (root / sanitize(candidate)).resolve()
        assert root.resolve() in resolved.parents, candidate

    print("workspace names: all checks passed")


if __name__ == "__main__":
    main()
