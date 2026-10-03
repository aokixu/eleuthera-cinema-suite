"""Herramientas de desarrollo de guion para Eleuthera Cinema Suite.



Este módulo se mantiene separado del editor, presupuesto y producción para que

las herramientas de desarrollo puedan evolucionar sin acoplarse a esos motores.

"""

from ui_i18n import ui_text, ui_join
from eleuthera_spreadsheet import EleutheraSpreadsheet

import re

from PySide6.QtCore import Qt, Signal, QTimer



from PySide6.QtCore import QEvent, QPointF, QRectF

from PySide6.QtGui import QBrush, QColor, QCursor, QPainter, QPainterPath, QPen

from PySide6.QtWidgets import (

    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsScene, QGraphicsSimpleTextItem,

    QGraphicsView, QTabWidget, QWidget

)

from PySide6.QtWidgets import (

    QAbstractItemView,

    QCheckBox,

    QColorDialog,

    QComboBox,

    QFrame,

    QFileDialog,

    QDialog,

    QDialogButtonBox,

    QHBoxLayout,

    QHeaderView,

    QLabel,

    QLineEdit,

    QInputDialog,

    QListWidget,

    QMessageBox,

    QPushButton,

    QScrollArea,

    QSlider,

    QStyledItemDelegate,

    QSizePolicy,

    QTextEdit,

    QTableWidget,

    QTableWidgetItem,

    QToolTip,

    QVBoxLayout,

)



from structure_templates import fields_for, row_data, value_change, orientation_for, export_xlsx, export_pdf





SCENE_ID_ROLE = Qt.ItemDataRole.UserRole

BLOCK_INDEX_ROLE = Qt.ItemDataRole.UserRole + 1





_CHARACTER_SUFFIX_RE = re.compile(

    r"\s*\((?:CONT[\'’]?D|CONTINUED|O\.?\s*S\.?|V\.?\s*O\.?|OFF|OS|VO)\)\s*$",

    re.IGNORECASE,

)





def normalize_character_name(value):

    """Une variantes técnicas del mismo personaje para análisis.



    Ej.: ``BRUNO ARCE (O.S.)`` y ``BRUNO ARCE (CONT'D)`` -> ``BRUNO ARCE``.

    El texto original del guion no se modifica.

    """

    name = str(value or '').strip()

    previous = None

    while name and name != previous:

        previous = name

        name = _CHARACTER_SUFFIX_RE.sub('', name).strip()

    return name





class _ExcelCellDelegate(QStyledItemDelegate):

    """Editor de celda plano: conserva la apariencia de grilla al editar."""

    def createEditor(self, parent, option, index):

        editor = super().createEditor(parent, option, index)

        if isinstance(editor, QLineEdit):

            editor.setFrame(False)

            editor.setStyleSheet(

                "QLineEdit { border: 0; border-radius: 0; padding: 0 4px; "

                "background: transparent; selection-background-color: palette(highlight); }"

            )

        return editor





class SceneNavigatorPage(QFrame):

    """Vista derivada del guion para buscar y navegar entre escenas."""



    scene_activated = Signal(str, int)

    development_changed = Signal()



    def __init__(self, parent=None):

        super().__init__(parent)

        self.setObjectName('workspace')

        self._scenes = []

        self._scene_development = {}

        self._loading_development = False

        self._build_ui()



    def _build_ui(self):

        layout = QVBoxLayout(self)

        layout.setContentsMargins(30, 25, 30, 28)

        layout.setSpacing(10)



        hint = QLabel(

            ui_text('Explora la estructura del guion, filtra escenas y salta directamente al punto que quieras revisar.')

        )

        hint.setObjectName('moduleHint')

        hint.setWordWrap(True)

        layout.addWidget(hint)



        search_row = QHBoxLayout()

        search_label = QLabel(ui_text('Buscar:'))

        self.search = QLineEdit()

        self.search.setPlaceholderText(ui_text('Escena, locación, personaje, INT/EXT, día, noche…'))

        self.search.setClearButtonEnabled(True)

        self.search.textChanged.connect(self._apply_filter)

        self.counter = QLabel(ui_text('0 escenas'))

        self.counter.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        search_row.addWidget(search_label)

        search_row.addWidget(self.search, 1)

        search_row.addWidget(self.counter)

        layout.addLayout(search_row)



        self.table = QTableWidget(0, 6)

        self.table.setHorizontalHeaderLabels(('N.º', ui_text('Escena'), 'INT/EXT', ui_text('Momento'), ui_text('Locación'), ui_text('Personajes')))

        self.table.setAlternatingRowColors(True)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setSortingEnabled(False)

        self.table.verticalHeader().setVisible(False)

        self.table.itemDoubleClicked.connect(self._activate_item)

        self.table.itemActivated.connect(self._activate_item)



        header = self.table.horizontalHeader()

        header.setStretchLastSection(False)

        header.resizeSection(0, 58)

        header.resizeSection(2, 82)

        header.resizeSection(3, 105)

        header.resizeSection(4, 190)

        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table, 1)



        development_title = QLabel(ui_text('Desarrollo de la escena'))

        development_title.setObjectName('moduleSectionTitle')

        layout.addWidget(development_title)



        development_row = QHBoxLayout()

        self.objective = QTextEdit()

        self.objective.setPlaceholderText(ui_text('¿Qué quiere conseguir el personaje o fuerza principal en esta escena?'))

        self.obstacle = QTextEdit()

        self.obstacle.setPlaceholderText(ui_text('¿Qué se lo impide o complica?'))

        self.result = QTextEdit()

        self.result.setPlaceholderText(ui_text('¿Cómo termina la escena? ¿Qué cambia?'))

        for label_text, editor in (

            (ui_text('Objetivo'), self.objective),

            (ui_text('Obstáculo'), self.obstacle),

            (ui_text('Resultado'), self.result),

        ):

            box = QVBoxLayout()

            label = QLabel(label_text)

            box.addWidget(label)

            editor.setMaximumHeight(92)

            box.addWidget(editor)

            development_row.addLayout(box, 1)

            editor.textChanged.connect(self._development_edited)

        layout.addLayout(development_row)



        footer = QLabel(

            ui_text('Selecciona una escena para editar su objetivo, obstáculo y resultado. Doble clic o Enter: abrir escena en el guion.')

        )

        footer.setObjectName('moduleHint')

        layout.addWidget(footer)

        self.table.itemSelectionChanged.connect(self._scene_selection_changed)



    @staticmethod

    def _text_item(value, scene_id='', block_index=-1):

        item = QTableWidgetItem(str(value or ''))

        item.setData(SCENE_ID_ROLE, scene_id)

        item.setData(BLOCK_INDEX_ROLE, int(block_index))

        return item



    def set_scenes(self, scenes):

        """Actualiza la tabla sin modificar el guion ni los datos del proyecto."""

        self._scenes = list(scenes or [])

        current_id = self.current_scene_id()

        self.table.setUpdatesEnabled(False)

        self.table.setRowCount(len(self._scenes))

        try:

            for row, scene in enumerate(self._scenes):

                scene_id = scene.get('id', '')

                block_index = int(scene.get('index', -1))

                characters = ', '.join(scene.get('characters', []))

                values = (

                    scene.get('number', row + 1),

                    scene.get('heading', ''),

                    scene.get('interior', ''),

                    scene.get('period', ''),

                    scene.get('location', ''),

                    characters,

                )

                for column, value in enumerate(values):

                    self.table.setItem(row, column, self._text_item(value, scene_id, block_index))

        finally:

            self.table.setUpdatesEnabled(True)

        self._apply_filter(self.search.text())

        if current_id:

            self.select_scene(current_id)

        self._scene_selection_changed()



    def set_development_data(self, data):

        self._scene_development = {

            str(scene_id): dict(values or {})

            for scene_id, values in (data or {}).items()

        }

        self._scene_selection_changed()



    def development_data(self):

        return self._scene_development



    def _scene_selection_changed(self):

        scene_id = self.current_scene_id()

        data = self._scene_development.get(scene_id, {}) if scene_id else {}

        self._loading_development = True

        try:

            self.objective.setPlainText(data.get('objective', ''))

            self.obstacle.setPlainText(data.get('obstacle', ''))

            self.result.setPlainText(data.get('result', ''))

            enabled = bool(scene_id)

            self.objective.setEnabled(enabled)

            self.obstacle.setEnabled(enabled)

            self.result.setEnabled(enabled)

        finally:

            self._loading_development = False



    def _development_edited(self):

        if self._loading_development:

            return

        scene_id = self.current_scene_id()

        if not scene_id:

            return

        values = {

            'objective': self.objective.toPlainText().strip(),

            'obstacle': self.obstacle.toPlainText().strip(),

            'result': self.result.toPlainText().strip(),

        }

        if any(values.values()):

            self._scene_development[scene_id] = values

        else:

            self._scene_development.pop(scene_id, None)

        self.development_changed.emit()



    def current_scene_id(self):

        row = self.table.currentRow()

        item = self.table.item(row, 0) if row >= 0 else None

        return item.data(SCENE_ID_ROLE) if item else ''



    def select_scene(self, scene_id):

        if not scene_id:

            return False

        for row in range(self.table.rowCount()):

            item = self.table.item(row, 0)

            if item and item.data(SCENE_ID_ROLE) == scene_id and not self.table.isRowHidden(row):

                self.table.selectRow(row)

                self.table.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

                return True

        return False



    def _apply_filter(self, text=''):

        query = (text or '').strip().casefold()

        visible = 0

        for row in range(self.table.rowCount()):

            haystack = ' '.join(

                self.table.item(row, column).text()

                for column in range(self.table.columnCount())

                if self.table.item(row, column)

            ).casefold()

            show = not query or all(term in haystack for term in query.split())

            self.table.setRowHidden(row, not show)

            if show:

                visible += 1

        total = self.table.rowCount()

        self.counter.setText(ui_join([f'{visible}', ui_text(' de '), f'{total}', ui_text(' escenas')]) if query else ui_join([f'{total}', ui_text(' escenas')]))



    def _activate_item(self, item):

        if item is None:

            return

        row = item.row()

        anchor = self.table.item(row, 0)

        if anchor is None:

            return

        self.scene_activated.emit(

            anchor.data(SCENE_ID_ROLE) or '',

            int(anchor.data(BLOCK_INDEX_ROLE) or 0),

        )





class SceneVersionsPage(QFrame):

    """Historial manual de versiones asociado a escenas reales del guion."""



    save_requested = Signal(str, str)

    restore_requested = Signal(str, str)

    delete_requested = Signal(str, str)

    scene_selected = Signal(str)



    def __init__(self, parent=None):

        super().__init__(parent)

        self.setObjectName('workspace')

        self._scenes = []

        self._versions = {}

        self._build_ui()



    def _build_ui(self):

        layout = QVBoxLayout(self)

        layout.setContentsMargins(30, 25, 30, 28)

        layout.setSpacing(10)



        hint = QLabel(

            ui_text('Conserva alternativas de una escena sin duplicar el guion completo. Solo una versión permanece activa en el guion.')

        )

        hint.setObjectName('moduleHint')

        hint.setWordWrap(True)

        layout.addWidget(hint)



        scene_row = QHBoxLayout()

        scene_row.addWidget(QLabel(ui_text('Escena:')))

        from PySide6.QtWidgets import QComboBox

        self.scene_combo = QComboBox()

        self.scene_combo.setMinimumWidth(420)

        self.scene_combo.currentIndexChanged.connect(self._scene_changed)

        self.open_scene_button = QPushButton(ui_text('Abrir en guion'))

        self.open_scene_button.clicked.connect(self._request_open_scene)

        self.save_button = QPushButton(ui_text('Guardar versión actual'))

        self.save_button.setObjectName('primary')

        self.save_button.clicked.connect(self._request_save)

        scene_row.addWidget(self.scene_combo, 1)

        scene_row.addWidget(self.open_scene_button)

        scene_row.addWidget(self.save_button)

        layout.addLayout(scene_row)



        content = QHBoxLayout()

        left = QVBoxLayout()

        left.addWidget(QLabel(ui_text('Versiones guardadas')))

        self.listing = QListWidget()

        self.listing.currentRowChanged.connect(self._show_selected)

        left.addWidget(self.listing, 1)

        buttons = QHBoxLayout()

        self.restore_button = QPushButton(ui_text('Restaurar'))

        self.delete_button = QPushButton(ui_text('Eliminar'))

        self.restore_button.clicked.connect(self._request_restore)

        self.delete_button.clicked.connect(self._request_delete)

        buttons.addWidget(self.restore_button)

        buttons.addWidget(self.delete_button)

        left.addLayout(buttons)



        right = QVBoxLayout()

        self.version_title = QLabel(ui_text('Selecciona una versión'))

        self.version_title.setStyleSheet('font-weight: 700;')

        right.addWidget(self.version_title)

        self.preview = QTextEdit()

        self.preview.setReadOnly(True)

        self.preview.setPlaceholderText(ui_text('Aquí verás el contenido de la versión seleccionada.'))

        right.addWidget(self.preview, 1)



        content.addLayout(left, 1)

        content.addLayout(right, 2)

        layout.addLayout(content, 1)



        note = QLabel(

            ui_text('Restaurar reemplaza únicamente la escena seleccionada. El resto del guion y sus vínculos de producción permanecen intactos.')

        )

        note.setObjectName('moduleHint')

        note.setWordWrap(True)

        layout.addWidget(note)

        self._update_buttons()



    def set_scenes(self, scenes):

        current = self.current_scene_id()

        self._scenes = list(scenes or [])

        self.scene_combo.blockSignals(True)

        self.scene_combo.clear()

        for scene in self._scenes:

            self.scene_combo.addItem(

                f"{scene.get('number', '')}. {scene.get('heading', '')}",

                scene.get('id', '')

            )

        self.scene_combo.blockSignals(False)

        if current:

            self.select_scene(current)

        elif self.scene_combo.count():

            self.scene_combo.setCurrentIndex(0)

        self._refresh_versions()



    def set_versions(self, versions):

        self._versions = versions or {}

        self._refresh_versions()



    def current_scene_id(self):

        return self.scene_combo.currentData() or ''



    def select_scene(self, scene_id):

        for index in range(self.scene_combo.count()):

            if self.scene_combo.itemData(index) == scene_id:

                self.scene_combo.setCurrentIndex(index)

                return True

        return False



    def _scene_changed(self, _index=0):

        self._refresh_versions()



    def _request_open_scene(self):

        scene_id = self.current_scene_id()

        if scene_id:

            self.scene_selected.emit(scene_id)



    def _versions_for_scene(self):

        return list(self._versions.get(self.current_scene_id(), []))



    def _refresh_versions(self):

        selected_id = self.current_version_id()

        rows = self._versions_for_scene()

        self.listing.blockSignals(True)

        self.listing.clear()

        for row in rows:

            created = str(row.get('created_at', '')).replace('T', ' ')[:19]

            label = row.get('name') or ui_text('Versión sin nombre')

            item_text = f'{label}  ·  {created}' if created else label

            self.listing.addItem(item_text)

            self.listing.item(self.listing.count() - 1).setData(Qt.ItemDataRole.UserRole, row.get('id', ''))

        self.listing.blockSignals(False)

        target = -1

        if selected_id:

            for index in range(self.listing.count()):

                if self.listing.item(index).data(Qt.ItemDataRole.UserRole) == selected_id:

                    target = index

                    break

        if target < 0 and self.listing.count():

            target = self.listing.count() - 1

        self.listing.setCurrentRow(target)

        self._show_selected(target)



    def current_version_id(self):

        item = self.listing.currentItem()

        return item.data(Qt.ItemDataRole.UserRole) if item else ''



    def current_version(self):

        identity = self.current_version_id()

        return next((row for row in self._versions_for_scene() if row.get('id') == identity), None)



    def _show_selected(self, _row=-1):

        version = self.current_version()

        if not version:

            self.version_title.setText(ui_text('Selecciona una versión'))

            self.preview.clear()

            self._update_buttons()

            return

        self.version_title.setText(version.get('name') or ui_text('Versión sin nombre'))

        lines = []

        for block in version.get('blocks', []):

            text = block.get('text', '')

            if block.get('type') == 'scene':

                if lines:

                    lines.append('')

                lines.append(text)

                lines.append('')

            elif block.get('type') == 'character':

                lines.extend(['', text])

            elif block.get('type') == 'parenthetical':

                lines.append(text)

            elif block.get('type') == 'dialogue':

                lines.append(text)

            elif block.get('type') == 'transition':

                lines.extend(['', text])

            else:

                lines.append(text)

        self.preview.setPlainText('\n'.join(lines).strip())

        self._update_buttons()



    def _update_buttons(self):

        enabled = bool(self.current_version_id())

        self.restore_button.setEnabled(enabled)

        self.delete_button.setEnabled(enabled)

        has_scene = bool(self.current_scene_id())

        self.save_button.setEnabled(has_scene)

        self.open_scene_button.setEnabled(has_scene)



    def _request_save(self):

        scene_id = self.current_scene_id()

        if not scene_id:

            return

        number = len(self._versions_for_scene()) + 1

        name, ok = QInputDialog.getText(self, ui_text('Guardar versión de escena'), ui_text('Nombre de la versión:'), text=f'Versión {number}')

        if ok:

            name = name.strip() or f'Versión {number}'

            self.save_requested.emit(scene_id, name)



    def _request_restore(self):

        scene_id = self.current_scene_id()

        version = self.current_version()

        if not scene_id or not version:

            return

        answer = QMessageBox.question(

            self,

            ui_text('Restaurar versión'),

            f"¿Restaurar «{version.get('name', 'esta versión')}»?\n\nLa escena activa será reemplazada.",

            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,

        )

        if answer == QMessageBox.StandardButton.Yes:

            self.restore_requested.emit(scene_id, version.get('id', ''))



    def _request_delete(self):

        scene_id = self.current_scene_id()

        version = self.current_version()

        if not scene_id or not version:

            return

        answer = QMessageBox.question(

            self,

            ui_text('Eliminar versión'),

            f"¿Eliminar «{version.get('name', 'esta versión')}» del historial?",

            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,

        )

        if answer == QMessageBox.StandardButton.Yes:

            self.delete_requested.emit(scene_id, version.get('id', ''))



class DialogueTunerPage(QFrame):

    """Revisión de la voz de un personaje a través de todos sus diálogos."""



    dialogue_activated = Signal(str, int)



    def __init__(self, parent=None):

        super().__init__(parent)

        self.setObjectName('workspace')

        self._entries = []

        self._build_ui()



    def _build_ui(self):

        layout = QVBoxLayout(self)

        layout.setContentsMargins(30, 25, 30, 28)

        layout.setSpacing(10)



        hint = QLabel(

            ui_text('Lee la voz de un personaje de principio a fin sin recorrer todo el guion. Filtra sus intervenciones y salta directamente al diálogo que quieras revisar.')

        )

        hint.setObjectName('moduleHint')

        hint.setWordWrap(True)

        layout.addWidget(hint)



        controls = QHBoxLayout()

        controls.addWidget(QLabel(ui_text('Personaje:')))

        self.character_combo = QComboBox()

        self.character_combo.setMinimumWidth(260)

        self.character_combo.currentIndexChanged.connect(self._apply_filter)

        controls.addWidget(self.character_combo)

        controls.addSpacing(12)

        controls.addWidget(QLabel(ui_text('Buscar:')))

        self.search = QLineEdit()

        self.search.setPlaceholderText(ui_text('Texto del diálogo, escena o acotación…'))

        self.search.setClearButtonEnabled(True)

        self.search.textChanged.connect(self._apply_filter)

        controls.addWidget(self.search, 1)

        self.summary = QLabel(ui_text('0 intervenciones'))

        self.summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        controls.addWidget(self.summary)

        layout.addLayout(controls)



        self.table = QTableWidget(0, 4)

        self.table.setHorizontalHeaderLabels((ui_text('Escena'), ui_text('Acotación'), ui_text('Diálogo'), ui_text('Palabras')))

        self.table.setAlternatingRowColors(True)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setSortingEnabled(False)

        self.table.verticalHeader().setVisible(False)

        self.table.setWordWrap(True)

        self.table.itemDoubleClicked.connect(self._activate_item)

        self.table.itemActivated.connect(self._activate_item)



        header = self.table.horizontalHeader()

        header.resizeSection(0, 245)

        header.resizeSection(1, 180)

        header.resizeSection(3, 78)

        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table, 1)



        self.stats = QLabel(ui_text('Selecciona un personaje para revisar su voz.'))

        self.stats.setObjectName('moduleHint')

        self.stats.setWordWrap(True)

        layout.addWidget(self.stats)



        footer = QLabel(ui_text('Doble clic o Enter: abrir esa intervención en el guion.'))

        footer.setObjectName('moduleHint')

        layout.addWidget(footer)



    def set_entries(self, entries):

        """Recibe intervenciones derivadas del guion; no modifica datos del proyecto."""

        previous = self.current_character()

        self._entries = list(entries or [])

        characters = sorted({row.get('character', '').strip() for row in self._entries if row.get('character', '').strip()}, key=str.casefold)



        self.character_combo.blockSignals(True)

        self.character_combo.clear()

        self.character_combo.addItems(characters)

        if previous in characters:

            self.character_combo.setCurrentText(previous)

        self.character_combo.blockSignals(False)

        self._apply_filter()



    def current_character(self):

        return self.character_combo.currentText().strip()



    def select_character(self, character):

        index = self.character_combo.findText(character)

        if index >= 0:

            self.character_combo.setCurrentIndex(index)

            return True

        return False



    @staticmethod

    def _item(value, scene_id='', block_index=-1):

        item = QTableWidgetItem(str(value or ''))

        item.setData(SCENE_ID_ROLE, scene_id)

        item.setData(BLOCK_INDEX_ROLE, int(block_index))

        return item



    def _matching_entries(self):

        character = self.current_character()

        query = self.search.text().strip().casefold()

        terms = query.split()

        rows = [row for row in self._entries if row.get('character', '').strip() == character]

        if not terms:

            return rows

        result = []

        for row in rows:

            haystack = ' '.join((

                row.get('heading', ''),

                row.get('parenthetical', ''),

                row.get('dialogue', ''),

            )).casefold()

            if all(term in haystack for term in terms):

                result.append(row)

        return result



    def _apply_filter(self, *_args):

        rows = self._matching_entries()

        self.table.setUpdatesEnabled(False)

        self.table.setRowCount(len(rows))

        try:

            for row_index, row in enumerate(rows):

                scene_label = f"{row.get('scene_number', '')}. {row.get('heading', '')}".strip()

                values = (

                    scene_label,

                    row.get('parenthetical', ''),

                    row.get('dialogue', ''),

                    row.get('word_count', 0),

                )

                for column, value in enumerate(values):

                    self.table.setItem(

                        row_index,

                        column,

                        self._item(value, row.get('scene_id', ''), row.get('block_index', -1)),

                    )

            self.table.resizeRowsToContents()

        finally:

            self.table.setUpdatesEnabled(True)



        all_for_character = [row for row in self._entries if row.get('character', '').strip() == self.current_character()]

        words = sum(int(row.get('word_count', 0)) for row in all_for_character)

        scenes = len({row.get('scene_id') for row in all_for_character if row.get('scene_id')})

        total = len(all_for_character)

        visible = len(rows)

        if self.search.text().strip():

            self.summary.setText(ui_join([f'{visible}', ui_text(' de '), f'{total}', ui_text(' intervenciones')]))

        else:

            self.summary.setText(ui_join([f'{total}', ui_text(' intervenciones')]))

        if self.current_character():

            self.stats.setText(

                f'{self.current_character()}: {total} intervenciones · {words} palabras de diálogo · {scenes} escenas con diálogo.'

            )

        else:

            self.stats.setText(ui_text('No se encontraron personajes con diálogo en el guion.'))



    def _activate_item(self, item):

        if item is None:

            return

        anchor = self.table.item(item.row(), 0)

        if anchor is None:

            return

        self.dialogue_activated.emit(

            anchor.data(SCENE_ID_ROLE) or '',

            int(anchor.data(BLOCK_INDEX_ROLE) or 0),

        )







class CharacterArcPage(QFrame):

    """Arco de personaje con hitos vinculables a escenas reales del guion."""



    scene_open_requested = Signal(str, int)

    data_changed = Signal()



    def __init__(self, parent=None):

        super().__init__(parent)

        self.setObjectName('workspace')

        self._scenes = []

        self._characters = []

        self._arcs = {}

        self._build_ui()



    def _build_ui(self):

        layout = QVBoxLayout(self)

        layout.setContentsMargins(30, 25, 30, 28)

        layout.setSpacing(10)



        hint = QLabel(

            ui_text('Sigue el arco de cada personaje a través del guion. Los hitos pueden vincularse a escenas reales y abrirse directamente en el editor.')

        )

        hint.setObjectName('moduleHint')

        hint.setWordWrap(True)

        layout.addWidget(hint)



        top = QHBoxLayout()

        top.addWidget(QLabel(ui_text('Personaje:')))

        self.character_combo = QComboBox()

        self.character_combo.setMinimumWidth(280)

        self.character_combo.currentIndexChanged.connect(self._character_changed)

        top.addWidget(self.character_combo, 1)

        self.scene_count = QLabel(ui_text('0 escenas'))

        top.addWidget(self.scene_count)

        layout.addLayout(top)



        summary = QHBoxLayout()

        self.initial_state = QLineEdit()

        self.initial_state.setPlaceholderText(ui_text('Cómo comienza el personaje'))

        self.need = QLineEdit()

        self.need.setPlaceholderText(ui_text('Qué desea o necesita'))

        self.final_state = QLineEdit()

        self.final_state.setPlaceholderText(ui_text('Cómo termina'))

        for label, widget in (

            (ui_text('Estado inicial:'), self.initial_state),

            (ui_text('Deseo / necesidad:'), self.need),

            (ui_text('Estado final:'), self.final_state),

        ):

            box = QVBoxLayout()

            box.addWidget(QLabel(label))

            box.addWidget(widget)

            summary.addLayout(box, 1)

            widget.editingFinished.connect(self._save_summary)

        layout.addLayout(summary)



        toolbar = QHBoxLayout()

        self.add_button = QPushButton(ui_text('+ Añadir hito'))

        self.edit_button = QPushButton(ui_text('Editar hito'))

        self.delete_button = QPushButton(ui_text('Eliminar hito'))

        self.open_button = QPushButton(ui_text('Abrir escena'))

        self.add_button.setObjectName('primary')

        self.add_button.clicked.connect(self._add_milestone)

        self.edit_button.clicked.connect(self._edit_milestone)

        self.delete_button.clicked.connect(self._delete_milestone)

        self.open_button.clicked.connect(self._open_selected)

        toolbar.addWidget(self.add_button)

        toolbar.addWidget(self.edit_button)

        toolbar.addWidget(self.delete_button)

        toolbar.addWidget(self.open_button)

        toolbar.addStretch(1)

        layout.addLayout(toolbar)



        self.table = QTableWidget(0, 4)

        self.table.setHorizontalHeaderLabels((ui_text('Momento del arco'), ui_text('Hito'), ui_text('Escena vinculada'), ui_text('Notas')))

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setAlternatingRowColors(True)

        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.table.itemDoubleClicked.connect(lambda _item: self._open_selected())

        self.table.itemSelectionChanged.connect(self._update_buttons)

        layout.addWidget(self.table, 1)



        note = QLabel(

            ui_text('Los personajes se detectan automáticamente a partir del guion. Los hitos son datos de desarrollo y no modifican el texto de las escenas.')

        )

        note.setObjectName('moduleHint')

        note.setWordWrap(True)

        layout.addWidget(note)

        self._update_buttons()



    def set_scenes(self, scenes):

        current = self.current_character()

        self._scenes = list(scenes or [])

        names = sorted({

            normalize_character_name(name)

            for scene in self._scenes

            for name in scene.get('characters', [])

            if normalize_character_name(name)

        })

        self._characters = names

        self.character_combo.blockSignals(True)

        self.character_combo.clear()

        self.character_combo.addItems(names)

        if current in names:

            self.character_combo.setCurrentText(current)

        self.character_combo.blockSignals(False)

        self._character_changed()



    def set_data(self, data):

        self._arcs = dict(data or {})

        self._character_changed()



    def to_data(self):

        self._save_summary(emit=False)

        return self._arcs



    def current_character(self):

        return self.character_combo.currentText().strip()



    def _record(self, create=False):

        name = self.current_character()

        if not name:

            return None

        if create:

            return self._arcs.setdefault(name, {

                'initial_state': '', 'need': '', 'final_state': '', 'milestones': []

            })

        return self._arcs.get(name)



    def _character_changed(self):

        name = self.current_character()

        record = self._record(False) or {}

        self.initial_state.blockSignals(True)

        self.need.blockSignals(True)

        self.final_state.blockSignals(True)

        self.initial_state.setText(record.get('initial_state', ''))

        self.need.setText(record.get('need', ''))

        self.final_state.setText(record.get('final_state', ''))

        self.initial_state.blockSignals(False)

        self.need.blockSignals(False)

        self.final_state.blockSignals(False)

        count = sum(1 for scene in self._scenes if name in {normalize_character_name(c) for c in scene.get('characters', [])})

        self.scene_count.setText(ui_join([f'{count}', ui_text(' escena')]) if count == 1 else ui_join([f'{count}', ui_text(' escenas')]))

        self._refresh_table()



    def _save_summary(self, emit=True):

        if not self.current_character():

            return

        record = self._record(True)

        record['initial_state'] = self.initial_state.text().strip()

        record['need'] = self.need.text().strip()

        record['final_state'] = self.final_state.text().strip()

        if emit:

            self.data_changed.emit()



    def _scene_label(self, scene_id):

        for scene in self._scenes:

            if scene.get('id') == scene_id:

                return f"{scene.get('number', '')}. {scene.get('heading', '')}".strip()

        return ui_text('Sin vínculo') if not scene_id else 'Escena no encontrada'



    def _refresh_table(self):

        self.table.setRowCount(0)

        record = self._record(False) or {}

        for milestone in record.get('milestones', []):

            row = self.table.rowCount()

            self.table.insertRow(row)

            values = (

                milestone.get('stage', ''),

                milestone.get('title', ''),

                self._scene_label(milestone.get('scene_id', '')),

                milestone.get('notes', ''),

            )

            for col, value in enumerate(values):

                item = QTableWidgetItem(str(value))

                item.setData(SCENE_ID_ROLE, milestone.get('scene_id', ''))

                self.table.setItem(row, col, item)

        self._update_buttons()



    def _milestone_dialog(self, existing=None):

        existing = existing or {}

        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout

        dialog = QDialog(self)

        dialog.setWindowTitle(ui_text('Hito del arco'))

        dialog.resize(560, 320)

        form = QFormLayout(dialog)



        stage = QComboBox()

        stages = ('Estado inicial', 'Incidente', 'Decisión', 'Progreso', 'Retroceso',

                  'Punto de quiebre', 'Clímax', 'Transformación', 'Estado final', 'Otro')

        stage.addItems(stages)

        if existing.get('stage') in stages:

            stage.setCurrentText(existing.get('stage'))



        title = QLineEdit(existing.get('title', ''))

        title.setPlaceholderText('Ej.: Edgar decide continuar con el ritual')



        scene = QComboBox()

        scene.addItem(ui_text('Sin vínculo'), '')

        for item in self._scenes:

            scene.addItem(f"{item.get('number', '')}. {item.get('heading', '')}", item.get('id', ''))

        wanted = existing.get('scene_id', '')

        for i in range(scene.count()):

            if scene.itemData(i) == wanted:

                scene.setCurrentIndex(i)

                break



        notes = QTextEdit()

        notes.setPlainText(existing.get('notes', ''))

        notes.setPlaceholderText(ui_text('Qué cambia en el personaje en este momento…'))

        notes.setMaximumHeight(110)



        form.addRow(ui_text('Momento:'), stage)

        form.addRow(ui_text('Hito:'), title)

        form.addRow(ui_text('Escena:'), scene)

        form.addRow(ui_text('Notas:'), notes)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)

        buttons.accepted.connect(dialog.accept)

        buttons.rejected.connect(dialog.reject)

        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:

            return None

        if not title.text().strip():

            QMessageBox.information(self, ui_text('Hito del arco'), ui_text('Escribe un nombre para el hito.'))

            return None

        return {

            'stage': stage.currentText(),

            'title': title.text().strip(),

            'scene_id': scene.currentData() or '',

            'notes': notes.toPlainText().strip(),

        }



    def _add_milestone(self):

        if not self.current_character():

            return

        data = self._milestone_dialog()

        if not data:

            return

        self._record(True).setdefault('milestones', []).append(data)

        self._refresh_table()

        self.table.selectRow(self.table.rowCount() - 1)

        self.data_changed.emit()



    def _selected_index(self):

        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []

        return rows[0].row() if rows else -1



    def _edit_milestone(self):

        index = self._selected_index()

        record = self._record(False)

        if index < 0 or not record:

            return

        milestones = record.get('milestones', [])

        if index >= len(milestones):

            return

        data = self._milestone_dialog(milestones[index])

        if not data:

            return

        milestones[index] = data

        self._refresh_table()

        self.table.selectRow(index)

        self.data_changed.emit()



    def _delete_milestone(self):

        index = self._selected_index()

        record = self._record(False)

        if index < 0 or not record:

            return

        answer = QMessageBox.question(

            self, ui_text('Eliminar hito'), ui_text('¿Eliminar el hito seleccionado del arco del personaje?')

        )

        if answer != QMessageBox.StandardButton.Yes:

            return

        milestones = record.get('milestones', [])

        if index < len(milestones):

            milestones.pop(index)

            self._refresh_table()

            self.data_changed.emit()



    def _open_selected(self):

        index = self._selected_index()

        record = self._record(False)

        if index < 0 or not record:

            return

        milestones = record.get('milestones', [])

        if index >= len(milestones):

            return

        scene_id = milestones[index].get('scene_id', '')

        if not scene_id:

            QMessageBox.information(self, ui_text('Abrir escena'), ui_text('Este hito todavía no está vinculado a una escena.'))

            return

        for scene in self._scenes:

            if scene.get('id') == scene_id:

                self.scene_open_requested.emit(scene_id, int(scene.get('index', -1)))

                return

        QMessageBox.warning(self, ui_text('Abrir escena'), ui_text('La escena vinculada ya no existe en el guion.'))



    def _update_buttons(self):

        enabled = self._selected_index() >= 0

        self.edit_button.setEnabled(enabled)

        self.delete_button.setEnabled(enabled)

        self.open_button.setEnabled(enabled)







class AnalysisPage(QFrame):

    """Panel visual de análisis estructural calculado desde el proyecto."""



    scene_open_requested = Signal(str, int)

    character_open_requested = Signal(str)

    markers_changed = Signal(dict)

    dramatic_structure_changed = Signal(dict)



    def __init__(self, parent=None):

        super().__init__(parent)

        self.setObjectName('workspace')

        self._scenes = []

        self._dialogues = []

        self._story_map = []

        self._scene_development = {}

        self._character_arcs = {}

        self._breakdown = []

        self._markers = {'characters': {}, 'scenes': {}, 'show_in_script': False}

        self._dramatic_structure = {}

        self._network_zoom = 1.0

        self._network_maximized = False

        self._updating_markers = False

        self._build_ui()



    # ---------- UI ----------

    def _build_ui(self):

        layout = QVBoxLayout(self)

        self._analysis_layout = layout

        layout.setContentsMargins(26, 18, 26, 24)

        layout.setSpacing(8)



        self.analysis_hint = QLabel(

            ui_text('Visualiza la estructura del guion, la presencia de personajes y sus relaciones. Los resultados se calculan a partir del proyecto; no modifican el guion.')

        )

        self.analysis_hint.setObjectName('moduleHint')

        self.analysis_hint.setWordWrap(True)

        layout.addWidget(self.analysis_hint)



        self.tabs = QTabWidget()

        self.tabs.setDocumentMode(True)

        layout.addWidget(self.tabs, 1)



        # Gráficos

        # El dashboard vive dentro de un QScrollArea. Así, en ventanas pequeñas

        # ningún gráfico queda recortado: aparece una barra vertical para subir/bajar.

        self.dashboard = QWidget()

        self.dashboard.setMinimumWidth(820)

        dash = QVBoxLayout(self.dashboard)

        dash.setContentsMargins(4, 8, 4, 8)

        dash.setSpacing(10)



        cards = QHBoxLayout()

        self.metric_scenes = QLabel('0\nEscenas')

        self.metric_characters = QLabel('0\nPersonajes')

        self.metric_words = QLabel(ui_text('0\nPalabras de diálogo'))

        self.metric_development = QLabel(ui_text('0%\nEscenas desarrolladas'))

        for metric in (self.metric_scenes, self.metric_characters, self.metric_words, self.metric_development):

            metric.setAlignment(Qt.AlignmentFlag.AlignCenter)

            metric.setMinimumHeight(62)

            metric.setStyleSheet(

                'QLabel { background: #292b30; border: 1px solid #3d4148; '

                'border-radius: 6px; padding: 7px; font-weight: 600; }'

            )

            cards.addWidget(metric, 1)

        dash.addLayout(cards)



        # Gráfico principal: presencia de personajes. Se coloca antes de los

        # gráficos secundarios para aprovechar todo el ancho del módulo.

        self.presence_panel = QFrame()

        self.presence_panel.setObjectName('analysisPanel')

        self.presence_panel.setStyleSheet(

            'QFrame#analysisPanel { background: #202226; border: 1px solid #3d4148; '

            'border-radius: 7px; }'

        )

        presence_layout = QVBoxLayout(self.presence_panel)

        presence_layout.setContentsMargins(10, 8, 10, 8)

        presence_layout.setSpacing(4)



        # Controles del gráfico principal. El botón permite dedicar prácticamente

        # toda la pestaña a la línea de presencia sin perder el resto del dashboard.

        presence_tools = QHBoxLayout()

        presence_tools.setContentsMargins(0, 0, 0, 0)

        presence_tools.addStretch(1)

        self.presence_maximize = QPushButton(ui_text('⛶ Maximizar'))

        self.presence_maximize.setToolTip('Maximizar/restaurar el gráfico de presencia')

        self.presence_maximize.setMaximumWidth(120)

        self.presence_maximize.clicked.connect(self._toggle_presence_maximize)

        presence_tools.addWidget(self.presence_maximize)

        presence_layout.addLayout(presence_tools)



        # El gráfico tiene un lienzo virtual mayor que el panel. El QScrollArea

        # aporta desplazamiento horizontal y vertical cuando hay muchas escenas

        # o personajes, evitando comprimir todos los puntos en pocos píxeles.

        self.presence_scroll = QScrollArea()

        self.presence_scroll.setWidgetResizable(False)

        self.presence_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.presence_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.presence_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.presence_chart = _AnalysisTimeline()

        self.presence_chart.scene_open_requested.connect(self.scene_open_requested)

        self.presence_chart.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.presence_scroll.setWidget(self.presence_chart)

        presence_layout.addWidget(self.presence_scroll, 1)

        dash.addWidget(self.presence_panel, 3)



        # Gráficos secundarios: comparación INT/EXT y ranking de diálogo.

        charts = QHBoxLayout()

        charts.setSpacing(10)



        self.scene_panel = QFrame()

        self.scene_panel.setObjectName('analysisPanel')

        self.scene_panel.setStyleSheet(

            'QFrame#analysisPanel { background: #202226; border: 1px solid #3d4148; '

            'border-radius: 7px; }'

        )

        scene_panel_layout = QVBoxLayout(self.scene_panel)

        scene_panel_layout.setContentsMargins(10, 8, 10, 8)

        scene_tools = QHBoxLayout()

        scene_tools.setContentsMargins(0, 0, 0, 0)

        scene_tools.addStretch(1)

        self.scene_maximize = QPushButton(ui_text('⛶ Maximizar'))

        self.scene_maximize.setToolTip('Maximizar/restaurar el gráfico de escenas por tipo')

        self.scene_maximize.setMaximumWidth(120)

        self.scene_maximize.clicked.connect(lambda: self._toggle_secondary_maximize('scene'))

        scene_tools.addWidget(self.scene_maximize)

        scene_panel_layout.addLayout(scene_tools)



        self.scene_scroll = QScrollArea()

        self.scene_scroll.setWidgetResizable(True)

        self.scene_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.scene_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.scene_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.scene_chart = _AnalysisBarChart('Escenas por tipo')

        self.scene_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.scene_scroll.setWidget(self.scene_chart)

        scene_panel_layout.addWidget(self.scene_scroll, 1)



        self.character_panel = QFrame()

        self.character_panel.setObjectName('analysisPanel')

        self.character_panel.setStyleSheet(

            'QFrame#analysisPanel { background: #202226; border: 1px solid #3d4148; '

            'border-radius: 7px; }'

        )

        character_panel_layout = QVBoxLayout(self.character_panel)

        character_panel_layout.setContentsMargins(10, 8, 10, 8)

        character_tools = QHBoxLayout()

        character_tools.setContentsMargins(0, 0, 0, 0)

        character_tools.addStretch(1)

        self.character_maximize = QPushButton(ui_text('⛶ Maximizar'))

        self.character_maximize.setToolTip('Maximizar/restaurar el gráfico de personajes con más diálogo')

        self.character_maximize.setMaximumWidth(120)

        self.character_maximize.clicked.connect(lambda: self._toggle_secondary_maximize('character'))

        character_tools.addWidget(self.character_maximize)

        character_panel_layout.addLayout(character_tools)



        self.character_scroll = QScrollArea()

        self.character_scroll.setWidgetResizable(True)

        self.character_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.character_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.character_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.character_chart = _AnalysisHorizontalBarChart('Personajes con más diálogo')

        self.character_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.character_scroll.setWidget(self.character_chart)

        character_panel_layout.addWidget(self.character_scroll, 1)



        charts.addWidget(self.scene_panel, 1)

        charts.addWidget(self.character_panel, 1)

        dash.addLayout(charts, 2)



        # Scroll general del dashboard: si la altura disponible es baja, el usuario

        # puede subir/bajar sin que los gráficos inferiores queden cortados.

        self.dashboard_scroll = QScrollArea()

        self.dashboard_scroll.setWidgetResizable(True)

        self.dashboard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.dashboard_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.dashboard_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.dashboard_scroll.setWidget(self.dashboard)

        self.tabs.addTab(self.dashboard_scroll, ui_text('Gráficos'))



        # Estructura dramática / mapa estructural

        self.structure_page = QWidget()

        structure_layout = QVBoxLayout(self.structure_page)

        self._structure_layout = structure_layout

        structure_layout.setContentsMargins(10, 10, 10, 10)

        structure_layout.setSpacing(10)



        self.structure_hint = QLabel(

            ui_text('Ubica los hitos estructurales sobre el recorrido real del guion. No modifica el guion ni el mapa de tramas: solo organiza la función dramática de escenas clave.')

        )

        self.structure_hint.setObjectName('moduleHint')

        self.structure_hint.setWordWrap(True)

        structure_layout.addWidget(self.structure_hint)



        self.structure_tools_widget = QWidget()

        tools = QHBoxLayout(self.structure_tools_widget)

        tools.setContentsMargins(0, 0, 0, 0)

        tools.setSpacing(8)

        tools.addWidget(QLabel(ui_text('Modelo:')))

        self.structure_model = QComboBox()

        self.structure_model.addItems(tuple(self._STRUCTURE_TEMPLATES.keys()))

        self.structure_model.currentTextChanged.connect(self._structure_model_changed)

        tools.addWidget(self.structure_model)

        tools.addStretch(1)

        tools.addWidget(QLabel('Zoom:'))

        self.structure_zoom_out = QPushButton('−')

        self.structure_zoom_in = QPushButton('+')

        self.structure_zoom_label = QLabel('100%')

        self.structure_zoom_out.setFixedWidth(36)

        self.structure_zoom_in.setFixedWidth(36)

        self.structure_zoom_label.setMinimumWidth(58)

        self.structure_zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tools.addWidget(self.structure_zoom_out)

        tools.addWidget(self.structure_zoom_label)

        tools.addWidget(self.structure_zoom_in)

        self.structure_maximize = QPushButton(ui_text('⛶ Maximizar mapa'))

        self.structure_maximize.setToolTip('Maximizar/restaurar el mapa de estructura dramática')

        self.structure_maximize.setMinimumWidth(140)

        self.structure_maximize.clicked.connect(self._toggle_structure_maximize)

        tools.addWidget(self.structure_maximize)

        structure_layout.addWidget(self.structure_tools_widget)



        self.structure_model_description = QLabel()

        self.structure_model_description.setObjectName('moduleHint')

        self.structure_model_description.setWordWrap(True)

        self.structure_model_description.setMinimumHeight(42)

        structure_layout.addWidget(self.structure_model_description)



        self.structure_timeline_scroll = QScrollArea()

        self.structure_timeline_scroll.setWidgetResizable(False)

        self.structure_timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.structure_timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.structure_timeline_scroll.setFrameShape(QFrame.Shape.StyledPanel)

        self.structure_timeline = _DramaticStructureTimeline()

        self.structure_timeline.setMinimumHeight(300)

        self.structure_timeline.label_visibility_changed.connect(self._structure_label_visibility_changed)

        self.structure_timeline_scroll.setWidget(self.structure_timeline)

        structure_layout.addWidget(self.structure_timeline_scroll, 1)



        self.structure_editor = QFrame()

        self.structure_editor.setFrameShape(QFrame.Shape.StyledPanel)

        editor_layout = QVBoxLayout(self.structure_editor)

        editor_layout.setContentsMargins(10, 8, 10, 8)

        editor_head = QHBoxLayout()

        self.structure_editor_title = QLabel(ui_text('Hitos estructurales'))

        editor_head.addWidget(self.structure_editor_title, 1)

        self.structure_assign = QPushButton(ui_text('Asignar escena'))

        self.structure_plan = QPushButton(ui_text('Planificar escena'))

        self.structure_clear = QPushButton(ui_text('Quitar asignación'))

        self.structure_add_custom = QPushButton(ui_text('+ Hito'))

        self.structure_remove_custom = QPushButton(ui_text('Eliminar hito'))

        self.structure_assign.clicked.connect(self._assign_structure_point)

        self.structure_plan.clicked.connect(self._plan_structure_point)

        self.structure_clear.clicked.connect(self._clear_structure_point)

        self.structure_add_custom.clicked.connect(self._add_custom_structure_point)

        self.structure_remove_custom.clicked.connect(self._remove_custom_structure_point)

        editor_head.addWidget(self.structure_assign)

        editor_head.addWidget(self.structure_plan)

        editor_head.addWidget(self.structure_clear)

        editor_head.addWidget(self.structure_add_custom)

        editor_head.addWidget(self.structure_remove_custom)

        self.structure_develop = QPushButton(ui_text('Ficha profesional'))

        self.structure_develop.setToolTip('Desarrollar los beats con campos adaptados a esta estructura')

        self.structure_develop.clicked.connect(self._open_structure_development)

        editor_head.addWidget(self.structure_develop)

        self.structure_export_xlsx = QPushButton('Excel')

        self.structure_export_xlsx.setToolTip(ui_text('Exportar plantilla profesional editable a Excel'))

        self.structure_export_xlsx.clicked.connect(lambda: self._export_structure_template('xlsx'))

        editor_head.addWidget(self.structure_export_xlsx)

        self.structure_export_pdf = QPushButton('PDF')

        self.structure_export_pdf.setToolTip(ui_text('Exportar informe estructural profesional a PDF'))

        self.structure_export_pdf.clicked.connect(lambda: self._export_structure_template('pdf'))

        editor_head.addWidget(self.structure_export_pdf)

        self.structure_maximize_editor = QPushButton(ui_text('⛶ Maximizar hitos'))

        self.structure_maximize_editor.setToolTip('Maximizar/restaurar la tabla de hitos estructurales')

        self.structure_maximize_editor.setMinimumWidth(140)

        self.structure_maximize_editor.clicked.connect(self._toggle_structure_editor_maximize)

        editor_head.addWidget(self.structure_maximize_editor)

        editor_layout.addLayout(editor_head)



        self.structure_table = QTableWidget(0, 3)

        self.structure_table.setHorizontalHeaderLabels((ui_text('Hito'), ui_text('Escena / planificación'), ui_text('Ubicación orientativa / real')))

        self.structure_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.structure_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.structure_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.structure_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.structure_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.structure_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.structure_table.verticalHeader().setVisible(False)

        # La tabla de hitos siempre conserva una barra vertical visible. Esto es

        # especialmente importante al maximizarla: la tabla debe adaptarse al

        # alto disponible en vez de crecer fuera del viewport.

        self.structure_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.structure_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.structure_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.structure_table.setMinimumHeight(190)

        self.structure_table.doubleClicked.connect(lambda _idx: self._edit_structure_point())

        editor_layout.addWidget(self.structure_table)

        structure_layout.addWidget(self.structure_editor)



        self.structure_footer = QLabel(

            ui_text('La barra horizontal representa el guion completo. Usa la barra de desplazamiento para recorrerlo y +/− para ampliar o reducir la escala.')

        )

        self.structure_footer.setObjectName('moduleHint')

        self.structure_footer.setWordWrap(True)

        structure_layout.addWidget(self.structure_footer)



        self.structure_zoom_out.clicked.connect(lambda: self._change_structure_zoom(1 / 1.20))

        self.structure_zoom_in.clicked.connect(lambda: self._change_structure_zoom(1.20))

        self.tabs.addTab(self.structure_page, ui_text('Estructura dramática'))

        self._structure_maximized = False

        self._structure_editor_maximized = False

        self._structure_zoom = 1.0

        self._refresh_structure_map()



        # Nodos — explorador visual de relaciones

        self.network_page = QWidget()

        network_layout = QVBoxLayout(self.network_page)

        self._network_layout = network_layout

        network_layout.setContentsMargins(4, 8, 4, 4)



        network_toolbar = QHBoxLayout()

        network_toolbar.addWidget(QLabel(ui_text('Vista:')))

        self.network_mode = QComboBox()

        self.network_mode.addItems((ui_text('Red completa'), ui_text('Islas / comunidades'), ui_text('Relaciones entre personajes')))

        self.network_mode.currentIndexChanged.connect(self._refresh_network)

        network_toolbar.addWidget(self.network_mode)



        self.network_characters = QCheckBox(ui_text('Personajes'))

        self.network_characters.setChecked(True)

        self.network_locations = QCheckBox(ui_text('Localizaciones'))

        self.network_locations.setChecked(True)

        self.network_scenes = QCheckBox(ui_text('Escenas'))

        self.network_scenes.setChecked(True)

        self.network_objects = QCheckBox(ui_text('Objetos'))

        self.network_objects.setChecked(False)

        self.network_objects.setToolTip(ui_text('Elementos reales tomados del Desglose del proyecto.'))

        for control in (self.network_characters, self.network_locations, self.network_scenes, self.network_objects):

            control.toggled.connect(self._refresh_network)

            network_toolbar.addWidget(control)



        self.network_weak = QCheckBox(ui_text('Ocultar vínculos débiles'))

        self.network_weak.setToolTip(ui_text('Oculta relaciones que solo aparecen una vez.'))

        self.network_weak.toggled.connect(self._on_network_weak_toggled)

        network_toolbar.addWidget(self.network_weak)

        self.network_disconnected = QCheckBox(ui_text('Mostrar desconectados'))

        self.network_disconnected.setChecked(False)

        self.network_disconnected.toggled.connect(self._on_network_disconnected_toggled)

        network_toolbar.addWidget(self.network_disconnected)

        self.network_bridges = QCheckBox(ui_text('Puentes críticos'))

        self.network_bridges.setToolTip(ui_text('Resalta conexiones cuya eliminación separaría grupos de personajes.'))

        self.network_bridges.toggled.connect(self._on_network_bridges_toggled)

        network_toolbar.addWidget(self.network_bridges)



        self.network_search = QLineEdit()

        self.network_search.setPlaceholderText(ui_text('Buscar nodo…'))

        self.network_search.setMaximumWidth(190)

        self.network_search.textChanged.connect(self._highlight_network_search)

        network_toolbar.addWidget(self.network_search)

        network_layout.addLayout(network_toolbar)



        network_toolbar2 = QHBoxLayout()

        network_toolbar2.addWidget(QLabel(ui_text('Separación:')))

        self.network_separation = QSlider(Qt.Orientation.Horizontal)

        self.network_separation.setRange(70, 170)

        self.network_separation.setValue(100)

        self.network_separation.setMaximumWidth(150)

        self.network_separation.sliderReleased.connect(self._refresh_network)

        network_toolbar2.addWidget(self.network_separation)



        self.zoom_out = QPushButton('−')

        self.zoom_in = QPushButton('+')

        self.zoom_fit = QPushButton(ui_text('Ajustar'))

        self.zoom_label = QLabel('100%')

        self.zoom_out.setFixedWidth(36)

        self.zoom_in.setFixedWidth(36)

        self.zoom_out.clicked.connect(lambda: self._zoom_network(1 / 1.22))

        self.zoom_in.clicked.connect(lambda: self._zoom_network(1.22))

        self.zoom_fit.clicked.connect(self._fit_network)

        network_toolbar2.addSpacing(10)

        network_toolbar2.addWidget(QLabel('Zoom:'))

        network_toolbar2.addWidget(self.zoom_out)

        network_toolbar2.addWidget(self.zoom_label)

        network_toolbar2.addWidget(self.zoom_in)

        network_toolbar2.addWidget(self.zoom_fit)

        self.network_release = QPushButton(ui_text('Mostrar todo'))

        self.network_release.setToolTip(ui_text('Quita el aislamiento de un nodo y vuelve a mostrar toda la red.'))

        self.network_release.clicked.connect(self._release_network_focus)

        network_toolbar2.addWidget(self.network_release)

        self.network_maximize = QPushButton(ui_text('⛶ Maximizar'))

        self.network_maximize.setToolTip('Maximizar/restaurar la vista de nodos')

        self.network_maximize.setMaximumWidth(120)

        self.network_maximize.clicked.connect(self._toggle_network_maximize)

        network_toolbar2.addWidget(self.network_maximize)

        # Mantener esta barra limpia: las ayudas permanentes y contadores del

        # análisis de red se retiraron para no saturar la vista. Los filtros

        # siguen funcionando exactamente igual.

        network_toolbar2.addStretch(1)

        network_layout.addLayout(network_toolbar2)



        self.network = QGraphicsView()

        self.network.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        self.network.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.network.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.network.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.network.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.network_scene = QGraphicsScene(self.network)

        self.network.setScene(self.network_scene)

        self.network.viewport().installEventFilter(self)

        self._network_nodes = []

        self._network_edges = []

        self._network_focus = None

        network_layout.addWidget(self.network, 1)

        self.network_relation_info = QLabel(ui_text('Selecciona un nodo o una conexión para ver por qué existe esa relación.'))

        self.network_relation_info.setObjectName('moduleHint')

        self.network_relation_info.setWordWrap(True)

        self.network_relation_info.setMinimumHeight(38)

        network_layout.addWidget(self.network_relation_info)

        self.tabs.addTab(self.network_page, ui_text('Nodos'))



        # Tabla de personajes

        self.details = QTableWidget(0, 5)

        self.details.setHorizontalHeaderLabels((ui_text('Personaje'), ui_text('Escenas'), ui_text('Intervenciones'), ui_text('Palabras'), '% diálogo'))

        self.details.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.details.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.details.setAlternatingRowColors(True)

        self.details.verticalHeader().setVisible(False)

        self.details.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        for column in range(1, 5):

            self.details.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        self.details.itemDoubleClicked.connect(self._open_character_row)

        self.tabs.addTab(self.details, ui_text('Personajes'))



        # Colores / marcadores

        self.markers_page = QWidget()

        markers_layout = QVBoxLayout(self.markers_page)

        markers_layout.setContentsMargins(8, 10, 8, 8)

        marker_hint = QLabel(

            ui_text('Asigna colores para destacar personajes o escenas. Los mismos colores se usan en los nodos y, si lo activas, como resaltado temporal en el Guion.')

        )

        marker_hint.setObjectName('moduleHint')

        marker_hint.setWordWrap(True)

        markers_layout.addWidget(marker_hint)



        marker_tools = QHBoxLayout()

        marker_tools.addWidget(QLabel(ui_text('Tipo:')))

        self.marker_type = QComboBox()

        self.marker_type.addItems((ui_text('Personaje'), ui_text('Escena')))

        self.marker_type.currentIndexChanged.connect(self._populate_marker_targets)

        marker_tools.addWidget(self.marker_type)

        marker_tools.addWidget(QLabel(ui_text('Elemento:')))

        self.marker_target = QComboBox()

        marker_tools.addWidget(self.marker_target, 1)



        self.marker_color = QPushButton(ui_text('Elegir color…'))

        self.marker_color.clicked.connect(self._choose_marker_color)

        marker_tools.addWidget(self.marker_color)

        self.marker_reset = QPushButton(ui_text('Quitar color'))

        self.marker_reset.clicked.connect(self._remove_marker_color)

        marker_tools.addWidget(self.marker_reset)

        self.marker_auto = QPushButton(ui_text('Asignar colores automáticos'))

        self.marker_auto.clicked.connect(self._assign_automatic_markers)

        marker_tools.addWidget(self.marker_auto)

        markers_layout.addLayout(marker_tools)



        self.show_script_markers = QCheckBox(ui_text('Mostrar marcadores en Guion'))

        self.show_script_markers.stateChanged.connect(self._script_marker_toggle)

        markers_layout.addWidget(self.show_script_markers)



        self.marker_table = QTableWidget(0, 3)

        self.marker_table.setHorizontalHeaderLabels((ui_text('Tipo'), ui_text('Elemento'), 'Color'))

        self.marker_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.marker_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.marker_table.verticalHeader().setVisible(False)

        self.marker_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self.marker_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.marker_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        markers_layout.addWidget(self.marker_table, 1)



        clear_all = QPushButton(ui_text('Quitar todos los marcadores'))

        clear_all.clicked.connect(self._clear_markers)

        markers_layout.addWidget(clear_all, 0, Qt.AlignmentFlag.AlignLeft)

        self.tabs.addTab(self.markers_page, ui_text('Marcadores'))



    def _toggle_presence_maximize(self):

        """Maximiza/restaura el gráfico de presencia dentro de la pestaña Gráficos."""

        maximized = not bool(getattr(self, '_presence_is_maximized', False))

        self._presence_is_maximized = maximized

        self._secondary_maximized = None



        for metric in (self.metric_scenes, self.metric_characters, self.metric_words, self.metric_development):

            metric.setVisible(not maximized)

        self.scene_panel.setVisible(not maximized)

        self.character_panel.setVisible(not maximized)

        self.presence_panel.setVisible(True)



        self.scene_maximize.setText(ui_text('⛶ Maximizar'))

        self.character_maximize.setText(ui_text('⛶ Maximizar'))

        self.presence_maximize.setText(ui_text('↙ Restaurar') if maximized else ui_text('⛶ Maximizar'))

        self.presence_panel.setMinimumHeight(520 if maximized else 0)

        self.scene_panel.setMinimumHeight(0)

        self.character_panel.setMinimumHeight(0)

        if maximized:

            self.presence_scroll.ensureVisible(0, 0)



    def _toggle_secondary_maximize(self, panel_name):

        """Maximiza/restaura uno de los gráficos secundarios sin perder sus barras de desplazamiento."""

        current = getattr(self, '_secondary_maximized', None)

        maximized = current != panel_name

        self._secondary_maximized = panel_name if maximized else None



        # Si estaba maximizada la presencia, restaurarla antes de abrir otro gráfico.

        if getattr(self, '_presence_is_maximized', False):

            self._presence_is_maximized = False

            self.presence_maximize.setText(ui_text('⛶ Maximizar'))

            self.presence_panel.setMinimumHeight(0)



        show_scene = (not maximized) or panel_name == 'scene'

        show_character = (not maximized) or panel_name == 'character'



        for metric in (self.metric_scenes, self.metric_characters, self.metric_words, self.metric_development):

            metric.setVisible(not maximized)

        self.presence_panel.setVisible(not maximized)

        self.scene_panel.setVisible(show_scene)

        self.character_panel.setVisible(show_character)



        self.scene_maximize.setText(ui_text('↙ Restaurar') if maximized and panel_name == 'scene' else ui_text('⛶ Maximizar'))

        self.character_maximize.setText(ui_text('↙ Restaurar') if maximized and panel_name == 'character' else ui_text('⛶ Maximizar'))



        self.scene_panel.setMinimumHeight(520 if maximized and panel_name == 'scene' else 0)

        self.character_panel.setMinimumHeight(520 if maximized and panel_name == 'character' else 0)

        if maximized:

            target = self.scene_scroll if panel_name == 'scene' else self.character_scroll

            target.ensureVisible(0, 0)



    # ---------- Datos ----------

    def set_project_data(self, scenes=None, dialogues=None, story_map=None,

                         scene_development=None, character_arcs=None, breakdown=None):

        self._scenes = list(scenes or [])

        self._dialogues = list(dialogues or [])

        self._story_map = list(story_map or [])

        self._scene_development = dict(scene_development or {})

        self._character_arcs = dict(character_arcs or {})

        self._breakdown = list(breakdown or [])

        self._populate_marker_targets()

        self._refresh_structure_map()

        self.refresh_analysis()



    def set_markers(self, data):

        payload = data or {}

        self._markers = {

            'characters': dict(payload.get('characters', {})),

            'scenes': dict(payload.get('scenes', {})),

            'show_in_script': bool(payload.get('show_in_script', False)),

        }

        self._updating_markers = True

        try:

            self.show_script_markers.setChecked(self._markers['show_in_script'])

        finally:

            self._updating_markers = False

        self._refresh_marker_table()

        self._recolor_analysis()



    def marker_data(self):

        return {

            'characters': dict(self._markers.get('characters', {})),

            'scenes': dict(self._markers.get('scenes', {})),

            'show_in_script': bool(self._markers.get('show_in_script', False)),

        }



    def _normalized_scene_characters(self, scene):

        return sorted({

            normalize_character_name(c)

            for c in scene.get('characters', [])

            if normalize_character_name(c)

        })



    def _all_characters(self):

        names = {

            normalize_character_name(c)

            for scene in self._scenes

            for c in scene.get('characters', [])

            if normalize_character_name(c)

        }

        names.update(

            normalize_character_name(d.get('character_normalized') or d.get('character', ''))

            for d in self._dialogues

            if normalize_character_name(d.get('character_normalized') or d.get('character', ''))

        )

        return sorted(names)



    def refresh_analysis(self):

        characters = self._all_characters()

        words = sum(int(d.get('word_count') or len(str(d.get('dialogue', '')).split())) for d in self._dialogues)

        developed = sum(

            1 for scene in self._scenes

            if any((self._scene_development.get(str(scene.get('id')), {}) or {}).values())

        )

        pct = round(100 * developed / len(self._scenes)) if self._scenes else 0

        self.metric_scenes.setText(ui_join([f'{len(self._scenes)}', ui_text('\nEscenas')]))

        self.metric_characters.setText(ui_join([f'{len(characters)}', ui_text('\nPersonajes')]))

        self.metric_words.setText(f'{words:,}'.replace(',', '.') + ui_text('\nPalabras de diálogo'))

        self.metric_development.setText(f'{pct}%\nEscenas desarrolladas')



        interior = sum(1 for s in self._scenes if str(s.get('interior', '')).upper() == 'INT')

        exterior = sum(1 for s in self._scenes if str(s.get('interior', '')).upper() == 'EXT')

        other = max(0, len(self._scenes) - interior - exterior)

        scene_values = [('INT', interior), ('EXT', exterior)]

        if other:

            scene_values.append(('OTRO', other))

        self.scene_chart.set_values(scene_values)



        stats = self._character_stats()

        ranked = sorted(stats.items(), key=lambda kv: (-kv[1]['words'], kv[0]))

        # No limitar a ocho personajes: los gráficos tienen lienzo virtual y scroll.

        self.character_chart.set_values(

            [(name, data['words'], self._character_color(name)) for name, data in ranked]

        )

        self.presence_chart.set_data(

            self._scenes,

            [name for name, _ in ranked],

            {name: self._character_color(name) for name, _ in ranked},

        )

        self._fill_details(stats)

        if hasattr(self, 'structure_timeline'):

            self._refresh_structure_map()

        self._refresh_network()



    def _character_stats(self):

        stats = {}

        for scene in self._scenes:

            for raw_name in scene.get('characters', []):

                name = normalize_character_name(raw_name)

                if not name:

                    continue

                stats.setdefault(name, {'scenes': set(), 'lines': 0, 'words': 0})

                stats[name]['scenes'].add(str(scene.get('id', '')))

        for d in self._dialogues:

            name = normalize_character_name(d.get('character_normalized') or d.get('character', ''))

            if not name:

                continue

            stats.setdefault(name, {'scenes': set(), 'lines': 0, 'words': 0})

            stats[name]['lines'] += 1

            stats[name]['words'] += int(d.get('word_count') or len(str(d.get('dialogue', '')).split()))

            if d.get('scene_id'):

                stats[name]['scenes'].add(str(d.get('scene_id')))

        return stats



    def _fill_details(self, stats):

        total_words = sum(v['words'] for v in stats.values())

        ordered = sorted(stats.items(), key=lambda kv: (-kv[1]['words'], kv[0]))

        self.details.setRowCount(0)

        for name, data in ordered:

            row = self.details.rowCount()

            self.details.insertRow(row)

            pct = (100.0 * data['words'] / total_words) if total_words else 0.0

            values = (name, len(data['scenes']), data['lines'], data['words'], f'{pct:.1f}%')

            for col, value in enumerate(values):

                item = QTableWidgetItem(str(value))

                item.setData(Qt.ItemDataRole.UserRole, name)

                if col == 0:

                    color = self._character_color(name)

                    item.setData(Qt.ItemDataRole.DecorationRole, color)

                self.details.setItem(row, col, item)



    def _open_character_row(self, item):

        name = item.data(Qt.ItemDataRole.UserRole) or self.details.item(item.row(), 0).text()

        if name:

            self.character_open_requested.emit(str(name))



    # ---------- Estructura dramática / mapa estructural ----------

    _STRUCTURE_TEMPLATES = {

        ui_text('Tres actos'): ('Presentación', 'Incidente detonante', 'Primer punto de giro', 'Midpoint', 'Crisis', 'Segundo punto de giro', 'Clímax', 'Resolución'),

        ui_text('Cinco actos'): ('Exposición', 'Acción ascendente', 'Punto medio', 'Nueva complicación', 'Clímax', 'Acción descendente', 'Desenlace'),

        'Syd Field': ('Planteamiento', 'Incidente incitador', 'Plot Point I', 'Confrontación', 'Midpoint', 'Plot Point II', 'Resolución'),

        'Save the Cat': ('Imagen inicial', 'Tema declarado', 'Planteamiento', 'Catalizador', 'Debate', 'Entrada al Acto II', 'Trama B', 'Diversión y juegos', 'Midpoint', 'Los malos se acercan', 'Todo está perdido', 'Noche oscura del alma', 'Entrada al Acto III', 'Finale', 'Imagen final'),

        'Freytag': ('Exposición', 'Acción ascendente', 'Clímax', 'Acción descendente', 'Resolución'),

        'Viaje del héroe (Vogler)': ('Mundo ordinario', 'Llamada a la aventura', 'Rechazo de la llamada', 'Encuentro con el mentor', 'Cruce del primer umbral', 'Pruebas, aliados y enemigos', 'Aproximación', 'Ordalía', 'Recompensa', 'Camino de regreso', 'Resurrección', 'Retorno con el elixir'),

        'Story Circle (Dan Harmon)': ('Zona de confort', ui_text('Necesidad'), 'Entrada a lo desconocido', 'Adaptación', 'Obtención', 'Precio', 'Regreso', ui_text('Cambio')),

        ui_text('Ocho secuencias'): ('Secuencia 1: planteamiento', 'Secuencia 2: detonación y giro', 'Secuencia 3: primera progresión', 'Secuencia 4: avance al punto medio', 'Secuencia 5: consecuencias', 'Secuencia 6: crisis y segundo giro', 'Secuencia 7: preparación del clímax', 'Secuencia 8: clímax y resolución'),

        'McKee': ('Incidente incitador', 'Complicaciones progresivas', 'Punto de no retorno', 'Crisis', 'Clímax', 'Resolución'),

        'Kishōtenketsu': ('Ki — Introducción', 'Shō — Desarrollo', 'Ten — Giro', 'Ketsu — Conclusión'),

        'Truby — 22 pasos': ('Debilidad y necesidad', 'Fantasma / herida', 'Problema presente', 'Deseo', 'Aliado', 'Oponente', 'Falso aliado / oponente', 'Primera revelación y decisión', 'Plan', 'Plan del oponente', 'Impulso', 'Ataque del aliado', 'Derrota aparente', 'Segunda revelación y nueva decisión', 'Revelación para el público', 'Tercera revelación y decisión', 'Puerta / desafío final', 'Batalla', 'Autorrevelación', 'Decisión moral', 'Nuevo equilibrio', 'Estado final'),

        'Story Spine': ('Érase una vez', 'Cada día', 'Hasta que un día', 'A causa de eso I', 'A causa de eso II', 'Hasta que finalmente', 'Y desde entonces'),

        'Fichtean Curve': ('Crisis inicial', 'Crisis creciente I', 'Crisis creciente II', 'Crisis creciente III', 'Clímax', 'Acción descendente'),

        'Seven-Point Story Structure': ('Gancho', 'Primer punto de giro', 'Primer punto de presión', 'Punto medio', 'Segundo punto de presión', 'Segundo punto de giro', 'Resolución'),

        'Heroine’s Journey (Murdock)': ('Separación de lo femenino', 'Identificación con lo masculino', 'Camino de pruebas', 'Éxito aparente', 'Despertar espiritual', 'Descenso', 'Reconexión con lo femenino', 'Sanación de la ruptura', 'Integración'),

        'Mini-Movie Method': ('Mini-película 1: planteamiento', 'Mini-película 2: nueva situación', 'Mini-película 3: progresión', 'Mini-película 4: punto medio', 'Mini-película 5: presión creciente', 'Mini-película 6: crisis', 'Mini-película 7: clímax', 'Mini-película 8: resolución'),

        'TV — Teaser + 4 actos': ('Teaser / Cold open', 'Acto I', 'Primer giro / corte', 'Acto II', 'Midpoint / corte', 'Acto III', 'Crisis / corte', 'Acto IV', 'Clímax', 'Tag / cierre'),

        'TV — 6 actos': ('Teaser / Cold open', 'Acto I', 'Acto II', 'Acto III', 'Midpoint', 'Acto IV', 'Acto V', 'Acto VI', 'Clímax', 'Tag / cierre'),

        'Círculo de conflicto': ('Equilibrio inicial', 'Desequilibrio', ui_text('Objetivo'), 'Obstáculo creciente', 'Decisión irreversible', 'Confrontación', 'Consecuencia', 'Nuevo equilibrio'),

        'Arco de transformación': ('Estado inicial', 'Carencia interna', 'Desafío', 'Resistencia al cambio', 'Prueba decisiva', 'Crisis de identidad', 'Elección transformadora', 'Nuevo estado'),

        ui_text('Personalizado'): (),

    }



    _STRUCTURE_DESCRIPTIONS = {

        ui_text('Tres actos'): ui_text('Modelo clásico: plantea la historia, desarrolla la confrontación y conduce al clímax y la resolución. Flexible y útil como lectura general de un largometraje.'),

        ui_text('Cinco actos'): 'Divide la progresión dramática en cinco grandes movimientos, permitiendo observar con más detalle la escalada, el punto medio, el clímax y el desenlace.',

        'Syd Field': 'Paradigma de guion centrado en tres actos y dos grandes puntos de giro que empujan la historia hacia una nueva dirección.',

        'Save the Cat': 'Plantilla de beats para largometraje que recorre quince momentos desde la imagen inicial hasta la imagen final. Útil para comprobar ritmo y progresión.',

        'Freytag': 'Modelo de cinco fases derivado del análisis dramático: exposición, ascenso, clímax, descenso y resolución.',

        'Viaje del héroe (Vogler)': 'Recorrido de transformación en doce etapas: salida del mundo ordinario, pruebas, crisis, transformación y regreso.',

        'Story Circle (Dan Harmon)': 'Estructura circular de ocho pasos enfocada en un personaje que desea algo, entra en una situación desconocida, paga un precio y regresa cambiado.',

        ui_text('Ocho secuencias'): 'Organiza el largometraje como ocho bloques con objetivos y giros propios. Resulta útil para estudiar ritmo y progresión dentro de los actos.',

        'McKee': 'Lectura basada en incidente incitador, complicaciones progresivas, crisis, clímax y resolución. Prioriza el cambio de valor dramático más que una plantilla rígida.',

        'Kishōtenketsu': 'Estructura de cuatro partes —introducción, desarrollo, giro y conclusión— que no exige que el conflicto sea el motor central de la historia.',

        'Truby — 22 pasos': 'Modelo detallado orientado al deseo, oposición, revelaciones, batalla y transformación moral del protagonista. Los hitos se presentan aquí de forma resumida.',

        'Story Spine': 'Esqueleto narrativo muy compacto que conecta normalidad, ruptura, cadena de consecuencias, resolución y nuevo estado.',

        'Fichtean Curve': 'Entra pronto en conflicto y encadena crisis cada vez mayores hasta el clímax, con poca exposición inicial y una caída breve.',

        'Seven-Point Story Structure': 'Siete hitos que conectan el gancho inicial con la resolución mediante giros, puntos de presión y un midpoint central.',

        'Heroine’s Journey (Murdock)': 'Modelo de transformación asociado a Maureen Murdock, centrado en separación, descenso, reconciliación e integración de la identidad.',

        'Mini-Movie Method': 'Observa el largometraje como ocho segmentos relativamente autónomos, cada uno con una función dramática que impulsa al siguiente.',

        'TV — Teaser + 4 actos': 'Plantilla práctica para episodios con cold open, cuatro movimientos dramáticos y cierre. Los cortes pueden adaptarse al formato y plataforma.',

        'TV — 6 actos': 'Lectura episódica en seis movimientos, útil para series con múltiples cortes, escaladas y puntos de suspensión antes del clímax.',

        'Círculo de conflicto': 'Modelo analítico general para seguir cómo un equilibrio se rompe, aparece un objetivo, crecen los obstáculos y la confrontación produce un nuevo equilibrio.',

        'Arco de transformación': 'Modelo analítico centrado en el cambio interno: carencia, resistencia, crisis, elección y estado final del personaje.',

        ui_text('Personalizado'): 'Crea tus propios hitos y asígnalos libremente a escenas. Eleuthera no impone ninguna estructura al guion.',

    }



    def set_dramatic_structure(self, data):

        # Se preservan todas las claves antiguas (tension, beats y Freytag) para

        # no romper proyectos previos, aunque esta interfaz ya no dependa de ellas.

        self._dramatic_structure = dict(data or {})

        model = str(self._dramatic_structure.get('structure_model') or ui_text('Tres actos'))

        if model not in self._STRUCTURE_TEMPLATES:

            model = ui_text('Tres actos')

        if not isinstance(self._dramatic_structure.get('structure_points'), dict):

            self._dramatic_structure['structure_points'] = {}

        if not isinstance(self._dramatic_structure.get('custom_structure_points'), list):

            self._dramatic_structure['custom_structure_points'] = []

        # Escenas planificadas permiten trabajar la estructura antes de escribir/cargar un guion.

        if not isinstance(self._dramatic_structure.get('structure_planned_scenes'), dict):

            self._dramatic_structure['structure_planned_scenes'] = {}

        # Etiquetas visibles elegidas manualmente por el usuario, separadas por modelo.

        # Por defecto el mapa queda limpio: los nombres aparecen solo al pasar el cursor.

        if not isinstance(self._dramatic_structure.get('structure_visible_labels'), dict):

            self._dramatic_structure['structure_visible_labels'] = {}

        self._dramatic_structure['structure_model'] = model

        if hasattr(self, 'structure_model'):

            self.structure_model.blockSignals(True)

            self.structure_model.setCurrentText(model)

            self.structure_model.blockSignals(False)

        self._refresh_structure_map()



    def dramatic_structure_data(self):

        return dict(self._dramatic_structure)



    def _structure_point_names(self):

        model = self.structure_model.currentText() if hasattr(self, 'structure_model') else ui_text('Tres actos')

        if model == ui_text('Personalizado'):

            return tuple(str(x) for x in self._dramatic_structure.get('custom_structure_points', []) if str(x).strip())

        return self._STRUCTURE_TEMPLATES.get(model, ())



    def _structure_model_changed(self, model):

        self._dramatic_structure['structure_model'] = str(model)

        self._refresh_structure_map()

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())



    def _selected_structure_row(self):

        rows = self.structure_table.selectionModel().selectedRows() if self.structure_table.selectionModel() else []

        return rows[0].row() if rows else -1



    def _plan_structure_point(self):

        row = self._selected_structure_row()

        names = self._structure_point_names()

        if row < 0 or row >= len(names):

            return

        model = self.structure_model.currentText()

        planned_by_model = self._dramatic_structure.setdefault('structure_planned_scenes', {}).setdefault(model, {})

        current = str(planned_by_model.get(names[row], '') or '')

        label, ok = QInputDialog.getText(

            self, ui_text('Planificar escena'),

            f'Escena o secuencia prevista para “{names[row]}”:',

            QLineEdit.EchoMode.Normal, current

        )

        if not ok:

            return

        label = str(label).strip()

        if label:

            planned_by_model[names[row]] = label

        else:

            planned_by_model.pop(names[row], None)

        self._refresh_structure_map(select_row=row)

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())



    def _edit_structure_point(self):

        """Editor único del hito: planificación y vínculo con guion conviven."""

        row = self._selected_structure_row()

        names = self._structure_point_names()

        if row < 0 or row >= len(names):

            return

        beat = names[row]

        model = self.structure_model.currentText()

        planned_by_model = self._dramatic_structure.setdefault('structure_planned_scenes', {}).setdefault(model, {})

        assigned = self._dramatic_structure.setdefault('structure_points', {})



        dialog = QDialog(self)

        dialog.setWindowTitle(f'Hito estructural — {beat}')

        dialog.resize(560, 230)

        lay = QVBoxLayout(dialog)

        lay.addWidget(QLabel(ui_text('Planificación de escena o secuencia:')))

        planned = QLineEdit(str(planned_by_model.get(beat, '') or ''))

        planned.setPlaceholderText(ui_text('Escribe una escena o secuencia prevista…'))

        lay.addWidget(planned)

        lay.addWidget(QLabel(ui_text('Vincular escena del guion:')))

        combo = QComboBox()

        combo.addItem(ui_text('— Sin escena vinculada —'), '')

        current_id = str(assigned.get(beat, '') or '')

        current_index = 0

        for i, sc in enumerate(self._scenes):

            sid = str(sc.get('id', '') or '')

            label = f"{sc.get('number', i + 1)}. {sc.get('heading', '')}"

            combo.addItem(label, sid)

            if sid and sid == current_id:

                current_index = combo.count() - 1

        combo.setCurrentIndex(current_index)

        combo.setEnabled(bool(self._scenes))

        if not self._scenes:

            combo.setToolTip(ui_text('Todavía no hay escenas escritas; la planificación sigue disponible.'))

        lay.addWidget(combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)

        buttons.button(QDialogButtonBox.StandardButton.Save).setText(ui_text('Guardar'))

        buttons.accepted.connect(dialog.accept)

        buttons.rejected.connect(dialog.reject)

        lay.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:

            return

        text = planned.text().strip()

        if text:

            planned_by_model[beat] = text

        else:

            planned_by_model.pop(beat, None)

        sid = str(combo.currentData() or '') if self._scenes else current_id

        if sid:

            assigned[beat] = sid

        else:

            assigned.pop(beat, None)

        self._refresh_structure_map(select_row=row)

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())



    def _assign_structure_point(self):

        row = self._selected_structure_row()

        names = self._structure_point_names()

        if row < 0 or row >= len(names):

            return

        if not self._scenes:

            QMessageBox.information(self, ui_text('Asignar escena'), ui_text('Todavía no hay escenas escritas. Usa “Planificar escena” para desarrollar este hito sin guion.'))

            return

        labels = [f"{sc.get('number', i + 1)}. {sc.get('heading', '')}" for i, sc in enumerate(self._scenes)]



        # QInputDialog.getItem() usa internamente un QComboBox, pero según el

        # estilo de Qt la barra vertical del desplegable puede quedar oculta.

        # Creamos la misma ventana de selección explícitamente para forzar una

        # barra de desplazamiento SIEMPRE visible en guiones largos.

        dialog = QInputDialog(self)

        dialog.setWindowTitle(ui_text('Asignar escena'))

        dialog.setLabelText(f'Escena para “{names[row]}”:')

        dialog.setComboBoxItems(labels)

        dialog.setComboBoxEditable(False)

        combo = dialog.findChild(QComboBox)

        if combo is not None and combo.view() is not None:

            combo.setMaxVisibleItems(24)

            combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        ok = dialog.exec() == QInputDialog.DialogCode.Accepted

        if not ok:

            return

        label = dialog.textValue()

        idx = labels.index(label)

        self._dramatic_structure.setdefault('structure_points', {})[names[row]] = str(self._scenes[idx].get('id', ''))

        self._refresh_structure_map(select_row=row)

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())



    def _clear_structure_point(self):

        row = self._selected_structure_row()

        names = self._structure_point_names()

        if row < 0 or row >= len(names):

            return

        self._dramatic_structure.setdefault('structure_points', {}).pop(names[row], None)

        model = self.structure_model.currentText()

        self._dramatic_structure.setdefault('structure_planned_scenes', {}).setdefault(model, {}).pop(names[row], None)

        self._refresh_structure_map(select_row=row)

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())



    def _add_custom_structure_point(self):

        if self.structure_model.currentText() != ui_text('Personalizado'):

            self.structure_model.setCurrentText(ui_text('Personalizado'))

        name, ok = QInputDialog.getText(self, ui_text('Nuevo hito'), ui_text('Nombre del hito estructural:'))

        name = str(name).strip()

        if not ok or not name:

            return

        custom = self._dramatic_structure.setdefault('custom_structure_points', [])

        if name not in custom:

            custom.append(name)

        self._refresh_structure_map()

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())



    def _remove_custom_structure_point(self):

        if self.structure_model.currentText() != ui_text('Personalizado'):

            return

        row = self._selected_structure_row()

        names = list(self._structure_point_names())

        if row < 0 or row >= len(names):

            return

        name = names[row]

        custom = self._dramatic_structure.setdefault('custom_structure_points', [])

        if name in custom:

            custom.remove(name)

        self._dramatic_structure.setdefault('structure_points', {}).pop(name, None)

        self._refresh_structure_map()

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())



    def _scene_label_map(self):

        return {

            str(sc.get('id', '')): f"{sc.get('number', i + 1)}. {sc.get('heading', '')}".strip()

            for i, sc in enumerate(self._scenes) if str(sc.get('id', '')).strip()

        }



    def _open_structure_development(self):

        """Ficha editable por metodología. Funciona incluso sin guion cargado."""

        model = self.structure_model.currentText()

        beats = list(self._structure_point_names())

        if not beats:

            QMessageBox.information(self, ui_text('Ficha profesional'), ui_text('Agrega al menos un hito personalizado para desarrollar la estructura.'))

            return

        dialog = QDialog(self)

        dialog.setWindowTitle(f'Ficha profesional — {model}')

        dialog.resize(1450, 720)

        layout = QVBoxLayout(dialog)

        hint = QLabel(

            'Desarrolla la estructura antes o después de escribir el guion. Los campos cambian según la metodología; '

            'el cambio de valor se calcula desde Valor inicial → Valor final.'

        )

        hint.setWordWrap(True)

        hint.setObjectName('moduleHint')

        layout.addWidget(hint)

        fields = fields_for(model)

        headers = ['Beat / etapa', 'Ubicación orientativa'] + [label for _key, label in fields] + ['Cambio de valor']

        table = EleutheraSpreadsheet(len(beats), len(headers))

        table.setHorizontalHeaderLabels(headers)

        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        table.verticalHeader().setVisible(True)

        table.setAlternatingRowColors(False)

        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)

        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.AnyKeyPressed)

        table.setWordWrap(False)

        # Las 20 metodologías usan la misma superficie de planilla: celdas

        # reales, sin QLineEdit/QComboBox permanentes ni píldoras internas.


        # Misma superficie EleutheraSpreadsheet usada por Mapa libre y las 20 estructuras.
        table.verticalHeader().setDefaultSectionSize(32)

        table.horizontalHeader().setMinimumHeight(34)

        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        table.setColumnWidth(0, 220)

        for c in range(1, len(headers)):

            table.setColumnWidth(c, 190)

        for r, beat in enumerate(beats):

            beat_item = QTableWidgetItem(beat)

            beat_item.setFlags(beat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(r, 0, beat_item)

            orientation = QTableWidgetItem(orientation_for(model, beat) or '—')

            orientation.setFlags(orientation.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(r, 1, orientation)

            data = row_data(self._dramatic_structure, model, beat)

            for c, (key, _label) in enumerate(fields, 2):

                table.setItem(r, c, QTableWidgetItem(str(data.get(key, ''))))

            change = QTableWidgetItem(value_change(data))

            change.setFlags(change.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(r, len(headers) - 1, change)

        layout.addWidget(table, 1)



        def refresh_change(row, _col):

            data = {key: (table.item(row, c).text() if table.item(row, c) else '') for c, (key, _label) in enumerate(fields, 2)}

            item = table.item(row, len(headers) - 1)

            if item:

                table.blockSignals(True)

                item.setText(value_change(data))

                table.blockSignals(False)

        table.cellChanged.connect(refresh_change)



        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)

        buttons.button(QDialogButtonBox.StandardButton.Save).setText(ui_text('Guardar ficha'))

        buttons.accepted.connect(dialog.accept)

        buttons.rejected.connect(dialog.reject)

        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:

            return

        for r, beat in enumerate(beats):

            data = row_data(self._dramatic_structure, model, beat)

            for c, (key, _label) in enumerate(fields, 2):

                data[key] = table.item(r, c).text().strip() if table.item(r, c) else ''

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())

        QMessageBox.information(self, ui_text('Ficha profesional'), ui_text('Desarrollo estructural guardado en el proyecto.'))



    def _export_structure_template(self, fmt):

        model = self.structure_model.currentText()

        beats = list(self._structure_point_names())

        if not beats:

            QMessageBox.information(self, ui_text('Exportar estructura'), ui_text('No hay hitos para exportar.'))

            return

        suffix = 'xlsx' if fmt == 'xlsx' else 'pdf'

        filename, _ = QFileDialog.getSaveFileName(

            self, ui_text('Exportar plantilla estructural'), f'{model}.{suffix}',

            'Excel (*.xlsx)' if fmt == 'xlsx' else 'PDF (*.pdf)'

        )

        if not filename:

            return

        if not filename.lower().endswith('.' + suffix):

            filename += '.' + suffix

        description = self._STRUCTURE_DESCRIPTIONS.get(model, '')

        scene_labels = self._scene_label_map()

        try:

            if fmt == 'xlsx':

                export_xlsx(filename, 'Proyecto Eleuthera', model, description, beats, self._dramatic_structure, scene_labels)

            else:

                export_pdf(filename, 'Proyecto Eleuthera', model, description, beats, self._dramatic_structure, scene_labels)

        except Exception as exc:

            QMessageBox.critical(self, ui_text('Exportar estructura'), ui_join([ui_text('No se pudo exportar:\n'), f'{exc}']))

            return

        QMessageBox.information(self, ui_text('Exportar estructura'), f'Plantilla {model} exportada correctamente.')



    def _refresh_structure_map(self, select_row=-1):

        if not hasattr(self, 'structure_table'):

            return

        names = self._structure_point_names()

        points = self._dramatic_structure.get('structure_points', {}) or {}

        model = self.structure_model.currentText()

        planned = (self._dramatic_structure.get('structure_planned_scenes', {}) or {}).get(model, {}) or {}

        scene_by_id = {str(sc.get('id', '')): (i, sc) for i, sc in enumerate(self._scenes)}

        self.structure_table.setRowCount(len(names))

        for row, name in enumerate(names):

            scene_id = str(points.get(name, '') or '')

            pair = scene_by_id.get(scene_id)

            if pair:

                idx, scene = pair

                scene_text = f"{scene.get('number', idx + 1)}. {scene.get('heading', '')}"

                planned_text = str(planned.get(name, '') or '').strip()

                if planned_text:

                    scene_text += f'  ·  Plan: {planned_text}'

                pos = f"{round(((idx + 1) / max(1, len(self._scenes))) * 100)}%"

            else:

                planned_text = str(planned.get(name, '') or '').strip()

                if planned_text:

                    scene_text = f'Planificada: {planned_text}'

                    pos = orientation_for(model, name) or '—'

                else:

                    scene_text = '— Sin asignar —'

                    pos = orientation_for(model, name) or '—'

            self.structure_table.setItem(row, 0, QTableWidgetItem(name))

            self.structure_table.setItem(row, 1, QTableWidgetItem(scene_text))

            self.structure_table.setItem(row, 2, QTableWidgetItem(pos))

        model = self.structure_model.currentText()

        if hasattr(self, 'structure_model_description'):

            self.structure_model_description.setText(self._STRUCTURE_DESCRIPTIONS.get(model, ''))

        custom = model == ui_text('Personalizado')

        self.structure_add_custom.setVisible(custom)

        self.structure_remove_custom.setVisible(custom)

        visible_by_model = self._dramatic_structure.get('structure_visible_labels', {}) or {}

        visible_labels = set(visible_by_model.get(model, []) or [])

        self.structure_timeline.set_data(

            self._scenes, names, points, self._structure_zoom, visible_labels=visible_labels, planned=planned

        )

        if select_row >= 0 and select_row < self.structure_table.rowCount():

            self.structure_table.selectRow(select_row)



    def _structure_label_visibility_changed(self, name, visible):

        name = str(name or '').strip()

        if not name:

            return

        model = self.structure_model.currentText()

        by_model = self._dramatic_structure.setdefault('structure_visible_labels', {})

        current = list(by_model.get(model, []) or [])

        if visible and name not in current:

            current.append(name)

        elif not visible and name in current:

            current.remove(name)

        by_model[model] = current

        # Redibujar únicamente el mapa; la asignación de escenas no cambia.

        self.structure_timeline.set_visible_labels(set(current))

        self.dramatic_structure_changed.emit(self.dramatic_structure_data())



    def _change_structure_zoom(self, factor):

        self._structure_zoom = max(0.55, min(3.0, self._structure_zoom * float(factor)))

        self.structure_zoom_label.setText(f'{round(self._structure_zoom * 100)}%')

        self._refresh_structure_map()



    def _toggle_structure_maximize(self):

        self._structure_maximized = not self._structure_maximized

        maximized = self._structure_maximized

        self.analysis_hint.setVisible(not maximized)

        self.tabs.tabBar().setVisible(not maximized)

        self.structure_hint.setVisible(not maximized)

        self.structure_editor.setVisible(not maximized)

        self.structure_footer.setVisible(not maximized)

        self.structure_maximize.setText(ui_text('↙ Restaurar') if maximized else ui_text('⛶ Maximizar mapa'))

        if maximized:

            self._analysis_layout.setContentsMargins(4, 4, 4, 4)

            self._analysis_layout.setSpacing(2)

            self._structure_layout.setContentsMargins(2, 2, 2, 2)

        else:

            self._analysis_layout.setContentsMargins(26, 18, 26, 24)

            self._analysis_layout.setSpacing(8)

            self._structure_layout.setContentsMargins(10, 10, 10, 10)

        QTimer.singleShot(0, self._refresh_structure_map)



    def _toggle_structure_editor_maximize(self):

        # Maximiza exclusivamente la tabla/editor de hitos. No altera la lógica

        # ni el comportamiento del botón "Maximizar mapa".

        self._structure_editor_maximized = not bool(getattr(self, '_structure_editor_maximized', False))

        maximized = self._structure_editor_maximized

        self.analysis_hint.setVisible(not maximized)

        self.tabs.tabBar().setVisible(not maximized)

        self.structure_hint.setVisible(not maximized)

        self.structure_tools_widget.setVisible(not maximized)

        self.structure_timeline_scroll.setVisible(not maximized)

        self.structure_footer.setVisible(not maximized)

        self.structure_editor.setVisible(True)

        self.structure_maximize_editor.setText(ui_text('↙ Restaurar') if maximized else ui_text('⛶ Maximizar hitos'))

        if maximized:

            self._analysis_layout.setContentsMargins(4, 4, 4, 4)

            self._analysis_layout.setSpacing(2)

            self._structure_layout.setContentsMargins(2, 2, 2, 2)

            # No fijar una altura gigante: si la tabla mide más que el área visible,

            # Qt recorta el widget completo y su scrollbar queda fuera de pantalla.

            # Con altura mínima 0 + política Expanding, ocupa exactamente el espacio

            # disponible y el scroll interno queda siempre accesible.

            self.structure_table.setMinimumHeight(0)

            self.structure_table.setMaximumHeight(16777215)

        else:

            self._analysis_layout.setContentsMargins(26, 18, 26, 24)

            self._analysis_layout.setSpacing(8)

            self._structure_layout.setContentsMargins(10, 10, 10, 10)

            self.structure_table.setMinimumHeight(190)

        QTimer.singleShot(0, self._refresh_structure_map)



    # ---------- Colores ----------

    @staticmethod

    def _automatic_color(key, salt=0):

        value = sum((i + 1) * ord(ch) for i, ch in enumerate(str(key))) + salt * 131

        hue = value % 360

        return QColor.fromHsv(hue, 155, 220)



    def _character_color(self, name):

        custom = self._markers.get('characters', {}).get(name)

        return QColor(custom) if custom and QColor(custom).isValid() else self._automatic_color(name, 7)



    def _scene_color(self, scene):

        scene_id = str(scene.get('id', ''))

        custom = self._markers.get('scenes', {}).get(scene_id)

        if custom and QColor(custom).isValid():

            return QColor(custom)

        return self._automatic_color(scene_id or scene.get('number', ''), 31)



    @staticmethod

    def _mix_colors(a, b):

        return QColor(

            (a.red() + b.red()) // 2,

            (a.green() + b.green()) // 2,

            (a.blue() + b.blue()) // 2,

        )



    def _populate_marker_targets(self):

        if not hasattr(self, 'marker_target'):

            return

        current = self.marker_target.currentData()

        self.marker_target.blockSignals(True)

        self.marker_target.clear()

        if self.marker_type.currentText() == ui_text('Personaje'):

            for name in self._all_characters():

                self.marker_target.addItem(name, name)

        else:

            for scene in self._scenes:

                label = f"{scene.get('number', '')}. {scene.get('heading', '')}"

                self.marker_target.addItem(label, str(scene.get('id', '')))

        if current:

            index = self.marker_target.findData(current)

            if index >= 0:

                self.marker_target.setCurrentIndex(index)

        self.marker_target.blockSignals(False)



    def _choose_marker_color(self):

        key = self.marker_target.currentData()

        if not key:

            return

        bucket = 'characters' if self.marker_type.currentText() == ui_text('Personaje') else 'scenes'

        existing = QColor(self._markers.get(bucket, {}).get(str(key), '#17616A'))

        color = QColorDialog.getColor(existing, self, 'Elegir color de marcador')

        if not color.isValid():

            return

        self._markers.setdefault(bucket, {})[str(key)] = color.name()

        self._markers_updated()



    def _remove_marker_color(self):

        key = self.marker_target.currentData()

        if not key:

            return

        bucket = 'characters' if self.marker_type.currentText() == ui_text('Personaje') else 'scenes'

        self._markers.setdefault(bucket, {}).pop(str(key), None)

        self._markers_updated()



    def _assign_automatic_markers(self):

        if self.marker_type.currentText() == ui_text('Personaje'):

            bucket = self._markers.setdefault('characters', {})

            for name in self._all_characters():

                bucket[name] = self._automatic_color(name, 7).name()

        else:

            bucket = self._markers.setdefault('scenes', {})

            for scene in self._scenes:

                sid = str(scene.get('id', ''))

                if sid:

                    bucket[sid] = self._automatic_color(sid, 31).name()

        self._markers_updated()



    def _script_marker_toggle(self, state):

        if self._updating_markers:

            return

        self._markers['show_in_script'] = state == Qt.CheckState.Checked.value

        self._markers_updated()



    def _clear_markers(self):

        answer = QMessageBox.question(

            self, ui_text('Quitar marcadores'),

            ui_text('¿Quitar todos los colores personalizados de personajes y escenas?')

        )

        if answer != QMessageBox.StandardButton.Yes:

            return

        self._markers['characters'] = {}

        self._markers['scenes'] = {}

        self._markers_updated()



    def _markers_updated(self):

        self._refresh_marker_table()

        self._recolor_analysis()

        self.markers_changed.emit(self.marker_data())



    def _recolor_analysis(self):

        """A color edit preserves the graph, its layout and the current selection."""

        self.character_chart.set_values([

            (name, value, self._character_color(name))

            for name, value, _ in self.character_chart.values

        ])

        self.presence_chart.colors = {

            name: self._character_color(name) for name in self.presence_chart.characters

        }

        self.presence_chart.update()

        for row in range(self.details.rowCount()):

            item = self.details.item(row, 0)

            if item:

                item.setData(Qt.ItemDataRole.DecorationRole, self._character_color(item.text()))

        scenes = {str(sc.get('id', '')): sc for sc in self._scenes}

        for node in getattr(self, '_network_nodes', []):

            kind, payload = node.data(0), node.data(1)

            if kind == 'character':

                color = self._character_color(str(payload))

            elif kind == 'scene':

                sid = str(payload[0]) if isinstance(payload, (list, tuple)) else str(payload)

                color = self._scene_color(scenes.get(sid, {'id': sid}))

            else:

                continue

            pen = node.pen(); pen.setColor(color.lighter(130)); node.setPen(pen)

            color.setAlpha(205); node.setBrush(QBrush(color))



    def _refresh_marker_table(self):

        if not hasattr(self, 'marker_table'):

            return

        rows = []

        for name, color in sorted(self._markers.get('characters', {}).items()):

            rows.append((ui_text('Personaje'), name, color))

        scene_by_id = {str(s.get('id', '')): s for s in self._scenes}

        for sid, color in self._markers.get('scenes', {}).items():

            scene = scene_by_id.get(str(sid), {})

            label = f"{scene.get('number', '')}. {scene.get('heading', '')}".strip('. ')

            rows.append((ui_text('Escena'), label or str(sid), color))

        self.marker_table.setRowCount(len(rows))

        for row, (kind, label, color_hex) in enumerate(rows):

            self.marker_table.setItem(row, 0, QTableWidgetItem(kind))

            self.marker_table.setItem(row, 1, QTableWidgetItem(label))

            color_item = QTableWidgetItem(color_hex)

            color = QColor(color_hex)

            color_item.setBackground(QBrush(color))

            color_item.setForeground(QBrush(QColor('#111111') if color.lightness() > 150 else QColor('#ffffff')))

            self.marker_table.setItem(row, 2, color_item)



    # ---------- Nodos ----------

    def _on_network_weak_toggled(self, checked):

        """Actualiza la red y confirma el resultado solo cuando el usuario activa Ocultar vínculos débiles."""

        self._refresh_network()

        if not checked:

            return

        count = int(getattr(self, '_network_hidden_weak', 0))

        if count == 0:

            message = 'No se detectaron vínculos débiles para ocultar en la red actual.'

        elif count == 1:

            message = 'Se ocultó 1 vínculo débil en la red actual.'

        else:

            message = f'Se ocultaron {count} vínculos débiles en la red actual.'

        QMessageBox.information(self, ui_text('Filtro de vínculos débiles'), message)



    def _on_network_disconnected_toggled(self, checked):

        """Actualiza la red y confirma el resultado solo cuando el usuario activa Mostrar desconectados."""

        self._refresh_network()

        if not checked:

            return

        count = int(getattr(self, '_network_disconnected_count', 0))

        if count == 0:

            message = 'No se detectaron nodos desconectados en la red actual.'

        elif count == 1:

            message = 'Se detectó 1 nodo desconectado en la red.\nSe ha mostrado en el gráfico.'

        else:

            message = f'Se detectaron {count} nodos desconectados en la red.\nSe han mostrado en el gráfico.'

        QMessageBox.information(self, ui_text('Análisis de nodos desconectados'), message)



    def _on_network_bridges_toggled(self, checked):

        """Actualiza la red y confirma el resultado solo cuando el usuario activa Puentes críticos."""

        self._refresh_network()

        if not checked:

            return

        count = int(getattr(self, '_network_bridge_count', 0))

        if count == 0:

            message = 'No se detectaron puentes críticos en la red actual.'

        elif count == 1:

            message = 'Se detectó 1 puente crítico en la red.\nSe ha resaltado en el gráfico.'

        else:

            message = f'Se detectaron {count} puentes críticos en la red.\nSe han resaltado en el gráfico.'

        QMessageBox.information(self, ui_text('Análisis de puentes críticos'), message)



    def _refresh_network(self):

        if not hasattr(self, 'network_scene'):

            return

        self.network_scene.clear()

        self._network_nodes, self._network_edges = [], []

        self._network_focus = None

        self._network_hidden_weak = 0

        self._network_bridge_count = 0

        self._network_disconnected_count = 0

        if hasattr(self, 'network_relation_info'):

            self.network_relation_info.setText(ui_text('Selecciona un nodo o una conexión para ver por qué existe esa relación.'))

        if not self._scenes:

            self.network_scene.addText('No hay escenas para analizar.')

            self._update_network_status()

            return

        mode = self.network_mode.currentIndex()

        if mode == 2:

            self._draw_character_network()

        else:

            self._draw_multilayer_network(islands=(mode == 1))

        self._finalize_network_filters()

        bounds = self.network_scene.itemsBoundingRect().adjusted(-110, -110, 110, 110)

        self.network_scene.setSceneRect(bounds)

        self._fit_network()

        self._highlight_network_search()

        self._update_network_status()



    def _finalize_network_filters(self):

        """Aplica de forma uniforme la visibilidad de nodos aislados en cualquier vista."""

        connected = set()

        for line, a, b in self._network_edges:

            if line.isVisible():

                connected.update((a, b))

        isolated = [node for node in self._network_nodes if node not in connected]

        self._network_disconnected_count = len(isolated)

        show = bool(self.network_disconnected.isChecked())

        for node in isolated:

            node.setVisible(show)



    def _update_network_status(self):

        if not hasattr(self, 'network_status'):

            return

        hidden = int(getattr(self, '_network_hidden_weak', 0))

        bridges = int(getattr(self, '_network_bridge_count', 0))

        disconnected = int(getattr(self, '_network_disconnected_count', 0))

        self.network_status.setText(

            f'{hidden} vínculos ocultos · {bridges} puentes críticos · {disconnected} desconectados'

        )



    def _network_node(self, x, y, text, kind, payload, color, radius=34, weight=1):

        radius = max(16.0, min(62.0, float(radius) + min(20.0, max(0, weight-1) * 1.7)))

        item = QGraphicsEllipseItem(x-radius, y-radius, radius*2, radius*2)

        border = QColor(color).lighter(130)

        item.setPen(QPen(border, 2.0))

        fill = QColor(color); fill.setAlpha(205)

        item.setBrush(QBrush(fill))

        item.setData(0, kind); item.setData(1, payload); item.setData(2, str(text)); item.setData(3, weight)

        item.setToolTip(f'{text}\n{weight} apariciones / conexiones')

        self.network_scene.addItem(item)

        label = QGraphicsSimpleTextItem(str(text), item)

        label.setBrush(QBrush(QColor('#f5f7fa')))

        font = label.font(); font.setPointSizeF(9.0 if kind == 'character' else 8.0); font.setBold(kind == 'character')

        label.setFont(font)

        rect = label.boundingRect(); label.setPos(x-rect.width()/2, y-radius-rect.height()-5)

        self._network_nodes.append(item)

        return item



    def _network_edge(self, a, b, color='#607d86', weight=1, payload=None):

        ax, ay = a.sceneBoundingRect().center().x(), a.sceneBoundingRect().center().y()

        bx, by = b.sceneBoundingRect().center().x(), b.sceneBoundingRect().center().y()

        line = QGraphicsLineItem(ax, ay, bx, by)

        c = QColor(color); c.setAlpha(min(210, 65 + int(weight)*25))

        line.setPen(QPen(c, min(6.0, 0.8 + float(weight)*0.48)))

        line.setZValue(-2); line.setData(0, 'edge'); line.setData(1, payload); line.setData(3, weight)

        line.setToolTip(f'{weight} coincidencia' + ('s' if weight != 1 else ''))

        self.network_scene.addItem(line); self._network_edges.append((line, a, b))

        return line



    def _network_objects_by_scene(self):

        """Elementos reales del Desglose, agrupados por scene_id; no infiere sustantivos."""

        out = {}

        excluded = {'personaje', 'personajes', 'actor', 'actores', 'reparto', 'extras'}

        for row in self._breakdown:

            sid = str(row.get('scene_id', '') or '')

            name = str(row.get('element', '') or '').strip()

            category = str(row.get('category', '') or '').strip().lower()

            if not sid or not name or category in excluded:

                continue

            out.setdefault(sid, [])

            if name not in out[sid]: out[sid].append(name)

        return out



    def _character_bridge_pairs(self):

        """Puentes (bridges) del grafo personaje-personaje mediante Tarjan, sin dependencias."""

        graph = {}

        for sc in self._scenes:

            cs = list(dict.fromkeys(self._normalized_scene_characters(sc)))

            for c in cs: graph.setdefault(c, set())

            for i,a in enumerate(cs):

                for b in cs[i+1:]: graph[a].add(b); graph[b].add(a)

        timer=[0]; disc={}; low={}; parent={}; bridges=set()

        def dfs(u):

            timer[0]+=1; disc[u]=low[u]=timer[0]

            for v in graph.get(u, ()):

                if v not in disc:

                    parent[v]=u; dfs(v); low[u]=min(low[u],low[v])

                    if low[v] > disc[u]: bridges.add(frozenset((u,v)))

                elif parent.get(u) != v: low[u]=min(low[u],disc[v])

        for u in graph:

            if u not in disc: dfs(u)

        return bridges



    def _describe_network_edge(self, edge):

        kind = edge.data(4) or ''

        payload = edge.data(1)

        weight = int(edge.data(3) or 1)

        if kind == 'character_pair' and payload:

            a,b = payload

            matches=[sc for sc in self._scenes if a in self._normalized_scene_characters(sc) and b in self._normalized_scene_characters(sc)]

            nums=', '.join(str(sc.get('number','')) for sc in matches[:12])

            extra='…' if len(matches)>12 else ''

            return f'{a} ↔ {b} · {len(matches)} escenas compartidas · Escenas: {nums}{extra}'

        if kind == 'character_location' and payload:

            a,b=payload; return ui_join([f'{a}', ui_text(' ↔ '), f'{b}', ui_text(' · coinciden en '), f'{weight}', ui_text(' escena')]) + ('s' if weight!=1 else '')

        if kind == 'scene_object' and payload:

            sid,obj=payload; sc=next((x for x in self._scenes if str(x.get('id',''))==str(sid)),{})

            return ui_join([ui_text('Escena '), f"{sc.get('number', '')}", ui_text(' ↔ '), f'{obj}', ui_text(' · elemento tomado del Desglose.')])

        if kind == 'scene_link' and payload:

            return f'Relación de escena · {weight} coincidencia' + ('s' if weight!=1 else '')

        return f'Relación · {weight} coincidencia' + ('s' if weight!=1 else '')



    def _draw_multilayer_network(self, islands=False):

        import math

        sep = self.network_separation.value() / 100.0

        scenes = self._scenes[:180]

        char_freq, loc_freq = {}, {}

        objects_by_scene = self._network_objects_by_scene()

        obj_freq = {}

        for sc in scenes:

            for c in self._normalized_scene_characters(sc): char_freq[c] = char_freq.get(c, 0) + 1

            loc = str(sc.get('location', '') or '').strip()

            if loc: loc_freq[loc] = loc_freq.get(loc, 0) + 1

            for obj in objects_by_scene.get(str(sc.get('id','')), []): obj_freq[obj] = obj_freq.get(obj, 0) + 1

        chars = [x for x,_ in sorted(char_freq.items(), key=lambda kv:(-kv[1],kv[0]))[:36]] if self.network_characters.isChecked() else []

        locs = [x for x,_ in sorted(loc_freq.items(), key=lambda kv:(-kv[1],kv[0]))[:28]] if self.network_locations.isChecked() else []

        objs = [x for x,_ in sorted(obj_freq.items(), key=lambda kv:(-kv[1],kv[0]))[:32]] if self.network_objects.isChecked() else []

        relevant=[]

        for sc in scenes:

            cs=set(self._normalized_scene_characters(sc)); loc=str(sc.get('location','') or '').strip()

            os=set(objects_by_scene.get(str(sc.get('id','')), []))

            if cs.intersection(chars) or loc in locs or os.intersection(objs): relevant.append(sc)

        if not chars and not locs and not objs and not self.network_scenes.isChecked():

            self.network_scene.addText('Activa al menos una capa para visualizar la red.'); return

        positions={}; nodes={}

        if islands:

            # Agrupa alrededor de las localizaciones más frecuentes; sin física costosa.

            anchors = locs[:12] or [ui_text('Guion')]

            cols=max(1, int(math.ceil(math.sqrt(len(anchors)))))

            for i, loc in enumerate(anchors):

                cx=(i%cols)*520*sep+280; cy=(i//cols)*430*sep+250

                if loc in locs:

                    nodes[('location',loc)] = self._network_node(cx,cy,loc,'location',loc,'#79d98c',32,loc_freq.get(loc,1)); positions[('location',loc)]=(cx,cy)

            for i,sc in enumerate(relevant):

                loc=str(sc.get('location','') or '').strip(); anchor=anchors.index(loc) if loc in anchors else i%len(anchors)

                cx=(anchor%cols)*520*sep+280; cy=(anchor//cols)*430*sep+250

                ang=(i*2.399963)% (2*math.pi); rad=(90+(i%5)*30)*sep

                if self.network_scenes.isChecked():

                    key=('scene',str(sc.get('id',''))); nodes[key]=self._network_node(cx+math.cos(ang)*rad,cy+math.sin(ang)*rad,f"E{sc.get('number','')}",'scene',(str(sc.get('id','')),int(sc.get('index',-1))),'#c56bea',17,1); positions[key]=(cx+math.cos(ang)*rad,cy+math.sin(ang)*rad)

            for j,c in enumerate(chars):

                related=[sc for sc in relevant if c in self._normalized_scene_characters(sc)]

                loc=str(related[0].get('location','') or '') if related else ''

                anchor=anchors.index(loc) if loc in anchors else j%len(anchors); cx=(anchor%cols)*520*sep+280; cy=(anchor//cols)*430*sep+250

                ang=(j*2.17)%(2*math.pi); key=('character',c); nodes[key]=self._network_node(cx+math.cos(ang)*180*sep,cy+math.sin(ang)*180*sep,c,'character',c,self._character_color(c),30,char_freq.get(c,1)); positions[key]=(cx+math.cos(ang)*180*sep,cy+math.sin(ang)*180*sep)

            for j,obj in enumerate(objs):

                related=[sc for sc in relevant if obj in objects_by_scene.get(str(sc.get('id','')), [])]

                loc=str(related[0].get('location','') or '') if related else ''

                anchor=anchors.index(loc) if loc in anchors else j%len(anchors); cx=(anchor%cols)*520*sep+280; cy=(anchor//cols)*430*sep+250

                ang=(j*2.61+0.7)%(2*math.pi); key=('object',obj); x=cx+math.cos(ang)*135*sep; y=cy+math.sin(ang)*135*sep

                nodes[key]=self._network_node(x,y,obj,'object',obj,'#e0b45c',23,obj_freq.get(obj,1)); positions[key]=(x,y)

        else:

            cx,cy=760,560

            groups=[('character',chars,560,'#5fd5e6'),('location',locs,365,'#79d98c'),('object',objs,250,'#e0b45c')]

            for kind,values,rad,basecol in groups:

                for i,val in enumerate(values):

                    ang=2*math.pi*i/max(1,len(values)) + (0.18 if kind=='location' else 0)

                    x=cx+math.cos(ang)*rad*sep; y=cy+math.sin(ang)*rad*.72*sep; key=(kind,val)

                    col=self._character_color(val) if kind=='character' else basecol

                    freq=char_freq.get(val,1) if kind=='character' else (loc_freq.get(val,1) if kind=='location' else obj_freq.get(val,1))

                    nodes[key]=self._network_node(x,y,val,kind,val,col,30,freq); positions[key]=(x,y)

            if self.network_scenes.isChecked():

                for i,sc in enumerate(relevant[:100]):

                    ang=2*math.pi*i/max(1,min(100,len(relevant))); rad=(170+(i%4)*42)*sep

                    key=('scene',str(sc.get('id',''))); x=cx+math.cos(ang)*rad; y=cy+math.sin(ang)*rad*.78

                    nodes[key]=self._network_node(x,y,f"E{sc.get('number','')}",'scene',(str(sc.get('id','')),int(sc.get('index',-1))),self._scene_color(sc),15,1); positions[key]=(x,y)

        # Relaciones escena-personaje/localización/objeto. El filtro débil funciona también con Escenas visibles:

        # se considera débil un elemento que solo aparece una vez en el guion analizado.

        if self.network_scenes.isChecked():

            for sc in relevant[:100]:

                sn=nodes.get(('scene',str(sc.get('id',''))))

                if not sn: continue

                for c in self._normalized_scene_characters(sc):

                    cn=nodes.get(('character',c))

                    if cn:

                        if self.network_weak.isChecked() and char_freq.get(c, 0) <= 1:

                            self._network_hidden_weak += 1

                        else:

                            edge=self._network_edge(sn,cn,self._character_color(c),1,(str(sc.get('id','')),c)); edge.setData(4,'scene_link')

                loc=str(sc.get('location','') or '').strip(); ln=nodes.get(('location',loc))

                if ln:

                    if self.network_weak.isChecked() and loc_freq.get(loc, 0) <= 1:

                        self._network_hidden_weak += 1

                    else:

                        edge=self._network_edge(sn,ln,'#79d98c',1,(str(sc.get('id','')),loc)); edge.setData(4,'scene_link')

                for obj in objects_by_scene.get(str(sc.get('id','')), []):

                    on=nodes.get(('object',obj))

                    if on:

                        if self.network_weak.isChecked() and obj_freq.get(obj, 0) <= 1:

                            self._network_hidden_weak += 1

                        else:

                            edge=self._network_edge(sn,on,'#e0b45c',1,(str(sc.get('id','')),obj)); edge.setData(4,'scene_object')

        else:

            weights={}

            for sc in relevant:

                loc=str(sc.get('location','') or '').strip()

                for c in self._normalized_scene_characters(sc):

                    if ('character',c) in nodes and ('location',loc) in nodes: weights[(c,loc)]=weights.get((c,loc),0)+1

            for (c,loc),w in weights.items():

                if self.network_weak.isChecked() and w <= 1:

                    self._network_hidden_weak += 1

                    continue

                edge=self._network_edge(nodes[('character',c)],nodes[('location',loc)],'#6fcf97',w,(c,loc)); edge.setData(4,'character_location')



        # Puentes críticos también son visibles en Red completa e Islas. Se superponen como líneas amarillas

        # entre personajes para que el análisis sea perceptible incluso cuando las escenas están activas.

        if self.network_bridges.isChecked() and self.network_characters.isChecked():

            bridges = self._character_bridge_pairs()

            for pair in bridges:

                names = list(pair)

                if len(names) != 2:

                    continue

                a, b = names[0], names[1]

                an, bn = nodes.get(('character',a)), nodes.get(('character',b))

                if not an or not bn:

                    continue

                edge = self._network_edge(an, bn, '#ffd166', 3, (a,b))

                edge.setData(4, 'character_pair')

                edge.setPen(QPen(QColor('#ffd166'), 3.6, Qt.PenStyle.DashLine))

                edge.setToolTip(self._describe_network_edge(edge) + '\nPuente crítico: conecta grupos que quedarían separados.')

                self._network_bridge_count += 1



    def _draw_character_network(self):

        import math

        chars=self._all_characters(); weights={}; freq={}

        for sc in self._scenes:

            present=self._normalized_scene_characters(sc)

            for c in present: freq[c]=freq.get(c,0)+1

            for i,a in enumerate(present):

                for b in present[i+1:]: weights[(a,b)]=weights.get((a,b),0)+1

        # Conserva también personajes aislados; la visibilidad se decide de forma uniforme al final.

        ranked=sorted(chars,key=lambda c:(-sum(v for pair,v in weights.items() if c in pair),c))[:42]

        bridges=self._character_bridge_pairs() if self.network_bridges.isChecked() else set()

        if not ranked: self.network_scene.addText('No se detectaron relaciones entre personajes.'); return

        sep=self.network_separation.value()/100.0; cx,cy=700,520; rx,ry=540*sep,400*sep; nodes={}

        for i,name in enumerate(ranked):

            angle=2*math.pi*i/max(1,len(ranked)); x=cx+rx*math.cos(angle); y=cy+ry*math.sin(angle)

            nodes[name]=self._network_node(x,y,name,'character',name,self._character_color(name),29,freq.get(name,1))

        for (a,b),w in weights.items():

            if a not in nodes or b not in nodes:

                continue

            if self.network_weak.isChecked() and w <= 1:

                self._network_hidden_weak += 1

                continue

            edge=self._network_edge(nodes[a],nodes[b],self._mix_colors(self._character_color(a),self._character_color(b)),w,(a,b)); edge.setData(4,'character_pair')

            if frozenset((a,b)) in bridges:

                edge.setPen(QPen(QColor('#ffd166'), max(3.2, edge.pen().widthF()+1.8)))

                edge.setToolTip(edge.toolTip() + '\nPuente crítico: conecta grupos que quedarían separados.')

                self._network_bridge_count += 1



    def _highlight_network_search(self):

        if not hasattr(self,'_network_nodes'): return

        query=self.network_search.text().strip().lower() if hasattr(self,'network_search') else ''

        for node in self._network_nodes:

            match=(not query) or query in str(node.data(2) or '').lower()

            node.setOpacity(1.0 if match else 0.16)

        if not query:

            for line,_,_ in self._network_edges: line.setOpacity(1.0)



    def _focus_network_node(self, node):

        self._network_focus=node

        if hasattr(self,'network_relation_info'):

            self.network_relation_info.setText(f'{node.data(2)} · {node.data(3) or 1} apariciones/conexiones. Se muestran sus relaciones directas.')

        connected={node}

        for line,a,b in self._network_edges:

            hit=(a is node or b is node)

            line.setOpacity(1.0 if hit else 0.06)

            if hit: connected.update((a,b))

        for n in self._network_nodes: n.setOpacity(1.0 if n in connected else 0.10)



    def _release_network_focus(self):

        self._network_focus=None

        if hasattr(self,'network_relation_info'): self.network_relation_info.setText(ui_text('Selecciona un nodo o una conexión para ver por qué existe esa relación.'))

        for n in getattr(self,'_network_nodes',[]): n.setOpacity(1.0)

        for line,_,_ in getattr(self,'_network_edges',[]): line.setOpacity(1.0)

        self._highlight_network_search()



    def _fit_network(self):

        bounds = self.network_scene.sceneRect()

        if bounds.isNull():

            return

        self.network.resetTransform()

        self.network.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)

        self._network_zoom = 1.0

        self.zoom_label.setText(ui_text('Ajustado'))



    def _zoom_network(self, factor):

        if factor <= 0:

            return

        # Avoid unusable extreme scales.

        proposed = self._network_zoom * factor

        if proposed < 0.20 or proposed > 6.0:

            return

        self.network.scale(factor, factor)

        self._network_zoom = proposed

        self.zoom_label.setText(f'{round(self._network_zoom * 100)}%')



    def _toggle_network_maximize(self):

        """Expande Nodos a toda el área de trabajo de Análisis sin quitar el zoom."""

        self._network_maximized = not bool(getattr(self, '_network_maximized', False))

        maximized = self._network_maximized



        # Igual que una vista de trabajo dedicada: se oculta el encabezado general

        # y la barra de pestañas, pero permanecen Red, Zoom y Restaurar.

        self.analysis_hint.setVisible(not maximized)

        self.tabs.tabBar().setVisible(not maximized)

        self.network_maximize.setText(ui_text('↙ Restaurar') if maximized else ui_text('⛶ Maximizar'))



        if maximized:

            self._analysis_layout.setContentsMargins(4, 4, 4, 4)

            self._analysis_layout.setSpacing(2)

            self._network_layout.setContentsMargins(2, 2, 2, 2)

            self._network_layout.setSpacing(3)

        else:

            self._analysis_layout.setContentsMargins(26, 18, 26, 24)

            self._analysis_layout.setSpacing(8)

            self._network_layout.setContentsMargins(4, 8, 4, 4)

            self._network_layout.setSpacing(6)



        # Espera a que Qt termine el relayout antes de reajustar la red al nuevo espacio.

        QTimer.singleShot(0, self._fit_network)



    def eventFilter(self, watched, event):

        if watched is self.network.viewport():

            if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier:

                self._zoom_network(1.18 if event.angleDelta().y() > 0 else 1 / 1.18)

                return True

            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:

                pos = self.network.mapToScene(event.position().toPoint())

                for hit in self.network_scene.items(pos):

                    target = hit

                    while target and target.data(0) is None:

                        target = target.parentItem()

                    if target and target.data(0) == 'edge':

                        if hasattr(self,'network_relation_info'): self.network_relation_info.setText(self._describe_network_edge(target))

                        return True

                    if target and target.data(0) in ('character', 'location', 'scene', 'object'):

                        self._focus_network_node(target)

                        return False

            if event.type() == QEvent.Type.MouseButtonDblClick:

                pos = self.network.mapToScene(event.position().toPoint())

                for item in self.network_scene.items(pos):

                    target = item

                    while target and target.data(0) is None:

                        target = target.parentItem()

                    if not target:

                        continue

                    kind, payload = target.data(0), target.data(1)

                    if kind == 'scene' and payload:

                        self.scene_open_requested.emit(str(payload[0]), int(payload[1]))

                        return True

                    if kind == 'character' and payload:

                        self.character_open_requested.emit(str(payload))

                        return True

        return super().eventFilter(watched, event)





class _AnalysisBarChart(QWidget):

    """Barras horizontales compactas para categorías de escena (INT/EXT)."""



    def __init__(self, title, parent=None):

        super().__init__(parent)

        self.title = title

        self.values = []

        self.setMinimumHeight(210)



    def set_values(self, values):

        self.values = [(str(k), int(v or 0)) for k, v in values]

        # Lienzo virtual para que el panel pueda desplazarse y maximizarse sin deformar barras.

        self.setMinimumWidth(0)

        self.setFixedHeight(max(210, 82 + len(self.values) * 64))

        self.update()



    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(QColor('#e7e7e7'))

        painter.drawText(10, 20, self.title)

        if not self.values:

            painter.setPen(QColor('#999999'))

            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Sin datos')

            return



        painter.setPen(QColor('#aeb4bc'))

        painter.drawText(10, 40, 'Distribución de escenas interiores y exteriores.')



        fm = painter.fontMetrics()

        label_w = min(max((fm.horizontalAdvance({'INT': 'INT (Interiores)', 'EXT': 'EXT (Exteriores)'}.get(label, label)) for label, _ in self.values), default=90) + 34, 220)

        left, top, right, bottom = label_w, 56, 58, 18

        w = max(1, self.width() - left - right)

        h = max(1, self.height() - top - bottom)

        row_h = h / max(1, len(self.values))

        maximum = max(1, max(v for _, v in self.values))



        palette = (QColor('#55c0cd'), QColor('#5b5bd6'), QColor('#7c858f'))

        for i, (label, value) in enumerate(self.values):

            cy = top + i * row_h + row_h / 2

            bar_h = max(14, min(30, row_h * 0.44))

            painter.setPen(QColor('#d6d6d6'))

            display = {'INT': 'INT (Interiores)', 'EXT': 'EXT (Exteriores)'}.get(label, label)

            painter.drawText(

                QRectF(12, cy - 12, left - 22, 24),

                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,

                display,

            )

            # guía tenue para facilitar la comparación

            painter.fillRect(QRectF(left, cy - bar_h / 2, w, bar_h), QColor('#292d33'))

            bw = w * value / maximum

            painter.fillRect(QRectF(left, cy - bar_h / 2, bw, bar_h), palette[i % len(palette)])

            painter.setPen(QColor('#e7e7e7'))

            painter.drawText(

                QRectF(left + bw + 7, cy - 12, right - 8, 24),

                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,

                str(value),

            )





class _AnalysisHorizontalBarChart(QWidget):

    """Barras horizontales: los nombres largos permanecen legibles."""



    def __init__(self, title, parent=None):

        super().__init__(parent)

        self.title = title

        self.values = []

        self.setMinimumHeight(220)



    def set_values(self, values):

        self.values = []

        for row in values:

            if len(row) == 3:

                label, value, color = row

            else:

                label, value = row

                color = QColor('#17616A')

            self.values.append((str(label), int(value or 0), QColor(color)))

        self.setMinimumWidth(0)

        self.setFixedHeight(max(220, 52 + len(self.values) * 32))

        self.update()



    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(QColor('#e7e7e7'))

        painter.drawText(10, 20, self.title)

        if not self.values:

            painter.setPen(QColor('#999999'))

            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Sin datos')

            return



        fm = painter.fontMetrics()

        label_w = min(max((fm.horizontalAdvance(label) for label, _, _ in self.values), default=120) + 28, 260)

        left, top, right, bottom = label_w, 38, 54, 12

        w = max(1, self.width() - left - right)

        h = max(1, self.height() - top - bottom)

        row_h = h / max(1, len(self.values))

        maximum = max(1, max(v for _, v, _ in self.values))

        for i, (label, value, color) in enumerate(self.values):

            y = top + i * row_h

            bar_h = max(8, min(20, row_h * 0.62))

            cy = y + row_h / 2

            painter.setPen(QColor('#e2e2e2'))

            painter.drawText(QRectF(12, cy-11, left-22, 22), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)

            bw = w * value / maximum

            painter.fillRect(QRectF(left, cy-bar_h/2, bw, bar_h), color)

            painter.setPen(QColor('#e7e7e7'))

            painter.drawText(QRectF(left+bw+6, cy-11, right-8, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(value))





class _AnalysisTimeline(QWidget):

    scene_open_requested = Signal(str, int)



    def __init__(self, parent=None):

        super().__init__(parent)

        self.setMouseTracking(True)

        self.scenes = []

        self.characters = []

        self.colors = {}

        self.resize(1100, 300)



    def set_data(self, scenes, characters, colors=None):

        self.scenes = list(scenes or [])

        self.characters = list(characters or [])

        self.colors = dict(colors or {})



        # Lienzo virtual: no aplastar 140+ escenas en el ancho de la ventana.

        # Cada escena recibe espacio horizontal y cada personaje su propia fila.

        virtual_width = max(1100, 190 + len(self.scenes) * 9)

        virtual_height = max(280, 62 + len(self.characters) * 34)

        self.setFixedSize(virtual_width, virtual_height)

        self.update()



    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(QColor('#e7e7e7'))

        painter.drawText(10, 20, 'Presencia de personajes a lo largo del guion')

        if not self.scenes or not self.characters:

            painter.setPen(QColor('#999999'))

            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Sin datos suficientes')

            return

        fm = painter.fontMetrics()

        left = min(max((fm.horizontalAdvance(name) for name in self.characters), default=100) + 28, 240)

        top, right, bottom = 38, 18, 24

        w = max(1, self.width() - left - right)

        h = max(1, self.height() - top - bottom)

        row_h = h / max(1, len(self.characters))

        for r, name in enumerate(self.characters):

            y = top + r*row_h + row_h/2

            color = QColor(self.colors.get(name, '#17616A'))

            painter.setPen(QColor('#d6d6d6'))

            painter.drawText(QRectF(8, y-10, left-18, 20), Qt.AlignmentFlag.AlignRight, name)

            grid = QColor('#3d4148')

            painter.setPen(grid)

            painter.drawLine(left, int(y), left+w, int(y))

            for i, scene in enumerate(self.scenes):

                present = {normalize_character_name(c) for c in scene.get('characters', [])}

                if name in present:

                    x = left + (i / max(1, len(self.scenes)-1)) * w

                    painter.setBrush(color)

                    painter.setPen(Qt.PenStyle.NoPen)

                    painter.drawEllipse(QPointF(x, y), 4.5, 4.5)





    def _layout_metrics(self):

        if not self.scenes or not self.characters:

            return None

        fm = self.fontMetrics()

        left = min(max((fm.horizontalAdvance(name) for name in self.characters), default=100) + 28, 240)

        top, right, bottom = 38, 18, 24

        w = max(1, self.width() - left - right)

        h = max(1, self.height() - top - bottom)

        row_h = h / max(1, len(self.characters))

        return left, top, right, bottom, w, h, row_h



    def _point_at(self, pos):

        metrics = self._layout_metrics()

        if not metrics:

            return None

        left, top, right, bottom, w, h, row_h = metrics

        px, py = pos.x(), pos.y()

        if px < left - 10 or px > left + w + 10 or py < top or py > top + h:

            return None

        r = int((py - top) / max(1e-6, row_h))

        if r < 0 or r >= len(self.characters):

            return None

        name = self.characters[r]

        y = top + r * row_h + row_h / 2

        if abs(py - y) > 9:

            return None

        present_norm = normalize_character_name(name)

        best = None

        best_dist = 9999

        for i, scene in enumerate(self.scenes):

            present = {normalize_character_name(c) for c in scene.get('characters', [])}

            if present_norm not in present:

                continue

            x = left + (i / max(1, len(self.scenes)-1)) * w

            dist = abs(px - x)

            if dist <= 8 and dist < best_dist:

                best = (name, scene, i)

                best_dist = dist

        return best



    def mouseMoveEvent(self, event):

        hit = self._point_at(event.position())

        if hit:

            name, scene, index = hit

            number = scene.get('number') or (index + 1)

            heading = str(scene.get('heading') or '').strip()

            text = ui_join([f'{name}', ui_text('\nEscena '), f'{number}'])

            if heading:

                text += f' — {heading}'

            QToolTip.showText(event.globalPosition().toPoint(), text, self)

            self.setCursor(Qt.CursorShape.PointingHandCursor)

        else:

            QToolTip.hideText()

            self.unsetCursor()

        super().mouseMoveEvent(event)



    def leaveEvent(self, event):

        QToolTip.hideText()

        self.unsetCursor()

        super().leaveEvent(event)



    def mouseDoubleClickEvent(self, event):

        hit = self._point_at(event.position())

        if hit:

            _name, scene, index = hit

            scene_id = str(scene.get('id', '') or '')

            if scene_id:

                self.scene_open_requested.emit(scene_id, int(scene.get('index', index)))

                event.accept()

                return

        super().mouseDoubleClickEvent(event)







class _DramaticStructureTimeline(QWidget):

    """Mapa lineal de hitos: hover identifica y clic fija/oculta la etiqueta."""



    label_visibility_changed = Signal(str, bool)



    def __init__(self, parent=None):

        super().__init__(parent)

        self._scenes = []

        self._names = ()

        self._points = {}

        self._planned = {}

        self._zoom = 1.0

        self._visible_labels = set()

        self._hit_regions = []

        self._hover_name = ''

        self.setMinimumHeight(300)

        self.setMouseTracking(True)



        # Tarjeta puramente informativa: no contiene controles interactivos.

        self._hover_card = QFrame(self)

        self._hover_card.setObjectName('structureHoverCard')

        self._hover_card.setFrameShape(QFrame.Shape.StyledPanel)

        self._hover_card.setStyleSheet(

            'QFrame#structureHoverCard {'

            ' background: #24272b; border: 1px solid #17616A; border-radius: 6px; }'

            'QLabel { border: none; background: transparent; padding: 1px; }'

        )

        card_layout = QVBoxLayout(self._hover_card)

        card_layout.setContentsMargins(10, 8, 10, 8)

        self._hover_text = QLabel('')

        self._hover_text.setWordWrap(False)

        card_layout.addWidget(self._hover_text)

        self._hover_card.hide()

        self._hover_card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)



    def set_data(self, scenes, names, points, zoom=1.0, visible_labels=None, planned=None):

        self._scenes = list(scenes or [])

        self._names = tuple(names or ())

        self._points = dict(points or {})

        self._planned = dict(planned or {})

        self._zoom = max(0.55, min(3.0, float(zoom or 1.0)))

        self._visible_labels = set(visible_labels or ())

        scene_count = max(1, len(self._scenes))

        width = max(1000, int((180 + scene_count * 28) * self._zoom))

        self.resize(width, 430)

        self.setMinimumSize(width, 430)

        self._hover_card.hide()

        self._hover_name = ''

        self.update()



    def set_visible_labels(self, labels):

        self._visible_labels = set(labels or ())

        self.update()



    def _hit_at(self, pos):

        found = None

        best_dist = 999999.0

        for region in self._hit_regions:

            x = float(region['x'])

            y1, y2 = float(region['y1']), float(region['y2'])

            dx = abs(pos.x() - x)

            if y1 - 8 <= pos.y() <= y2 + 8 and dx <= 10:

                dist = dx + abs(pos.y() - float(region['point_y'])) * 0.02

                if dist < best_dist:

                    best_dist = dist

                    found = region

        return found



    def _show_hover_card(self, region):

        self._hover_name = str(region['name'])

        scene_number = str(region['scene_number'])

        planned = str(region.get('planned', '') or '').strip()

        plan_note = str(region.get('plan_note', '') or '').strip()

        if planned:

            text = f'{self._hover_name.upper()} · PLANIFICADA — {planned}'

        else:

            text = f'{self._hover_name.upper()} · ESC. {scene_number}'

            if plan_note:

                text += f' · PLAN: {plan_note}'

        self._hover_text.setText(text)

        self._hover_card.adjustSize()

        card_w = self._hover_card.width()

        card_h = self._hover_card.height()

        anchor_x = float(region['x'])

        anchor_y = float(region['point_y'])

        x = int(anchor_x + 14)

        y = int(anchor_y - card_h / 2)

        if x + card_w > self.width() - 8:

            x = int(anchor_x - card_w - 14)

        x = max(8, min(x, self.width() - card_w - 8))

        y = max(8, min(y, self.height() - card_h - 8))

        self._hover_card.move(x, y)

        self._hover_card.raise_()

        self._hover_card.show()



    def mouseMoveEvent(self, event):

        found = self._hit_at(event.position())

        if found is not None:

            self.setCursor(Qt.CursorShape.PointingHandCursor)

            self._show_hover_card(found)

        else:

            self.unsetCursor()

            self._hover_card.hide()

            self._hover_name = ''

        super().mouseMoveEvent(event)



    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            found = self._hit_at(event.position())

            if found is not None:

                name = str(found['name'])

                make_visible = name not in self._visible_labels

                if make_visible:

                    self._visible_labels.add(name)

                else:

                    self._visible_labels.discard(name)

                self.label_visibility_changed.emit(name, make_visible)

                self.update()

                event.accept()

                return

        super().mousePressEvent(event)



    def leaveEvent(self, event):

        self._hover_card.hide()

        self._hover_name = ''

        self.unsetCursor()

        super().leaveEvent(event)



    def paintEvent(self, event):

        super().paintEvent(event)

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fg = self.palette().color(self.foregroundRole())

        muted = QColor(fg); muted.setAlpha(150)

        accent = QColor('#17616A')

        left, right = 70, max(90, self.width() - 70)

        y = 215

        p.setPen(QPen(muted, 2))

        p.drawLine(left, y, right, y)

        p.setPen(fg)

        p.drawText(left, 35, 'Estructura del guion')

        p.setPen(muted)

        p.drawText(left, 58, f'{len(self._scenes)} escenas · hover identifica · clic muestra/oculta etiqueta')

        if not self._scenes:

            p.drawText(left, y - 20, 'Planifica escenas o vincula escenas del guion a los hitos estructurales.')



        span = right - left

        for frac, text in ((1/3, '33%'), (2/3, '66%')):

            x = left + span * frac

            pen = QPen(muted, 1, Qt.PenStyle.DashLine)

            p.setPen(pen)

            p.drawLine(int(x), 105, int(x), 325)

            p.drawText(int(x) - 14, 95, text)



        scene_by_id = {str(sc.get('id', '')): (i, sc) for i, sc in enumerate(self._scenes)}

        assigned = []

        denom = max(1, len(self._names) - 1)

        for order, name in enumerate(self._names):

            pair = scene_by_id.get(str(self._points.get(name, '') or ''))

            if pair:

                assigned.append((pair[0], order, name, pair[1], False))

            elif str(self._planned.get(name, '') or '').strip():

                virtual_idx = (order / denom) * max(1, len(self._scenes) - 1) if self._scenes else order

                assigned.append((virtual_idx, order, name, {'number': 'PLAN', 'heading': self._planned.get(name, '')}, True))

        assigned.sort(key=lambda row: (row[0], row[1]))



        self._hit_regions = []

        stem_len = 62

        label_w = 250

        label_h = 34

        for stack, (idx, order, name, scene, is_planned) in enumerate(assigned):

            if self._scenes:

                x = left + (span * idx / max(1, len(self._scenes) - 1))

            else:

                x = left + (span * order / max(1, len(self._names) - 1))

            above = (stack % 2 == 0)

            stem_end = y - stem_len if above else y + stem_len

            p.setPen(QPen(accent, 2))

            p.drawLine(int(x), y, int(x), int(stem_end))

            p.setBrush(QBrush(accent))

            p.setPen(QPen(accent, 1))

            p.drawEllipse(QPointF(x, y), 6, 6)



            scene_number = scene.get('number', idx + 1)

            self._hit_regions.append({

                'x': float(x),

                'y1': float(min(y, stem_end)),

                'y2': float(max(y, stem_end)),

                'point_y': float(y),

                'name': str(name),

                'scene_number': str(scene_number),

                'planned': str(self._planned.get(name, '') or '') if is_planned else '',

                'plan_note': str(self._planned.get(name, '') or ''),

            })



            if name in self._visible_labels:

                if above:

                    rect = QRectF(x - label_w / 2, stem_end - label_h - 5, label_w, label_h)

                else:

                    rect = QRectF(x - label_w / 2, stem_end + 5, label_w, label_h)

                rect.moveLeft(max(8.0, min(rect.left(), self.width() - label_w - 8.0)))

                p.setPen(fg)

                label = f'{name} · Esc. {scene_number}'

                p.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, label)



        p.setPen(muted)

        p.drawText(left - 10, y + 28, 'Inicio')

        p.drawText(right - 22, y + 28, 'Fin')





class _TensionCurveChart(QGraphicsView):

    """Curva interactiva de tensión para guion completo y beats de una escena."""



    scene_open_requested = Signal(str, int)

    scene_selected = Signal(str)

    scene_tension_changed = Signal(str, int)

    beat_intensity_changed = Signal(int, int)

    zoom_changed = Signal(object)



    LEGACY_STAGES = (

        ('exposition', 'Exposición'),

        ('rising_action', 'Acción ascendente'),

        ('climax', 'Clímax'),

        ('falling_action', 'Acción descendente'),

        ('resolution', 'Resolución'),

    )



    def __init__(self, parent=None):

        super().__init__(parent)

        self._scenes = []

        self._structure = {}

        self._markers = {}

        self._mode = 'script'

        self._scene_id = ''

        self._zoom = 1.0

        self._auto_readable = True

        self._drag_item = None

        self._drag_kind = None

        self._drag_payload = None

        self._drag_x = 0.0

        self._drag_radius = 6.0

        self._drag_value = None

        self._drag_moved = False

        self._drag_press_pos = None

        self._drag_prev_mode = None

        self._drag_preview_item = None

        self._drag_preview_pen = QPen(QColor('#d9f0f2'), 2)

        self._plot_top = 58.0

        self._plot_bottom = 440.0

        self._scene = QGraphicsScene(self)

        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.setMinimumHeight(330)

        self.viewport().setMouseTracking(True)

        self.viewport().installEventFilter(self)



    def set_data(self, scenes, structure, markers=None, mode='script', scene_id=''):

        self._scenes = list(scenes or [])

        self._structure = dict(structure or {})

        self._markers = dict(markers or {})

        self._mode = mode

        self._scene_id = str(scene_id or '')

        self._redraw()



    def _accent_for_scene(self, scene_id, index):

        custom = self._markers.get('scenes', {}).get(str(scene_id))

        if custom and QColor(custom).isValid():

            return QColor(custom)

        return QColor.fromHsv((190 + index * 29) % 360, 150, 225)



    def _redraw(self):

        self._drag_preview_item = None

        self._scene.clear()

        if self._mode == 'scene':

            self._draw_scene_beats()

        else:

            self._draw_script_curve()

        # No encoger automáticamente todo el guion al ancho de la ventana.

        # Se ajusta por ALTURA para mantener puntos y textos legibles, dejando

        # desplazamiento horizontal cuando hay muchas escenas/beats.

        self._auto_readable = True

        self.fit_readable()



    def _draw_axes(self, width, height, left=80, top=55, bottom=70):

        plot_bottom = height - bottom

        self._plot_top = float(top)

        self._plot_bottom = float(plot_bottom)

        axis_pen = QPen(QColor('#59616a'), 1.5)

        grid_pen = QPen(QColor('#343a40'), 1)

        for value in range(0, 11, 2):

            y = top + (10 - value) * (plot_bottom - top) / 10

            grid = self._scene.addLine(left, y, width - 30, y, grid_pen)

            grid.setZValue(-20)

        y_axis = self._scene.addLine(left, top, left, plot_bottom, axis_pen)

        x_axis = self._scene.addLine(left, plot_bottom, width - 30, plot_bottom, axis_pen)

        y_axis.setZValue(90)

        x_axis.setZValue(90)

        return plot_bottom



    def _draw_script_curve(self):

        count = max(1, len(self._scenes))

        width = max(1100, 120 + count * 24)

        height = 520

        left, top = 82, 58

        bottom = self._draw_axes(width, height, left, top, 78)



        title = self._scene.addText('Curva de tensión · Guion completo')

        title.setDefaultTextColor(QColor('#eeeeee'))

        f = title.font(); f.setPointSizeF(13); f.setBold(True); title.setFont(f)

        title.setPos(left, 18)



        tension = self._structure.get('tension', {}) or {}

        plot_w = width - left - 45

        points = []

        for i, scene in enumerate(self._scenes):

            x = left + (plot_w * i / max(1, count - 1))

            scene_id = str(scene.get('id', ''))

            if scene_id in tension:

                value = max(0, min(10, int(tension.get(scene_id, 0))))

                y = top + (10 - value) * (bottom - top) / 10

                points.append(QPointF(x, y))

                color = self._accent_for_scene(scene_id, i)

                dot = QGraphicsEllipseItem(x-6, y-6, 12, 12)

                dot.setBrush(QBrush(color)); dot.setPen(QPen(color.lighter(130), 1.5))

                dot.setZValue(20)

                dot.setData(0, 'scene'); dot.setData(1, (scene_id, int(scene.get('index', i))))

                dot.setToolTip(

                    ui_join([ui_text('Escena '), f"{scene.get('number', '')}", ui_text(' · Tensión '), f'{value}', ui_text('/10\n'), f"{scene.get('heading', '')}"])

                )

                self._scene.addItem(dot)

            else:

                # Sin valoración: marca discreta bajo el eje para no inventar tensión.

                dot = QGraphicsEllipseItem(x-3, bottom+13, 6, 6)

                dot.setBrush(QBrush(QColor('#6c737a'))); dot.setPen(QPen(Qt.PenStyle.NoPen))

                dot.setZValue(20)

                dot.setData(0, 'scene'); dot.setData(1, (scene_id, int(scene.get('index', i))))

                dot.setToolTip(ui_join([ui_text('Escena '), f"{scene.get('number', '')}", ui_text(' · Sin valorar\n'), f"{scene.get('heading', '')}"]))

                self._scene.addItem(dot)



            if i == 0 or i == count - 1 or i % max(1, count // 12) == 0:

                lab = QGraphicsSimpleTextItem(str(scene.get('number', i+1)))

                lab.setBrush(QBrush(QColor('#9da4aa')))

                lab.setZValue(100)

                r = lab.boundingRect(); lab.setPos(x-r.width()/2, bottom+30)

                self._scene.addItem(lab)



        if len(points) >= 2:

            path = QPainterPath(points[0])

            for p in points[1:]:

                path.lineTo(p)

            item = self._scene.addPath(path, QPen(QColor('#17616A'), 3))

            item.setZValue(-1)



        # Reutiliza hitos antiguos de la pirámide como referencias estructurales.

        by_id = {str(sc.get('id', '')): (i, sc) for i, sc in enumerate(self._scenes)}

        stage_pen = QPen(QColor('#8f969d'), 1, Qt.PenStyle.DashLine)

        for key, label in self.LEGACY_STAGES:

            sid = str(self._structure.get(key, '') or '')

            if sid not in by_id:

                continue

            i, sc = by_id[sid]

            x = left + (plot_w * i / max(1, count - 1))

            self._scene.addLine(x, top, x, bottom, stage_pen)

            txt = QGraphicsSimpleTextItem(label)

            txt.setBrush(QBrush(QColor('#c7ccd0')))

            txt.setRotation(-35)

            txt.setPos(x+4, top+8)

            self._scene.addItem(txt)



        note = QGraphicsSimpleTextItem('Puntos bajo el eje = escenas aún sin valorar')

        note.setBrush(QBrush(QColor('#8f969d')))

        note.setPos(left, height-28)

        self._scene.addItem(note)

        self._scene.setSceneRect(15, 8, width, height)



    def _draw_scene_beats(self):

        scene = next((s for s in self._scenes if str(s.get('id', '')) == self._scene_id), None)

        beats = list((self._structure.get('beats', {}) or {}).get(self._scene_id, []) or [])

        count = max(1, len(beats))

        width = max(1000, 180 + count * 150)

        height = 520

        left, top = 82, 58

        bottom = self._draw_axes(width, height, left, top, 82)

        title_text = 'Curva de tensión · Escena'

        if scene:

            title_text += f" {scene.get('number', '')} — {scene.get('heading', '')}"

        title = self._scene.addText(title_text)

        title.setDefaultTextColor(QColor('#eeeeee'))

        f = title.font(); f.setPointSizeF(13); f.setBold(True); title.setFont(f)

        title.setPos(left, 18)



        if not beats:

            empty = self._scene.addText('Esta escena todavía no tiene beats. Usa “+ Añadir beat” para comenzar.')

            empty.setDefaultTextColor(QColor('#aeb4ba'))

            empty.setPos(left+40, 220)

            self._scene.setSceneRect(15, 8, width, height)

            return



        plot_w = width - left - 55

        pts = []

        for i, beat in enumerate(beats):

            x = left + (plot_w * i / max(1, len(beats)-1)) if len(beats) > 1 else left + plot_w/2

            value = max(0, min(10, int(beat.get('intensity', 0) or 0)))

            y = top + (10-value) * (bottom-top) / 10

            pts.append(QPointF(x, y))

            color = QColor.fromHsv((195 + i*43) % 360, 145, 225)

            dot = QGraphicsEllipseItem(x-7, y-7, 14, 14)

            dot.setBrush(QBrush(color)); dot.setPen(QPen(color.lighter(130), 1.5))

            dot.setZValue(20)

            dot.setData(0, 'beat')

            dot.setData(1, i)

            dot.setToolTip(f"{beat.get('type', 'Beat')} · {value}/10\n{beat.get('label', '')}")

            self._scene.addItem(dot)

            typ = QGraphicsSimpleTextItem(str(beat.get('type', 'Beat')))

            typ.setBrush(QBrush(QColor('#f0f0f0')))

            r = typ.boundingRect(); typ.setPos(x-r.width()/2, bottom+22)

            self._scene.addItem(typ)

            label_text = str(beat.get('label', ''))

            if len(label_text) > 28:

                label_text = label_text[:27] + '…'

            desc = QGraphicsSimpleTextItem(label_text)

            desc.setBrush(QBrush(QColor('#9da4aa')))

            r2 = desc.boundingRect(); desc.setPos(x-r2.width()/2, bottom+43)

            self._scene.addItem(desc)

        if len(pts) >= 2:

            path = QPainterPath(pts[0])

            for p in pts[1:]:

                path.lineTo(p)

            item = self._scene.addPath(path, QPen(QColor('#17616A'), 3))

            item.setZValue(-1)

        self._scene.setSceneRect(15, 8, width, height)



    def paintEvent(self, event):

        # El eje Y se pinta como HUD sobre el viewport. Así sus números no

        # forman parte de la escena desplazable y jamás desaparecen al

        # seleccionar/arrastrar un punto ni al usar el scroll horizontal.

        super().paintEvent(event)

        if self._scene.sceneRect().isNull():

            return

        painter = QPainter(self.viewport())

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(QPen(QColor('#aeb4ba')))

        font = painter.font()

        font.setPointSizeF(max(8.0, font.pointSizeF()))

        painter.setFont(font)



        for value in range(0, 11, 2):

            y_scene = self._plot_top + (10 - value) * (self._plot_bottom - self._plot_top) / 10.0

            y_view = self.mapFromScene(QPointF(0.0, y_scene)).y()

            painter.drawText(7, int(y_view + 4), str(value))



        painter.setPen(QPen(QColor('#cfd3d7')))

        top_view = self.mapFromScene(QPointF(0.0, self._plot_top)).y()

        painter.drawText(7, max(14, int(top_view - 10)), 'Tensión')

        painter.end()



    def fit_readable(self):

        """Ajusta la curva por altura, no por el ancho total del guion.



        Así una película con muchas escenas conserva puntos, ejes y etiquetas

        legibles y usa scroll horizontal en vez de convertirse en una línea.

        """

        rect = self._scene.sceneRect()

        if rect.isNull() or rect.height() <= 0:

            return

        self.resetTransform()

        available_h = max(220.0, float(self.viewport().height()) - 18.0)

        factor = available_h / float(rect.height())

        factor = max(0.55, min(2.0, factor))

        self.scale(factor, factor)

        self._zoom = factor

        self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())

        self.zoom_changed.emit(self._zoom)



    def fit_chart(self):

        # "Ajustar" sí muestra deliberadamente la curva completa.

        if self._scene.sceneRect().isNull():

            return

        self._auto_readable = False

        self.resetTransform()

        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

        self._zoom = 1.0

        self.zoom_changed.emit(None)



    def zoom_by(self, factor):

        self._auto_readable = False

        proposed = self._zoom * factor

        if proposed < 0.25 or proposed > 6.0:

            return

        self.scale(factor, factor)

        self._zoom = proposed

        self.zoom_changed.emit(self._zoom)



    def _hit_curve_point(self, viewport_pos):

        scene_pos = self.mapToScene(viewport_pos.toPoint())

        for item in self._scene.items(scene_pos):

            target = item

            while target and target.data(0) is None:

                target = target.parentItem()

            if target and target.data(0) in ('scene', 'beat'):

                return target

        return None



    def _value_from_scene_y(self, y):

        top = float(self._plot_top)

        bottom = float(self._plot_bottom)

        y = max(top, min(bottom, float(y)))

        if bottom <= top:

            return 0, y

        raw = 10.0 - ((y - top) * 10.0 / (bottom - top))

        value = max(0, min(10, int(round(raw))))

        snapped_y = top + (10 - value) * (bottom - top) / 10.0

        return value, snapped_y



    def eventFilter(self, watched, event):

        if watched is self.viewport():

            if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier:

                self.zoom_by(1.18 if event.angleDelta().y() > 0 else 1 / 1.18)

                return True



            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:

                target = self._hit_curve_point(event.position())

                if target is not None:

                    kind = str(target.data(0))

                    payload = target.data(1)

                    self._drag_item = target

                    self._drag_kind = kind

                    self._drag_payload = payload

                    rect = target.rect() if hasattr(target, 'rect') else QRectF()

                    scene_rect = target.sceneBoundingRect()

                    self._drag_radius = max(3.0, scene_rect.width() / 2.0)

                    self._drag_x = scene_rect.center().x()

                    self._drag_value = None

                    self._drag_moved = False

                    self._drag_press_pos = event.position()

                    # Mientras se arrastra un punto desactivamos completamente el

                    # ScrollHandDrag de QGraphicsView. Evita que Qt intente mover

                    # simultáneamente el viewport y el punto.

                    self._drag_prev_mode = self.dragMode()

                    self.setDragMode(QGraphicsView.DragMode.NoDrag)

                    # El clic simple NO cambia la escena seleccionada ni fuerza

                    # un repintado externo. Solo prepara el posible drag vertical.

                    # La navegación de escena queda para el doble clic.

                    self.viewport().setCursor(Qt.CursorShape.SizeVerCursor)

                    return True



            if event.type() == QEvent.Type.MouseMove and self._drag_item is not None:

                # Un clic normal suele producir 1–2 px de jitter. No lo tratamos

                # como drag para evitar guardar/redibujar la curva por accidente.

                if not self._drag_moved and self._drag_press_pos is not None:

                    dy = abs(float(event.position().y() - self._drag_press_pos.y()))

                    if dy < 4.0:

                        return True

                    self._drag_moved = True



                # IMPORTANTE: no movemos físicamente el punto real. El mouse se

                # convierte a coordenadas de ESCENA con mapToScene(), calculamos

                # únicamente la tensión Y y mostramos un punto PREVIEW temporal

                # con la X original bloqueada. Al soltar se guarda el valor y el

                # gráfico se redibuja desde los datos. Así no se mezclan las

                # coordenadas del viewport con las del QGraphicsScene.

                pos = self.mapToScene(event.position().toPoint())

                value, snapped_y = self._value_from_scene_y(pos.y())

                radius = self._drag_radius

                if self._drag_preview_item is None:

                    preview = QGraphicsEllipseItem(

                        self._drag_x - radius, snapped_y - radius,

                        radius * 2, radius * 2

                    )

                    preview.setBrush(QBrush(QColor('#17616A')))

                    preview.setPen(self._drag_preview_pen)

                    preview.setZValue(250)

                    self._scene.addItem(preview)

                    self._drag_preview_item = preview

                else:

                    self._drag_preview_item.setRect(

                        self._drag_x - radius, snapped_y - radius,

                        radius * 2, radius * 2

                    )

                self._drag_value = value

                QToolTip.showText(event.globalPosition().toPoint(), f'Tensión: {value}/10', self)

                return True



            # Hover explícito sobre los puntos. En QGraphicsView el tooltip nativo

            # puede perderse al usar el eventFilter para drag/zoom, así que lo

            # mostramos nosotros. En Guion completo indica claramente la escena.

            if event.type() == QEvent.Type.MouseMove and self._drag_item is None:

                target = self._hit_curve_point(event.position())

                if target is not None:

                    tip = target.toolTip()

                    if tip:

                        QToolTip.showText(event.globalPosition().toPoint(), tip, self)

                    if target.data(0) == 'scene':

                        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

                    else:

                        self.viewport().setCursor(Qt.CursorShape.SizeVerCursor)

                else:

                    QToolTip.hideText()

                    self.viewport().unsetCursor()

                return False



            if event.type() == QEvent.Type.Leave:

                QToolTip.hideText()

                self.viewport().unsetCursor()



            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton and self._drag_item is not None:

                kind = self._drag_kind

                payload = self._drag_payload

                moved = self._drag_moved

                value = self._drag_value

                self._drag_item = None

                self._drag_kind = None

                self._drag_payload = None

                self._drag_value = None

                self._drag_moved = False

                self._drag_press_pos = None

                if self._drag_preview_item is not None:

                    try:

                        self._scene.removeItem(self._drag_preview_item)

                    except RuntimeError:

                        pass

                    self._drag_preview_item = None

                if self._drag_prev_mode is not None:

                    self.setDragMode(self._drag_prev_mode)

                else:

                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

                self._drag_prev_mode = None

                self.viewport().unsetCursor()

                QToolTip.hideText()

                if moved and value is not None:

                    if kind == 'scene':

                        scene_id, _index = payload

                        self.scene_tension_changed.emit(str(scene_id), int(value))

                    elif kind == 'beat':

                        self.beat_intensity_changed.emit(int(payload), int(value))

                return True



            if event.type() == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:

                target = self._hit_curve_point(event.position())

                if target is not None and target.data(0) == 'scene':

                    scene_id, index = target.data(1)

                    self.scene_open_requested.emit(str(scene_id), int(index))

                    return True



        return super().eventFilter(watched, event)



