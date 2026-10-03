import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from suite import SuiteWindow
from project_store import fingerprint
q=QApplication([])
for edition in ('standard','professional'):
 w=SuiteWindow(edition);w.autosave.stop();w.poll.stop()
 names=[w.modules.tabText(i) for i in range(w.modules.count())]
 assert 'Dictado' not in names and 'Buscar' not in names,names
 assert not hasattr(w,'search_page') and not hasattr(w,'voice_page')
 assert not hasattr(w, 'excel_button')
 print(edition,names)
 w._last_saved=fingerprint(w.project_data());w.dirty=False;w.close()
