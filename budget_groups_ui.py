"""Widgets de Groups: administración, asignación, filtro y resumen Excel."""
from ui_i18n import ui_text, ui_join
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout)
from budget_values import BudgetError


def warn(parent, error): QMessageBox.warning(parent, 'Groups', str(error))


def table_widget(headers):
    table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return table


class GroupsDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle('Groups'); self.resize(760, 420)
        layout = QVBoxLayout(self)
        hint = QLabel(ui_text('Clasificaciones independientes. Desactivar conserva asignaciones y totales.')); hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = table_widget((ui_text('Nombre'), ui_text('Descripción'), ui_text('Estado'))); layout.addWidget(self.table)
        row = QHBoxLayout()
        for label, callback in [(ui_text('Agregar'),lambda:self.edit(True)),(ui_text('Editar'),lambda:self.edit(False)),
                                (ui_text('Eliminar'),self.remove),('Activar / desactivar',self.toggle)]:
            button = QPushButton(label); button.clicked.connect(callback); row.addWidget(button)
        layout.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(self.reject); layout.addWidget(close)
        controller.changed.connect(self.refresh); self.refresh()
        from budget_tools_ui import searchable_table
        searchable_table(self, self.table)

    def selected(self):
        index = self.table.currentRow()
        return self.controller.catalog.items()[index] if index >= 0 else None

    def refresh(self):
        selected = self.table.currentRow(); items = self.controller.catalog.items()
        self.table.setRowCount(len(items))
        for row,item in enumerate(items):
            for col,text in enumerate((item.name,item.description,ui_text('Activo') if item.active else ui_text('Inactivo'))):
                cell=QTableWidgetItem(text); cell.setToolTip(text); self.table.setItem(row,col,cell)
        if items: self.table.selectRow(max(0,min(selected,len(items)-1)))

    def edit(self, add):
        item = None if add else self.selected()
        if not add and item is None: return
        form=QDialog(self); form.setWindowTitle(ui_text('Agregar Group') if add else ui_text('Editar Group')); layout=QFormLayout(form)
        name=QLineEdit(item.name if item else ''); name.setMaxLength(64)
        description=QLineEdit(item.description if item else ''); description.setMaxLength(1000)
        active=QCheckBox(ui_text('Activo')); active.setChecked(item.active if item else True)
        for label,widget in [(ui_text('Nombre'),name),(ui_text('Descripción'),description),(ui_text('Estado'),active)]: layout.addRow(label,widget)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons);buttons.rejected.connect(form.reject)
        def save():
            try: self.controller.mutate('add' if add else 'edit', item.id if item else None,
                        name=name.text(),description=description.text(),active=active.isChecked())
            except BudgetError as error: warn(form,error);return
            form.accept()
        buttons.accepted.connect(save); form.exec()

    def remove(self):
        item=self.selected()
        if item is None:return
        try:self.controller.mutate('remove',item.id)
        except BudgetError as error:warn(self,error)

    def toggle(self):
        item=self.selected()
        if item is None:return
        try:self.controller.mutate('edit',item.id,name=item.name,description=item.description,active=not item.active)
        except BudgetError as error:warn(self,error)


class GroupSelectionDialog(QDialog):
    def __init__(self, controller, index=None, parent=None):
        super().__init__(parent)
        controller.ready(); self.controller,self.index=controller,index
        if index is not None and (not 0 <= index < len(controller.budget.rows) or controller.budget.rows[index]['level']==ui_text('Cuenta')):
            raise BudgetError('Selecciona una partida, no una Cuenta.')
        selected=controller.selected_filter if index is None else controller.budget.rows[index].get('group_ids',[])
        self.setWindowTitle(ui_text('Filtrar por Groups') if index is None else ui_text('Asignar Groups')); self.resize(560,400)
        layout=QVBoxLayout(self)
        label=QLabel('Mostrar partidas de cualquiera de los Groups marcados. Ninguno = mostrar todo.' if index is None
                     else 'Marca uno o varios Groups. Desmarcar todos quita las asignaciones. Los inactivos conservan sus datos.')
        label.setWordWrap(True);layout.addWidget(label)
        self.listing=QListWidget();layout.addWidget(self.listing)
        for item in controller.catalog.items():
            cell=QListWidgetItem(item.name+('' if item.active else ' (inactivo)'))
            cell.setData(Qt.ItemDataRole.UserRole,item.id);cell.setToolTip(item.description)
            cell.setCheckState(Qt.CheckState.Checked if item.id in selected else Qt.CheckState.Unchecked)
            self.listing.addItem(cell)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons);buttons.rejected.connect(self.reject);buttons.accepted.connect(self.save)

    def save(self):
        ids=[self.listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.listing.count())
             if self.listing.item(i).checkState()==Qt.CheckState.Checked]
        try:
            if self.index is None:self.controller.set_filter(ids)
            else:self.controller.assign([self.index],ids)
        except BudgetError as error:warn(self,error);return
        self.accept()


class GroupSummaryDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent); self.controller=controller
        self.setWindowTitle(ui_text('Totales por Groups'));self.resize(760,420)
        layout=QVBoxLayout(self);self.hint=QLabel();self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.table=table_widget(('Group','Nº de partidas','Total'));layout.addWidget(self.table)
        export=QPushButton(ui_text('Exportar Excel'));export.clicked.connect(lambda:export_groups(controller,self));layout.addWidget(export)
        members=QPushButton(ui_text('Ver partidas del Group seleccionado'));members.clicked.connect(self.show_members);layout.addWidget(members)
        self.table.cellDoubleClicked.connect(lambda *_: self.show_members())
        controller.changed.connect(self.refresh);self.refresh()

    def show_members(self):
        row = self.table.currentRow()
        if row < 0: return
        try:
            self.controller.set_filter([self.controller.catalog.items()[row].id])
        except BudgetError as error:
            warn(self, error); return
        self.accept()

    def refresh(self):
        c=self.controller; ready=not c.budget.busy and c.analysis is not None and c.budget.result is not None
        currency=c.budget.window.base_currency.currentText()
        self.hint.setText(('Recalculando o resultado no disponible. ' if not ready else '')+
                         'Totales independientes en '+currency+'. Una partida puede aparecer en varios Groups; no sumes los Groups como total del presupuesto.')
        self.table.setRowCount(len(c.catalog.items()))
        for row,item in enumerate(c.catalog.items()):
            values=(item.name+('' if item.active else ' (inactivo)'),
                    str(len(c.analysis.members[item.id])) if ready else '—',
                    ('ERROR' if c.budget.result.errors else f'{c.analysis.totals[item.id]:.2f}') if ready else ui_text('Pendiente'))
            for col,value in enumerate(values):self.table.setItem(row,col,QTableWidgetItem(value))


def export_groups(controller, parent=None):
    w=controller.budget.window
    try:
        w.commit_active_cell()
        rows=controller.summary_rows()
        filename,_=QFileDialog.getSaveFileName(parent or w,ui_text('Exportar resumen por Groups'),'','Excel (*.xlsx)')
        if not filename:return
        if not filename.lower().endswith('.xlsx'):filename+='.xlsx'
        from production_reports import write_excel
        currency=w.base_currency.currentText()
        info={**w.project_info,'currency':currency}
        write_excel(filename,info.get('title') or 'Resumen por Groups',info,
                    [('Groups',['Group','Nº de partidas','Total '+currency],rows)])
        w.statusBar().showMessage('Resumen de Groups exportado.')
    except (BudgetError,OSError,ValueError,ImportError) as error:warn(parent or w,error)


def open_dialog(window, kind):
    c=window.budget_controller.groups
    try:
        window.commit_active_cell()
        if kind=='admin':dialog=GroupsDialog(c,window)
        elif kind=='summary':dialog=GroupSummaryDialog(c,window)
        else:
            index=window.budget.currentRow() if kind=='assign' else None
            dialog=GroupSelectionDialog(c,index,window)
        dialog.exec();dialog.deleteLater()
    except BudgetError as error:warn(window,error)


def install_groups_controls(window, actions, layout):
    button=QPushButton('Groups');menu=QMenu(button)
    for label,kind in [('Administrar','admin'),('Asignar a partida','assign'),('Filtrar','filter'),(ui_text('Totales por Groups'),'summary')]:
        menu.addAction(label,lambda checked=False,k=kind:open_dialog(window,k))
    menu.addAction('Exportar resumen Excel',lambda:export_groups(window.budget_controller.groups,window))
    button.setMenu(menu);actions.insertWidget(3,button);window.groups_button=button
    row=QHBoxLayout();window.groups_filter_label=QLabel(ui_text('Groups: todo el presupuesto'));window.groups_filter_label.setWordWrap(True)
    row.addWidget(window.groups_filter_label,1)
    window.show_all_groups_button=QPushButton(ui_text('Mostrar todo'));window.show_all_groups_button.hide()
    def clear():
        try:window.budget_controller.groups.set_filter([])
        except BudgetError as error:warn(window,error)
    window.show_all_groups_button.clicked.connect(clear);row.addWidget(window.show_all_groups_button)
    layout.addLayout(row)
