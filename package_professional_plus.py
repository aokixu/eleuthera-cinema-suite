"""Empaquetado reproducible después de validar el build de cliente y QA compilada."""
from pathlib import Path
import hashlib,json,struct,subprocess,zipfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent


def main():
    evidence=ROOT/'test-results/final/build-validation'
    assert json.loads((evidence/'compiled-results.json').read_text())['compiled_nuitka']
    assert len(json.loads((evidence/'production-results.json').read_text())['passed'])==5
    source=ROOT/'dist/professional_licensed_main.dist'
    exe=source/'Eleuthera Professional Plus.exe'
    raw=exe.read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0]
    assert raw[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',raw,pe+4)[0]==0x8664
    report=ET.parse(ROOT/'dist/professional_licensed_main-report.xml')
    modules={node.get('name') for node in report.iter('module')}
    assert not modules.intersection({'generador_licencias_pro','preparar_licencias_pro','compiled_validation_probe','test_licenses_final'})
    files=[p for p in source.rglob('*') if p.is_file() and '.runtime' not in p.relative_to(source).parts]
    for path in files:
        assert path.name not in ('private_key.pem','generador_licencias_pro.py') and path.suffix!='.ecplic'
        if path.suffix.lower()=='.pem':assert b'PRIVATE KEY' not in path.read_bytes()
    compiler=Path.home()/'AppData/Local/Programs/Inno Setup 6/ISCC.exe'
    installer=ROOT/'dist/installers/Eleuthera-Professional-Plus-0.9.0-Setup.exe'
    newest=max(p.stat().st_mtime for p in files+[ROOT/'installers/professional-plus.iss'])
    if not installer.exists() or installer.stat().st_mtime < newest:
        with (ROOT/'test-results/final/inno-build.log').open('w') as log:
            subprocess.run([str(compiler),str(ROOT/'installers/professional-plus.iss')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    portable=ROOT/'dist/Eleuthera-Professional-Plus-Windows-x64.zip'
    with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files:archive.write(path,Path('Eleuthera Professional Plus')/path.relative_to(source))
    installer=ROOT/'dist/installers/Eleuthera-Professional-Plus-0.9.0-Setup.exe'
    assert installer.exists()
    outputs=[exe,portable,installer]
    manifest={str(p.relative_to(ROOT)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in outputs}
    (ROOT/'dist/distribution-sha256.json').write_text(json.dumps(manifest,indent=2))
    print('PASS: Windows x64 portable + Inno installer; no private key or generator in customer package.')


if __name__=='__main__':main()
