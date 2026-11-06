# CONTEXT.md

Project background: its origins, its evolution, the rationale behind key decisions, and any remaining open questions.
Detailed methodology and data can be found in [REPORT.md](REPORT.md); coding conventions are outlined in [CLAUDE.md](CLAUDE.md).

## 1. Overarching Goal and Scope of the Repository

**Overarching Goal:** OCR (Optical Character Recognition) for Hán-Nôm (Sino-Vietnamese) script found on *mộc bản* (traditional woodblocks—carved wooden blocks with reversed characters used for printing) and photographs thereof.

**The Challenge:** Training data is scarce, while actual photographs exhibit significant variability in terms of viewing angles, lighting, shadows, wear and tear, and obstructions (such as fingers, rulers, or labels). Capturing additional images is labor-intensive and still fails to cover every possible scenario.

**This Repository** focuses on a single link in the pipeline: generating **controlled 2D images** from 3D scans of the woodblocks to augment the training dataset.
The OCR component itself (training and evaluation) is **not** included here.

## 2. Data

**3D Scans**
- **No 3D scans of Hán-Nôm woodblocks** could be found in public 3D model repositories or museum collections.
- The scan currently in use is a publicly available model (with a license permitting reuse) of a woodblock used for printing **patterns** on fabric; however, as it **contains no text**, it cannot be used to generate images with character labels.
- Several 3D scans of woodblocks **containing text** have been identified as potential candidates, though they have not yet been downloaded.
- Many 3D model platforms require user login for downloads; consequently, these scans must be downloaded manually and subsequently uploaded to a Kaggle Dataset.
- One 3D model of a Vietnamese woodblock is available for public viewing, but the author **does not permit downloads**, and no license is specified. To use these, you must request permission directly from the author; do not extract them from the viewer.

**Actual Photographs**
- Previous OCR experiments utilized **two sets of photographs of authentic woodblocks**. These sets are **not** included in the repository. They serve as a benchmark for evaluating the "realism" of rendered images (a task yet to be completed).
- The CER labels for one of these sets were **automatically aligned** against a publicly available text of the sutra; they have **not been manually verified**. While they can be used for A/B comparisons between different configurations, they should not be interpreted as absolute accuracy metrics.

## 3. History

| Date | Event |
|---|---|
| Before 09/2026 | OCR experiments conducted using PaddleOCR PP-OCRv6 on actual photographs. Conclusion regarding pre-processing: using **raw images** yields better results—in terms of both CER and character detection—than using CLAHE; in fact, CLAHE was found to degrade performance. |
| 16/09/2026 | Initiation of 3D-based image generation, consisting of three branches: **A1** (generating meshes of Chinese characters from fonts, with character-level labeling), **A2** (creating reliefs from actual photographs), and **A3** (utilizing actual 3D scans). |
| 16–22/09 | Testing on A1-rendered images revealed that PP-OCRv6 performs reasonably well under favorable viewing angles (recall ~0.7), but becomes virtually **unable to read characters when the camera angle is ≤ 50°**. Furthermore, the model is highly sensitive to **partial wear of character strokes**. This is why the "A" approach mandates a camera angle of ≥ 45°. |
| 23/09 | Decision made to **abandon branches A1 and A2**, retaining only the actual 3D scans; OCR evaluation is no longer required for this branch. When running on actual 3D scans, several issues were identified: scans were oriented incorrectly (the AABB axis selection was wrong), the transformation matrix caused axis swapping and mirroring, and there was no distinction between the carved face and the back. This led to the development of `prepare_scan`, `detect_main_face`, and `orient_to_face`. During the transition to actual scans, a "false cavity" artifact—caused by the point-scattering method—was discovered; this was resolved by switching to triangle rasterization. |
| 24/09 | Merged two separate notebooks (rendering and augmentation) into a **single** Kaggle notebook. Performed the first full run on Kaggle (using 2 × T4 GPUs): while orientation B was correct, **images for orientation A appeared entirely gray** due to nested ZIP files disrupting texture file paths; this has been fixed. The notebook was refactored so that each function resides in its own cell, accompanied by explanatory text. |
| 25/09 | Decoupled from the legacy OCR project (`OCRMocBan`) by removing all OCR and preprocessing code. Restructured the project into `src/`, `tests/`, and `notebooks/` directories, with modules organized into `sNN_` files following the pipeline sequence. Consolidated three separate reports into a single `REPORT.md` and named the project **WoodblockSynth**. Re-ran the notebook on Kaggle: the gray-image issue was resolved, and the metrics for orientation B matched those from the local machine. A subsequent run generated a `run_info.json` file, confirming that OpenGL on Kaggle was running via CPU (`llvmpipe`) at a speed of 4.42 seconds per image. |

## 4. Design Decisions and Rationale

| Decision | Rationale |
|---|---|
| Use only real 3D scans | Based on the user's decision on Sept 23. Real textures (wood grain, ink marks) produce images that are significantly more realistic than procedural textures. |
| Assume each block has **one** informative face | Simplifies the process of identifying the carved face; handling double-sided carved blocks is deferred to a later stage. |
| Identify the engraved surface through **relative comparison** between faces, including a confidence score and a visual indicator (pointing arrow) | Must function on any scan, regardless of unknown units or orientation; if uncertain, the system prompts for manual review rather than producing an incorrect surface identification. |
| Two approaches: A and B (parallel) | Approach A resembles a photograph but is sensitive to lighting (low-angle light causes loss of feature definition); Approach B is lighting-independent, deriving features directly from the geometry. |
| Camera angle for Approach A must be ≥ 45° | Low angles cause foreshortening of the engraved surface and excessive shadowing; experiments with A1 showed a recall of ≈ 0 at angles ≤ 50°. |
| Primary execution on **Kaggle** | Leverages free GPU resources for Approach A. Local machines are used for rapid prototyping (note: local OpenGL runs on an integrated Intel UHD 630 GPU, not the GTX 1660 Ti). |
| Notebooks **generated from source code**, with each function in a dedicated cell accompanied by an explanation | Facilitates step-by-step comprehension directly within the notebook; ensures the local codebase and notebooks remain perfectly synchronized (verified via an AST-based builder). |
| Filenames prefixed with `sNN_` following the pipeline sequence | The processing flow is immediately apparent upon opening the directory; if an error occurs in a specific notebook section, it is clear which file to investigate. |

## 5. Current Status

- The pipeline is fully functional on local machines, regardless of whether a GPU is present.