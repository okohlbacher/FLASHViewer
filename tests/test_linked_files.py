"""Desktop links files instead of copying them — and never deletes the originals.

Run: FLASHAPP_DESKTOP=1 python3 tests/test_linked_files.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("FLASHAPP_DESKTOP", "1")
from src.workflow.FileManager import FileManager, DESKTOP  # noqa: E402


def main():
    assert DESKTOP, "run with FLASHAPP_DESKTOP=1"
    tmp = Path(tempfile.mkdtemp())
    try:
        source = tmp / "elsewhere" / "run_deconv.mzML"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"x" * 4096)

        cache = tmp / "ws" / "cache"
        cache.mkdir(parents=True)
        fm = FileManager(tmp / "ws", cache)
        fm.store_file("run", "out_deconv_mzML", source, remove=True)

        # Referenced, not copied: nothing lands under the cache.
        stored = Path(fm.get_results("run", ["out_deconv_mzML"])["out_deconv_mzML"])
        assert stored == source.resolve(), stored
        assert not (cache / "files" / "run").exists(), "file was copied into the cache"

        # remove=True must NOT delete a linked original.
        assert source.exists(), "linked source file was deleted"

        # Deleting the dataset must not touch the user's file, and must not
        # crash on the missing per-dataset directory.
        fm.remove_results("run")
        assert source.exists(), "remove_results() deleted the user's original"
        assert fm.get_results_list(["out_deconv_mzML"]) == []

        # An explicit link=False still copies, so hosted behaviour is unchanged.
        fm.store_file("run2", "out_deconv_mzML", source, remove=False, link=False)
        copied = Path(fm.get_results("run2", ["out_deconv_mzML"])["out_deconv_mzML"])
        assert copied.parent == cache / "files" / "run2", copied
        assert source.exists()

        print("linked files: all checks passed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
