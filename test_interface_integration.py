"""Etapa 7: flujos de widgets reales Qt, navegación y presentación."""
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QLineEdit,QDialogButtonBox,QMessageBox
from suite import SuiteWindow
from project_store import fingerprint
from plus_theme import ACCENT,SELECTION
from budget_globals_ui import GlobalsDialog
from budget_fringes_ui import FringesDialog,AssignmentDialog
from budget_charges_ui import ChargesDialog,ChargeAssignmentDialog
from budget_credits_ui import CreditsDialog,CreditAssignmentDialog
from budget_groups_ui import GroupsDialog,GroupSelectionDialog,GroupSummaryDialog

app=QApplication([]);out=Path('test-results/stage7');out.mkdir(exist_ok=True)
passed=[]
QMessageBox.warning=lambda *args: (_ for _ in ()).throw(AssertionError(str(args)))
QMessageBox.information=lambda *args:None
def window():
    w=SuiteWindow('professional');w.poll.stop();w.autosave.stop()
    w.modules.setCurrentWidget(w.budget_page);w.show();app.processEvents();return w
def drain(predicate):
    end=perf_counter()+90
    while predicate() and perf_counter()<end:app.processEvents()
    assert not predicate()
def close(w):
    w._last_saved=fingerprint(w.project_data());w.dirty=False;w.close()
def form(dialog, values, add):
    def fill(child):
        fields=child.findChildren(QLineEdit)
        assert len(fields)==len(values)
        for field,value in zip(fields,values):field.setText(value)
        child.findChild(QDialogButtonBox).accepted.emit()
        assert child.result()==QDialog.DialogCode.Accepted
        return child.result()
    with patch.object(QDialog,'exec',fill):dialog.edit(add)

w=window();c=w.budget_controller
menu=w.budget_tools_button.menu()
assert [a.text() for a in menu.actions()]==['Globals…','Fringes','Cargos contractuales','Credits','Groups']
for old in (w.globals_button,w.fringes_button,w.assign_fringes_button,w.charges_button,w.credits_button,w.groups_button):assert old.isHidden()
assert w.dark and ACCENT in app.styleSheet() and '#633743' not in app.styleSheet()
assert app.palette().color(QPalette.ColorRole.Highlight).name()==SELECTION
passed.append('Un solo menu, cinco herramientas, sin botones duplicados; oscuro y petroleo coherentes')

dialogs=[GlobalsDialog(c,w),FringesDialog(c,w),ChargesDialog(c,w),CreditsDialog(c,w),GroupsDialog(c.groups,w)]
values=[('CARGO','400','Prueba'),('SEGURO','10','','Prueba'),('CONTRATO','CARGO','Prueba'),('DEVOLUCION','1500','Prueba'),('UNIDAD','Prueba')]
for d,v in zip(dialogs,values):
    form(d,v,True)
    d.table.selectRow(d.table.rowCount()-1)
    updated=list(v);updated[-1]='Editado desde interfaz';form(d,updated,False)
    assert hasattr(d,'search')
    d.search.setText('no_coincide');app.processEvents()
    assert all(d.table.isRowHidden(i) for i in range(d.table.rowCount()))
    d.search.clear();app.processEvents();assert not d.table.isRowHidden(d.table.currentRow())
    d.show();app.processEvents();d.grab().save(str(out/(type(d).__name__+'.png')));d.hide()
passed.append('Crear y editar los cinco catalogos desde sus formularios; buscar sin cambiar IDs ni orden')

w.add_budget_row(data={'concept':'Partida de prueba','quantity':'1','days':'1','unit_price':'10000'})
w.budget.selectRow(0)
for cls,controller in [(AssignmentDialog,c),(ChargeAssignmentDialog,c),(CreditAssignmentDialog,c),(GroupSelectionDialog,c.groups)]:
    d=cls(controller,0,w);d.listing.item(0).setCheckState(Qt.CheckState.Checked);d.save()
assert c.result.total==9900
g=dialogs[0];g.table.selectRow(g.table.rowCount()-1);form(g,('CARGO','500','Editado desde interfaz'),False)
assert c.result.total==10000 and list(c.groups.analysis.totals.values())==[10000]
passed.append('Asignar Fringes, cargos, Credits y Groups; editar Global recalcula 10000+1000+500-1500=10000')

selected=[(i.row(),i.column()) for i in w.budget.selectedIndexes()]
current=(w.budget.currentRow(),w.budget.currentColumn())
opened=[]
def visit(d):
    opened.append(type(d).__name__);d.show();app.processEvents();d.reject();return 0
with patch.object(QDialog,'exec',visit):
    menu.actions()[0].trigger()
    for action in menu.actions()[1:]:
        for sub in action.menu().actions():
            if 'Exportar' not in sub.text():sub.trigger()
assert len(opened)==13,len(opened)
assert selected==[(i.row(),i.column()) for i in w.budget.selectedIndexes()]
assert current==(w.budget.currentRow(),w.budget.currentColumn())
assert w.modules.currentWidget()==w.budget_page
passed.append('Todas las entradas abren su dialogo; cerrar conserva seleccion y modulo')

summary=GroupSummaryDialog(c.groups,w);summary.table.selectRow(0);summary.show_members()
assert c.groups.selected_filter and not w.budget.isRowHidden(0)
QTest.mouseClick(w.show_all_groups_button,Qt.MouseButton.LeftButton)
assert not c.groups.selected_filter
passed.append('Resumen Groups permite ir a sus partidas y volver a mostrar todo')

for width,height in [(1600,900),(1280,720),(1024,700)]:
    w.resize(width,height);app.processEvents()
    button=w.budget_tools_button
    assert w.rect().contains(button.mapTo(w,QPoint(0,0)))
    assert w.rect().contains(button.mapTo(w,button.rect().bottomRight()))
    w.grab().save(str(out/f'budget-{width}.png'))
    for d in dialogs:
        d.resize(720,400);d.show();app.processEvents()
        assert d.rect().contains(d.search.geometry())
        assert d.table.width()>250
        d.hide()
passed.append('Redimensionado: herramientas accesibles, tablas desplazables y busqueda visible')

project=out/'interface-project.eguion';w.path=project;assert w.save();saved=w.project_data();close(w)
w=window();c=w.budget_controller;assert w.open_path(project);drain(lambda:getattr(w,'_import_job',None) is not None)
assert c.result.total==10000
for key in ('budget_globals','budget_fringes','budget_charges','budget_credits','budget_groups'):
    assert w.project_data()[key]==saved[key]
assert w.budget_data()[0]['charge_ids']==saved['budget'][0]['charge_ids']
close(w)
passed.append('Guardar, cerrar y reabrir conserva catalogos, asignaciones y total calculado desde la interfaz')
(out/'interface-results.json').write_text(json.dumps({'passed':passed},indent=2),encoding='utf-8')
print('PASS:',len(passed),'escenarios de interfaz Etapa 7')
