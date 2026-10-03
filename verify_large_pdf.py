import os,json,time
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path

def main():
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtCore import QTimer,QEventLoop
    from PySide6.QtGui import QFontDatabase
    from suite import SuiteWindow
    from project_store import fingerprint
    qt=QApplication([])
    for font in ('cour.ttf','courbd.ttf','segoeui.ttf'):QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
    w=SuiteWindow('professional');w.poll.stop();w.autosave.stop();w.show();qt.processEvents()
    w._last_saved=fingerprint(w.project_data());w.dirty=False
    gaps=[];last=[time.perf_counter()];timer=QTimer();timer.setInterval(10)
    def tick():
        now=time.perf_counter();gaps.append(now-last[0]);last[0]=now
    timer.timeout.connect(tick);timer.start();loop=QEventLoop();poll=QTimer();poll.setInterval(20);poll.timeout.connect(lambda:loop.quit() if not getattr(w,'_import_job',None) else None)
    w.open_path(Path('perf-import/large.pdf'));poll.start();loop.exec();poll.stop();timer.stop()
    result={**w.last_import_profile,'max_gap_ms':max(gaps)*1000,'ticks':len(gaps),'scenes':len(w.current_scenes())};print(result,flush=True)
    # Compare against the original, sequential extraction, not against the new implementation.
    expected_path=Path('perf-import/pdf-original-blocks.json')
    if not expected_path.exists():
        t=time.perf_counter();text=w.read_pdf(Path('perf-import/large.pdf'));expected=w.parse_fountain(text)
        result['original_pdf_extraction_and_parse']=time.perf_counter()-t;expected_path.write_text(json.dumps(expected),encoding='utf-8')
    else:expected=json.loads(expected_path.read_text())
    actual=[{k:b[k] for k in ('type','text')} for b in w.editor.blocks()]
    assert actual==expected
    Path('perf-import/pdf-parallel.json').write_text(json.dumps(result,indent=2));print('PDF parity OK',flush=True)
    w._last_saved=fingerprint(w.project_data());w.dirty=False;w.close()
if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support();main()
