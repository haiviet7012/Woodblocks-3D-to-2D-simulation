# Install dependencies, run the notebook, and inspect results

This guide targets **CPython 3.14.4 on Linux x86_64**, including VS Code Remote SSH over WireGuard. Run terminal commands on the machine that will execute the notebook. WireGuard provides network access; it does not select Python or install packages.

## 1. Open the checkout on the execution machine

In VS Code Remote SSH, connect to your server, choose **File > Open Folder**, and open your checkout. In Codespaces, use the Codespace terminal. For a new checkout:

```bash
git clone https://github.com/haiviet7012/Woodblocks-3D-to-2D-simulation.git
cd Woodblocks-3D-to-2D-simulation
pwd
```

For an existing checkout, `cd` to its actual directory instead of cloning again. The repository root contains `requirements.txt`, `v5_metrics_update.py`, the notebook, and `metrics/`.

Fonts and textures are committed separately from scan files. Confirm the assets available in your checkout:

```bash
ls -lh input/fonts/NomNaTong-Regular.ttf
ls -lh input/wood_texture/Natural-Oak-Wood-Texture.jpg
```

Provide your real scan at `input/stl/03284.stl` locally. STL files are ignored by Git and are not supplied by cloning. If your scan has another name or lives in a date directory, configure its exact path in section 1 of the notebook.

## 2. Create an environment with Python 3.14.4

Check the installed executable first:

```bash
python3.14 --version
python3.14 -c 'import sys; print(sys.executable); assert sys.version_info[:3] == (3, 14, 4), sys.version'
```

If the command is missing or shows another patch version, install/provide CPython 3.14.4 using the server's approved installation method. `.python-version` records the desired version but does not install it. If Python 3.14.4 has a different absolute executable path, use that path instead of `python3.14` in the next command.

From the repository root:

```bash
python3.14 -m venv .venv
.venv/bin/python --version
.venv/bin/python -m pip --version
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

Wait for installation to finish successfully. `pip check` should report no broken requirements. Always use `.venv/bin/python -m pip` to install into this environment; a bare `pip` command might target another interpreter. Activation is optional when using these explicit paths. If preferred, activate with `source .venv/bin/activate` and confirm `python` points to this environment.

The requirements file is the server's package freeze, including CUDA packages and packages outside the rendering path. Installation may be large. The exact Python version alone does not guarantee that every pinned wheel is available for your system. If installation fails, keep the first failing package/version and error; do not assume later imports will work or silently substitute versions for a reproduction.

If creating the environment reports missing pip/ensurepip, ask the host administrator to provision the venv/pip support for this exact Python installation. If pip is present but installation reports network/DNS errors, use the offline workflow in [SETUP.md](SETUP.md#8-offline-installation). Installing packages on your laptop will not install them on a remote server.

## 3. Select the Python interpreter and notebook kernel

Install/enable the **Python**, **Pylance**, and **Jupyter** VS Code extensions in the remote execution environment when using Remote SSH or Codespaces.

Register the kernel:

```bash
.venv/bin/python -m ipykernel install --user --name woodblocks-py314 --display-name 'Woodblocks (Python 3.14.4)'
```

Then in VS Code:

1. Open the repository folder.
2. Open the Command Palette (`Ctrl+Shift+P`).
3. Run **Python: Select Interpreter**.
4. Select the checkout's `.venv/bin/python`. Use **Enter interpreter path** if necessary.
5. Open `mitsuba_research_v5_gpu.ipynb`.
6. Use **Select Kernel** in the notebook's top-right corner and select **Woodblocks (Python 3.14.4)** or the same `.venv` under Python Environments.
7. Restart the notebook kernel after switching environments.

The Python-file interpreter controls analysis of `.py` files. The notebook kernel controls executed cells. Select both; changing only one can leave yellow diagnostics or runtime import errors.

Run this diagnostic cell before the pipeline:

```python
import sys
print(sys.executable)
print(sys.version)
assert sys.version_info[:3] == (3, 14, 4)
```

The executable should point to this checkout's `.venv/bin/python`. To inspect packages in the active kernel without relying on shell quoting:

```python
import subprocess
subprocess.run([sys.executable, '-m', 'pip', 'show',
                'numpy', 'opencv-python-headless', 'mitsuba', 'drjit'], check=False)
```

## 4. Resolve “import could not be resolved” diagnostics

Open **View > Problems** (`Ctrl+Shift+M`) and read the full message, including the import and diagnostic source. A yellow Pylance warning is an editor diagnostic; `ModuleNotFoundError` in a cell traceback is an execution failure. A Git `U` or `M` marker is file status, not an import error.

First verify the selected interpreter and kernel using section 3. Then run:

```bash
.venv/bin/python scripts/preflight.py
.venv/bin/python -m pip check
```

Preflight reports imports that actually fail in this interpreter. Common import names differ from their package names:

| Python import | Package in requirements.txt |
| --- | --- |
| `cv2` | `opencv-python-headless` |
| `PIL` | `pillow` |
| `numpy` | `numpy` |
| `mitsuba` | `mitsuba` |
| `drjit` | `drjit` |
| `trimesh` | `trimesh` |
| `fast_simplification` | `fast_simplification` |
| `rtree` | `rtree` |
| `scipy` | `scipy` |
| `pandas` | `pandas` |
| `matplotlib` | `matplotlib` |
| `psutil` | `psutil` |
| `ipykernel` | `ipykernel` |

Do not run `pip install cv2` or `pip install PIL`. Install the supplied requirements using the intended interpreter:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c 'import numpy, cv2, trimesh, mitsuba, drjit; print("Core imports OK")'
```

If imports succeed in that terminal but Pylance still warns, reselect the same interpreter and use **Developer: Reload Window**. Restart the notebook kernel if packages were installed while it was running. Keep the warning enabled until you know its cause; suppressing it does not install a missing dependency.

If only a local module is unresolved, open the repository root rather than an isolated file. Keep the `metrics/` directory alongside the notebook. `v5_metrics_update.py` intentionally obtains notebook functions through `exec(..., globals())`; it must be loaded at section 12.5 after its dependencies exist, not executed as a standalone script.

An import error mentioning a shared library, driver or undefined symbol needs the relevant host library/runtime investigated. Reinstalling Python packages or hiding Pylance diagnostics does not repair an NVIDIA driver. Run the render probe and preserve its full error:

```bash
.venv/bin/python scripts/preflight.py --render-probe --variant cuda_ad_rgb
```

A Codespace or SSH connection does not itself provide a CUDA GPU. Deliberate LLVM execution can be probed with `--variant llvm_ad_rgb`, but is a different condition from a GPU reference run.

## 5. Create and check the output directory

From the repository root:

```bash
mkdir -p testing_outputs
.venv/bin/python -c 'from pathlib import Path; p=Path("testing_outputs")/"write_probe.tmp"; p.write_text("ok"); p.unlink(); print("Output directory is writable")'
```

`mkdir -p` keeps existing files. The write check should finish without a permission error. If it fails, choose an output directory you own or ask the server owner to grant access; do not change permissions recursively on shared research data.

The notebook also creates output directories automatically. Section 1 sets the output base to `PROJECT_ROOT / "testing_outputs"` and appends a generated run ID. The environment section creates that run's subdirectories and checks writing. Therefore the actual destination is:

```text
testing_outputs/<RUN_ID>/
```

For example, a new run might be named `metric_pilot_a1b2c3d4`; read the printed name from your own run. Output data is ignored by Git and must be copied/exported separately when needed.

## 6. Configure an initial pilot

Open the existing notebook; do not create a replacement notebook. In the **section 1 configuration cell**, review the actual assignments before executing it:

```python
cfg.mesh_source = "file"
cfg.input_dir = str(PROJECT_ROOT / "input" / "stl")
cfg.mesh_path = str(PROJECT_ROOT / "input" / "stl" / "03284.stl")
cfg.mesh_paths = []
```

These show the desired values. The existing `Config` class already supplies the default paths. If changing them, edit the defaults or add the assignments immediately after `cfg = Config()` and before the run setup. `input_dir` must remain a directory and `mesh_path` must identify a real file. `cfg.mesh_paths` is later populated with processed mesh paths; do not fill it with stale paths from another run.

Find the existing override `cfg.n_images = 12` in the configuration cell and **replace it** with:

```python
cfg.n_images = 1
```

Do not add an earlier assignment that the later override would replace. This requests one image per mesh, not a one-image full experiment covering every profile. Inspect the pilot before expanding.

Keep `cfg.resume_run_id = ""` for a fresh run. Running the configuration cell again creates a new run ID. To preserve a run, note `RUN_ID` and `ROOT` before restarting; resuming requires intentionally setting the existing run ID and matching configuration/input provenance. Do not mix runs by manually copying old logs into a new run directory.

If the kernel working directory is outside the repository, set `WOODBLOCK_PROJECT_ROOT` to the absolute checkout path before running section 1, as described in SETUP.md. Never confuse `PROJECT_ROOT` (source checkout) with `ROOT` (this run's output directory).

## 7. Run the notebook in order

For the first pilot, execute section by section rather than launching a large batch immediately:

| Notebook section | What to do and inspect |
| --- | --- |
| 0–1 | Confirm the environment is already installed; review configuration, selected scan, image count and printed output path. |
| 2 | Confirm a Mitsuba variant really initializes. Record the actual variant and SPP. |
| 3 / 3b | Verify inputs, reduce the mesh and inspect the CPU surface-distance report. Large scans can require significant RAM/time even for one image. |
| 4–12 | Execute definitions and preparation cells in order. Synthetic-board definitions do not mean the selected file scan is replaced. |
| 12.5 | Load `v5_metrics_update.py`; check printed pipeline/metric versions and external backend path. |
| 13–15 | Define rendering, exports and notebook checks. Some checks execute work rather than merely defining functions. |
| 16 / 16.1 | Load the selected object, inspect annotation status and run the projection check. A failed check must be investigated. |
| 17 | Run the pilot render. Read acceptance/rejection and metric messages. |
| 17.1 | Build and display metric tables from the per-sample logs. |
| 18 | View the notebook QA dashboard. |
| 19–20 | Inspect checks and write run summaries. Archive creation is optional and commented out. |

If a cell fails, save its full traceback. Fix that problem before proceeding. After editing configuration, mesh setup or dependencies, restart the kernel and rerun the necessary preceding sections; old in-memory values may otherwise remain.

The notebook tries CUDA before LLVM and uses different default SPP for CPU. A successful LLVM fallback is not evidence of identical GPU output. Keep actual variant, SPP, seed, assets and configuration aligned with the reference experiment.

## 8. Find images and inspect the run visually

After rendering, print these variables in the existing notebook kernel:

```python
print("Run ID:", RUN_ID)
print("Run directory:", ROOT)
print("Final images:", ROOT / "images")
print("Diagnostics:", ROOT / "overlays")
```

In VS Code Explorer expand `testing_outputs`, then the printed run directory. Open images directly, or use this cell to preview the first final image:

```python
from IPython.display import display, Image
images = sorted((ROOT / "images").glob("*.jpg"))
print("Saved final images:", len(images))
if images:
    display(Image(filename=str(images[0]), width=1000))
```

Inspect diagnostic overlays as well:

```python
diagnostics = sorted((ROOT / "overlays").glob("*_diagnostic.png"))
if diagnostics:
    display(Image(filename=str(diagnostics[0]), width=1200))
```

The four panels show final RGB, the stroke mask, reviewed/proposed ROI and exclusion, and measurement regions. Amber is proposal ROI; cyan is reviewed ROI; magenta is exclusion. Red is the edge measurement band and green is the background control. These colors are not correctness labels. Inspect individual strokes and background contamination before trusting quality scores.

## 9. Read CSV metrics and per-sample JSON

Use section 17.1 or a later cell in the same kernel:

```python
import pandas as pd
metrics = pd.read_csv(ROOT / "render_metrics.csv")
columns = ["sample_id", "stage", "lap_global", "lap_local", "E_net",
           "E_proxy", "E_status", "external_backend_status"]
display(metrics[[c for c in columns if c in metrics.columns]])
final_metrics = metrics.loc[metrics["stage"].eq("final")].copy()
display(final_metrics)
```

Each measured sample has separate `render` and `final` rows. Select `final` for final-image analysis instead of accidentally counting both stages as separate images. External backend columns start with `external__`. `metrics_long.csv` stores metric names, values and statuses in long format.

Empty/NaN `E_net`, `lap_local`, `ec_2d`, `ec_3d` or `edge_f1` may reflect missing reviewed ROI/stroke or another measurement status. Check status/reason columns and the sample JSON before interpreting missing data. Do not replace missing values with zero or turn validation flags on to fill a table. CER remains pending until a separate OCR handoff.

Read an authoritative per-sample metric log:

```python
import json
logs = sorted((ROOT / "logs").glob("*_metric.json"))
if logs:
    record = json.loads(logs[0].read_text(encoding="utf-8"))
    print("Metric log:", logs[0])
    print("Sample:", record.get("sample_id"))
    print("Final E status:", record["stages"]["final"].get("E_status"))
    print("External backend:", record["stages"]["final"].get("external_backend"))
    print("Saved files:", record.get("files"))
```

Paths in `record["files"]` are relative to `ROOT`. Use them to find the evidence belonging to the same sample rather than choosing unrelated files by name.

## 10. Output reference

| Path within a run | Contents / viewing method |
| --- | --- |
| `images/` | Final JPEG images; open in VS Code or display in a cell. |
| `render_images/` | Render-stage PNG images before the final stage. |
| `overlays/` | Label/metric overlays and `*_diagnostic.png`; inspect visually. |
| `masks/` | Exported stroke, ROI, support and control masks; white pixels mark selected regions. |
| `edge_maps/` | Gradient maps and display previews; previews are scaled for viewing, not raw measurement values. |
| `geometry/*_maps.npz` | Numerical geometry/mask/gradient arrays; use NumPy, not an image viewer. |
| `logs/*_metric.json` | Per-sample metric provenance, stages, statuses and saved-file references. |
| `labels/` | Image labels, metadata and acceptance/rejection information. |
| `assets/annotation_reference/` | Normalized-mesh reference assets for annotation review. |
| `selftest/` | Projection/check images where generated. |
| `render_metrics.csv` | Wide table with render/final stage rows and status columns. |
| `metrics_long.csv` | Long-format metric values/statuses. |
| `summary.json`, `run_summary.json` | Run summaries produced at the relevant export steps. |
| `dataset_qa.csv`, `dataset_audit.json`, `parameter_metric_bins.csv` | Audit outputs when the corresponding steps run. |

Inspect NPZ array names/shapes without loading a mesh:

```python
import numpy as np
maps = sorted((ROOT / "geometry").glob("*_maps.npz"))
if maps:
    with np.load(maps[0], allow_pickle=False) as arrays:
        for name in arrays.files:
            print(name, arrays[name].shape, arrays[name].dtype)
```

Some outputs appear only after their notebook export/audit steps run. A created run directory alone does not indicate a successful render. If no final images exist, inspect the rendering traceback, rejection records and sample logs.

## 11. Preserve and download results

Capture the environment on the execution host; replace `YOUR_RUN_ID` with the printed ID:

```bash
.venv/bin/python scripts/capture_environment.py --output testing_outputs/YOUR_RUN_ID/environment.json
```

In VS Code Remote SSH, browse the run folder and use the available download/copy facilities to transfer selected images, CSVs and JSON logs. Keep all evidence for the same run together. Large geometry arrays and processed meshes may make a full archive expensive.

To explicitly archive a completed run from the notebook:

```python
import shutil
archive = shutil.make_archive(str(ROOT), "zip", root_dir=ROOT)
print(archive)
```

This writes a ZIP beside the run directory and needs additional disk space. It does not upload results to GitHub. Outputs remain local/remote files until you transfer them. Preserve the code commit, environment snapshot, configuration and input hashes with reported results. Exact pixel equivalence across GPU/drivers/variants remains unverified.
