# 01 — Setup & Prerequisites

Goal: a machine that can build **both** targets (native C++ server + WebAssembly) before any project code exists.

## 1.1 Required Toolchain

| Tool                   | Minimum version | Purpose                                      | Check command         |
| ---------------------- | --------------- | -------------------------------------------- | --------------------- |
| Git                    | 2.30+           | Version control                              | `git --version`     |
| CMake                  | 3.16+           | Build orchestration                          | `cmake --version`   |
| C++17 compiler         | see §1.2       | Core + server builds                         | `c++ --version`     |
| Python 3               | 3.8+            | Dataset normalizer utility (stdlib only)     | `python3 --version` |
| Emscripten SDK (emsdk) | 3.1.x pinned    | WASM build                                   | `emcc --version`    |
| Node.js                | 18+             | Runs WASM module in Node during parity tests | `node --version`    |

**Commit point:** After verifying the toolchain versions, record them (e.g., in a `TOOLCHAINS.md` file) and commit.

```bash
git add TOOLCHAINS.md
git commit -m "chore: record required toolchain versions"
```

## 1.2 Compilers by OS

**macOS** (this project's dev machine):

```bash
xcode-select --install          # Apple clang + headers
brew install cmake git node
```

Apple clang 14+ is fine.

**Linux (Ubuntu/Debian)**:

```bash
sudo apt update
sudo apt install -y build-essential cmake git python3 nodejs npm
```

**Windows**: install *Visual Studio 2022* with the "Desktop development with C++" workload, plus Git for Windows and CMake (`winget install Kitware.CMake`). Use the *Developer Command Prompt* for all commands below.

**Commit point:** After installing the compiler and basic tools, commit any environment‑setup scripts or notes.

```bash
git add <any-setup-files>
git commit -m "chore: add OS‑specific compiler setup notes"
```

## 1.3 Install Emscripten SDK

Pin one SDK version and use it everywhere (local + CI) to keep WASM output reproducible:

```bash
git clone https://github.com/emscripten-core/emsdk.git "$HOME/tools/emsdk"
cd "$HOME/tools/emsdk"
./emsdk install 3.1.61           # ← pin this exact version
./emsdk activate 3.1.61
source ./emsdk_env.sh            # add to ~/.zshrc / ~/.bashrc for convenience
```

Verify:

```bash
emcc --version        # must report 3.1.61
emcmake --version     # wrapper around cmake
```

> Windows: run `emsdk.bat` instead; use `emsdk_env.cmd` in the prompt you build from.

**Commit point:** After activating the Emscripten SDK, record the exact version used (e.g., in `TOOLCHAINS.md`) and commit.

```bash
git add TOOLCHAINS.md
git commit -m "chore: pin Emscripten SDK version 3.1.61"
```

## 1.4 Editor Setup (VS Code recommended)

Extensions:

- `ms-vscode.cpptools` — IntelliSense/debug
- `ms-vscode.cmake-tools` — CMake integration
- `esbenp.prettier-vscode`, `dbaeumer.vscode-eslint` — JS formatting/linting
- `eamodio.gitlens` — git history

Recommended `.vscode/c_cpp_properties.json` include path once the repo exists:

```json
{
  "configurations": [{
    "name": "Mac/Linux",
    "includePath": ["${workspaceFolder}/core/include", "${workspaceFolder}/server/third_party"]
  }]
}
```

**Commit point:** After adding VS Code configuration files, commit them.

```bash
git add .vscode/
git commit -m "chore: add VS Code workspace settings"
```

## 1.5 CLion Setup (Alternative to VS Code)

If you prefer JetBrains CLion, you can either **open an existing repository** (as described below) or **start a brand‑new CLion CMake project** and then populate it with the canonical structure. Both paths end with the same layout; choose the one that fits your workflow.

### 1.5.1 Opening an Existing Repository (recommended if you already followed the Git steps in doc 02)

1. **Install CLion** (download from https://www.jetbrains.com/clion/).  
2. Launch CLion and choose **Open** → navigate to the folder that contains the top‑level `CMakeLists.txt` (the repo root).  
3. CLion will automatically detect the default toolchain for native builds.  
4. **Toolchain configuration for WASM** – add a custom toolchain:  
   *Settings → Build, Execution, Deployment → Toolchains → + →*  
   - Name: `Emscripten`  
   - C compiler: path to `emcc` (from the emsdk)  
   - C++ compiler: path to `em++`  
   - Ensure the environment variables from `emsdk_env.sh` are sourced (launch CLion from a shell where you ran `source ./emsdk_env.sh`).  
5. **CMake profiles** – create two profiles:  
   - **Native**: default toolchain, build type `Release` (or `Debug`).  
   - **WASM**: select the Emscripten toolchain, set `CMAKE_BUILD_TYPE=Release`.  
   Switch profiles via the dropdown in the lower‑right corner and click the *Reload CMake Project* icon after changing.  
6. **Build** – use the *Build* hammer icon or `Ctrl+F9`.  
7. **Run/Debug** – for the native server create a Run configuration targeting `currency_server`; for WASM you’ll usually test via the web frontend (see later docs).  

**Commit point:** After configuring CLion and saving the workspace (`.idea/` folder), commit the IDE‑specific files (if you choose to version them; otherwise add `.idea/` to `.gitignore` and skip this commit).

```bash
# If you decide to version CLion settings:
git add .idea/
git commit -m "chore: add CLion workspace and toolchain settings"
# Otherwise, ensure .idea/ is ignored:
echo ".idea/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore CLion IDE files"
```

### 1.5.2 Starting a Fresh CLion CMake Project (no prior repo)

Follow these steps to create the project directly inside CLion, then add the required directories and files as described in doc 02.

1. **Launch CLion** → **File → New Project**.  
2. Choose **CMake Executable** as the project type.  
3. Set **Project name** to `currency-converter-dashboard` (or any name you prefer).  
4. Choose a **location** (e.g., `~/Projects/currency-converter-dashboard`).  
5. Keep the default **CMake** and **toolchain** selections for now; we’ll adjust them later.  
6. Click **Create**. CLion will generate a minimal `CMakeLists.txt` and a `main.cpp` inside a `src` folder.  

#### 1.5.2.1 Replace the generated skeleton with the canonical structure

Close the default `main.cpp` (we won’t need it) and delete the `src` folder that CLion created (or keep it empty). Then, using the file system or CLion’s tool window, create the directories exactly as specified in doc 02:

```
currency-converter-dashboard/
├── CMakeLists.txt                    # will be edited below
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy-pages.yml
├── core/
│   ├── CMakeLists.txt
│   ├── include/ccd/
│   │   ├── models.h
│   │   ├── csv_parser.h
│   │   ├── rate_engine.h
│   │   └── stats_engine.h
│   ├── src/
│   │   ├── csv_parser.cpp
│   │   ├── rate_engine.cpp
│   │   └── stats_engine.cpp
│   └── tests/
│       ├── third_party/doctest.h
│       ├── test_csv_parser.cpp
│       ├── test_rate_engine.cpp
│       └── test_stats_engine.cpp
├── server/
│   ├── CMakeLists.txt
│   ├── third_party/httplib.h
│   ├── third_party/json.hpp
│   ├── main.cpp
│   └── api_routes.{h,cpp}
├── wasm/
│   ├── CMakeLists.txt
│   └── bindings.cpp
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   ├── js/{config.js, api.js, app.js, chart_panel.js, utils.js}
│   ├── vendor/chart.umd.min.js
│   └── wasm/                         # build output (gitignored)
├── data/
│   ├── exchange_rates.csv
│   ├── sample_rates.csv
│   └── CREDITS.md
├── tools/
│   └── normalize_dataset.py
├── scripts/
│   ├── smoke_api.sh
│   └── parity_test.mjs
├── docs/
│   ├── PRD.md
│   └── implementation/
├── .gitignore
├── .gitattributes
├── LICENSE
└── README.md
```

You can create these folders via **File → New → Directory** in CLion, or using your terminal and then **Refresh** the CLion view.

#### 1.5.2.2 Configure the top‑level `CMakeLists.txt`

Replace the content of the generated `CMakeLists.txt` with the following (this is the hub that uses `add_subdirectory` for each module):

```cmake
cmake_minimum_required(VERSION 3.16)
project(currency-converter-dashboard LANGUAGES C CXX)

# Options
option(BUILD_WASM "Build WebAssembly target" OFF)

# Core library
add_subdirectory(core)

# Native HTTP server
add_subdirectory(server)

# WASM target (only when requested)
if(BUILD_WASM)
    add_subdirectory(wasm)
endif()

# Optional: install rules, testing, etc. can be added later
```

#### 1.5.2.3 Set up toolchains and CMake profiles

1. **Native toolchain** – CLion will auto‑detect your system compiler (e.g., Apple clang, GCC, or MSVC). No extra action needed unless you want to force a specific one.  
2. **WASM/Emscripten toolchain** –  
   - Open *Settings → Build, Execution, Deployment → Toolchains*.  
   - Click the **+** button to add a new toolchain.  
   - **Name**: `Emscripten`  
   - **C compiler**: `<path-to-emsdk>/emscripten/<version>/emcc`  
   - **C++ compiler**: `<path-to-emsdk>/emscripten/<version>/em++`  
   - **Environment**: make sure the variables from `emsdk_env.sh` are present; the easiest way is to launch CLion from a terminal where you ran `source ./emsdk_env.sh`.  
3. **CMake profiles** –  
   - Go to *Settings → Build, Execution, Deployment → CMake*.  
   - Click **+** to add a profile.  
   - **Profile name**: `Native-Release`  
     - Toolchain: `<default>` (or your native compiler)  
     - Build type: `Release`  
     - CMake options: `-DBUILD_WASM=OFF`  
   - Add another profile:  
   - **Profile name**: `WASM-Release`  
     - Toolchain: `Emscripten` (the one you just created)  
     - Build type: `Release`  
     - CMake options: `-DBUILD_WASM=ON`  
   - Apply and close settings.  

You can now switch between the profiles using the dropdown in the lower‑right corner of the CLion window. After switching, click the **Reload CMake Project** icon (the circular arrows) to re‑run CMake with the new options.

#### 1.5.2.4 Build and run

- **Native build**: select the `Native-Release` profile, then click the **Build** hammer icon or press `Ctrl+F9`. The executable `currency_server` will appear under `build/` (CLion’s default cmake-build-<profile> directory).  
- **WASM build**: switch to the `WASM-Release` profile, reload CMake, then build. Outputs (`currency_core.js` and `currency_core.wasm`) will be generated in the `wasm/` subdirectory under the build folder. The CI/deploy workflow later copies these to `frontend/wasm/`.  

- **Running the native server**: create a *Run/Debug* configuration:  
  - **Executable**: `currency_server`  
  - **Program arguments** (optional): `--data data/exchange_rates.csv --static frontend`  
  - Apply and click **Debug** or **Run**.  

- **Testing WASM**: open `frontend/index.html` in a browser (or serve it with a simple static server). The page loads the WASM module via the generated `currency_core.js`.  

**Commit point:** After you have set up the directory structure, edited the top‑level `CMakeLists.txt`, configured the toolchains/profiles, and verified that both native and WASM builds succeed, make a commit.

```bash
git add .
git commit -m "chore: initialize project structure via CLion (native + WASM profiles)"
```

If you prefer not to version the `.idea/` folder, add it to `.gitignore` before committing:

```bash
echo ".idea/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore CLion IDE files"
```

## 1.6 Third-Party Headers to Vendor Later

These are downloaded in [02](02-repository-and-project-structure.md) and committed so CI never depends on external downloads at build time:

| File                                 | Source                                         | Pinned version |
| ------------------------------------ | ---------------------------------------------- | -------------- |
| `server/third_party/httplib.h`     | github.com/yhirose/cpp-httplib (single header) | v0.15.3        |
| `server/third_party/json.hpp`      | github.com/nlohmann/json (single header)       | v3.11.3        |
| `core/tests/third_party/doctest.h` | github.com/doctest/doctest (single header)     | v2.4.12        |

No package manager, no FetchContent, no network during builds.

**Commit point:** After vendoring each third‑party header, commit it.

```bash
git add server/third_party/httplib.h server/third_party/json.hpp core/tests/third_party/doctest.h
git commit -m "chore: vendor third‑party headers (httplib, nlohmann/json, doctest)"
```

## 1.7 Kaggle Dataset — ✅ ACQUIRED

The dataset is already in hand and processed. **Do not re-do acquisition** — the full pipeline lives in [`A-data-pipeline.md`](A-data-pipeline.md). Summary:

| Artifact                                                                     | Status                                          |
| ---------------------------------------------------------------------------- | ----------------------------------------------- |
| `daily_forex_rates.csv` (raw, 21.8 MB, long format, EUR base)              | ✅ downloaded 2026-08-25 · gitignored          |
| `data/exchange_rates.csv` (canonical wide, 4.6 MB, 174 cur × 6,551 dates) | ✅ generated + verified                         |
| `data/sample_rates.csv` (fixture: 40 days × 8 majors)                     | ✅ generated                                    |
| `data/CREDITS.md` (Kaggle URL + license)                                   | ⚠️ owner must fill in before repo goes public |

If you ever switch to a different/newer export of the same type, follow [A-data-pipeline §A.4](A-data-pipeline.md#a4-regeneration-procedure-updatednew-dataset-of-the-same-type) — it is a 4-command procedure gated by `scripts/verify_dataset.py`.

**Commit point:** After generating the canonical dataset and updating `data/CREDITS.md`, commit those files.

```bash
git add data/exchange_rates.csv data/sample_rates.csv data/CREDITS.md
git commit -m "data: add canonical dataset and attribution"
```

## 1.8 Verification Checklist

Run all of these; every one must succeed before starting [02](02-repository-and-project-structure.md):

- [ ] `git --version`
- [ ] `cmake --version` ≥ 3.16
- [ ] `c++ --version` (or MSVC `cl` available)
- [ ] `emcc --version` reports the pinned SDK
- [ ] `node --version` ≥ 18
- [ ] `python3 --version` ≥ 3.8
- [X] Dataset acquired & verified — see [A-data-pipeline](A-data-pipeline.md)

**Commit point:** After the verification checklist passes, add a final commit indicating the setup is complete.

```bash
git add -u  # update any modified tracking files
git commit -m "setup: verify toolchain and dataset ready for development"
```

## ✅ Exit Checklist

- [ ] Both build paths proven viable (compiler + emsdk both functional)
- [ ] Pinned versions recorded: emsdk `3.1.61`, httplib `0.15.3`, nlohmann/json `3.11.3`, doctest `2.4.12`
- [ ] Dataset pipeline re-runnable: `scripts/verify_dataset.py` passes (CREDITS.md attribution filled in)
