"""Regresión completa aislada y comprobación de integridad; no escribe en el original."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

root=Path(__file__).resolve().parent
out=root/'test-results/stage7';out.mkdir(exist_ok=True)
results=[]
targets=[p.name for p in sorted(root.glob('test_budget_*.py'))]
targets+=['test_globals_integration.py','test_formula_integration.py','test_fringe_integration.py','test_group_integration.py','test_credit_integration.py','test_charge_integration.py','test_interface_integration.py']
targets+=[p.name for p in sorted(root.glob('verify*.py'))]+['check_compact_controls.py']
jobs=[(name,'test_bootstrap.py',name) for name in targets]
jobs += [('baseline-'+name,'.baseline/test_bootstrap.py',name) for name in
         ['verify_suite.py','verify_large_pdf.py','check_compact_controls.py']]
for label, bootstrap, target in jobs:
    start=perf_counter()
    with (out/(label+'.log')).open('w',encoding='utf-8') as log:
        try:
            result=subprocess.run([sys.executable,'-B',bootstrap,target],cwd=root,stdout=log,stderr=subprocess.STDOUT,
                                  timeout=180 if target.startswith('test_') else 75)
            status='PASS' if result.returncode==0 else 'FAIL'
        except subprocess.TimeoutExpired: status='TIMEOUT'
    results.append(dict(test=label,status=status,seconds=round(perf_counter()-start,3)))
    (out/'validation-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(label,status,flush=True)
original=root.parent/'Eleuthera Cinema Suite FINAL'/'Master 1'
manifest=json.loads((root/'original-sha256.json').read_text(encoding='utf-8-sig'))
changes=[item['Path'] for item in manifest if not (original/item['Path']).exists() or
         hashlib.sha256((original/item['Path']).read_bytes()).hexdigest().upper()!=item['Hash']]
(out/'original-after.json').write_text(json.dumps(dict(checked=len(manifest),changed=changes),indent=2),encoding='utf-8')
print('Original SHA-256:',len(manifest),'archivos;',len(changes),'cambios',flush=True)
assert not changes
