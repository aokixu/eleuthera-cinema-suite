import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QFontDatabase
from suite import SuiteWindow
from project_store import fingerprint
qt=QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf'): QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+name)
for edition in ('professional','standard'):
    w=SuiteWindow(edition);w.poll.stop();w.autosave.stop();w.resize(1146,740);w.show();qt.processEvents()
    for key,page in [('budget',w.budget_page),('breakdown',w.breakdown_page),('schedule',w.schedule_page)]:
        if edition=='standard' and key=='schedule':continue
        w.modules.setCurrentWidget(page);qt.processEvents()
        assert not any(label.isVisible() and label.objectName()=='moduleTitle' for label in page.findChildren(QLabel))
        w.grab().save('workflow-checks/compact-'+edition+'-'+key+'.png')
    w.currency_change.click();assert w.modules.currentWidget() is w.metadata_page
    assert w.info_fields['currency'].hasFocus()
    w.load_project({'blocks':[],'budget_settings':{'base_currency':'BOB'}},None)
    assert w.currency_label.text()=='Moneda base: BOB'
    w._last_saved=fingerprint(w.project_data());w.dirty=False;w.close()
print('OK: compact layout and currency navigation in both editions.')
