# FLASHApp desktop branch — handoff

Everything found, fixed, deferred or rejected while turning FLASHViewer into a
cross-platform desktop app and cleaning up what that exposed.

Branch `desktop` on `okohlbacher/FLASHViewer`, forked from `t0mdavid-m/FLASHViewer`
at `develop`. Draft PR: t0mdavid-m/FLASHViewer#90.

Test suite: `tests/run_all.sh` — 11 files. Each skips cleanly rather than passing
falsely when a prerequisite (example data, a FLASHDeconv binary) is absent.

---

## 1. Bugs in the app as it shipped

These were all present on `develop` before any of this work. Several are data-loss
or "workspace permanently broken" class. **They are the most valuable part of this
branch to upstream, independently of the desktop app.**

| # | Bug | Effect | Status |
|---|---|---|---|
| 1 | `Delete Workspace` joined an unsanitised text box into a path and `rmtree`'d it | Typing an absolute path deleted **that directory**; `..` removed every workspace | fixed, `valid_workspace_name()` + test |
| 2 | `store_file()` read `file.suffix` before its file-like branch; `UploadedFile` has no `.suffix` | **Every browser upload** raised `AttributeError` — the only path all three upload pages use | fixed |
| 3 | Dataset ids (user filenames) interpolated into SQL | One apostrophe made every later query raise `OperationalError`; the dataset stayed listed, its page threw, and it could not be deleted from inside the app | fixed, parameterised + identifier allow-list + test |
| 4 | Every file dialog used Tk off the main thread | On macOS this **aborts the process** (`NSException`, `libc++abi`), it does not raise. Streamlit runs page code in a ScriptRunner thread | fixed, Electron dialog over a token-guarded loopback endpoint |
| 5 | `clean-up-workspaces.py` looked in `/workspaces-flashapp`; the app writes `../workspaces-FLASHViewer` | The hosted janitor reclaimed **nothing**; abandoned workspaces accumulated forever | fixed |
| 6 | `export_parameters_markdown()` indexed an empty list when no TOPP ini files exist | Took down the whole Configure tab in any build without TOPP binaries | fixed |
| 7 | FLASHTnT "Add results" indexed `results['tags_tsv']` directly | Bare `KeyError` for anyone who added the two mzMLs before the TSVs | fixed, reports missing files and skips that dataset |
| 8 | `captcha_.py` imported four private `streamlit.source_util` symbols | Pinned Streamlit to 1.42.2 — **via dead code**; nothing called the functions using them | fixed, 167 lines deleted, unpinned, verified on 1.60 |

### Still open, deliberately

| Bug | Why not fixed |
|---|---|
| `src/masstable.py` assigns `df['CombinedPeaks'] = noisyPeaks`, duplicating `NoisyPeaks` | Visibly wrong, but it changes **plotted scientific data**. Needs a maintainer to state the intended semantics — guessing would be worse than the bug |
| `get_results_list()` silently drops columns that do not exist, degrading AND to partial | The root cause of #7 and a landmine for any "do I have this data?" check. `presets.py` already documents and avoids it. A real fix changes query semantics app-wide |
| `preset_page._cache_dir()` raises `KeyError` for `"FLASHQuant"`, plus three more FLASHQuant `KeyError`s in that module | Unreachable today (only the two Layout Manager pages call it). Becomes reachable the moment anything iterates all three tools |
| The Download zip is cached as `download_archive` and never invalidated | A re-run of the same dataset id serves a stale archive |
| A killed app leaves `pids/` behind, so the app believes a run is still executing | Pre-existing; the Run step status inherits it |
| Destructive actions have no confirmation | `Remove all` → `clear_cache()` (×3), `Delete Workspace`, and a per-experiment delete button whose entire label is the experiment name |
| `src/fileupload.py` (all five functions) and `content/TODO_Update/*` are dead | Unreferenced; deleting them belongs in its own change |

---

## 2. Bugs introduced during this work, and caught

Recorded because the pattern matters more than the individual mistakes: **every one
was caught by an adversarial review or a test, not by the change's author.**

| Bug | How it would have failed | Caught by |
|---|---|---|
| `link=` inferred from "is this a Path on desktop" | Linked the workflow's **own temp output**, which is deleted seconds later — every desktop run would have produced an unopenable dataset | design review |
| Making `link` default to `False` then sent the desktop picker down the copy branch, where `remove=True` unlinks the source | **Deleted the user's original mzML** on add. Reproduced before and after | adversarial review of the design |
| Removing the uploader left `files_dir` empty, so the "no data yet" branch always won and referenced files were never listed | Picking a file appeared to do nothing | user report |
| Phase 1 deleted the layout editor that owned the comparison slot count | Multi-dataset comparison became unreachable | self-review before commit |
| Tab flattening | `IndexError` at runtime | smoke test |
| An emoji-removal regex collapsed whitespace runs | Destroyed indentation in ten files | next `git diff` |
| `test_input_listing.py` re-implemented the logic it was testing | Would have stayed green through a refactor that broke the real code | adversarial review of the plan |

**Lesson worth keeping:** ownership must be a recorded property of a file, never
inferred from deployment mode or argument type. Both data-loss bugs above are the
same mistake in two forms.

---

## 3. The desktop app

Electron spawns a bundled portable Python running Streamlit on a random localhost
port. `desktop/` plus one CI workflow; nothing outside it is desktop-specific except
the `FLASHAPP_DESKTOP` branches.

Decisions and the reasons, so they are not relitigated:

- **stlite/WASM is impossible here.** Pyodide installs only pure-Python or
  Emscripten wheels; FLASHApp needs `pyopenms` (compiled C++, no `wasm32` wheel),
  `subprocess` calls to native TOPP tools, and a Vue custom component.
- **uv's managed interpreters are not relocatable** — they bake in an absolute
  prefix. The build downloads a python-build-standalone `install_only` tarball.
- **`pyopenms==3.4.0` on macOS only.** The 3.5.0 macOS wheels ship both
  `libomp.dylib` and `libgomp.1.dylib`; importing aborts with `OMP: Error #15`.
  Marked `sys_platform == "darwin"` because 3.4.0 has no linux-aarch64 wheel.
- **Intel macOS is not built.** Those runners queued for hours while every other
  target finished in minutes.
- **Streamlit is unpinned** — see bug 8. This matters beyond hygiene: 1.60 exposes
  ~50 theme keys and `st.navigation(position="top")`, so the visual system is
  declarative config rather than CSS injection against internal class names.
- **The app writes `../workspaces-<repo>` relative to its cwd**, so it cannot run
  from a read-only resource directory. `main.js` copies the payload into `userData`
  on first run.
- **"Copy share link" is hidden on desktop** — Electron binds a random localhost
  port, so the URL means nothing to anyone else and differs next launch.
- **Signing is wired but dormant**: macOS entitlements exist (hardened runtime
  refuses to load `pyopenms`/`numpy`/`pyarrow` without `disable-library-validation`);
  Windows goes through SignPath, whose artifact configuration must expect a ZIP
  because `upload-artifact` always zips.

### Desktop asymmetry worth knowing

Workflow **input** is referenced in place (paths in `external_files.txt`). Results
added via **Add results** are **copied** — `link=True` is never passed in production.
Switching that on is decided but not implemented, and should ship together with the
"referenced file has moved" handling (clear failure + size/mtime fingerprint), or a
moved file becomes an unopenable dataset.

---

## 4. Design handoffs

Three arrived from Claude Design. Each was reviewed against the code before anything
was built; roughly a quarter of the last one was buildable.

| Handoff | Verdict |
|---|---|
| v1 — navigation/IA + presets | Preset catalogue named two components that do not exist (`flash_quant_view`, `conflict_resolution`) and shipped a preset that raised `KeyError` in the viewer. Design system it cited (`tokens/*.css`, logo SVG, a Font Awesome loader at a Hugo path) did not exist |
| v2 — same, plus a design system | Shipped real tokens, but they contradicted the README that came with them: six of seven cited colours absent, and **no status palette at all** while preset availability depends on three |
| v3 — wizard navigation | Much the best: reviewed the actual commit, cited real symbols. Still: its run model is unbuildable (three tools, three caches, three id namespaces, and one run produces one dataset per input file), its drop zone cannot infer the tool from filenames (`_deconv.mzML` is accepted identically by two tools), and its Workspace settings tab would have leaked per-session workspaces across tenants on the hosted deployment |

**Adopted from v3:** `st.navigation(position="top")` — the headline "remove the
sidebar" change turned out to be one keyword, keeping page URLs and history that a
hand-rolled router would have lost; workspace management in a dialog; step-named
workflow tabs; parsing given a visible phase; the viewer no longer gated on a run
this app performed.

**Two diagnoses from v3 that were right and are now fixed:** parsing was a silent
multi-minute phase, and the viewer claimed you had to run a workflow when adding
finished output is equally valid.

All reviews are in `../design-reviews/`.

---

## 5. Deferred with decisions recorded

`../design-reviews/file-management/DECISIONS.md`:

- **URI ingest**: `https://` everywhere with private ranges blocked; `file://`
  desktop-only.
- **Moved referenced files**: fail clearly, plus a size+mtime fingerprint.
- **Migration**: do **not** migrate existing workspaces. Consequence: filename-derived
  ids stay, so the SQL-injection surface was closed by parameterising instead — which
  protects old workspaces too.
- **Opaque dataset ids: rejected.** The upload pages use the stripped filename as a
  *join key*, deliberately: `sampleA_deconv.mzML` and `sampleA_annotated.mzML` must
  collide into one dataset. Minting ids per acquisition would produce four datasets
  where one is needed, and nothing would render.

In-flight cleanup plan and its adversarial review:
`../design-reviews/file-management/ADVERSARIAL-CLEANUP-PLAN.md`.

---

## 6. Things that will bite the next person

- **`st.tabs` renders every tab body on page load.** `execution()` reads
  `get_parameters_from_json()['FLASHTnT']` unguarded — it only works because the
  Method tab always rendered. Switching to lazy tabs gives a bare `KeyError` inside a
  detached `multiprocessing.Process`, visible only as `ERROR:` in a log file.
- **`FileManager.__init__` has side effects** — `mkdir` plus `CREATE TABLE`. Anything
  that iterates all three tools to ask a question will *create* caches for tools the
  user never opened.
- **SQLite connections must not outlive a script run.** Streamlit runs each rerun on
  a fresh thread; caching a `FileManager` in session state raises intermittently.
- **`save_parameters()` runs on every widget render**, so `params.json` exists after
  the first page load. Its existence proves nothing about user intent.
- **`upload_widget` auto-copies the example files** whenever its directory is empty,
  so "input present" is true after one visit with no user action.
- **Cache tag names are load-bearing**: `parseDeconv(**results)` works only because
  the tags equal the parser's parameter names. `parseTnT`'s do **not** match
  (`deconv_mzML` vs `out_deconv_mzML`), so it is called positionally.
- **Dataset ids are unique only within one tool's cache.**
- **The run log is wiped at the start of every run** and is per-tool, not per-dataset.
  There is no persisted record that a run completed, only `WORKFLOW FINISHED` in the
  current log.
