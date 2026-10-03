"""Distribución Windows x64 sin activación/licencia, compilada con Nuitka en modo standalone."""
from pathlib import Path
import json, subprocess, sys

ROOT=Path(__file__).resolve().parent


def command(entry, output, name, gui=True):
    args=[sys.executable,'-m','nuitka','--mode=standalone','--zig','--jobs=4',
          '--assume-yes-for-downloads','--enable-plugin=tk-inter',
          '--output-dir='+str(output),'--output-filename='+name,
          '--report='+str(output/(Path(entry).stem+'-report.xml')),
          '--windows-console-mode='+('disable' if gui else 'force'),
          '--windows-icon-from-ico=assets/eleuthera-clapperboard.ico',
          '--nofollow-import-to=pytest,IPython,matplotlib,scipy,*.tests']
    if entry!='generador_licencias_pro.py':
        args+=['--enable-plugin=pyside6','--include-data-dir=assets=assets',
               '--include-package-data=qtawesome',
               '--nofollow-import-to='+','.join('PySide6.'+name for name in
                   ('QtDataVisualization','QtCharts','QtGraphs','QtGraphsWidgets','QtCanvasPainter','QtCoap',
                    'QtGrpc','QtHttpServer','QtLottie','QtMqtt','QtNetworkAuth','QtQmlCompiler','QtQuick3D',
                    'QtQuick3DPhysics','QtQuickTimeline','QtVirtualKeyboard','QtWaylandCompositor'))]
    return args+[entry]


def main():
    results=json.loads((ROOT/'test-results/final/validation-results.json').read_text())
    expected={'verify_suite.py':'FAIL','verify_large_pdf.py':'FAIL','check_compact_controls.py':'TIMEOUT',
              'baseline-verify_suite.py':'FAIL','baseline-verify_large_pdf.py':'FAIL','baseline-check_compact_controls.py':'TIMEOUT'}
    assert len(results)==37 and {r['test']:r['status'] for r in results if r['status']!='PASS'}==expected
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    subprocess.run(command('professional_main.py',out,'Eleuthera Professional Plus.exe'),cwd=ROOT,check=True)


if __name__=='__main__':main()
