# Woodblocks: 3D to 2D simulation (V5)

Mitsuba research pipeline for rendering 2D images from scanned Han-Nom woodblocks at HMI Laboratory, UET–VNU. Based on the [initial pipeline](https://www.kaggle.com/code/zendeptrai/woodblock-mitsuba-pipeline). This repository contains the renderer and draft image-quality metrics; OCR is managed separately.

**Reference Python: CPython 3.14.4. Reference platform: Linux x86_64.** `requirements.txt` is the server's frozen environment, including CUDA packages. It is not a cross-platform dependency guarantee. See [the full setup and run guide](docs/SETUP.md).

## Detailed walkthrough

See [Install dependencies, run the notebook, and inspect results](docs/RUNNING.md) for step-by-step Linux/Remote SSH instructions, interpreter/kernel selection, “import could not be resolved” fixes, creating `testing_outputs`, previewing images, reading CSV/JSON metrics and exporting a run.

## Quick start

Install Git and Python 3.14.4 on the host first. These commands assume Bash on Linux and a `python3.14` executable for exactly that Python release.

```bash
git clone https://github.com/haiviet7012/Woodblocks-3D-to-2D-simulation.git
cd Woodblocks-3D-to-2D-simulation
python3.14 -c 'import sys; assert sys.version_info[:3] == (3, 14, 4), sys.version'
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name woodblocks-py314 --display-name 'Woodblocks (Python 3.14.4)'
.venv/bin/python scripts/preflight.py --render-probe --variant cuda_ad_rgb
```

Open `mitsuba_research_v5_gpu.ipynb` in VS Code, select the **Woodblocks (Python 3.14.4)** kernel, and run cells in order. Also select `.venv/bin/python` with **Python: Select Interpreter** for Python-file analysis. Full instructions for setting up the environment is in the first cell of the notebook.

The default scan is `input/stl/03284.stl`. STL files anywhere under `input/` are ignored by Git; copy the scan into place locally after cloning. Fonts and textures in `input/fonts/` and `input/wood_texture/` can be committed normally and will be included in clones once uploaded. See [input asset instructions](input/README.md).

## Pipeline layout

- `mitsuba_research_v5_gpu.ipynb`: rendering, decimation and experiment configuration.
- `v5_metrics_update.py`: versioned reference metrics and research exports, loaded by section 12.5.
- `metrics/metrics.py`: independent comparison implementation.
- `metrics/backend.py`: external API adapter; comparison values do not overwrite reference results.
- `metrics/render_hook.py`: standalone geometry helper; the notebook uses the richer geometry implementation in the update file.
- `scripts/`: read-only preflight, environment capture and input hash tooling.
- `testing_outputs/<run_id>/`: generated run artifacts, ignored by Git.

## Research status

Metric definitions are draft implementations pending supervisor review. Generated masks remain proposals until independently reviewed. `E_proxy` is not validated `E_net`; missing validated ROI/stroke scores must not be filled by changing approval flags. Annotation masks must match the normalized mesh hash and coordinate frame. Sampled central-board decimation checks do not certify the whole scan. There is no OCR/CER or real-image similarity claim in this repository.

Reproducing the seed and packages does not guarantee identical pixels across GPU models, drivers, render variants or numerical libraries. Preserve the inputs, configuration, code commit and environment metadata for every reported experiment.
