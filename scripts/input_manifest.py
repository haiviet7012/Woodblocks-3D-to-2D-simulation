"""Write or verify SHA-256/size for all local input assets (streaming, no mesh load)."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest = ROOT / 'input/manifest.json'
    if args.write:
        files = [p for p in sorted((ROOT / 'input').rglob('*')) if p.is_file()
                 and p != manifest and p.name not in ('.gitkeep', 'README.md')]
        if not files:
            raise SystemExit('No input assets found; no manifest was written.')
        entries = []
        for p in files:
            with p.open('rb') as stream:
                if stream.read(100).startswith(b'version https://git-lfs.github.com/spec/v1'):
                    raise SystemExit(f'LFS pointer found: {p}; run git lfs pull first.')
            entries.append({'path': p.relative_to(ROOT).as_posix(), 'size_bytes': p.stat().st_size, 'sha256': digest(p)})
        manifest.write_text(json.dumps({'schema_version': 1, 'files': entries}, indent=2) + '\n')
        print('Wrote', manifest)
    else:
        data = json.loads(manifest.read_text())
        if not data.get('files'):
            raise SystemExit('Manifest has no assets; ask the maintainer to generate it from the real inputs.')
        failures = []
        for entry in data['files']:
            path = (ROOT / entry['path']).resolve()
            if not path.is_relative_to((ROOT / 'input').resolve()):
                raise SystemExit('Manifest path outside input directory')
            if not path.is_file() or path.stat().st_size != entry['size_bytes'] or digest(path) != entry['sha256']:
                failures.append(entry['path'])
        if failures:
            raise SystemExit('Missing or changed inputs: ' + ', '.join(failures))
        print('All input sizes and SHA-256 hashes match.')


if __name__ == '__main__':
    main()
