"""Host Python runner: --blender PATH [--blender PATH ...]."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--blender', action='append', required=True)
parser.add_argument('--timeout', type=int, default=180)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = root / 'tests' / 'results'
output.mkdir(exist_ok=True)
results = []
for executable in args.blender:
    version = subprocess.check_output([executable, '--version'], text=True, encoding='utf-8', errors='replace').splitlines()[0]
    for test in sorted((root / 'tests').glob('test_*.py')):
        start = time.monotonic()
        try:
            result = subprocess.run([executable, '--background', '--factory-startup', '--python-exit-code', '1',
                                     '--python', str(test)], cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                    timeout=args.timeout)
            log = result.stdout + '\n' + result.stderr
            passed = result.returncode == 0 and 'QC_TEST PASS' in log and 'Traceback' not in log
        except subprocess.TimeoutExpired:
            passed, log = False, f'Timed out after {args.timeout} seconds'
        name = version.replace(' ', '_').replace('.', '_') + '_' + test.stem
        (output / (name + '.log')).write_text(log, encoding='utf-8')
        entry = {'version': version, 'test': test.name, 'passed': passed,
                 'seconds': round(time.monotonic() - start, 3), 'log': name + '.log'}
        results.append(entry)
        print(version, test.name, 'PASS' if passed else 'FAIL', flush=True)
        if not passed:
            print(log, flush=True)
(output / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
sys.exit(0 if all(x['passed'] for x in results) else 1)
