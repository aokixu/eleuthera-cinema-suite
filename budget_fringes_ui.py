"""Administración y asignación de Fringes; validación delegada al controlador."""
from ui_i18n import ui_text, ui_join
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)
from budget_values import BudgetError
from budget_controller import FRINGE_ROLE


class FringesDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle('Fringes'); self.resize(1120, 440)
        layout = QVBoxLayout(self)
        hint = QLabel(ui_text('Porcentajes aditivos sobre la base de cada partida. Tope en moneda de la partida; vacío = sin tope.'))
        hint.setWordWrap(True); layout.addWidget(hint)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels((ui_text('Nombre'), ui_text('Porcentaje / fórmula'), ui_text('Resultado %'), ui_text('Tope'), ui_text('Descripción'), ui_text('Estado')))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setMaximumSectionSize(360)
        for column in (0, 1, 2, 3, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        row = QHBoxLayout(); self.buttons = []
        for label, callback in [(ui_text('Agregar'), lambda: self.edit(True)), (ui_text('Editar'), lambda: self.edit(False)),
                                (ui_text('Eliminar'), self.remove), ('Activar / desactivar', self.toggle)]:
            button = QPushButton(label); button.clicked.connect(callback); row.addWidget(button); self.buttons.append(button)
        layout.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject); layout.addWidget(close)
        controller.finished.connect(self.refresh); self.refresh()
        from budget_tools_ui import searchable_table
        searchable_table(self, self.table)

    def selected(self):
        index = self.table.currentRow()
        return self.controller.fringes.items()[index] if index >= 0 else None

    def refresh(self):
        selected = self.table.currentRow(); catalog = self.controller.fringes
        self.table.setRowCount(len(catalog.items()))
        for index, item in enumerate(catalog.items()):
            percentage, cap, active = catalog.resolved[item.id]
            values = (item.name, item.percentage, str(percentage),
                      'Sin tope' if cap is None else item.cap + ' = ' + str(cap), item.description,
                      ui_text('Activo') if active else ui_text('Inactivo'))
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value); cell.setToolTip(value); self.table.setItem(index, column, cell)
        if self.table.rowCount(): self.table.selectRow(max(0, min(selected, self.table.rowCount()-1)))
        for button in self.buttons: button.setEnabled(not self.controller.busy)

    def edit(self, add):
        item = None if add else self.selected()
        if not add and item is None: return
        form = QDialog(self); form.setWindowTitle(ui_text('Agregar Fringe') if add else ui_text('Editar Fringe'))
        layout = QFormLayout(form)
        name = QLineEdit(item.name if item else '')
        percentage = QLineEdit(item.percentage if item else '')
        cap = QLineEdit(item.cap or '' if item else '')
        description = QLineEdit(item.description if item else '')
        active = QCheckBox(ui_text('Activo')); active.setChecked(item.active if item else True)
        name.setMaxLength(64); percentage.setMaxLength(256); cap.setMaxLength(256); description.setMaxLength(1000)
        percentage.setPlaceholderText('12.5 o PORCENTAJE_CARGAS')
        cap.setPlaceholderText('Sin tope; o 5000 / TOPE_SEGURO')
        for label, widget in [(ui_text('Nombre'), name), (ui_text('Porcentaje / fórmula'), percentage), ('Tope / fórmula', cap),
                               (ui_text('Descripción'), description), (ui_text('Estado'), active)]: layout.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons); buttons.rejected.connect(form.reject)
        def save():
            try:
                self.controller.mutate_fringe('add' if add else 'edit', item.id if item else None,
                    name=name.text(), percentage=percentage.text(), cap=cap.text().strip() or None,
                    description=description.text(), active=active.isChecked())
            except BudgetError as error:
                QMessageBox.warning(form, ui_text('Fringe inválido'), str(error)); return
            form.accept()
        buttons.accepted.connect(save)
        if form.exec(): self.refresh()

    def remove(self):
        item = self.selected()
        if item is None: return
        try: self.controller.mutate_fringe('remove', item.id)
        except BudgetError as error: QMessageBox.warning(self, ui_text('Fringe en uso'), str(error))
        self.refresh()

    def toggle(self):
        item = self.selected()
        if item is None: return
        try:
            self.controller.mutate_fringe('edit', item.id, name=item.name, percentage=item.percentage,
                cap=item.cap, description=item.description, active=not item.active)
        except BudgetError as error: QMessageBox.warning(self, ui_text('Fringe inválido'), str(error))
        self.refresh()


class AssignmentDialog(QDialog):
    def __init__(self, controller, index, parent=None):
        super().__init__(parent)
        self.controller, self.index = controller, index
        controller._ready()
        row = controller.rows[index]
        if row['level'] == ui_text('Cuenta'): raise BudgetError('Selecciona una partida, no una Cuenta.')
        self.setWindowTitle(ui_text('Asignar Fringes')); self.resize(560, 400)
        layout = QVBoxLayout(self)
        hint = QLabel(row.get('concept', '') + '\nSe suman al Fringe % legado de la partida. Desmarca todos para quitar las asignaciones.')
        hint.setWordWrap(True); layout.addWidget(hint)
        self.listing = QListWidget(); layout.addWidget(self.listing)
        assigned = row.get('fringe_ids', [])
        for fringe in controller.fringes.items():
            pct, cap, active = controller.fringes.resolved[fringe.id]
            label = f'{fringe.name} — {pct} %' + (f' | Tope {cap}' if cap is not None else '') + ('' if active else ' (inactivo)')
            item = QListWidgetItem(label); item.setData(Qt.ItemDataRole.UserRole, fringe.id)
            item.setCheckState(Qt.CheckState.Checked if fringe.id in assigned else Qt.CheckState.Unchecked)
            self.listing.addItem(item)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def save(self):
        ids = [self.listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.listing.count())
               if self.listing.item(i).checkState() == Qt.CheckState.Checked]
        try: self.controller.assign_fringes([self.index], ids)
        except BudgetError as error:
            QMessageBox.warning(self, ui_text('Asignación inválida'), str(error)); return
        self.accept()


def open_fringes(window):
    dialog = FringesDialog(window.budget_controller, window)
    dialog.exec(); dialog.deleteLater()


def open_assignment(window):
    index = window.budget.currentRow()
    if index < 0:
        QMessageBox.information(window, ui_text('Asignar Fringes'), ui_text('Selecciona una partida.')); return
    try: dialog = AssignmentDialog(window.budget_controller, index, window)
    except BudgetError as error:
        QMessageBox.warning(window, ui_text('Asignar Fringes'), str(error)); return
    dialog.exec(); dialog.deleteLater()
