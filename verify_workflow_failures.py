import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QPushButton, QDialog, QPlainTextEdit
from PySide6.QtTest import QTest
from pypdf import PdfReader
from suite import SuiteWindow
from project_store import atomic_json, fingerprint
from professional import parse_fdx

qt = QApplication([]); qt.setOrganizationName('EleutheraWorkflowTests'); qt.setApplicationName('FailureChecks')
for font in ('segoeui.ttf', 'segoeuib.ttf', 'arial.ttf', 'arialbd.ttf', 'cour.ttf', 'courbd.ttf'): QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
artifacts = Path('workflow-checks')
QMessageBox.information = lambda *a, **k: QMessageBox.StandardButton.Ok
QMessageBox.question = lambda *a, **k: QMessageBox.StandardButton.Yes
with TemporaryDirectory() as temp:
    root = Path(temp); target = root / 'atomic.eguion'; atomic_json(target, {'before': True})
    with patch('project_store.os.replace', side_effect=OSError('Simulated full disk')):
        try: atomic_json(target, {'after': True}); raise AssertionError('Should fail')
        except OSError: pass
    assert json.loads(target.read_text()) == {'before': True}
    assert not list(root.glob('*.tmp'))
    w = SuiteWindow('professional'); w.poll.stop(); w.autosave.stop(); w.recovery_root = root / 'recovery'; w.show(); qt.processEvents()
    w.editor.load_blocks([{'type': 'scene', 'text': 'INT. HOSPITAL - NOCHE'}, {'type': 'character', 'text': 'PEDRO'}, {'type': 'dialogue', 'text': 'Hola.'}]); w.analyze_script(); w.sync_schedule()
    # Real preflight buttons allow export or navigate without exporting.
    def click_dialog(text):
        dialog = qt.activeModalWidget(); assert dialog
        next(b for b in dialog.findChildren(QPushButton) if b.text() == text).click()
    QTimer.singleShot(30, lambda: click_dialog('Exportar igualmente')); assert w.preflight('schedule')
    QTimer.singleShot(30, lambda: click_dialog('Revisar')); assert not w.preflight('schedule')
    assert w.modules.currentWidget() is w.schedule_page
    # A bad file leaves the open document and metadata untouched.
    w.info_fields['title'].setText('Prueba de portada'); w.apply_metadata()
    w.path = root / 'good.eguion'; assert w.save(); previous = w.project_data()
    corrupt = root / 'bad.eguion'; atomic_json(corrupt, {'blocks': [{'type': 'unknown', 'text': 'Bad'}]})
    errors = []; QMessageBox.critical = lambda *args: errors.append(args[-1])
    assert not w.open_path(corrupt, asynchronous=False); assert w.project_data() == previous and errors
    # Pending metadata form edits are recovered without being applied silently.
    w.info_fields['company'].setText('Borrador de productora'); w.path = None; w.auto_save()
    data = w.recovery_candidates()[0][1]['data']; assert data['metadata_draft']['company'] == 'Borrador de productora'; assert not data['project_info']['company']
    # Actual script PDF keeps the script after its title page.
    QFileDialog.getSaveFileName = lambda *a, **k: (str(artifacts / 'guion.pdf'), '')
    w.export_pdf(); pdf = PdfReader(artifacts / 'guion.pdf'); assert len(pdf.pages) >= 2
    text = '\n'.join(p.extract_text() for p in pdf.pages); assert 'portada' in text.lower() and 'PEDRO' in text and 'Hola.' in text
    QFileDialog.getSaveFileName = lambda *a, **k: (str(artifacts / 'para-scheduling.fdx'), '')
    w.export_scheduling_fdx(); parsed = parse_fdx(artifacts / 'para-scheduling.fdx'); assert any(b['type'] == 'character' and b['text'] == 'PEDRO' for b in parsed)
    # Test writing from the table selection, and Tab confirmation.
    w.add_budget_row(concept='Original'); w.modules.setCurrentWidget(w.budget_page); w.budget.setCurrentCell(0, 4); w.activateWindow(); qt.setActiveWindow(w); w.budget.setFocus(); qt.processEvents()
    QTest.keyClick(w.budget, Qt.Key.Key_C); qt.processEvents()
    active = qt.focusWidget(); assert isinstance(active, QPlainTextEdit)
    QTest.keyClicks(active, 'amara'); QTest.keyClick(active, Qt.Key.Key_Tab); qt.processEvents()
    assert w.budget.item(0, 4).text().lower() == 'camara'
    # Recovery selection restores complete data as a copy.
    w.commit_active_cell(); w._last_saved = fingerprint(w.project_data()); w.dirty = False
    def select_recovery():
        from PySide6.QtWidgets import QListWidget
        dialog = qt.activeModalWidget(); dialog.findChild(QListWidget).setCurrentRow(0)
        next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Recuperar seleccionada').click()
    QTimer.singleShot(30, select_recovery); w.recover_dialog(); assert w.path is None and w.dirty
    def welcome():
        dialog = qt.activeModalWidget(); dialog.grab().save(str(artifacts / 'welcome.png')); dialog.accept()
    QTimer.singleShot(60, welcome); w.show_welcome()
    w._last_saved = fingerprint(w.project_data()); w.dirty = False; w.close()
print('OK: atomic failure, corrupt project, preflight controls, draft recovery, script PDF, FDX, keyboard cell entry, recovery dialog and welcome.')
