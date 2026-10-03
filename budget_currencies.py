"""Budget currency catalog, manual rates and conservative legacy migration."""
from ui_i18n import ui_text, ui_join
import copy
import math
import re
from eleuthera_spreadsheet import EleutheraCellDelegate
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QStyledItemDelegate, QTableWidget, QTableWidgetItem, QVBoxLayout)

SYMBOLS = {'BOB': 'Bs', 'USD': '$', 'EUR': '€', 'GBP': '£'}
ROLE = Qt.ItemDataRole.UserRole + 81


def number(value):
    try:
        result = float(str(value).strip().replace(',', '.'))
        return result if math.isfinite(result) and result > 0 else None
    except (TypeError, ValueError):
        return None


def validate_catalog(catalog):
    if not isinstance(catalog, dict) or catalog.get('version') != 1:
        raise ValueError('Catalogo de monedas incompatible.')
    rows = catalog.get('currencies')
    if not isinstance(rows, list):
        raise ValueError('Lista de monedas invalida.')
    codes = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('code'), str) or not re.fullmatch(r'[A-Z]{3}', row.get('code', '')):
            raise ValueError('Codigo de moneda invalido.')
        if row['code'] in codes or not isinstance(row.get('symbol'), str):
            raise ValueError('Moneda duplicada o simbolo invalido.')
        codes.add(row['code'])
        if row.get('rate') is not None and (not isinstance(row['rate'], (int, float)) or isinstance(row['rate'], bool) or number(row['rate']) is None):
            raise ValueError('Tasa de moneda invalida.')
    base = next((r for r in rows if r['code'] == catalog.get('base')), None)
    if not base or base['rate'] != 1:
        raise ValueError('La moneda base debe existir con tasa 1.00000.')


def migrate(data):
    data = copy.deepcopy(data)
    if 'budget_currencies' in data:
        validate_catalog(data['budget_currencies'])
        return data
    info = data.get('project_info', {})
    base = str(info.get('currency') or data.get('budget_settings', {}).get('base_currency') or 'USD').strip().upper()
    if not re.fullmatch(r'[A-Z]{3}', base):
        raise ValueError('Moneda base antigua invalida: ' + base)
    catalog = {base: {'code': base, 'symbol': SYMBOLS.get(base, base), 'rate': 1.0}}
    for code, raw in info.get('rates', {}).items():
        code = str(code).strip().upper()
        if re.fullmatch(r'[A-Z]{3}', code) and code != base:
            catalog[code] = {'code': code, 'symbol': SYMBOLS.get(code, code), 'rate': number(raw)}
    for row in data.get('budget', []):
        code = str(row.get('currency') or base).strip().upper()
        if not re.fullmatch(r'[A-Z]{3}', code):
            raise ValueError('Moneda antigua de partida invalida: ' + code)
        rate = number(row.get('exchange'))
        if code not in catalog:
            catalog[code] = {'code': code, 'symbol': SYMBOLS.get(code, code), 'rate': rate}
        if row.get('level') != ui_text('Cuenta') and rate != catalog[code]['rate']:
            # Preserve old per-line values (including pending ones), not silently reprice.
            row['legacy_exchange'] = str(row.get('exchange', ''))
    data['budget_currencies'] = {'version': 1, 'base': base, 'currencies': list(catalog.values())}
    data['budget_currency_legacy'] = {'rates': copy.deepcopy(info.get('rates', {})),
                                    'rates_text': data.get('metadata_draft', {}).get('rates_text', '')}
    return data


def synchronize(window, start=0, stop=None):
    catalog = getattr(window, 'budget_currencies', None)
    if not catalog:
        return
    by_code = {r['code']: r for r in catalog['currencies']}
    previous = window.budget.blockSignals(True)
    pending = 0 if start == 0 else getattr(window, '_pending_currency_rates', 0)
    try:
        for row in range(start, window.budget.rowCount() if stop is None else stop):
            code_item, rate_item = window.budget.item(row, 9), window.budget.item(row, 10)
            if code_item is None or rate_item is None:
                continue
            code = code_item.text().strip().upper() or catalog['base']
            override = rate_item.data(ROLE)
            rate = by_code.get(code, {}).get('rate')
            value = override if override is not None else '' if rate is None else f'{rate:.10g}'
            rate_item.setText(str(value))
            rate_item.setFlags(rate_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            rate_item.setToolTip('Tasa historica conservada. Edita esta moneda para unificarla.' if override is not None else ui_text('Administrada en Monedas del presupuesto.'))
            if window.budget.item(row, 0).text() != ui_text('Cuenta') and number(value) is None:
                pending += 1
    finally:
        window.budget.blockSignals(previous)
    window._pending_currency_rates = pending


def mirror(window):
    catalog = window.budget_currencies
    window.base_currency.blockSignals(True)
    window.base_currency.setCurrentText(catalog['base'])
    window.base_currency.blockSignals(False)
    window._last_base_currency = catalog['base']
    window.project_info['currency'] = catalog['base']
    window.project_info['rates'] = {r['code']: r['rate'] for r in catalog['currencies'] if r['rate'] is not None}
    if hasattr(window, 'rates'):
        window.rates.setText('; '.join(f'{k}={v}' for k, v in window.project_info['rates'].items()))
        window.info_fields['currency'].setText(catalog['base'])
    window.refresh_currency_label()


class CurrencyDelegate(EleutheraCellDelegate):
    # Conservar la geometria del combo; heredar solo el pintado de la hoja.
    updateEditorGeometry = QStyledItemDelegate.updateEditorGeometry

    def __init__(self, window):
        super().__init__(window.budget)
        self.window = window

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem(ui_text('Moneda base (automatico)'), '')
        for row in self.window.budget_currencies['currencies']:
            editor.addItem(f"{row['code']}  {row['symbol']}", row['code'])
        return editor

    def setEditorData(self, editor, index):
        editor.setCurrentIndex(max(0, editor.findData(str(index.data() or '').strip().upper())))

    def setModelData(self, editor, model, index):
        self.window.budget.item(index.row(), 10).setData(ROLE, None)
        model.setData(index, editor.currentData(), Qt.ItemDataRole.EditRole)
        self.window.update_budget_total()


def setup(window):
    window.budget_currencies = migrate({'project_info': {'currency': window.base_currency.currentText()}})['budget_currencies']
    window.budget_currency_legacy = {}
    window.budget.setItemDelegateForColumn(9, CurrencyDelegate(window))
    window.currency_change.setText(ui_text('Monedas...'))
    window.currency_change.setToolTip(ui_text('Agregar, editar o eliminar monedas del presupuesto.'))
    # Keep old metadata fields readable, but one authoritative currency editor.
    window.info_fields['currency'].setReadOnly(True)
    window.rates.setReadOnly(True)
    window.rates.setToolTip('Las monedas se administran desde Presupuesto > Monedas.')


def edit_currencies(window):
    window.commit_active_cell()
    original = copy.deepcopy(window.budget_currencies)
    catalog = copy.deepcopy(original)
    dialog = QDialog(window)
    dialog.setWindowTitle(ui_text('Monedas del presupuesto'))
    dialog.resize(530, 390)
    layout = QVBoxLayout(dialog)
    base = QComboBox()
    bar = QHBoxLayout()
    bar.addWidget(QLabel(ui_text('Moneda base:')))
    bar.addWidget(base, 1)
    layout.addLayout(bar)
    layout.addWidget(QLabel(ui_text('Monedas del presupuesto')))
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels([ui_text('Codigo'), ui_text('Simbolo'), ui_text('Tasa')])
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    layout.addWidget(table)
    if any(window.budget.item(i, 10).data(ROLE) is not None for i in range(window.budget.rowCount())):
        notice = QLabel('Este proyecto conserva tasas antiguas por partida. Al editar una moneda puedes unificarlas con su nueva tasa.'); notice.setWordWrap(True); layout.addWidget(notice)
    changed = set()
    def refresh(selected=0):
        base.blockSignals(True)
        base.clear()
        base.addItems([r['code'] for r in catalog['currencies']])
        base.setCurrentText(catalog['base'])
        base.blockSignals(False)
        table.setRowCount(len(catalog['currencies']))
        for i, row in enumerate(catalog['currencies']):
            for col, value in enumerate((row['code'], row['symbol'], ui_text('Pendiente') if row['rate'] is None else f"{row['rate']:.5f}")):
                table.setItem(i, col, QTableWidgetItem(value))
        table.selectRow(min(selected, table.rowCount() - 1))
    def edit(add=False):
        index = table.currentRow()
        if not add and index < 0:
            return
        row = {'code': '', 'symbol': '', 'rate': None} if add else catalog['currencies'][index]
        form = QDialog(dialog)
        form.setWindowTitle(ui_text('Agregar moneda') if add else ui_text('Editar moneda'))
        fields = QFormLayout(form)
        code = QLineEdit(row['code'])
        code.setReadOnly(not add)
        symbol = QLineEdit(row['symbol'])
        rate = QDoubleSpinBox()
        rate.setDecimals(5)
        rate.setRange(0.00001, 1e10)
        rate.setValue(row['rate'] or 1)
        rate.setEnabled(row['code'] != catalog['base'])
        fields.addRow(ui_text('Codigo'), code)
        fields.addRow(ui_text('Simbolo'), symbol)
        fields.addRow(ui_text('Tasa'), rate)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        fields.addRow(buttons)
        def save():
            value = code.text().strip().upper()
            if not re.fullmatch(r'[A-Z]{3}', value) or (add and any(r['code'] == value for r in catalog['currencies'])):
                QMessageBox.warning(form, ui_text('Moneda invalida'), ui_text('Usa un codigo unico de tres letras.'))
                return
            new = {'code': value, 'symbol': symbol.text().strip(), 'rate': 1.0 if value == catalog['base'] else rate.value()}
            if add:
                catalog['currencies'].append(new)
            else:
                catalog['currencies'][index] = new
            changed.add(value)
            form.accept()
        buttons.accepted.connect(save)
        buttons.rejected.connect(form.reject)
        if form.exec(): refresh(index if not add else len(catalog['currencies']) - 1)
    def remove():
        index = table.currentRow()
        if index < 0: return
        code = catalog['currencies'][index]['code']
        used = {r['currency'].strip().upper() for r in window.budget_data()}
        if code == catalog['base'] or code in used:
            QMessageBox.warning(dialog, ui_text('Moneda en uso'), ui_text('No puedes eliminar la moneda base ni una moneda utilizada en partidas.'))
            return
        catalog['currencies'].pop(index)
        refresh()
    def change_base(code):
        selected = next(r for r in catalog['currencies'] if r['code'] == code)
        if selected['rate'] is None:
            QMessageBox.warning(dialog, ui_text('Tasa pendiente'), ui_text('Define la tasa de esa moneda antes de usarla como base.'))
            refresh()
            return
        factor = selected['rate']
        for row in catalog['currencies']:
            if row['rate'] is not None:
                row['rate'] = row['rate'] / factor
        catalog['base'] = code
        selected['rate'] = 1.0
        changed.update(r['code'] for r in catalog['currencies'])
        refresh()
    base.currentTextChanged.connect(change_base)
    controls = QHBoxLayout()
    for label, callback in [(ui_text('Agregar moneda'), lambda: edit(True)), (ui_text('Editar'), lambda: edit(False)), (ui_text('Eliminar'), remove)]:
        button = QPushButton(label)
        button.clicked.connect(callback)
        controls.addWidget(button)
    layout.addLayout(controls)
    footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(footer)
    footer.rejected.connect(dialog.reject)
    def apply():
        validate_catalog(catalog)
        affected = [i for i in range(window.budget.rowCount()) if window.budget.item(i, 10).data(ROLE) is not None
                    and (window.budget.item(i, 9).text().strip().upper() or original['base']) in changed]
        if affected and QMessageBox.question(dialog, ui_text('Tasas historicas'),
                f'{len(affected)} partidas conservan tasas antiguas distintas. Aplicar las tasas de la lista a esas partidas?') != QMessageBox.StandardButton.Yes:
            return
        window.budget_currencies = copy.deepcopy(catalog)
        for i in affected: window.budget.item(i, 10).setData(ROLE, None)
        mirror(window)
        window.update_budget_total()
        window.dirty = True
        dialog.accept()
    footer.accepted.connect(apply)
    refresh()
    dialog.exec()
