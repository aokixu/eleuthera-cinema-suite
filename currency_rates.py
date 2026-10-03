"""Structured rate editor and backward-compatible draft reader."""
from ui_i18n import ui_text, ui_join
import math
import re
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView


def legacy_rows(value):
    if isinstance(value, dict):
        return [{'currency': str(k), 'rate': str(v)} for k, v in value.items()]
    rows = []
    for part in str(value or '').split(';'):
        if not part.strip():
            continue
        code, separator, rate = part.partition('=')
        # Incomplete old drafts remain visible for correction, never guessed.
        if not separator and re.fullmatch(r'[0-9.,]+', code.strip()):
            rows.append({'currency': '', 'rate': code.strip()})
        else:
            rows.append({'currency': code.strip(), 'rate': rate.strip()})
    return rows


def validate_rows(rows, base=None):
    rates = {}
    for index, row in enumerate(rows, 1):
        code, raw = row['currency'].strip().upper(), row['rate'].strip()
        if not code and not raw:
            continue
        if not re.fullmatch(r'[A-Z]{3}', code):
            raise ValueError(f'Fila {index}: indica la moneda de origen (por ejemplo USD).')
        if not raw:
            raise ValueError(f'Fila {index} ({code}): falta el valor de la tasa.')
        try:
            rate = float(raw.replace(',', '.'))
        except ValueError:
            raise ValueError(f'Fila {index} ({code}): la tasa debe ser un numero, por ejemplo 6.96.') from None
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError(f'Fila {index} ({code}): la tasa debe ser positiva y finita.')
        if code in rates:
            raise ValueError(f'La moneda {code} aparece mas de una vez.')
        if base and code == base and rate != 1:
            raise ValueError(f'La tasa de la moneda base {code} debe ser 1.')
        rates[code] = rate
    return rates


class RateEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([ui_text('Moneda de origen'), ui_text('Tasa en moneda base')])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(125)
        self.table.setMaximumHeight(220)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        add = QPushButton(ui_text('Agregar tasa'))
        add.clicked.connect(lambda: self.add_row('', ''))
        remove = QPushButton(ui_text('Quitar tasa'))
        remove.clicked.connect(self.remove_rows)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch()
        layout.addLayout(buttons)

    def add_row(self, code, rate):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(code)))
        self.table.setItem(row, 1, QTableWidgetItem(str(rate)))

    def remove_rows(self):
        for row in sorted({item.row() for item in self.table.selectedItems()}, reverse=True):
            self.table.removeRow(row)

    def rows(self):
        return [{'currency': self.table.item(i, 0).text(), 'rate': self.table.item(i, 1).text()}
                for i in range(self.table.rowCount())]

    def set_rows(self, rows):
        self.clear()
        for row in rows:
            self.add_row(row.get('currency', ''), row.get('rate', ''))

    def clear(self):
        self.table.setRowCount(0)

    def text(self):
        # Compatibility for older project readers; the new draft also stores rows.
        return '; '.join(f"{r['currency']}={r['rate']}" for r in self.rows())

    def setText(self, value):
        self.set_rows(legacy_rows(value))

    def mapping(self, base=None):
        return validate_rows(self.rows(), base)
