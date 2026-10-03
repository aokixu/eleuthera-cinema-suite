from ui_i18n import ui_text, ui_join
import re
from collections import defaultdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QStyledItemDelegate, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


COLUMNS = (
    ui_text('Escena'), ui_text('Jornada'), 'I/E', 'D/N', ui_text('Localización'), ui_text('Diálogo'), ui_text('Ambiente'),
    'Foley', 'SFX', ui_text('Música'), 'Wild / Room tone', ui_text('Tratamiento'), ui_text('Notas'),
)

SFX_PATTERNS = (
    ('DISPARO', r'\b(?:disparo|dispara|balazo|detonaci[oó]n|pistola|rev[oó]lver)\b'),
    ('EXPLOSIÓN', r'\b(?:explosi[oó]n|explota|estalla)\b'),
    ('GOLPE', r'\b(?:golpe|golpea|impacto|choque|puñetazo|patada)\b'),
    ('PUERTA', r'\b(?:portazo|puerta\s+(?:se\s+)?(?:abre|cierra)|abre\s+la\s+puerta|cierra\s+la\s+puerta)\b'),
    ('TELÉFONO', r'\b(?:tel[eé]fono|celular)\s+(?:suena|vibra)|\b(?:timbre|ringtone)\b'),
    ('VEHÍCULO', r'\b(?:motor|auto|coche|veh[ií]culo|camioneta|moto|motocicleta)\b.*\b(?:arranca|frena|acelera|pasa|choca)\b'),
    ('VIDRIO', r'\b(?:vidrio|cristal)\b.*\b(?:rompe|quiebra|estalla)\b'),
    ('ALARMA', r'\b(?:alarma|sirena)\b'),
    ('TRUENO', r'\b(?:trueno|rel[aá]mpago)\b'),
)

FOLEY_PATTERNS = (
    ('Pasos', r'\b(?:camina|caminan|caminar|pasos|corre|corren|correr|sube|suben|baja|bajan|se acerca|se aleja)\b'),
    ('Ropa / movimiento corporal', r'\b(?:se pone|se quita|ajusta|abrocha|desabrocha|roza|sacude)\b.{0,45}\b(?:ropa|chaqueta|abrigo|vestido|pantal[oó]n|camisa|uniforme)\b|\b(?:ropa|chaqueta|abrigo|vestido|pantal[oó]n|camisa|uniforme)\b.{0,45}\b(?:pone|quita|ajusta|abrocha|desabrocha|roza|sacude)\b'),
    ('Llaves manipuladas', r'\b(?:toma|saca|guarda|mete|deja|gira|introduce|busca|agarra)\b.{0,45}\bllaves?\b|\bllaves?\b.{0,45}\b(?:toma|saca|guarda|mete|deja|gira|introduce|busca|agarra)\b'),
    ('Documentos / papel manipulados', r'\b(?:abre|cierra|revisa|extiende|dobla|rompe|toma|agarra|deja|guarda|saca|pasa|hojea)\b.{0,60}\b(?:papel(?:es)?|hojas?|carpeta|documentos?|fotograf[ií]as?|recibos?)\b|\b(?:papel(?:es)?|hojas?|carpeta|documentos?|fotograf[ií]as?|recibos?)\b.{0,60}\b(?:abre|cierra|revisa|extiende|dobla|rompe|toma|agarra|deja|guarda|saca|pasa|hojea)\b'),
    ('Objeto manipulado', r'\b(?:toma|agarra|deja|guarda|saca|apoya|arrastra|mueve|levanta|cae|golpea)\b.{0,50}\b(?:taza|vaso|botella|plato|cuchillo|arma|mochila|bolso|silla|mesa)\b|\b(?:taza|vaso|botella|plato|cuchillo|arma|mochila|bolso|silla|mesa)\b.{0,50}\b(?:toma|agarra|deja|guarda|saca|apoya|arrastra|mueve|levanta|cae|golpea)\b'),
    ('Puerta / manilla', r'\b(?:abre|cierra|empuja|tira de|gira)\b.{0,35}\b(?:puerta|port[oó]n|manilla|picaporte)\b|\b(?:puerta|port[oó]n|manilla|picaporte)\b.{0,35}\b(?:abre|cierra|empuja|gira)\b'),
)

MUSIC_PATTERN = re.compile(
    r'\b(?:m[uú]sica|canci[oó]n|radio|parlante|altavoz|banda|orquesta|canta|cantando|melod[ií]a|aud[ií]fonos)\b',
    re.I,
)


def _cell(value='', editable=True):
    item = QTableWidgetItem(str(value or ''))
    if not editable:
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _scene_fields(heading):
    heading = re.sub(r"^\d+[A-Z]?[.\-:)]?\s+(?=(?:INT|EXT|I/E))", "", (heading or '').strip(), flags=re.I)
    text = heading.upper().strip()
    interior = 'EXT' if text.startswith(('EXT.', 'EXT ', 'I/E')) else 'INT'
    if text.startswith(('I/E', 'INT/EXT', 'INT./EXT.')):
        interior = 'I/E'
    period = 'NOCHE' if any(word in text for word in ('NOCHE', 'ANOCHECER', 'MADRUGADA')) else 'DÍA'
    location = re.sub(r'^(INT\.?\s*/\s*EXT\.?|INT\.?/EXT\.?|I/E\.?|INT\.?|EXT\.?)\s*', '', heading, flags=re.I)
    location = re.split(r'\s+[-–—]\s+(?:D[IÍ]A|NOCHE|TARDE|AMANECER|ANOCHECER|MADRUGADA|CONTINUO)\b', location, flags=re.I)[0].strip()
    return interior, period, location


def _unique_matches(text, patterns):
    found = []
    for label, pattern in patterns:
        if re.search(pattern, text, re.I) and label not in found:
            found.append(label)
    return ', '.join(found)


class _ExcelCellDelegate(QStyledItemDelegate):
    """Editor plano que ocupa la celda completa, sin 'pastillas' de estilo global."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setContentsMargins(0, 0, 0, 0)
        editor.setStyleSheet(
            'QLineEdit { border: 0; border-radius: 0; padding: 0 4px; '
            'margin: 0; background: palette(base); color: palette(text); }'
        )
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class ExcelSoundTable(QTableWidget):
    """Grilla editable tipo Excel: selección por celdas, copiar, pegar y borrar."""

    def __init__(self, rows, columns, parent=None):
        super().__init__(rows, columns, parent)
        self.setItemDelegate(_ExcelCellDelegate(self))
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selection()
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            self._paste_selection()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not self.state() == QAbstractItemView.State.EditingState:
            self._clear_selection()
            return
        super().keyPressEvent(event)

    def _copy_selection(self):
        ranges = self.selectedRanges()
        if not ranges:
            return
        selection = ranges[0]
        lines = []
        for row in range(selection.topRow(), selection.bottomRow() + 1):
            values = []
            for column in range(selection.leftColumn(), selection.rightColumn() + 1):
                cell = self.item(row, column)
                values.append(cell.text() if cell else '')
            lines.append('\t'.join(values))
        QApplication.clipboard().setText('\n'.join(lines))

    def _paste_selection(self):
        current = self.currentIndex()
        if not current.isValid():
            return
        text = QApplication.clipboard().text()
        if text is None:
            return
        rows = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        if rows and rows[-1] == '':
            rows.pop()
        self.blockSignals(True)
        try:
            for row_offset, line in enumerate(rows):
                for column_offset, value in enumerate(line.split('\t')):
                    row = current.row() + row_offset
                    column = current.column() + column_offset
                    if row >= self.rowCount() or column >= self.columnCount():
                        continue
                    cell = self.item(row, column)
                    if cell is None:
                        cell = QTableWidgetItem('')
                        self.setItem(row, column, cell)
                    cell.setText(value)
        finally:
            self.blockSignals(False)
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, SoundPlanningPage):
            parent = parent.parentWidget()
        if parent is not None:
            parent._update_summary()
            parent.changed.emit()

    def _clear_selection(self):
        indexes = self.selectedIndexes()
        if not indexes:
            return
        self.blockSignals(True)
        try:
            for index in indexes:
                cell = self.item(index.row(), index.column())
                if cell is not None:
                    cell.setText('')
        finally:
            self.blockSignals(False)
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, SoundPlanningPage):
            parent = parent.parentWidget()
        if parent is not None:
            parent._update_summary()
            parent.changed.emit()


class SoundPlanningPage(QFrame):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('workspace')
        self._maximized = False
        self._main_tabs = None
        self._saved_margins = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 28)
        self._layout = layout

        tools = QHBoxLayout()
        self.sync_button = QPushButton(ui_text('Actualizar desde guion'))
        self.sync_button.setObjectName('primary')
        self.analyze_button = QPushButton(ui_text('Analizar sonido'))
        self.analyze_button.setToolTip(ui_text('Detecta necesidades sonoras con reglas locales. No usa IA.'))
        self.clear_button = QPushButton(ui_text('Limpiar análisis'))
        self.export_button = QPushButton('Excel')
        self.maximize_button = QPushButton(ui_text('⛶ Maximizar sonido'))
        tools.addWidget(self.sync_button)
        tools.addWidget(self.analyze_button)
        tools.addWidget(self.clear_button)
        tools.addStretch()
        tools.addWidget(self.export_button)
        tools.addWidget(self.maximize_button)
        layout.addLayout(tools)

        hint = QLabel('Planificación sonora por escena · diálogo, ambiente, Foley, SFX, música, wild/room tone y tratamiento de grabación. El análisis es determinista y no modifica el guion.')
        hint.setObjectName('moduleHint')
        hint.setWordWrap(True)
        self.hint = hint
        layout.addWidget(hint)

        self.table = ExcelSoundTable(0, len(COLUMNS), self)
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 250)
        self.table.setColumnWidth(1, 75)
        self.table.setColumnWidth(2, 55)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 190)
        for column in range(5, 12):
            self.table.setColumnWidth(column, 150)
        self.table.setColumnWidth(12, 220)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        self.summary = QLabel('0 escenas · 0 con diálogo · 0 SFX · 0 música')
        self.summary.setObjectName('moduleHint')
        footer.addWidget(self.summary)
        footer.addStretch()
        self.legend = QLabel(ui_text('Directo = registrar en set · Post = recrear/diseñar después'))
        self.legend.setObjectName('moduleHint')
        footer.addWidget(self.legend)
        layout.addLayout(footer)

        self.table.itemChanged.connect(self._item_changed)
        self.analyze_button.clicked.connect(self.analyze_all)
        self.clear_button.clicked.connect(self.clear_analysis)
        self.export_button.clicked.connect(self.export_excel)
        self.maximize_button.clicked.connect(self.toggle_maximize)

    def _item_changed(self, _item):
        self._update_summary()
        self.changed.emit()

    def _find_main_tabs(self):
        widget = self.parentWidget()
        while widget is not None:
            if hasattr(widget, 'tabBar') and hasattr(widget, 'indexOf'):
                try:
                    if widget.indexOf(self) >= 0:
                        return widget
                except Exception:
                    pass
            widget = widget.parentWidget()
        return None

    def toggle_maximize(self):
        self._maximized = not self._maximized
        if self._main_tabs is None:
            self._main_tabs = self._find_main_tabs()
        if self._maximized:
            self._saved_margins = self._layout.contentsMargins()
            self._layout.setContentsMargins(8, 8, 8, 8)
            if self._main_tabs is not None:
                self._main_tabs.tabBar().hide()
            self.hint.hide()
            self.legend.hide()
            self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self.maximize_button.setText(ui_text('↙ Restaurar'))
        else:
            if self._saved_margins is not None:
                margins = self._saved_margins
                self._layout.setContentsMargins(margins.left(), margins.top(), margins.right(), margins.bottom())
            if self._main_tabs is not None:
                self._main_tabs.tabBar().show()
            self.hint.show()
            self.legend.show()
            self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.maximize_button.setText(ui_text('⛶ Maximizar sonido'))

    def sync_from_project(self, blocks, schedule_rows=None):
        previous_by_id = {}
        previous_by_heading = {}
        for row in range(self.table.rowCount()):
            data = self.row_data(row)
            scene_id = data.get('scene_id', '')
            if scene_id:
                previous_by_id[scene_id] = data
            previous_by_heading[data.get('scene', '')] = data

        schedule_by_id = {}
        schedule_by_heading = {}
        for row in schedule_rows or []:
            if row.get('scene_id'):
                schedule_by_id[row.get('scene_id')] = row
            schedule_by_heading[row.get('scene', '')] = row

        scenes = []
        current = None
        for block in blocks or []:
            if block.get('type') == 'scene':
                current = {
                    'scene_id': block.get('id', ''),
                    'heading': block.get('text', '').strip(),
                    'blocks': [],
                }
                scenes.append(current)
            elif current:
                current['blocks'].append({'type': block.get('type', ''), 'text': block.get('text', '')})

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for scene in scenes:
            previous = previous_by_id.get(scene['scene_id']) or previous_by_heading.get(scene['heading']) or {}
            schedule = schedule_by_id.get(scene['scene_id']) or schedule_by_heading.get(scene['heading']) or {}
            interior, period, location = _scene_fields(scene['heading'])
            self._append_row({
                'scene_id': scene['scene_id'],
                'scene': scene['heading'],
                'day': schedule.get('day', previous.get('day', '')),
                'interior': interior,
                'period': period,
                'location': location,
                'dialogue': previous.get('dialogue', ''),
                'ambience': previous.get('ambience', ''),
                'foley': previous.get('foley', ''),
                'sfx': previous.get('sfx', ''),
                'music': previous.get('music', ''),
                'room_tone': previous.get('room_tone', ''),
                'treatment': previous.get('treatment', ''),
                'notes': previous.get('notes', ''),
            })
        self.table.blockSignals(False)
        self._update_summary()
        self.changed.emit()

    def _append_row(self, data):
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = (
            data.get('scene', ''), data.get('day', ''), data.get('interior', ''),
            data.get('period', ''), data.get('location', ''), data.get('dialogue', ''),
            data.get('ambience', ''), data.get('foley', ''), data.get('sfx', ''),
            data.get('music', ''), data.get('room_tone', ''), data.get('treatment', ''),
            data.get('notes', ''),
        )
        for column, value in enumerate(values):
            cell = _cell(value, editable=True)
            self.table.setItem(row, column, cell)
        self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, data.get('scene_id', ''))

    def row_data(self, row):
        keys = ('scene', 'day', 'interior', 'period', 'location', 'dialogue', 'ambience', 'foley', 'sfx', 'music', 'room_tone', 'treatment', 'notes')
        result = {key: (self.table.item(row, col).text() if self.table.item(row, col) else '') for col, key in enumerate(keys)}
        first = self.table.item(row, 0)
        result['scene_id'] = first.data(Qt.ItemDataRole.UserRole) if first else ''
        return result

    def to_data(self):
        return [self.row_data(row) for row in range(self.table.rowCount())]

    def load_data(self, rows):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row in rows or []:
            self._append_row(row)
        self.table.blockSignals(False)
        self._update_summary()

    def analyze_all(self):
        if not self.table.rowCount():
            QMessageBox.information(self, ui_text('Sonido'), ui_text('Primero actualiza el módulo desde el guion.'))
            return
        blocks_by_scene = defaultdict(list)
        # Scene text is kept in UserRole+1 by the suite before this call when available.
        source_blocks = getattr(self, '_source_blocks', [])
        current_key = None
        for block in source_blocks:
            if block.get('type') == 'scene':
                current_key = block.get('id') or block.get('text', '').strip()
            elif current_key:
                blocks_by_scene[current_key].append(block)

        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            scene_item = self.table.item(row, 0)
            scene_id = scene_item.data(Qt.ItemDataRole.UserRole) or ''
            heading = scene_item.text()
            blocks = blocks_by_scene.get(scene_id) or blocks_by_scene.get(heading) or []
            dialogue_characters = []
            action_texts = []
            music_lines = []
            for block in blocks:
                kind = block.get('type', '')
                text = block.get('text', '').strip()
                if kind == 'character' and text and text not in dialogue_characters:
                    dialogue_characters.append(text)
                if kind == 'action':
                    action_texts.append(text)
                    if MUSIC_PATTERN.search(text):
                        music_lines.append(text)
            action = ' '.join(action_texts)
            interior = self.table.item(row, 2).text()
            period = self.table.item(row, 3).text()
            location = self.table.item(row, 4).text()

            dialogue = ', '.join(dialogue_characters)
            ambience = self._default_ambience(interior, period, location)
            foley = _unique_matches(action, FOLEY_PATTERNS)
            sfx = _unique_matches(action, SFX_PATTERNS)
            music = 'Música en escena' if music_lines else ''
            room = 'Room tone: ' + location if location else 'Room tone'
            if dialogue:
                treatment = ui_text('Directo')
                if sfx or music:
                    treatment = 'Directo + post'
            elif sfx or music:
                treatment = 'Post / referencia en set'
            else:
                treatment = ui_text('Directo')

            for column, value in ((5, dialogue), (6, ambience), (7, foley), (8, sfx), (9, music), (10, room), (11, treatment)):
                cell = self.table.item(row, column)
                if cell is not None and not cell.text().strip():
                    cell.setText(value)
        self.table.blockSignals(False)
        self._update_summary()
        self.changed.emit()

    def set_source_blocks(self, blocks):
        self._source_blocks = list(blocks or [])

    @staticmethod
    def _default_ambience(interior, period, location):
        place = location or 'localización'
        if interior == 'EXT':
            base = 'Ambiente exterior'
            if period == 'NOCHE':
                base += ' nocturno'
            else:
                base += ' diurno'
        elif interior == 'I/E':
            base = 'Ambiente interior/exterior'
        else:
            base = 'Ambiente interior'
        return f'{base}: {place}'

    def clear_analysis(self):
        if not self.table.rowCount():
            return
        answer = QMessageBox.question(self, ui_text('Limpiar análisis'), '¿Limpiar Diálogo, Ambiente, Foley, SFX, Música, Room tone y Tratamiento? Las Notas se conservarán.')
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            for column in range(5, 12):
                self.table.item(row, column).setText('')
        self.table.blockSignals(False)
        self._update_summary()
        self.changed.emit()

    def _update_summary(self):
        rows = self.table.rowCount()
        dialogue = sum(bool(self.table.item(r, 5) and self.table.item(r, 5).text().strip()) for r in range(rows))
        sfx = sum(bool(self.table.item(r, 8) and self.table.item(r, 8).text().strip()) for r in range(rows))
        music = sum(bool(self.table.item(r, 9) and self.table.item(r, 9).text().strip()) for r in range(rows))
        self.summary.setText(f'{rows} escenas · {dialogue} con diálogo · {sfx} SFX · {music} música')

    def export_excel(self):
        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Exportar planificación sonora'), '', 'Excel (*.xlsx)')
        if not filename:
            return
        if not filename.lower().endswith('.xlsx'):
            filename += '.xlsx'
        try:
            from openpyxl import Workbook
            book = Workbook()
            sheet = book.active
            sheet.title = 'Plan de sonido'
            sheet.append(list(COLUMNS))
            for row in self.to_data():
                sheet.append([row.get(key, '') for key in ('scene', 'day', 'interior', 'period', 'location', 'dialogue', 'ambience', 'foley', 'sfx', 'music', 'room_tone', 'treatment', 'notes')])
            sheet.freeze_panes = 'A2'
            sheet.auto_filter.ref = sheet.dimensions
            book.save(filename)
            QMessageBox.information(self, ui_text('Sonido'), ui_text('Planificación sonora exportada correctamente.'))
        except Exception as error:
            QMessageBox.critical(self, ui_text('Sonido'), str(error))
