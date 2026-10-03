from pathlib import Path
import json,zipfile,hashlib
root=Path.cwd();delivery=Path('C:/Users/Francisco/Documents/New project')/'ELEUTHERA_v14_ENTREGA';delivery.mkdir(exist_ok=True)
readme='''ELEUTHERA PROFESSIONAL PLUS v14 — ESPAÑOL / ENGLISH

VERSIONES
• Directa: abre sin activación.
• Licenciada: conserva la activación offline y la clave pública existente; requiere una licencia válida.

USO
1. Extrae el ZIP completo.
2. Abre el .exe dentro de su carpeta.
3. Conserva la carpeta _internal junto al ejecutable. No copies solo el .exe.
4. Usa el menú superior Idioma / Language para elegir Español o English.
La preferencia se guarda para el siguiente inicio. El contenido del guion y los datos del proyecto conservan sus valores originales.

Se mantienen el cursor amarillo con parpadeo, la actualización optimizada de colores y la exportación Excel general del proyecto.

COMPILACIÓN
PyInstaller 6.22.2, Python 3.14 y PySide6 6.11.2. Distribuciones de carpeta, sin consola. No necesitan Python ni Nuitka instalados en el equipo de uso.
Para volver a compilar desde el código fuente: python build_v14_pyinstaller.py

VALIDACIÓN
• Ambos ejecutables: inicio, español/inglés, valores internos, proyecto sin modificaciones al cambiar idioma, PDF, Excel, iconos y clave pública.
• Preferencia de idioma persistente entre procesos.
• Siete escenarios de integración de presupuesto en español y en inglés.
• Entrada licenciada: no inicia la aplicación cuando no se acepta la activación. Las licencias inválidas se rechazan. No se realizó una activación real con una nueva licencia.
• Dos pruebas antiguas (verify_suite.py, cambio de moneda; verify_workflow.py, retorno de new_document) fallan de la misma forma en v12 y v14. No se atribuyen al cambio de idioma.
'''
(delivery/'LEEME_v14.txt').write_text(readme,encoding='utf-8')
outputs=[]
for edition in ('Directa','Licenciada'):
    name='Eleuthera Plus v14 '+edition;folder=root/'dist-v14-pyinstaller'/name
    (folder/'LEEME_v14.txt').write_text(readme,encoding='utf-8')
    files=[p for p in folder.rglob('*') if p.is_file()]
    assert not any(p.name.lower() in ('private_key.pem','private_key.json') or p.suffix in ('.ecplic','.eguion') for p in files)
    output=delivery/('ELEUTHERA_PLUS_v14_'+edition.upper()+'_PYINSTALLER.zip')
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(folder.parent))
    with zipfile.ZipFile(output) as z:assert z.testzip() is None
    outputs.append(output);print('ZIP verificado:',output.name,round(output.stat().st_size/1024**2,1),'MB',flush=True)
source=delivery/'ELEUTHERA_PLUS_v14_CODIGO.zip'
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
    for p in root.glob('*.py'):
        if p.name in ('translate_ui.py',):continue
        z.write(p,p.name)
    for p in (root/'assets').rglob('*'):
        if p.is_file():z.write(p,p.relative_to(root))
    for p in root.glob('requirements*.txt'):z.write(p,p.name)
    z.writestr('LEEME_v14.txt',readme)
with zipfile.ZipFile(source) as z:assert z.testzip() is None
outputs.append(source)
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs}
(delivery/'SHA256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('ENTREGA:',delivery,flush=True)
