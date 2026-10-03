"""Professional regression with optional GPL Qt modules unavailable."""
import importlib.abc
import sys
import tempfile
from pathlib import Path


class BlockOptionalQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('PySide6.', 'qtpy.')) and any(name in fullname for name in (
                'DataVisualization', 'Charts', 'Graphs', 'VirtualKeyboard', 'Quick3D')):
            raise ImportError('Optional Qt module intentionally unavailable: ' + fullname)


sys.meta_path.insert(0, BlockOptionalQt())
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings
from suite import SuiteWindow
from production_reports import write_pdf, write_excel, budget_tables
from script_docx import export_script_docx
from professional import write_fdx, parse_fdx
from pypdf import PdfReader
from openpyxl import load_workbook

qt = QApplication([])
qt.setOrganizationName('Eleuthera-Pro-Package-Test')
qt.setApplicationName('Qt audit')
qt.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    window = SuiteWindow('professional')
    window.autosave.stop()
    window.poll.stop()
    window.recovery_root = root / 'recovery'
    window.show()
    qt.processEvents()
    blocks = [{'type': 'scene', 'text': 'INT. CASA - DIA'},
              {'type': 'action', 'text': 'Un telefono sobre la mesa.'},
              {'type': 'character', 'text': 'ANA'},
              {'type': 'dialogue', 'text': 'Hola.'}]
    window.editor.load_blocks(blocks)
    window.analyze_script()
    assert window.breakdown_data()
    window.sync_schedule()
    assert len(window.schedule_page.to_data()) == 1
    window.add_budget_row(concept='Camara', data={'concept': 'Camara', 'quantity': '2',
                         'days': '3', 'unit_price': '100', 'currency': 'USD', 'exchange': '1'})
    window.update_budget_total()
    assert window.budget_data()
    for i in range(window.modules.count()):
        window.modules.setCurrentIndex(i)
        qt.processEvents()
        assert not window.grab().isNull()
        if not window.modules.tabIcon(i).isNull():
            assert not window.modules.tabIcon(i).pixmap(24, 24).isNull()
    window.path = root / 'test.eguion'
    assert window.save()
    data = __import__('json').loads(window.path.read_text(encoding='utf-8'))
    window.load_project(data, window.path)
    assert window.editor.blocks()[0]['text'] == blocks[0]['text']
    tables = budget_tables(window.budget_data(), window.total_label.text())
    write_pdf(root / 'test.pdf', 'Test', {}, tables)
    assert PdfReader(root / 'test.pdf').pages
    write_excel(root / 'test.xlsx', 'Test', {}, tables)
    assert load_workbook(root / 'test.xlsx').worksheets
    export_script_docx(root / 'test.docx', window.editor.blocks())
    write_fdx(root / 'test.fdx', window.editor.blocks())
    assert parse_fdx(root / 'test.fdx')
    assert not any('QtDataVisualization' in name for name in sys.modules)
    window.hide()
    window.deleteLater()
QSettings().clear()
print('OK Pro: icons, all tabs, script, breakdown, schedule, budget, save/reopen, PDF/Excel/DOCX/FDX; optional Qt blocked.')
