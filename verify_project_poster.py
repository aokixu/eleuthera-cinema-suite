import os,tempfile,json
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from suite import SuiteWindow
app=QApplication([])
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder); image=QImage(600,900,QImage.Format.Format_RGB32); image.fill(0xff336699); image.save(str(root/'poster.png'))
 w=SuiteWindow('professional'); w.poll.stop(); w.autosave.stop(); w.project_poster.load_image(root/'poster.png'); assert w.dirty
 w.path=root/'film.eguion'; assert w.save(); data=json.loads(w.path.read_text(encoding='utf-8')); original=data['project_poster']; (root/'poster.png').unlink()
 w.load_project(data,w.path); assert w.project_poster.payload==original; assert w.project_poster.preview.image.size()==image.size()
 w.apply_metadata(); assert w.project_data()['project_poster']==original
 w.modules.setCurrentWidget(w.metadata_page); w.show()
 for size in [(1040,680),(1920,1080)]:
  w.resize(*size); app.processEvents(); assert w.project_poster.preview.width()>=220
 w.project_poster.remove(); assert w.project_data()['project_poster'] is None
 data.pop('project_poster'); w.load_project(data); assert w.project_poster.payload is None
 w.dirty=False; w.close()
print('PASS: poster integrado, guardar/reabrir sin imagen externa, quitar, proyecto antiguo y redimensionado.')
