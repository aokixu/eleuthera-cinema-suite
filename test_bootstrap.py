"""Ejecuta una prueba con preferencias, temporales y escrituras dentro de Plus."""
import os
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent
runtime = root / '.runtime' / 'tests'
runtime.mkdir(parents=True, exist_ok=True)
for key in ('TEMP', 'TMP', 'TMPDIR', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME'):
    location = runtime / key.lower()
    location.mkdir(exist_ok=True)
    os.environ[key] = str(location)
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.chdir(root)

def inside(path):
    if isinstance(path, (str, bytes, os.PathLike)):
        value = Path(os.fsdecode(path)).resolve()
        if not value.is_relative_to(root):
            raise PermissionError('Prueba intentó escribir fuera de Plus: ' + str(value))

def audit(event, args):
    if event == 'open':
        path, mode, flags = args
        if (mode and any(x in mode for x in 'wax+')) or (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            inside(path)
    elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime'):
        inside(args[0])
    elif event in ('os.rename', 'os.replace'):
        inside(args[0]); inside(args[1])

sys.addaudithook(audit)
import plus_runtime
target = sys.argv[1]
sys.argv = [target] + sys.argv[2:]
runpy.run_path(str(root / target), run_name='__main__')
