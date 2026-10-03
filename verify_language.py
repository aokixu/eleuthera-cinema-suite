import os,json
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QLabel,QComboBox
from suite import SuiteWindow
from ui_i18n import set_language,ui_text,_records
app=QApplication([]);w=SuiteWindow('professional');w.autosave.stop();w.poll.stop()
set_language('en',persist=False)
print('MENU', [a.property('text') for a in w.menuBar().actions()])
print('TABS', [w.modules.tabBar().tabText(i) for i in range(w.modules.count())])
print('COMBO',w.analysis_page.marker_type.currentText(),w.analysis_page.marker_type.model().index(w.analysis_page.marker_type.currentIndex(),0).data())
assert w.analysis_page.marker_type.currentText()=='Personaje'
assert w.analysis_page.marker_type.model().index(w.analysis_page.marker_type.currentIndex(),0).data()=='Character'
assert any(a.property('text')=='File' for a in w.menuBar().actions())
combo=QComboBox();combo.addItems([ui_text('Personaje'),ui_text('Escena')]);values=[];combo.currentTextChanged.connect(values.append);combo.setCurrentIndex(1);assert values==['Escena'],values
set_language('es',persist=False);assert combo.model().index(combo.currentIndex(),0).data()=='Escena'
print('PASS language switching, canonical values, signals',len(_records))
