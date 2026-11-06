"""Capture an environment snapshot without importing the renderer or changing it."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys


def command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        return {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'error': str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New JSON file, e.g. a run/environment.json')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    snapshot = {
        'python': sys.version, 'executable': sys.executable,
        'platform': platform.platform(), 'machine': platform.machine(),
        'libc': platform.libc_ver(),
        'packages': sorted([{'name': d.metadata['Name'], 'version': d.version}
                            for d in importlib.metadata.distributions()], key=lambda d: d['name'].lower()),
        'pip_freeze': command([sys.executable, '-m', 'pip', 'freeze']),
        'nvidia_smi': command(['nvidia-smi']),
        'git_commit': command(['git', '-C', str(root), 'rev-parse', 'HEAD']),
        'git_status': command(['git', '-C', str(root), 'status', '--porcelain']),
        'note': 'Record actual Mitsuba variant and SPP from the notebook run metadata as well.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(snapshot, stream, indent=2, ensure_ascii=False)
    print(args.output)


if __name__ == '__main__':
    main()
