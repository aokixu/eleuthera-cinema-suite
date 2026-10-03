import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from production import analyze_blocks
from suite import SuiteWindow


blocks = [
    {'type': 'scene', 'text': 'EXT. CARRETERA - NOCHE'},
    {'type': 'action', 'text': 'Elena baja de un automovil destrozado con un revolver.'},
    {'type': 'character', 'text': 'ELENA'},
    {'type': 'dialogue', 'text': 'No debi venir.'},
]

suggestions = analyze_blocks(blocks)
assert any(row['category'] == 'Vehiculo' for row in suggestions)
assert any(row['category'] == 'Utileria' for row in suggestions)
assert any(row['category'] == 'Reparto' for row in suggestions)

qt = QApplication([])
window = SuiteWindow('professional')
window.set_workspace_mode('professional')
window.editor.load_blocks(blocks)
window.analyze_script()
assert window.breakdown.rowCount() >= 5
assert window.modules.currentWidget() is window.breakdown_page
window.breakdown.item(0, 0).setCheckState(Qt.CheckState.Checked)
window.sync_schedule()
assert window.schedule_page.table.rowCount() == 1
assert window.schedule_page.table.item(0, 3).text() == 'EXT. CARRETERA - NOCHE'
assert window.schedule_page.table.item(0, 4).text() == 'EXT'
assert window.schedule_page.table.item(0, 5).text() == 'NOCHE'
assert window.schedule_page.table.item(0, 3).foreground().color().name() == '#252329'
window.schedule_page.table.selectRow(0)
window.schedule_page.day.setValue(2)
window.schedule_page.assign_day()
assert window.schedule_page.table.item(0, 1).text() == '2'
window.add_budget_row(category='Cámara', concept='Personal', level='Cuenta', block='ATL')
window.approved_to_budget()
assert window.budget.rowCount() == 2
window.global_days.setValue(3)
window.budget.item(1, 1).setText('ATL')
window.budget.item(1, 5).setText('2')
window.budget.item(1, 7).setText('@DIAS_RODAJE')
window.budget.item(1, 8).setText('100')
window.budget.item(1, 11).setText('10')
window.update_budget_total()
assert window.budget.item(1, 12).text() == '660.00'
assert window.budget.item(0, 12).text() == '660.00'
assert 'ATL 660.00' in window.top_sheet_label.text()
window.base_currency.setCurrentText('BOB')
assert window.budget.item(0, 9).text() == 'BOB'
assert window.budget.item(1, 9).text() == 'BOB'
assert window.budget.item(1, 10).text() == '1'
assert window.budget.columnWidth(10) >= 100
assert window.budget.columnWidth(8) >= 100

with tempfile.TemporaryDirectory() as temp:
    export_path = Path(temp) / 'desglose.csv'
    original_dialog = QFileDialog.getSaveFileName
    original_information = QMessageBox.information
    try:
        QFileDialog.getSaveFileName = staticmethod(lambda *args: (str(export_path), ''))
        QMessageBox.information = staticmethod(lambda *args: None)
        window.export_breakdown()
    finally:
        QFileDialog.getSaveFileName = original_dialog
        QMessageBox.information = original_information
    exported = export_path.read_text(encoding='utf-8-sig')
    assert exported.startswith('Aprobado;Escena;Categoria;Elemento;Texto de origen')
    assert 'EXT. CARRETERA - NOCHE' in exported

    report_path = Path(temp) / 'informes.xlsx'
    try:
        QFileDialog.getSaveFileName = staticmethod(lambda *args: (str(report_path), ''))
        QMessageBox.information = staticmethod(lambda *args: None)
        window.schedule_page.export_reports()
    finally:
        QFileDialog.getSaveFileName = original_dialog
        QMessageBox.information = original_information
    assert report_path.is_file()

    window.path = Path(temp) / 'suite.eguion'
    window.dirty = True
    assert window.save()
    data = json.loads(window.path.read_text(encoding='utf-8'))
    assert data['suite_format'] == 4
    assert 'story_map' in data
    assert len(data['breakdown']) >= 5
    assert data['budget'][1]['total'] == '660.00'
    assert data['budget_settings']['shooting_days'] == 3
    assert data['schedule'][0]['day'] == '2'

window.resize(1380, 860)
window.modules.setCurrentWidget(window.breakdown_page)
qt.processEvents()
window.grab().save(str(Path(__file__).parent / 'vista-desglose.png'))
window.modules.setCurrentWidget(window.budget_page)
qt.processEvents()
window.grab().save(str(Path(__file__).parent / 'vista-presupuesto.png'))
window.dirty = False
window.close()
print('OK: suite, desglose automatico, aprobacion, presupuesto y persistencia.')



