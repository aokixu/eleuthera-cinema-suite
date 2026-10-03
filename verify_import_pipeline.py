import os,json,time,importlib.util
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QEventLoop,QTimer
from app import ScriptEditor
from suite import SuiteWindow
from script_import import read_import
from project_store import fingerprint
qt=QApplication([])
spec=importlib.util.spec_from_file_location('previous_editor',Path('perf-import/app.py'));previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
fixtures=[[],[{'type':'scene','text':'INT. CASA - NOCHE'},{'type':'action','text':'Uno\nDos'},{'type':'character','text':'ANA'},{'type':'dialogue','text':'Hola.\nAdiós.'},{'type':'transition','text':'CORTE A:'}],json.loads(Path('perf-import/large.eguion').read_text())['blocks'][:42]]
for blocks in fixtures:
    old=previous.ScriptEditor();new=ScriptEditor();old.load_blocks(blocks);new.load_blocks(blocks)
    a=[(b['type'],b['text']) for b in old.blocks()];b=[(b['type'],b['text']) for b in new.blocks()];assert a==b,(a,b)
    ob=old.document().firstBlock();nb=new.document().firstBlock()
    while ob.isValid():
        expected = {'character': (267, 25), 'dialogue': (160, 160), 'parenthetical': (205, 205)}.get(new.block_type(nb), (ob.blockFormat().leftMargin(), ob.blockFormat().rightMargin()))
        assert (nb.blockFormat().leftMargin(), nb.blockFormat().rightMargin()) == expected
        assert ob.blockFormat().topMargin() == nb.blockFormat().topMargin()
        ob=ob.next();nb=nb.next()
    old.deleteLater();new.deleteLater()
print('OK: editor text, block types and margins match updated screenplay layout.',flush=True)
w=SuiteWindow('professional');w.autosave.stop();w.poll.stop();w.show();qt.processEvents();errors=[]
QMessageBox.critical=lambda *a:errors.append(a[-1]);QMessageBox.question=lambda *a:QMessageBox.StandardButton.Discard
w.editor.load_blocks([{'type':'scene','text':'INT. ORIGINAL - DÍA'}]);w._last_saved=fingerprint(w.project_data());w.dirty=False
original=w.project_data()
def wait():
    loop=QEventLoop();timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:loop.quit() if getattr(w,'_import_job',None) is None else None);timer.start();QTimer.singleShot(20000,loop.quit);loop.exec();timer.stop();assert w._import_job is None
w.open_path(Path('perf-import/large.fdx'));w._import_job.cancel();wait();assert w.project_data()==original
bad=Path('perf-import/invalid.eguion');bad.write_text('{broken');w.open_path(bad);wait();assert errors and w.project_data()==original
# Cancellation during document construction preserves the live document.
w.open_path(Path('perf-import/large.fdx'))
timer=QTimer();timer.setInterval(1)
def cancel_build():
    job=w._import_job
    if job and job.generator is not None:timer.stop();job.cancel()
timer.timeout.connect(cancel_build);timer.start();wait();timer.stop();assert w.project_data()==original
# Consecutive successful imports must not restore the prior document when progress closes.
for name in ('large.eguion','large.fdx'):
    w.open_path(Path('perf-import')/name);wait();expected,_=read_import(Path('perf-import')/name)
    assert [(b['type'],b['text']) for b in w.editor.blocks()]==[(b['type'],b['text']) for b in expected['blocks']]
    qt.processEvents();assert w.last_import_profile['success']
    w._last_saved=fingerprint(w.project_data());w.dirty=False
w.close();print('OK: cancellation, malformed input and repeated asynchronous imports.')
