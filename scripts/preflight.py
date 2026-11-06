"""Read-only setup checks. Run with the same interpreter as the notebook kernel."""
import argparse
import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('numpy', 'cv2', 'PIL', 'trimesh', 'mitsuba', 'drjit',
           'fast_simplification', 'rtree', 'scipy', 'psutil', 'pandas',
           'matplotlib', 'ipykernel')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh', type=Path, default=ROOT / 'input/stl/03284.stl')
    parser.add_argument('--render-probe', action='store_true', help='Actually render an 8x8 scene')
    parser.add_argument('--variant', choices=('cuda_ad_rgb', 'llvm_ad_rgb'), default='cuda_ad_rgb')
    args = parser.parse_args()
    failures = []
    print('Interpreter:', sys.executable)
    print('Python:', sys.version.split()[0])
    if sys.version_info[:3] != (3, 14, 4):
        failures.append('Use Python 3.14.4 for the reference environment.')
    for name in MODULES:
        try:
            module = importlib.import_module(name)
            print('OK import:', name, getattr(module, '__version__', ''))
        except Exception as exc:
            failures.append(f'{name}: {type(exc).__name__}: {exc}')
    mesh = args.mesh.resolve()
    if not mesh.is_file():
        failures.append(f'Missing scan: {mesh}. Run git lfs pull, or ask the maintainer to upload it.')
    else:
        with mesh.open('rb') as stream:
            header = stream.read(256)
        if header.startswith(b'version https://git-lfs.github.com/spec/v1'):
            failures.append('The scan is an LFS pointer, not mesh data. Run git lfs pull.')
        elif mesh.stat().st_size < 84:
            failures.append('Scan is empty or too short; check the uploaded asset.')
        else:
            print('OK scan:', mesh, mesh.stat().st_size, 'bytes (not a geometry validation)')
    for path in ('v5_metrics_update.py', 'metrics/backend.py', 'metrics/metrics.py', 'metrics/render_hook.py'):
        if not (ROOT / path).is_file():
            failures.append('Missing repository file: ' + path)
    for path in ('input/wood_texture/Natural-Oak-Wood-Texture.jpg', 'input/fonts/NomNaTong-Regular.ttf'):
        if not (ROOT / path).is_file():
            print('OPTIONAL asset missing:', path, '(supply if using that feature)')
    if args.render_probe:
        try:
            import mitsuba as mi
            import numpy as np
            mi.set_variant(args.variant)
            scene = mi.load_dict({'type': 'scene', 'integrator': {'type': 'path'},
                'sensor': {'type': 'perspective', 'film': {'type': 'hdrfilm', 'width': 8, 'height': 8}},
                'emitter': {'type': 'constant'}})
            pixels = np.asarray(mi.render(scene, spp=1))
            if not np.isfinite(pixels).all():
                raise ValueError('Non-finite render output')
            print('OK render probe:', mi.variant())
        except Exception as exc:
            failures.append(f'Render probe: {type(exc).__name__}: {exc}')
    for message in failures:
        print('FAIL:', message)
    print(f'{len(failures)} blocking issue(s). No packages were installed.')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
