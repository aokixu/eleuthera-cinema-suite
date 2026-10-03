import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from suite import SuiteWindow
q=QApplication([]);w=SuiteWindow('professional');w.autosave.stop();w.poll.stop();w.show();q.processEvents();e=w.editor
e.load_blocks([{'type':'action','text':'abcdef'}]);c=e.textCursor();c.setPosition(3);e.setTextCursor(c)
for i in range(4): QTest.keyClick(e,Qt.Key.Key_Return)
assert e.toPlainText()=='abc\n\n\n\ndef',repr(e.toPlainText())
QTest.keyClicks(e,'XYZ');assert e.toPlainText()=='abc\n\n\n\nXYZdef'
QTest.keyClick(e,Qt.Key.Key_Backspace);assert e.toPlainText().endswith('XYdef')
e.load_blocks([{'type':'action','text':'abc'}]);e.moveCursor(QTextCursor.MoveOperation.End)
QTest.keyClick(e,Qt.Key.Key_Return);e.undo();assert e.toPlainText()=='abc';e.redo();assert e.toPlainText()=='abc\n'
for i in range(70): QTest.keyClick(e,Qt.Key.Key_Return)
assert e.document().blockCount()==72
q.processEvents(); print(e.document().pageSize(), e.document().size(), e.document().pageCount()); assert e.document().pageCount()>1
assert e.verticalScrollBar().value()>0
for i in range(100):
 w.insert_breakdown({'approved':False,'scene':'INT. CASA - DIA','category':'Utileria','element':str(i),'source':'Una mesa.'})
QTest.mouseClick(w.approve_all_button,Qt.MouseButton.LeftButton)
assert all(row['approved'] for row in w.breakdown_data())
w.approved_to_budget(); assert w.budget.rowCount()==100
w.approved_to_budget(); assert w.budget.rowCount()==100
QTest.mouseClick(w.unapprove_all_button,Qt.MouseButton.LeftButton)
assert not any(row['approved'] for row in w.breakdown_data())
print('OK: repeated Enter, middle insertion, typing, backspace, undo/redo, page scrolling and bulk approval.')
from project_store import fingerprint
w._last_saved=fingerprint(w.project_data());w.dirty=False;w.close()

