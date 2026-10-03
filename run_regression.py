"""Regresión existente, un proceso aislado por prueba y límite de tiempo."""
import json
from pathlib import Path
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
output = root / 'test-results'
output.mkdir(exist_ok=True)
results = []
targets = sorted(root.glob('verify*.py'))
if '--include-checks' in sys.argv: targets.append(root / 'check_compact_controls.py')
for target in targets:
    start = time.monotonic()
    with (output / (target.stem + '.log')).open('w', encoding='utf-8') as log:
        try:
            completed = subprocess.run([sys.executable, '-B', 'test_bootstrap.py', target.name], cwd=root,
                                       stdout=log, stderr=subprocess.STDOUT, timeout=75)
            status = 'PASS' if completed.returncode == 0 else 'FAIL'
        except subprocess.TimeoutExpired:
            status = 'TIMEOUT'
    results.append({'test': target.name, 'status': status, 'seconds': round(time.monotonic() - start, 2)})
    (output / 'existing-tests.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(status, target.name, flush=True)
print('Final:', len(results), 'pruebas', flush=True)
