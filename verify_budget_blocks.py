import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QItemSelectionModel
from suite import SuiteWindow
from project_store import fingerprint
q=QApplication([])
for edition in ('standard','professional'):
 w=SuiteWindow(edition);w.autosave.stop();w.poll.stop()
 for i in range(3): w.add_budget_row('Otro',str(i),block='BTL')
 w.budget_block.setCurrentText('ATL')
 assert all(w.budget.item(i,1).text()=='BTL' for i in range(3))
 for row in (0,2): w.budget.selectionModel().select(w.budget.model().index(row,0),QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)
 w.apply_selected_budget_block()
 assert [w.budget.item(i,1).text() for i in range(3)]==['ATL','BTL','ATL']
 w.insert_breakdown({'approved':True,'scene':'INT. CASA','category':'Utileria','element':'Mesa','source':'Mesa'})
 w.breakdown_budget_block.setCurrentText('ATL');w.approved_to_budget()
 assert w.budget.item(3,1).text()=='ATL'
 w.breakdown_budget_block.setCurrentText('BTL');w.approved_to_budget();assert w.budget.rowCount()==4
 assert w.budget.item(3,1).text()=='ATL'
 w.insert_breakdown({'approved':True,'scene':'INT. CASA','category':'Utileria','element':'Silla','source':'Silla'});w.approved_to_budget()
 assert w.budget.item(4,1).text()=='BTL'
 w._last_saved=fingerprint(w.project_data());w.dirty=False;w.close()
print('OK: both editions, selected rows only, ATL/BTL import and no duplicate/reclassification.')
