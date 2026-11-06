# Input assets

The default scan is `stl/03284.stl`, relative to this directory. STL files are retained in the repository through Git LFS. The actual scan is not included by the setup change; its owner must upload it from the server.

## Maintainer: add the scan

Install Git LFS, update your checkout to include `.gitattributes`, and copy the real file to `input/stl/03284.stl`. Then, from the repository root:

```bash
git lfs install
git check-attr filter -- input/stl/03284.stl
git add input/stl/03284.stl
.venv/bin/python scripts/input_manifest.py --write
git add input/manifest.json
git commit -m "Add 03284 scan and input checksums"
git push
git lfs ls-files
```

The filter check should print `lfs`. `git push` uploads the actual LFS object through the installed LFS hook. Verify the upload by running preflight and hash checks in a fresh clone. Do not commit a placeholder pointer without uploading its object. If STL files were already tracked as ordinary Git blobs, enabling attributes alone does not migrate their existing history; plan migration separately rather than rewriting shared history automatically.

GitHub blocks ordinary Git files above 100 MiB. Git LFS also has a per-file limit depending on the account plan (currently 2 GB for Free/Pro, 4 GB for Team and 5 GB for Enterprise Cloud). Check the current limits and available storage/bandwidth before upload:

- https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
- https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage
- https://docs.github.com/en/billing/concepts/product-billing/git-lfs

The size of 03284 is not known here. If it exceeds your plan's per-file limit, it cannot be pushed as one LFS object. The earlier approximately 7.8 GB scan would exceed these limits. Decide on a documented, validated smaller distributable or a separately designed chunk/reassembly workflow; do not silently substitute a reduced scan or claim it is identical. This PR does not alter the source mesh.

## Optional assets

- `wood_texture/Natural-Oak-Wood-Texture.jpg`: local texture used by the notebook when available.
- `fonts/NomNaTong-Regular.ttf`: font for synthetic boards; provide locally for offline use.
- Annotation index and masks: set `cfg.annotation_index_path`; preserve the exact normalized-mesh identity and UV frame.
- Character labels: set `cfg.labels_path` for matching labels.

Non-STL local assets remain ignored by default. To distribute a specific asset with permission, explicitly add that file (for example `git add -f input/wood_texture/Natural-Oak-Wood-Texture.jpg`) and include it in the manifest. Share the assets needed by the selected configuration, including annotations, to reproduce the same run. Do not publish assets without their required license/attribution.
