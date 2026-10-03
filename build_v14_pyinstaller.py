"""Build both Windows editions without Nuitka or external compilers."""
from pathlib import Path
import subprocess,sys,json,hashlib
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dist-v14-pyinstaller'

def main():
    from PySide6.QtCore import QLibraryInfo
    translations=Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    assets=ROOT/'assets'
    versions=[('Eleuthera Plus v14 Directa','professional_main.py'),('Eleuthera Plus v14 Licenciada','professional_licensed_main.py')]
    logs=ROOT/'build-v14-logs';logs.mkdir(exist_ok=True)
    for name,entry in versions:
        cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--noupx',
             '--name',name,'--distpath',str(OUT),'--workpath',str(ROOT/'build-v14'/name),
             '--specpath',str(ROOT/'build-v14-specs'),'--add-data',str(assets)+';assets',
             '--icon',str(assets/'eleuthera-clapperboard.ico'),'--collect-data','qtawesome',
             '--add-data',str(translations/'qtbase_es.qm')+';PySide6/translations',
             str(ROOT/entry)]
        print('BUILD',name,flush=True)
        with (logs/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        exe=OUT/name/(name+'.exe');assert exe.is_file()
        print('DONE',exe,flush=True)
    (OUT/'build-manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py') if not p.name.startswith(('test','verify','build'))},indent=2),encoding='utf-8')
if __name__=='__main__':main()
