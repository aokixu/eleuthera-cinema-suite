import copy
import json
from pathlib import Path
import tempfile
import time
from decimal import Decimal
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit, QMessageBox, QFileDialog
from suite import SuiteWindow
from budget_globals_ui import GlobalsDialog
from budget_model import BudgetError
from project_store import fingerprint

app = QApplication([])
warnings = []
QMessageBox.warning = lambda *args: warnings.append(args)
QMessageBox.critical = lambda *args: (_ for _ in ()).throw(AssertionError(args))
QMessageBox.information = lambda *args: None
QMessageBox.question = lambda *args: QMessageBox.StandardButton.Yes

def window():
    w = SuiteWindow('professional')
    w.poll.stop(); w.autosave.stop()
    return w

def close(w):
    w.budget_controller.cancel()
    w._last_saved = fingerprint(w.project_data()); w.dirty = False; w.close()

def drain(controller):
    end = time.monotonic() + 30
    while controller.busy and time.monotonic() < end: app.processEvents()
    assert not controller.busy and controller.result is not None

w = window()
c = w.budget_controller
dialog = GlobalsDialog(c, w)
original_exec = QDialog.exec
fields = ('NUM_EXTRAS', '20', 'Figuración')
def fill(form):
    for widget, value in zip(form.findChildren(QLineEdit), fields): widget.setText(value)
    form.findChild(QDialogButtonBox).accepted.emit()
    return form.result()
QDialog.exec = fill
dialog.edit(True)
assert c.catalog.get('NUM_EXTRAS').value == 20
fields = ('num_extras', '21', '')
dialog.edit(True)
assert warnings and c.catalog.get('NUM_EXTRAS').value == 20
fields = ('USD_BOB', '6,96', 'Cambio de referencia')
dialog.edit(True)
assert c.catalog.get('USD_BOB').value == Decimal('6.96')
w.add_budget_row(data={'quantity': 'NUM_EXTRAS', 'days': 'DIAS_RODAJE', 'unit_price': '150'})
assert w.budget.item(0, 12).text() == '3000.00'
dialog.table.selectRow(0)
fields = ('DIAS_RODAJE', '12', 'Rodaje principal')
dialog.edit(False)
assert w.budget.item(0, 12).text() == '36000.00'
assert w.global_days.value() == 12
dialog.remove()
assert c.catalog.get('DIAS_RODAJE').value == 12
assert 'DIAS_RODAJE' in str(warnings[-1])
dialog.table.selectRow(2)
dialog.remove()
assert 'USD_BOB' not in c.catalog.values()
QDialog.exec = original_exec
dialog.close()
w.global_days.setValue(10)
assert c.catalog.get('DIAS_RODAJE').value == 10
assert w.budget.item(0, 12).text() == '30000.00'
c.mutate('add', 'USD_BOB', '6.960000000000000001', 'Exacto')
preview = GlobalsDialog(c, w)
preview.show(); app.processEvents()
preview.grab().save('test-results/globals-preview.png')
preview.close()
with tempfile.TemporaryDirectory() as folder:
    p = Path(folder) / 'globals.eguion'
    w.path = p
    assert w.save()
    payload = json.loads(p.read_text(encoding='utf-8'))
    expected = copy.deepcopy(payload['budget_globals'])
    close(w)
    w = window(); c = w.budget_controller
    w.load_project(payload, p)
    assert w.project_data()['budget_globals'] == expected
    assert w.budget.item(0, 12).text() == '30000.00'
    before = fingerprint(w.project_data())
    invalid = copy.deepcopy(payload)
    invalid['budget_globals']['items'].append({'name': 'num_extras', 'value': 1})
    try: w.load_project(invalid)
    except BudgetError: pass
    else: raise AssertionError('Duplicado aceptado')
    assert before == fingerprint(w.project_data())
    legacy = copy.deepcopy(payload)
    legacy.pop('budget_globals')
    legacy['budget'][0]['quantity'] = '2'
    legacy['budget'][0]['days'] = '@DIAS_RODAJE'
    w.load_project(legacy)
    assert c.catalog.get('DIAS_RODAJE').value == 10
    assert w.budget.item(0, 12).text() == '3000.00'
    # Missing reference is visible and resolves automatically when added.
    w.budget.item(0, 5).setText('FUTURO')
    assert w.budget.item(0, 12).text() == 'ERROR'
    c.mutate('add', 'FUTURO', 3)
    assert w.budget.item(0, 12).text() == '4500.00'
    # Bulk job: GUI events continue; newer input cancels obsolete computation.
    w._loading = True
    for i in range(1200): w.add_budget_row(data={'quantity': 'FUTURO', 'days': '1', 'unit_price': '2'})
    w._loading = False
    ticks = []
    timer = QTimer(); timer.setInterval(1); timer.timeout.connect(lambda: ticks.append(time.monotonic())); timer.start()
    start = time.monotonic(); c.request(); elapsed = time.monotonic() - start
    assert c.busy and elapsed < .2
    assert not w.save()
    w.budget.item(0, 5).setText('2 * FUTURO')
    drain(c); timer.stop()
    assert len(ticks) > 2, ticks
    assert w.budget.item(0, 12).text() == '9000.00'
    assert c.result.total == 16200
    assert len(c.result.dependents['FUTURO']) == 1201
    c.mutate('edit', 'FUTURO', 'FUTURO', '4', '')
    assert c.busy
    drain(c)
    assert c.result.total == 21600
    assert not any('inv?lido' in issue[0] for issue in w.export_issues('budget'))
    report = Path(folder) / 'globals-report.xlsx'
    QFileDialog.getSaveFileName = lambda *a, **k: (str(report), '')
    w.preflight = lambda kind: True
    w.export_report('budget', 'xlsx')
    assert report.exists() and not c.busy
    # Switching projects cancels a pending job and discards the prior Globals.
    c.request()
    w.load_project({'blocks': [], 'budget': []})
    drain(c)
    assert set(c.catalog.values()) == {'DIAS_RODAJE'}
    assert c.result.total == 0
    print('PASS: Globals UI CRUD, duplicates, decimals, legacy days, save/close/reopen, invalid-load atomicity, missing references, 1201-row responsive recalculation and stale cancellation.', flush=True)
    print('GUI heartbeat events:', len(ticks), 'request seconds:', elapsed, flush=True)
close(w)
