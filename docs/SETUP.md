# Setup, execution and reproducibility

## 1. Host prerequisites

The recorded server uses CPython **3.14.4**, Linux x86_64 and glibc 2.43. The Python patch version is also recorded in `.python-version`; tools that understand that file can use it, but it does not install Python automatically.

Install Python 3.14.4, Git and Git LFS using your host's supported installation method. For CUDA rendering, the host needs an NVIDIA GPU and a compatible NVIDIA driver. Python CUDA packages do not install the host driver. For LLVM rendering, the host must provide the LLVM runtime supported by Mitsuba/Dr.Jit. This project has not validated Windows, macOS or a different Linux distribution against the reference server.

Check `python3.14 --version`, `git lfs version` and, for GPU runs, `nvidia-smi`. Obtain the actual reference GPU/driver information using the environment capture below; it has not been invented or inferred from the package freeze.

## 2. Clone with scan data

```bash
git lfs install
git clone https://github.com/haiviet7012/Woodblocks-3D-to-2D-simulation.git
cd Woodblocks-3D-to-2D-simulation
git lfs pull
git lfs ls-files
```

The expected input is `input/stl/03284.stl`. A text file beginning with `version https://git-lfs.github.com/spec/v1` is an unresolved pointer, not a mesh. Run `git lfs pull` and check access/quota if it remains a pointer. A ZIP download is not the recommended setup path.

The actual STL must first be committed and pushed by its owner. This setup PR includes tracking rules and documentation, not a fabricated scan. Follow `input/README.md` to upload it.

## 3. Create the Python environment

From the repository root:

```bash
python3.14 -c 'import sys; assert sys.version_info[:3] == (3, 14, 4), sys.version'
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name woodblocks-py314 --display-name 'Woodblocks (Python 3.14.4)'
```

`requirements.txt` preserves the supplied server freeze, including packages not required by the rendering path. Do not silently relax its versions when reporting a reproduction. If a pinned package is unavailable for Python 3.14.4 or the host platform, retain the installation error and compare with the source server's package index, cached wheels and environment capture. Installing a package with the same version number does not prove that a local/custom build is identical.

The notebook does not automatically install missing packages. In VS Code Remote SSH/Codespaces, select the remote `.venv/bin/python` as both the Python-file interpreter and notebook kernel. A local laptop interpreter will not use packages installed on the server. Confirm in a notebook cell:

```python
import sys
print(sys.executable)
print(sys.version)
```

## 4. Preflight before loading the scan

```bash
.venv/bin/python scripts/preflight.py --render-probe --variant cuda_ad_rgb
```

Preflight checks the Python version, imports, required code files and scan presence; the optional render probe really renders an 8×8 scene. It does not load the large scan, install dependencies or validate the scan geometry/masks. Exit status 1 means a blocking check failed. Missing optional font/texture assets are printed separately.

For a deliberately CPU-based run use `--variant llvm_ad_rgb`. This verifies that variant, but does not change notebook configuration. The notebook currently tries CUDA, then LLVM and adjusts default SPP for CPU; check its selected variant and actual SPP before proceeding. For comparisons with the reference server, use its variant and SPP. Do not treat a CPU fallback as an identical GPU reproduction.

## 5. Configure and run the notebook

Open the existing notebook and restart its kernel. Run cells sequentially from the beginning.

Section 1 resolves paths relative to this checkout. If the kernel starts outside it, set the environment variable `WOODBLOCK_PROJECT_ROOT` to the absolute checkout path before running the configuration cell. The run output directory is separate from the checkout root.

Default file configuration:

```python
cfg.mesh_source = "file"
cfg.input_dir = str(PROJECT_ROOT / "input" / "stl")
cfg.mesh_path = str(PROJECT_ROOT / "input" / "stl" / "03284.stl")
cfg.mesh_paths = []
```

Edit these in the configuration cell before the preprocessing cells. `input_dir` is a directory; `mesh_path` is one file. `mesh_paths` is populated with processed mesh paths. To discover every supported mesh in `input_dir`, deliberately set `cfg.mesh_path = ""`. The default selects only 03284.

Use `cfg.n_images = 1` for an initial pilot (replace the existing override in section 1), then inspect geometry, overlays, masks and logs before increasing it. Keep the same seed and all render settings when comparing runs. New run IDs intentionally produce separate directories.

The environment section initializes the actual Mitsuba variant. Decimation and the sampled surface-distance check run before large render jobs; the distance validator remains CPU-only. This can take substantial time and RAM even for a one-image pilot. Do not bypass failed checks to produce research data.

Section 12.5 loads the repository's `v5_metrics_update.py` with notebook globals, before section 13 defines the rendering path. Do not run that update as a standalone Python program. Run section 16 to load the objects and write annotation references, then the subsequent render and export sections. Run only the notebook checks appropriate to your investigation; they may perform additional rendering.

## 6. Metrics and annotations

`cfg.metric_backend_path` points to `metrics/backend.py` by default. This adapts `metrics/metrics.py:measure()` to the external backend contract. External results have their own names/status in JSON and tables and cannot override reference approval gates. Inspect per-sample `stages.*.external_backend.status` for backend errors.

Set `cfg.annotation_index_path` only when an annotation index is available for this exact normalized mesh. Set `cfg.labels_path` only for corresponding label data. Verify mesh hashes and UV conventions; do not transfer masks from another scan merely because it has the same dimensions. Generated stroke/ROI proposals remain unvalidated. Missing scores can be expected without reviewed annotations.

For texture and synthetic-font features, supply the optional files described in `input/README.md`. Ensure all local assets used in a published run are distributed with the same paths and hashes; otherwise the clone may use a different fallback or fail at that feature.

## 7. Outputs and reference evidence

Outputs are written below `testing_outputs/<run_id>/`. The primary artifacts include `images/`, `labels/`, `masks/`, `edge_maps/`, `geometry/`, `overlays/`, `logs/`, `assets/annotation_reference/`, `render_metrics.csv`, `metrics_long.csv` and `summary.json`. Audit tables are available when the corresponding notebook steps run. `render_metrics.csv` records render and final stages separately.

Capture the actual environment alongside an existing run (replace RUN_ID):

```bash
.venv/bin/python scripts/capture_environment.py --output testing_outputs/RUN_ID/environment.json
```

This records Python, packages, pip freeze, platform/libc, `nvidia-smi`, commit and working-tree status. It creates a new file and refuses to overwrite one. Keep the run metadata containing the actual Mitsuba variant, SPP, full configuration and code/input provenance as well. Capture on the reference server and on the new host; compare both before interpreting image differences.

The maintainer should also generate and commit `input/manifest.json` from the real assets:

```bash
.venv/bin/python scripts/input_manifest.py --write
```

Other users can then verify inputs with:

```bash
.venv/bin/python scripts/input_manifest.py --check
```

Hashing streams data and may take time for multi-GB scans. No reference hashes or reference images are shipped until generated from the actual server. For a reference bundle retain a few accepted images, their full JSON/metrics, input manifest, environment snapshot and the commit ID. Run artifacts are ignored by Git; distribute a reference bundle deliberately rather than committing all generated data.

Exact pixel equality is not promised across hardware/drivers/variants. Even matching environment snapshots require validation on the actual scan. These setup tools do not certify geometry quality, mask accuracy or OCR performance.

## 8. Offline installation

If the target server cannot reach the package index, prepare wheels on a connected host matching Python 3.14.4, Linux architecture and compatible system libraries:

```bash
python3.14 -m pip download --only-binary=:all: -r requirements.txt -d wheelhouse
```

If a wheel is unavailable, obtain/build the correct wheel in a compatible environment before transferring it. Do not assume packages built for another Python version will work. Transfer `wheelhouse/` to the target, then install there:

```bash
.venv/bin/python -m pip install --no-index --find-links wheelhouse -r requirements.txt
```

Host drivers and system libraries still need separate provisioning. Store wheelhouse outside Git; it can be very large.

## 9. Troubleshooting

- Yellow VS Code import diagnostics: select the remote Python interpreter and kernel, then check `scripts/preflight.py`. A Git `U` marker means untracked, and `M` means modified; neither is a Python traceback.
- Missing STL/pointer: push the real LFS object first, then run `git lfs pull` in the clone.
- Backend errors: inspect the per-sample JSON; do not interpret an empty metric as zero.
- CUDA initialization failure: compare host driver/runtime and the selected variant with the reference server. LLVM is a separate execution condition.
- Different output: compare input hashes, dirty code, configuration, seed, actual variant/SPP, texture/font/annotation assets and environment snapshots.
