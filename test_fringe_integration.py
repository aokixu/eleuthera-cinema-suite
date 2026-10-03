"""Flujo real Qt, 1025 partidas, exportaciones y mediciones de Etapa 3."""
import copy
import json
from pathlib import Path
from time import perf_counter
from decimal import Decimal
from dataclasses import asdict
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QDialogButtonBox, QMessageBox, QFileDialog
from openpyxl import load_workbook
from suite import SuiteWindow
from project_store import fingerprint
from budget_values import BudgetError
from budget_fringes_ui import FringesDialog, AssignmentDialog
from budget_controller import FRINGE_ROLE

app = QApplication([])
out = Path('test-results/stage3'); out.mkdir(exist_ok=True)
passed, metrics, warnings = [], {}, []
QMessageBox.warning = lambda *a, **k: warnings.append(a)
QMessageBox.information = lambda *a, **k: None
QMessageBox.question = lambda *a, **k: QMessageBox.StandardButton.Yes
QMessageBox.critical = lambda *a, **k: (_ for _ in ()).throw(AssertionError(a))

def window():
    w=SuiteWindow('professional'); w.poll.stop(); w.autosave.stop(); return w

def drain(predicate):
    deadline=perf_counter()+90
    while predicate() and perf_counter()<deadline: app.processEvents()
    assert not predicate(), 'Trabajo no finalizado'

def close(w):
    w._last_saved=fingerprint(w.project_data()); w.dirty=False; w.close()

def update(c, identifier, **changes):
    fields=asdict(c.fringes.get(identifier)); fields.pop('id'); fields.update(changes)
    c.mutate_fringe('edit', identifier, **fields)

def rejects(w, call):
    before=fingerprint(w.project_data())
    try: call()
    except BudgetError: pass
    else: raise AssertionError('Aceptó una operación inválida')
    assert fingerprint(w.project_data())==before

w=window(); c=w.budget_controller
c.mutate('add', 'P', '10', '')
c.mutate('add', 'Q', '10', '')
c.mutate('add', 'TOPE', '5000', '')
c.mutate('add', 'DOBLE', 'P * 2', '')
dialog=FringesDialog(c,w)
old_exec=QDialog.exec
fields=('SEGURO','P','TOPE','Seguro de producción')
def fill(form):
    for widget, text in zip(form.findChildren(QLineEdit), fields): widget.setText(text)
    form.findChild(QDialogButtonBox).accepted.emit()
    return form.result()
QDialog.exec=fill
dialog.edit(True)
fringe=c.fringes.items()[0].id
before=fingerprint(w.project_data())
fields=('SEGURO','-5','','Inválido')
dialog.edit(False)
assert warnings and fingerprint(w.project_data())==before
QDialog.exec=old_exec
w.add_budget_row(data={'concept':'Actor principal','quantity':'1','days':'1','unit_price':'10000'})
assignment=AssignmentDialog(c,0,w)
assignment.listing.item(0).setCheckState(Qt.CheckState.Checked); assignment.save()
assert w.budget.item(0,12).text()=='10500.00'
assert w.budget_data()[0]['fringe_ids']==[fringe]
dialog.toggle(); assert w.budget.item(0,12).text()=='10000.00'
dialog.toggle(); assert w.budget.item(0,12).text()=='10500.00'
dialog.remove(); assert 'fila 1' in str(warnings[-1])
update(c,fringe,name='SEGURO_RENOMBRADO')
assert w.budget_data()[0]['fringe_ids']==[fringe]
dialog.refresh(); dialog.show(); app.processEvents(); dialog.grab().save(str(out/'fringes.png')); dialog.close()
passed.append('UI CRUD, asignación, activación, renombrado estable y eliminación bloqueada')

rejects(w,lambda: c.mutate('remove','P'))
rejects(w,lambda: c.mutate('edit','P','OTRO','10',''))
rejects(w,lambda: c.mutate('edit','P','P','-1',''))
rejects(w,lambda: c.mutate('edit','TOPE','TOPE','-1',''))
rejects(w,lambda: update(c,fringe,percentage='1/0'))
rejects(w,lambda: update(c,fringe,cap='NO_EXISTE'))
rejects(w,lambda: c.assign_fringes([0],['missing']))
c.assign_fringes([0],[fringe,fringe])
assert w.budget_data()[0]['fringe_ids']==[fringe]
c.assign_fringes([0],[]); assert w.budget.item(0,12).text()=='10000.00'
c.assign_fringes([0],[fringe])
passed.append('Errores y Globals referenciados: transacciones sin estado parcial; deduplicación y desasignación')

# A Fringe expression can change references while keeping the same result.
update(c,fringe,percentage='Q')
c.mutate('edit','P','P','11',''); assert c.last_run['evaluated_rows']==0
c.mutate('edit','Q','Q','12',''); assert w.budget.item(0,12).text()=='10600.00'
update(c,fringe,percentage='DOBLE')
c.mutate('edit','P','P','10',''); assert w.budget.item(0,12).text()=='11000.00'
passed.append('Grafo transitivo Global → Global → Fringe → partida y cambio de referencias con resultado igual')

rare=c.mutate_fringe('add',name='ESPECIAL',percentage='5')
update(c,fringe,percentage='P',cap=None)
w._loading=True; w.budget.setRowCount(0)
w.add_budget_row(data={'level':'Cuenta','concept':'Equipo','block':'ATL'})
for i in range(1025):
    w.add_budget_row(data={'concept':'Partida '+str(i),'block':'ATL','quantity':'1','days':'1',
        'unit_price':'1000','fringe_ids':([fringe] if i<1005 else [rare])})
w._loading=False; c.request(); drain(lambda:c.busy)
assert c.result.total==Decimal(1126500)
unchanged=c.result.totals[1:1006]
start=perf_counter(); update(c,rare,percentage='6'); drain(lambda:c.busy)
metrics['rare_20_rows_ms']=(perf_counter()-start)*1000
assert c.last_run['evaluated_rows']==20 and c.result.totals[1:1006]==unchanged
metrics['rare_selective']=dict(c.last_run)
passed.append('1025 partidas: editar Fringe de 20 evalúa solo 20 y conserva otras 1005')

ticks=[perf_counter()]; timer=QTimer();timer.setInterval(1);timer.timeout.connect(lambda:ticks.append(perf_counter()));timer.start()
start=perf_counter();update(c,fringe,percentage='P + 1')
metrics['fringe_1005_submit_ms']=(perf_counter()-start)*1000
assert c.busy
drain(lambda:c.busy);metrics['fringe_1005_complete_ms']=(perf_counter()-start)*1000
timer.stop(); assert len(ticks)>2 and c.last_run['evaluated_rows']==1005
metrics['gui_heartbeat_events']=len(ticks)-1
metrics['max_gui_gap_ms']=max(b-a for a,b in zip(ticks,ticks[1:]))*1000
start=perf_counter(); c.mutate('edit','P','P','12',''); drain(lambda:c.busy)
metrics['global_through_fringe_1005_ms']=(perf_counter()-start)*1000
assert c.last_run['evaluated_rows']==1005
assert c.result.total==Decimal(1156850)
passed.append('Cambio de Fringe y Global con 1005 partidas, Qt responde y actualiza cuenta/total')

project=out/'fringes-project.eguion'; excel=out/'fringes-report.xlsx'; pdf=out/'fringes-report.pdf'
w.path=project
start=perf_counter(); assert w.save();metrics['save_1026_rows_ms']=(perf_counter()-start)*1000
saved=w.project_data(); close(w)
w=window(); c=w.budget_controller
start=perf_counter();assert w.open_path(project)
drain(lambda:getattr(w,'_import_job',None) is not None)
metrics['open_1026_rows_ms']=(perf_counter()-start)*1000
assert w.project_data()['budget_fringes']==saved['budget_fringes']
assert w.budget_data()[1]['fringe_ids']==[fringe]
assert c.result.total==Decimal(1156850)
passed.append('Guardar, cerrar y reabrir: catálogo, fórmulas, estados, IDs y asignaciones conservados')

for corrupt in ('missing-id','negative','global','account'):
    bad=copy.deepcopy(saved)
    if corrupt=='missing-id':bad['budget'][1]['fringe_ids']=['missing']
    if corrupt=='negative':bad['budget_fringes']['items'][0]['percentage']='-1'
    if corrupt=='global':bad['budget_fringes']['items'][0]['cap']='NO_EXISTE'
    if corrupt=='account':bad['budget'][0]['fringe_ids']=[fringe]
    rejects(w,lambda: w.load_project(bad))
passed.append('Carga corrupta rechazada antes de reemplazar proyecto')

before=project.read_bytes();update(c,fringe,percentage='P + 2');assert c.busy
assert not w.save() and project.read_bytes()==before
pending=out/'must-not-export.xlsx'
QFileDialog.getSaveFileName=lambda *a,**k:(str(pending),'')
w.export_report('budget','xlsx'); assert not pending.exists()
pending_pdf=out/'must-not-export.pdf'
QFileDialog.getSaveFileName=lambda *a,**k:(str(pending_pdf),'')
w.export_report('budget','pdf'); assert not pending_pdf.exists()
drain(lambda:c.busy)
assert c.result.total==Decimal(1166900)
assert not w.export_issues('budget')
QFileDialog.getSaveFileName=lambda *a,**k:(str(excel),'')
start=perf_counter();w.export_report('budget','xlsx');metrics['export_excel_ms']=(perf_counter()-start)*1000
book=load_workbook(excel); assert 'Base y Fringes' in book.sheetnames
values=[str(value) for sheet in book for row in sheet.iter_rows(values_only=True) for value in row if value is not None]
assert w.total_label.text() in values and '1140.00' in values and '140.00' in values
QFileDialog.getSaveFileName=lambda *a,**k:(str(pdf),'')
start=perf_counter();w.export_report('budget','pdf');metrics['export_pdf_ms']=(perf_counter()-start)*1000
assert pdf.read_bytes().startswith(b'%PDF')
from pypdf import PdfReader
text=''.join(page.extract_text() or '' for page in PdfReader(pdf).pages)
import re
assert re.search(r'1140\s*\.\s*00', text) and re.search(r'(?<![0-9])140\s*\.\s*00', text)
passed.append('Exportación Excel/PDF actualizada con base/cargas/total; ambas bloqueadas durante pendiente')

update(c,fringe,percentage='15');assert c.busy
w.budget.item(1,5).setText('2');drain(lambda:c.busy)
assert c.last_run['mode']=='full' and w.budget.item(1,12).text()=='2300.00'
passed.append('Cancelar recálculo de Fringe ante edición de partida no publica resultados obsoletos')

# Currency test through real migration and UI: local 10000, cap 5000 at 10%, rate 6.96.
small=copy.deepcopy(saved); small['budget']=small['budget'][1:2]
small['budget'][0].update(quantity='1',days='1',unit_price='10000',currency='USD',exchange='6.96',fringe='5')
small['budget_fringes']['items'][0].update(percentage='10',cap='5000')
small.pop('budget_currencies',None);small.pop('budget_currency_legacy',None)
small['project_info']['currency']='BOB';small['project_info']['rates']={'USD':6.96}
small['budget_settings']['base_currency']='BOB'
w.load_project(small)
assert w.budget.item(0,12).text()=='76560.00'
assert c.result.bases[0]==69600 and c.result.fringe_totals[0]==6960
small.pop('budget_fringes');small['budget'][0].pop('fringe_ids')
w.load_project(small);assert w.budget.item(0,12).text()=='73080.00'
passed.append('Moneda real + tope + legado sin doble conversión; proyecto antiguo sin catálogo')
close(w)
(out/'integration-results.json').write_text(json.dumps({'passed':passed,'metrics':metrics},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS:',len(passed),'escenarios de Etapa 3')
print(json.dumps(metrics,indent=2))
