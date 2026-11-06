# Woodblocks-3D-to-2D-simulation (Version 5)
A part of the OCR pipeline for recognizing ancient Han-Nom letters on woodblocks, which is one of my research group projects at HMI Laboratory, University of Engineering and Technology-VNU.
This pipeline was redesigned and upgraded from the initial version: https://www.kaggle.com/code/zendeptrai/woodblock-mitsuba-pipeline

This projects does not include the OCR system, only the image renderer and its assets.
### Note: this is not the complete version, changes will be updated as soon as possible.

## This repository included: 
### Assets:
- Texture (.jpg)
- Fonts (NomNaTong.ttf)
- STL models (this repository only consists of 2 models due to their size)

### Metrics rendering:
- metrics.py
- render_hook.py

### Metrics calculations:
- v5_metrics_update.py

### Pipeline notebook:
- mitsuba_research_v5_gpu.ipynb


## Run this checkout

1. Place the scan at `input/stl/03284.stl` locally. Scans are ignored by Git and are not included in a fresh clone.
2. Open `mitsuba_research_v5_gpu.ipynb` and select the server Python environment containing the dependencies in `requirements.txt`. Select the same interpreter in VS Code for Python files. No automatic pip install is performed.
3. Run cells in order. Section 1 finds the project root from the working directory; for a kernel started elsewhere set `WOODBLOCK_PROJECT_ROOT` to the checkout directory before running it. Change `cfg.mesh_path` there for a different scan; keep `cfg.input_dir` as a directory.
4. Section 12.5 loads `v5_metrics_update.py` with the notebook globals. It preserves the CPU decimation validator and CUDA/LLVM renderer. Results go to `testing_outputs/<run_id>/`.
5. `metrics/backend.py` adapts `metrics/metrics.py:measure()` to the external metric API. External values are exported with their own namespace/status in the CSV and JSON; they do not replace the reference metrics. The separate `metrics/render_hook.py` geometry helper is available for standalone integrations; the notebook uses the richer `project_geometry()` in the update file.

Optional annotations: set `cfg.annotation_index_path` to the annotation index JSON. Reviewed masks must match the normalized mesh hash and UV frame. Do not reuse annotations from another scan or turn validation flags on to fill empty scores. No annotations are fabricated for 03284.

Textures and fonts are optional local assets at `input/wood_texture/` and `input/fonts/`. Supply them when enabling the corresponding features. A fresh clone does not contain those ignored files either.

VS Code: yellow numbers indicate diagnostics; `U` means untracked and `M` means modified in Git. Inspect the Problems panel for exact messages. Missing `cv2`/`numpy` imports usually require selecting the environment where they are installed; choosing a notebook kernel alone does not select the Python-file interpreter. This change does not suppress missing dependency warnings.

Validation scope: syntax, path resolution and metric adapter can be checked without the large scan. Successful rendering and mask quality must be checked on the actual server and scan.
