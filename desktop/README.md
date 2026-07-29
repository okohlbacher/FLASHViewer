# FLASHApp Desktop

Packages FLASHApp as a self-contained desktop app for Windows, macOS and Linux.
Electron spawns a bundled Python running Streamlit on a random localhost port and
loads it in a window. End users install nothing — no Python, no Node, no browser
setup.

```bash
cd desktop
./build.sh              # stage repo + portable Python + deps + TOPP tools
npm install
npm start               # dev run
npx electron-builder    # .dmg / .exe / .AppImage for the host OS
```

Installers must be built on their target OS; `.github/workflows/desktop.yml`
does that on a three-OS matrix.

## How it works

`main.js` picks a free port, spawns `runtime/bin/python3 -m streamlit run app.py`,
waits for the port to answer, then opens a `BrowserWindow` on it. Nothing in
`app.py`, `src/` or `content/` had to change.

Two details worth knowing:

- The app writes workspaces to `../workspaces-FLASHViewer` relative to its cwd,
  which cannot be inside the read-only resource dir. `main.js` copies the payload
  into the per-user `userData` directory on first run and runs it from there.
- TOPP binaries staged into `topp/` are prepended to the child's `PATH`, which is
  how `CommandExecutor` resolves `FLASHDeconv` and friends. Without them the
  Viewer and Upload pages work and the Workflow pages do not. `build.sh` copies
  whatever it finds in `$OPENMS_BIN`.

## Pins (`constraints.txt`)

Both are upstream issues this build has to work around:

- `pyopenms==3.4.0` — the 3.5.0 macOS wheels ship both `libomp.dylib` and
  `libgomp.1.dylib`; importing pyopenms aborts with `OMP: Error #15`.
- `streamlit==1.42.2` — `src/common/captcha_.py` imports the private
  `streamlit.source_util.calc_md5`, removed in Streamlit 1.43. `requirements.txt`
  says `streamlit>=1.39.0` with no upper bound, so a fresh install picks 1.60 and
  every page raises `ImportError`.

## Not done yet

- Code signing and notarization. macOS shows "damaged and can't be opened" for
  downloaded unsigned bundles; Windows SmartScreen warns. Needs a Developer ID
  and hardened-runtime entitlements for the bundled interpreter.
- App icon (the default Electron icon is used).
- Auto-update.

## Why not stlite/WASM

stlite runs Python under Pyodide, which can only install pure-Python or
Emscripten-built wheels. FLASHApp needs three things Pyodide has no answer for:
`pyopenms` (compiled C++, no `wasm32` wheel exists), `subprocess` calls to native
TOPP tools, and the Vue custom component served from `js-component/dist`.
