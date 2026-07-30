"""Dataset ids come from user filenames and land in SQL.

Before this, an id containing an apostrophe stored fine and then made every
later query against that workspace raise OperationalError — the dataset stayed
listed, its page threw, and it could not be deleted from inside the app. The
workspace was unrecoverable without hand-editing SQLite.

Run: python3 tests/test_filemanager_sql.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.workflow.FileManager import FileManager, _identifier  # noqa: E402

NASTY = [
    "o'brien_sample",                 # the one that bricked workspaces
    'quote"double',
    "semi;colon",
    "drop'); DROP TABLE stored_data;--",
    "sample with spaces",
    "unicode_Ω_sample",
    "back\\slash",
    "percent%_under_score",
]


def main():
    tmp = Path(tempfile.mkdtemp())
    try:
        cache = tmp / "cache"
        cache.mkdir(parents=True)
        fm = FileManager(tmp, cache)

        for dataset_id in NASTY:
            fm.store_data(dataset_id, "deconv_dfs", pd.DataFrame({"x": [1, 2]}))

            # Every read path must survive the id.
            assert fm.result_exists(dataset_id, "deconv_dfs"), dataset_id
            got = fm.get_results(dataset_id, ["deconv_dfs"])["deconv_dfs"]
            assert len(got) == 2, dataset_id
            assert dataset_id in fm.get_results_list(["deconv_dfs"]), dataset_id

            # And it must be removable from inside the app.
            fm.remove_results(dataset_id)
            assert dataset_id not in fm.get_results_list(["deconv_dfs"]), dataset_id

        # The tables are still there: no injected DDL ran.
        fm.cache_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [r[0] for r in fm.cache_cursor.fetchall()]
        assert "stored_data" in tables and "stored_files" in tables, tables

        # Column/table identifiers are code constants; anything else is refused.
        for bad in ("a-b", "1abc", "a b", "drop;", "", "a'b", "a\"b"):
            try:
                _identifier(bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted unsafe identifier {bad!r}")
        for good in ("deconv_dfs", "stored_files", "_x", "a1"):
            assert _identifier(good) == good

        print("filemanager sql: all checks passed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
