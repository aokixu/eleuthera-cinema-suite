import os,json,time
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QTimer,QEventLoop
from suite import SuiteWindow
from project_store import fingerprint
qt=QApplication([]);w=SuiteWindow('professional');w.poll.stop();w.autosave.stop()
blocks=json.loads(Path('perf-import/large.eguion').read_text())['blocks'];scene_ids=[]
for i,b in enumerate(blocks):
    b['id']='block-'+str(i)
    if b['type']=='scene':scene_ids.append((b['id'],b['text']))
data={'blocks':blocks,'budget':[{'concept':'Partida '+str(i),'quantity':'1','days':'1','unit_price':'10','exchange':'1','fringe':'0','currency':'USD'} for i in range(750)],'breakdown':[{'scene_id':scene_ids[i%150][0],'scene':scene_ids[i%150][1],'category':'Utilería','element':'Elemento '+str(i),'source':'Detalle original','approved':True} for i in range(1500)],'schedule':[{'scene_id':identity,'scene':heading,'day':str(i//5+1),'location':'Hospital'} for i,(identity,heading) in enumerate(scene_ids)]}
path=Path('perf-import/populated.eguion');path.write_text(json.dumps(data),encoding='utf-8')
errors=[];QMessageBox.critical=lambda *a:errors.append(a[-1]);w._last_saved=fingerprint(w.project_data());w.dirty=False
w.open_path(path);loop=QEventLoop();timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:loop.quit() if w._import_job is None else None);timer.start();loop.exec();timer.stop()
assert not errors,errors
assert w.budget.rowCount()==750 and w.breakdown.rowCount()==1500 and w.schedule_page.table.rowCount()==150
assert '7,500.00' in w.total_label.text(),w.total_label.text()
Path('perf-import/populated-profile.json').write_text(json.dumps(w.last_import_profile,indent=2));print(json.dumps(w.last_import_profile,ensure_ascii=True))
w._last_saved=fingerprint(w.project_data());w.dirty=False;w.close()
