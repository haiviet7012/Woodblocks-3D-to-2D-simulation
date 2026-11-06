# Input assets

Only STL files under `input/` are ignored by Git (case-insensitive extension, including nested directories). Fonts, textures, JSON labels and other non-STL input assets can be committed normally.

## Commit fonts and textures

From the checkout containing the real files:

```bash
git add input/fonts/NomNaTong-Regular.ttf
git add input/wood_texture/Natural-Oak-Wood-Texture.jpg
git commit -m "Add font and wood texture assets"
git push
```

No `git add -f` is required. Commit the real assets and their required license/attribution before expecting another clone to contain them. This change only adjusts the tracking policy; it does not supply files that exist exclusively on the server.

Expected notebook paths:

- `input/fonts/NomNaTong-Regular.ttf`: font for synthetic boards.
- `input/wood_texture/Natural-Oak-Wood-Texture.jpg`: wood texture.
- `input/stl/03284.stl`: local default scan, not distributed by Git.

## Supply the scan locally

After cloning, create `input/stl/` if needed and copy the real scan to `input/stl/03284.stl`. Alternatively, edit `cfg.mesh_path` in section 1 of the notebook to use another local file. Keep `cfg.input_dir` as a directory. Scans inside date subdirectories such as `input/stl/031022/` also remain ignored.

The ignore rule does not remove files already tracked in Git. Check `git ls-files input` if an STL was committed previously; removing it from tracking requires a separate deliberate change. This update does not delete local scans or rewrite history.

## Verify shared inputs

On the source server, run `.venv/bin/python scripts/input_manifest.py --write`, then commit `input/manifest.json`. It records all local input assets, including the ignored STL, so recipients can verify their separately supplied scan with `--check`. A checksum does not upload the scan.

For annotations, set `cfg.annotation_index_path` and preserve the exact normalized-mesh identity and UV frame. Set `cfg.labels_path` for matching character labels. Include the non-STL annotation assets needed by a reproducible run.
