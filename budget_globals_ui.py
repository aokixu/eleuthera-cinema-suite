"""Widgets de Globals: fuente, resultado y descripción; dominio sin widgets."""
from ui_i18n import ui_text, ui_join
from PySide6.QtGui import QColor
from plus_theme import TEXT_ACCENT
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout)
from budget_model import BudgetError


class GlobalsDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle('Globals')
        self.resize(850, 440)
        layout = QVBoxLayout(self)
        hint = QLabel(ui_text('Variables reutilizables del presupuesto. ƒ indica una fórmula; su resultado se calcula automáticamente.'))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels((ui_text('Nombre'), ui_text('Valor o fórmula'), ui_text('Resultado'), ui_text('Descripción')))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 260)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        self.buttons = []
        for label, callback in [(ui_text('Agregar'), lambda: self.edit(True)), (ui_text('Editar'), lambda: self.edit(False)), (ui_text('Eliminar'), self.remove)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
            self.buttons.append(button)
        layout.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText(ui_text('Cerrar'))
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        controller.finished.connect(self.refresh)
        self.refresh()
        from budget_tools_ui import searchable_table
        searchable_table(self, self.table)

    def refresh(self):
        selected = self.table.currentRow()
        items = self.controller.catalog.items()
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            source = 'ƒ  ' + item.formula if item.formula is not None else item.source
            for column, value in enumerate((item.name, source, str(item.value), item.description)):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.table.setItem(row, column, cell)
            if item.formula is not None:
                self.table.item(row, 1).setForeground(QColor(TEXT_ACCENT))
                self.table.item(row, 1).setToolTip('Global calculado: ' + item.formula)
            else:
                self.table.item(row, 1).setToolTip('Global constante: ' + item.source)
        if items: self.table.selectRow(min(max(selected, 0), len(items) - 1))
        for button in self.buttons: button.setEnabled(not self.controller.busy)

    def edit(self, add):
        selected = self.table.currentRow()
        if not add and selected < 0: return
        item = None if add else self.controller.catalog.items()[selected]
        form = QDialog(self)
        form.setWindowTitle(ui_text('Agregar Global') if add else ui_text('Editar Global'))
        layout = QFormLayout(form)
        name = QLineEdit('' if add else item.name)
        value = QLineEdit('' if add else item.source)
        description = QLineEdit('' if add else item.description)
        name.setMaxLength(64); value.setMaxLength(256); description.setMaxLength(1000)
        value.setPlaceholderText('12 o DIAS_RODAJE + 5')
        for label, field in [(ui_text('Nombre'), name), (ui_text('Valor o fórmula'), value), (ui_text('Descripción'), description)]: layout.addRow(label, field)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons)
        buttons.rejected.connect(form.reject)
        def save():
            args = (name.text(), value.text(), description.text())
            try:
                self.controller.mutate('add' if add else 'edit', *args if add else (item.name, *args))
            except BudgetError as error:
                QMessageBox.warning(form, ui_text('Global inválido'), str(error))
                return
            form.accept()
        buttons.accepted.connect(save)
        if form.exec(): self.refresh()

    def remove(self):
        row = self.table.currentRow()
        if row < 0: return
        try:
            self.controller.mutate('remove', self.controller.catalog.items()[row].name)
        except BudgetError as error:
            QMessageBox.warning(self, ui_text('Global en uso'), str(error))
        self.refresh()


def open_globals(window):
    dialog = GlobalsDialog(window.budget_controller, window)
    dialog.exec()
    dialog.deleteLater()
