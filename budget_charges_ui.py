"""Administración, asignación e inspección de cargos; dominio fuera de widgets."""
from ui_i18n import ui_text, ui_join
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox,QDialog,QDialogButtonBox,QFormLayout,QHBoxLayout,
    QLabel,QLineEdit,QListWidget,QListWidgetItem,QMenu,QMessageBox,QPushButton,QTableWidgetItem,QVBoxLayout)
from budget_groups_ui import table_widget
from budget_values import BudgetError


def warn(parent,error): QMessageBox.warning(parent,'Charges',str(error))


class ChargesDialog(QDialog):
    def __init__(self,controller,parent=None):
        super().__init__(parent);self.controller=controller
        self.setWindowTitle(ui_text('Cargos contractuales'));self.resize(1040,440)
        layout=QVBoxLayout(self)
        hint=QLabel('Cargos adicionales por partida, después de Fringes y antes de Credits. Importes en moneda de la partida; admiten Globals.')
        hint.setWordWrap(True);layout.addWidget(hint)
        self.table=table_widget((ui_text('Nombre'),'Importe / fórmula',ui_text('Resultado'),ui_text('Descripción'),ui_text('Estado')));layout.addWidget(self.table)
        row=QHBoxLayout()
        for label,callback in [(ui_text('Agregar'),lambda:self.edit(True)),(ui_text('Editar'),lambda:self.edit(False)),
                               (ui_text('Eliminar'),self.remove),('Activar / desactivar',self.toggle)]:
            button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText(ui_text('Cerrar'));close.rejected.connect(self.reject);layout.addWidget(close)
        controller.finished.connect(self.refresh);self.refresh()
        from budget_tools_ui import searchable_table
        searchable_table(self, self.table)

    def selected(self):
        index=self.table.currentRow()
        return self.controller.charges.items()[index] if index>=0 else None

    def refresh(self):
        selected=self.table.currentRow();items=self.controller.charges.items()
        self.table.setRowCount(len(items))
        for row,item in enumerate(items):
            for col,value in enumerate((item.name,item.amount,str(self.controller.charges.resolved[item.id][0]),item.description,ui_text('Activo') if item.active else ui_text('Inactivo'))):
                cell=QTableWidgetItem(value);cell.setToolTip(value);self.table.setItem(row,col,cell)
        if items:self.table.selectRow(max(0,min(selected,len(items)-1)))

    def edit(self,add):
        item=None if add else self.selected()
        if not add and item is None:return
        form=QDialog(self);form.setWindowTitle(ui_text('Agregar Charge') if add else ui_text('Editar Charge'));layout=QFormLayout(form)
        name=QLineEdit(item.name if item else '');name.setMaxLength(64)
        amount=QLineEdit(item.amount if item else '');amount.setMaxLength(256);amount.setPlaceholderText('1500 o APORTE_PROVEEDOR')
        description=QLineEdit(item.description if item else '');description.setMaxLength(1000)
        active=QCheckBox(ui_text('Activo'));active.setChecked(item.active if item else True)
        for label,widget in [(ui_text('Nombre'),name),('Importe / fórmula',amount),(ui_text('Descripción'),description),(ui_text('Estado'),active)]:layout.addRow(label,widget)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons);buttons.rejected.connect(form.reject)
        def save():
            try:self.controller.mutate_charge('add' if add else 'edit',item.id if item else None,
                          name=name.text(),amount=amount.text(),description=description.text(),active=active.isChecked())
            except BudgetError as error:warn(form,error);return
            form.accept()
        buttons.accepted.connect(save)
        if form.exec():self.refresh()

    def remove(self):
        item=self.selected()
        if item is None:return
        try:self.controller.mutate_charge('remove',item.id)
        except BudgetError as error:warn(self,error)
        self.refresh()

    def toggle(self):
        item=self.selected()
        if item is None:return
        try:self.controller.mutate_charge('edit',item.id,name=item.name,amount=item.amount,description=item.description,active=not item.active)
        except BudgetError as error:warn(self,error)
        self.refresh()


class ChargeAssignmentDialog(QDialog):
    def __init__(self,controller,index,parent=None):
        super().__init__(parent);controller._ready();self.controller,self.index=controller,index
        if not 0<=index<len(controller.rows) or controller.rows[index]['level']==ui_text('Cuenta'):raise BudgetError('Selecciona una partida, no una Cuenta.')
        row=controller.rows[index];self.setWindowTitle(ui_text('Asignar Charges'));self.resize(620,420)
        layout=QVBoxLayout(self)
        hint=QLabel(row['concept']+'\nMarca los cargos en '+row['currency']+'. Desmarca todas para retirar los Charges.');hint.setWordWrap(True);layout.addWidget(hint)
        self.listing=QListWidget();layout.addWidget(self.listing)
        for item in controller.charges.items():
            amount,active=controller.charges.resolved[item.id]
            cell=QListWidgetItem(f'{item.name}: {amount} '+row['currency']+('' if active else ' (inactivo)'))
            cell.setData(Qt.ItemDataRole.UserRole,item.id);cell.setToolTip(item.description)
            cell.setCheckState(Qt.CheckState.Checked if item.id in row.get('charge_ids',[]) else Qt.CheckState.Unchecked)
            self.listing.addItem(cell)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def save(self):
        ids=[self.listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.listing.count())
             if self.listing.item(i).checkState()==Qt.CheckState.Checked]
        try:self.controller.assign_charges([self.index],ids)
        except BudgetError as error:warn(self,error);return
        self.accept()


class ChargeDetailDialog(QDialog):
    def __init__(self,controller,index,parent=None):
        super().__init__(parent);controller._ready();self.controller,self.index=controller,index
        if not 0<=index<len(controller.rows) or controller.rows[index]['level']==ui_text('Cuenta'):raise BudgetError('Selecciona una partida, no una Cuenta.')
        self.setWindowTitle(ui_text('Charges de la partida'));self.resize(1000,400)
        layout=QVBoxLayout(self);self.hint=QLabel();self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.table=table_widget(('Charge','Importe local','Cargo',ui_text('Estado')));layout.addWidget(self.table)
        controller.started.connect(self.refresh);controller.finished.connect(self.refresh);self.refresh()

    def refresh(self):
        c,index=self.controller,self.index
        if c.busy or c.result is None or index>=len(c.rows):
            self.hint.setText('Recalculando; detalle no disponible.');self.table.setRowCount(0);return
        if index in c.result.errors:
            self.hint.setText(c.result.errors[index]);self.table.setRowCount(0);return
        row,result=c.rows[index],c.result;currency=c.window.base_currency.currentText()
        self.hint.setText(f"{row['concept']} · Antes de Charges: {result.before_charges[index]:.2f} {currency} · Charges: {result.charge_totals[index]:.2f} {currency} · Credits: {result.credit_totals[index]:.2f} {currency} · Total final: {result.totals[index]:.2f} {currency}")
        details=result.charge_details[index];self.table.setRowCount(len(details))
        for line,(identifier,local,converted) in enumerate(details):
            item=c.charges.get(identifier)
            for col,value in enumerate((item.name,f'{local:.2f} '+row['currency'],f'{converted:.2f} '+currency,ui_text('Activo') if item.active else ui_text('Inactivo'))):
                cell=QTableWidgetItem(value);cell.setToolTip(value);self.table.setItem(line,col,cell)


def open_charge_dialog(window,kind):
    c=window.budget_controller
    try:
        window.commit_active_cell()
        if kind=='admin':dialog=ChargesDialog(c,window)
        elif kind=='assign':dialog=ChargeAssignmentDialog(c,window.budget.currentRow(),window)
        else:dialog=ChargeDetailDialog(c,window.budget.currentRow(),window)
        dialog.exec();dialog.deleteLater()
    except BudgetError as error:warn(window,error)


def install_charges_controls(window,actions):
    button=QPushButton(ui_text('Cargos contractuales'));menu=QMenu(button)
    for label,kind in [('Administrar','admin'),('Asignar / desasignar','assign'),('Consultar cargos de partida','detail')]:
        menu.addAction(label,lambda checked=False,k=kind:open_charge_dialog(window,k))
    button.setMenu(menu);window.charges_button=button;actions.insertWidget(5,button)
