import os, json, tempfile, copy
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QPushButton,QLineEdit,QDoubleSpinBox,QTableWidget,QComboBox,QMessageBox
from suite import SuiteWindow
import budget_currencies as m
app=QApplication([]); app.setOrganizationName('CurrencyRegression'); app.setApplicationName('CurrencyRegression')
QMessageBox.question=staticmethod(lambda *a,**k: QMessageBox.StandardButton.Yes)
QMessageBox.warning=staticmethod(lambda *a,**k: QMessageBox.StandardButton.Ok)
def fail(*a,**k): raise AssertionError(a)
QMessageBox.critical=staticmethod(fail)
def window():
 w=SuiteWindow('professional'); w.poll.stop(); w.autosave.stop(); return w
w=window()
data=w.project_data(); data.pop('budget_currencies'); data['project_info']={'currency':'BOB','rates':{'USD':6.96}}; data['metadata_draft']={'rates_text':'6.96'}
data['budget']=[{'concept':'Camera','quantity':'2','days':'3','unit_price':'100','currency':'USD','exchange':'6.96'}]
w.load_project(data)
assert w.budget.item(0,12).text()=='4176.00'
assert w.budget_currency_legacy['rates_text']=='6.96'
w.modules.setCurrentWidget(w.budget_page); w.budget.setCurrentCell(0,4)
original_exec=QDialog.exec
operations=[]
def dialog_exec(d):
 if d.windowTitle()=='Monedas del presupuesto':
  t=d.findChild(QTableWidget)
  for action,code,symbol,rate in operations:
   if action=='base': d.findChild(QComboBox).setCurrentText(code); continue
   if action!='add':
    t.selectRow(next(i for i in range(t.rowCount()) if t.item(i,0).text()==code))
   global values
   values=(code,symbol,rate)
   label={'add':'Agregar moneda','edit':'Editar','delete':'Eliminar'}[action]
   next(b for b in d.findChildren(QPushButton) if b.text()==label).click()
  d.findChild(QDialogButtonBox).accepted.emit()
  return d.result()
 fields=d.findChildren(QLineEdit); fields[0].setText(values[0]); fields[1].setText(values[1]); d.findChild(QDoubleSpinBox).setValue(values[2]); d.findChild(QDialogButtonBox).accepted.emit(); return d.result()
QDialog.exec=dialog_exec
operations=[('add','EUR','Euro',8.1),('edit','USD','$',7.0)]
w.open_currency_settings()
assert w.budget.item(0,12).text()=='4200.00'
assert w.modules.currentWidget()==w.budget_page and w.budget.currentRow()==0 and w.budget.currentColumn()==4
# Real currency editor delegate: choose EUR, then automatic base.
def choose(code):
 delegate=w.budget.itemDelegateForColumn(9); idx=w.budget.model().index(0,9); editor=delegate.createEditor(w.budget,None,idx); delegate.setEditorData(editor,idx); editor.setCurrentIndex(editor.findData(code)); delegate.setModelData(editor,w.budget.model(),idx); editor.deleteLater()
choose('EUR'); assert w.budget.item(0,12).text()=='4860.00'
operations=[('delete','EUR','',0)]; w.open_currency_settings(); assert len(w.budget_currencies['currencies'])==3
choose(''); assert w.budget.item(0,12).text()=='600.00'
operations=[('delete','EUR','',0)]; w.open_currency_settings(); assert len(w.budget_currencies['currencies'])==2
choose('USD')
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory)/'monedas.eguion'; w.path=p; assert w.save(); expected=w.budget_data(); catalog=copy.deepcopy(w.budget_currencies)
 w.dirty=False; w.close(); reopened=window(); reopened.load_project(json.loads(p.read_text(encoding='utf-8')),p)
 assert reopened.budget_data()==expected and reopened.budget_currencies==catalog
 assert reopened.budget.item(0,12).text()=='4200.00'
 # Legacy conflicting per-line rate survives migration and a second save/reopen.
 old=copy.deepcopy(data); old['budget'][0]['exchange']='6.5'; reopened.load_project(old,p)
 assert reopened.budget.item(0,12).text()=='3900.00'; assert reopened.budget_data()[0]['legacy_exchange']=='6.5'
 assert reopened.save(); reopened.load_project(json.loads(p.read_text(encoding='utf-8')),p); assert reopened.budget.item(0,12).text()=='3900.00'
 operations=[('edit','USD','$',7.0)]; reopened.open_currency_settings(); assert reopened.budget.item(0,12).text()=='4200.00'
 operations=[('base','USD','',0)]; reopened.open_currency_settings(); assert reopened.budget.item(0,12).text()=='600.00'
 assert next(r for r in reopened.budget_currencies['currencies'] if r['code']=='USD')['rate']==1
 reopened.dirty=False; reopened.close()
QDialog.exec=original_exec
print('PASS: add/edit/delete, used-currency protection, line selector, automatic base, conversion, save-close-reopen, legacy malformed draft, historical rates, base change, Budget state.')
