from ui_i18n import ui_text, ui_join
from eleuthera_spreadsheet import EleutheraSpreadsheet, EleutheraCellDelegate, BORDER_ROLE
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QAction, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFileDialog, QFrame, QGraphicsItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QRadioButton, QVBoxLayout, QWidget, QInputDialog, QColorDialog, QMenu, QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget, QComboBox, QLineEdit, QApplication, QSpinBox, QStyledItemDelegate,
)


class WorkspaceModeDialog(QDialog):
    mode_selected = Signal(str)

    def __init__(self, current='standard', parent=None):
        super().__init__(parent)
        self.setWindowTitle(ui_text('Bienvenido a Eleuthera Cinema Suite'))
        self.setMinimumWidth(720)
        layout = QVBoxLayout(self)
        title = QLabel(ui_text('Elige tu espacio de trabajo'))
        title.setStyleSheet('font-family: Georgia; font-size: 20pt; font-weight: 700; color: #7b2638;')
        hint = QLabel(ui_text('Ambos modos pertenecen al mismo programa. Puedes cambiar después sin perder información.'))
        hint.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(hint)
        cards = QHBoxLayout(); self.group = QButtonGroup(self)
        descriptions = {
            'standard': ('Modo estándar', 'Para escribir y organizar sin configuraciones complejas.\n\n• Editor y dictado\n• Mapa de tramas\n• Desglose simplificado\n• Presupuesto básico\n• PDF, TXT y Fountain'),
            'professional': ('Modo profesional', 'Para producciones con planificación detallada.\n\n• FDX y revisiones\n• Desglose por departamentos\n• Plantillas Excel\n• Presupuesto avanzado\n• Mapa de tramas completo'),
        }
        for key, (heading, body) in descriptions.items():
            card = QFrame(); card.setFrameShape(QFrame.Shape.StyledPanel)
            box = QVBoxLayout(card); radio = QRadioButton(heading); radio.setStyleSheet('font-size: 14pt; font-weight: 700;')
            radio.setProperty('mode', key); radio.setChecked(key == current); self.group.addButton(radio)
            text = QLabel(body); text.setWordWrap(True); text.setMinimumHeight(190)
            box.addWidget(radio); box.addWidget(text); cards.addWidget(card)
        layout.addLayout(cards)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(ui_text('Continuar'))
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def selected_mode(self):
        button = self.group.checkedButton()
        return button.property('mode') if button else 'standard'


class BeatCard(QGraphicsRectItem):
    COLORS = {ui_text('Principal'): '#f5d7dd', ui_text('Subtrama'): '#d9e8f5', ui_text('Personaje'): '#e1efd8', ui_text('Giro'): '#f8e5b8'}
    MIN_W, MIN_H = 170, 110

    def __init__(self, title='Nuevo beat', lane=ui_text('Principal'), x=0, y=0, scene_id=None, scene_label='', color=None,
                 width=240, height=145, content='', title_color='#111111', text_color='#222222'):
        super().__init__(0, 0, max(self.MIN_W, float(width or 240)), max(self.MIN_H, float(height or 145)))
        self.lane = lane
        self.scene_id = scene_id
        self.scene_label = scene_label or ''
        self.card_color = color or self.COLORS.get(lane, '#eeeeee')
        self.title_color = title_color or '#111111'
        self.text_color = text_color or '#222222'
        self._resizing = False
        self._resize_origin = None
        self._start_rect = None
        self.setBrush(QBrush(QColor(self.card_color)))
        self.setPen(QPen(QColor('#7b2638'), 2))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        # Título y contenido son campos independientes: el mapa sigue siendo completamente libre.
        self.title_text = QGraphicsTextItem(title, self)
        self.title_text.setDefaultTextColor(QColor(self.title_color))
        title_font = QFont(self.title_text.font()); title_font.setBold(True); title_font.setPointSizeF(max(10.0, title_font.pointSizeF()))
        self.title_text.setFont(title_font)
        self.title_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

        self.body_text = QGraphicsTextItem(content or '', self)
        self.body_text.setDefaultTextColor(QColor(self.text_color))
        self.body_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

        # Alias de compatibilidad con código/proyectos anteriores que esperaban card.text.
        self.text = self.title_text
        self.link_text = QGraphicsTextItem(self)
        self.link_text.setDefaultTextColor(QColor('#17616A'))
        self.update_link_text()
        self._layout_text()
        self.setPos(x, y)

    def _layout_text(self):
        r = self.rect(); usable = max(90, r.width() - 20)
        self.title_text.setTextWidth(usable); self.title_text.setPos(10, 7)
        title_h = max(28, self.title_text.boundingRect().height())
        self.body_text.setTextWidth(usable); self.body_text.setPos(10, 8 + title_h)
        self.link_text.setTextWidth(usable)
        self.link_text.setPos(10, max(72, r.height() - 34))

    def _resize_zone(self, pos):
        r = self.rect()
        return pos.x() >= r.width() - 16 and pos.y() >= r.height() - 16

    def hoverMoveEvent(self, event):
        self.setCursor(Qt.CursorShape.SizeFDiagCursor if self._resize_zone(event.pos()) else Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor(); super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._resize_zone(event.pos()):
            self._resizing = True; self._resize_origin = event.scenePos(); self._start_rect = self.rect()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.scenePos() - self._resize_origin
            self.setRect(0, 0, max(self.MIN_W, self._start_rect.width()+delta.x()), max(self.MIN_H, self._start_rect.height()+delta.y()))
            self._layout_text(); event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False; self._resize_origin = None; self._start_rect = None; event.accept(); return
        super().mouseReleaseEvent(event)

    def update_link_text(self):
        self.link_text.setPlainText(('↳ ' + self.scene_label) if self.scene_id and self.scene_label else '')

    def set_scene_link(self, scene_id=None, scene_label=''):
        self.scene_id = scene_id; self.scene_label = scene_label or ''; self.update_link_text()

    def set_card_color(self, color):
        if color:
            self.card_color = color; self.setBrush(QBrush(QColor(color)))

    def set_title_color(self, color):
        if color:
            self.title_color = color; self.title_text.setDefaultTextColor(QColor(color))

    def set_text_color(self, color):
        if color:
            self.text_color = color; self.body_text.setDefaultTextColor(QColor(color))

    def data_dict(self):
        r = self.rect()
        return {'title': self.title_text.toPlainText(), 'content': self.body_text.toPlainText(), 'lane': self.lane,
                'x': self.x(), 'y': self.y(), 'scene_id': self.scene_id, 'scene_label': self.scene_label,
                'color': self.card_color, 'title_color': self.title_color, 'text_color': self.text_color,
                'width': r.width(), 'height': r.height()}


class _SpreadsheetCellDelegate(QStyledItemDelegate):
    """Editor plano integrado a la celda, igual al comportamiento de las tablas clásicas de Eleuthera."""

    def initStyleOption(self, option, index):
        # Plantilla libre usa este delegate propio (no EleutheraCellDelegate).
        # Fijar ElideNone aquí es necesario porque QStyledItemDelegate.paint()
        # reinicializa la opción antes de dibujar; así no reaparece "...".
        super().initStyleOption(option, index)
        option.textElideMode = Qt.TextElideMode.ElideNone

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

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        color = index.data(BORDER_ROLE)
        if color:
            painter.save()
            painter.setPen(QPen(QColor(str(color)), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
            painter.restore()


class FreeSpreadsheet(QTableWidget):
    """Hoja libre: edición y pegado de rangos sin imponer estructura narrativa."""
    def __init__(self, rows, columns, parent=None):
        super().__init__(rows, columns, parent)
        # Reutiliza el mismo lenguaje de edición plana de las tablas clásicas:
        # el editor ocupa toda la celda y nunca aparece como una "pastilla" redondeada.
        self.setItemDelegate(_SpreadsheetCellDelegate(self))

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            ranges = self.selectedRanges()
            if ranges:
                rg = ranges[0]; lines = []
                for r in range(rg.topRow(), rg.bottomRow() + 1):
                    vals = []
                    for c in range(rg.leftColumn(), rg.rightColumn() + 1):
                        item = self.item(r, c); vals.append(item.text() if item else '')
                    lines.append('\t'.join(vals))
                QApplication.clipboard().setText('\n'.join(lines)); return
        if event.matches(QKeySequence.StandardKey.Paste):
            text = QApplication.clipboard().text()
            if text:
                start_row = max(0, self.currentRow()); start_col = max(0, self.currentColumn())
                rows = text.rstrip('\n').splitlines()
                matrix = [row.split('\t') for row in rows]
                need_rows = start_row + len(matrix)
                need_cols = start_col + max((len(row) for row in matrix), default=0)
                if need_rows > self.rowCount(): self.setRowCount(need_rows)
                if need_cols > self.columnCount(): self.setColumnCount(need_cols)
                for rr, row in enumerate(matrix):
                    for cc, value in enumerate(row):
                        item = self.item(start_row + rr, start_col + cc) or QTableWidgetItem()
                        item.setText(value); self.setItem(start_row + rr, start_col + cc, item)
                parent = self.parent()
                while parent is not None:
                    if hasattr(parent, '_refresh_sheet_headers'):
                        parent._refresh_sheet_headers(); break
                    parent = parent.parent()
                return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selectedItems():
            for item in self.selectedItems(): item.setText('')
            return
        super().keyPressEvent(event)


class _TemplateCellDelegate(EleutheraCellDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Mostrar titulo y contenido sin elipsis por saltos de linea ocultos.
        # Solo cambia la presentacion; el texto del modelo permanece intacto.
        option.text = option.text.replace('\r\u2028', ' ').replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ').replace('\u2028', ' ').replace('\u2029', ' ')


class StoryMapPage(QFrame):
    scene_open_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName('workspace'); self._scenes = []
        self._template_rows, self._template_cols = 100, 52
        layout = QVBoxLayout(self); layout.setContentsMargins(30, 25, 30, 28)
        self.mode_hint = QLabel(ui_text('Mapa libre: crea, mueve, redimensiona y colorea tarjetas aunque todavía no exista un guion. Vincular una escena es opcional.'))
        self.mode_hint.setObjectName('moduleHint'); self.mode_hint.setWordWrap(True)

        # Barra principal: primero el modo de trabajo, después las acciones.
        tools = QHBoxLayout(); tools.setSpacing(8)
        self.map_mode_btn = QPushButton(ui_text('Mapa libre')); self.template_mode_btn = QPushButton(ui_text('Plantilla'))
        for button in (self.map_mode_btn, self.template_mode_btn):
            button.setCheckable(True); button.setMinimumWidth(112)
        self.map_mode_btn.clicked.connect(lambda: self._set_mode(0)); self.template_mode_btn.clicked.connect(lambda: self._set_mode(1))
        tools.addWidget(self.map_mode_btn); tools.addWidget(self.template_mode_btn); tools.addSpacing(14)

        self.add_button = QPushButton('+ Añadir ▾'); add_menu = QMenu(self.add_button)
        for label, lane, shortcut in (('Beat principal', ui_text('Principal'), 'Alt+1'), (ui_text('Subtrama'), ui_text('Subtrama'), 'Alt+2'),
                                      (ui_text('Personaje'), ui_text('Personaje'), 'Alt+3'), ('Punto de giro', ui_text('Giro'), 'Alt+4'),
                                      ('Personalizado', 'Personalizado', 'Alt+5')):
            action = add_menu.addAction(label); action.setShortcut(QKeySequence(shortcut)); action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(lambda checked=False, value=lane: self.add_card(value)); self.addAction(action)
        self.add_button.setMenu(add_menu); tools.addWidget(self.add_button)

        self.color_button = QPushButton(ui_text('Color…') + ' ▾'); color_menu = QMenu(self.color_button)
        for label, callback, shortcut in (('Color de tarjeta…', self.change_selected_color, 'Alt+C'), ('Color del título…', self.change_selected_title_color, 'Alt+T'),
                                          ('Color del texto…', self.change_selected_text_color, 'Alt+X'), ('Restablecer colores', self.reset_selected_colors, 'Alt+R')):
            action = color_menu.addAction(ui_text(label)); action.setShortcut(QKeySequence(shortcut)); action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(callback); self.addAction(action)
        self.color_button.setMenu(color_menu); tools.addWidget(self.color_button)

        self.more_button = QPushButton(ui_text('Más') + ' ▾'); more_menu = QMenu(self.more_button)
        for label, callback, shortcut in (('Vincular escena…', self.link_selected, 'Alt+L'), ('Desvincular', self.unlink_selected, 'Alt+U'),
                                          ('Abrir escena', self.open_selected_scene, 'Alt+O'), ('Quitar seleccionados', self.remove_selected, 'Alt+Delete')):
            action = more_menu.addAction(ui_text(label)); action.setShortcut(QKeySequence(shortcut)); action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(callback); self.addAction(action)
        self.more_button.setMenu(more_menu); tools.addWidget(self.more_button)

        self.new_sheet_btn = QPushButton(ui_text('Nueva plantilla')); self.new_sheet_btn.clicked.connect(self.new_template); tools.addWidget(self.new_sheet_btn)
        self.insert_card_btn = QPushButton(ui_text('Añadir tarjeta a celda…')); self.insert_card_btn.clicked.connect(self.insert_card_into_template); tools.addWidget(self.insert_card_btn)
        self.insert_all_cards_btn = QPushButton(ui_text('Agregar todo a plantilla')); self.insert_all_cards_btn.clicked.connect(self.insert_all_cards_into_template); tools.addWidget(self.insert_all_cards_btn)
        self.export_xlsx_btn = QPushButton(ui_text('Exportar Excel')); self.export_xlsx_btn.clicked.connect(self.export_template_excel); tools.addWidget(self.export_xlsx_btn)
        tools.addStretch()
        layout.addLayout(tools)
        layout.addWidget(self.mode_hint)

        self.scene = QGraphicsScene(self); self.scene.setSceneRect(-1200, -800, 2400, 1600)
        self.view = QGraphicsView(self.scene); self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.stack = QStackedWidget(); self.stack.addWidget(self.view)

        self.sheet_page = QWidget(); sheet_page = self.sheet_page; sheet_layout = QVBoxLayout(sheet_page); sheet_layout.setContentsMargins(0, 0, 0, 0)
        self.sheet_format_bar = QWidget(); format_tools = QHBoxLayout(self.sheet_format_bar); format_tools.setContentsMargins(0, 0, 0, 0); format_tools.setSpacing(6)
        bg_btn = QPushButton(ui_text('Fondo…')); bg_btn.clicked.connect(self.format_sheet_background); format_tools.addWidget(bg_btn)
        fg_btn = QPushButton(ui_text('Texto…')); fg_btn.clicked.connect(self.format_sheet_text_color); format_tools.addWidget(fg_btn)
        self.bold_btn = QPushButton('B'); self.bold_btn.setCheckable(True); self.bold_btn.setMaximumWidth(38); self.bold_btn.clicked.connect(self.format_sheet_bold); format_tools.addWidget(self.bold_btn)
        self.italic_btn = QPushButton('I'); self.italic_btn.setCheckable(True); self.italic_btn.setMaximumWidth(38); self.italic_btn.clicked.connect(self.format_sheet_italic); format_tools.addWidget(self.italic_btn)
        self.font_size = QSpinBox(); self.font_size.setRange(7, 48); self.font_size.setValue(10); self.font_size.setPrefix(ui_text('Tamaño ')); self.font_size.valueChanged.connect(self.format_sheet_font_size); format_tools.addWidget(self.font_size)
        align_btn = QPushButton(ui_text('Alinear') + ' ▾'); align_menu = QMenu(align_btn)
        for label, alignment in ((ui_text('Izquierda'), Qt.AlignmentFlag.AlignLeft), (ui_text('Centro'), Qt.AlignmentFlag.AlignHCenter), (ui_text('Derecha'), Qt.AlignmentFlag.AlignRight)):
            act = align_menu.addAction(label); act.triggered.connect(lambda checked=False, a=alignment: self.format_sheet_alignment(a))
        align_btn.setMenu(align_menu); format_tools.addWidget(align_btn)
        border_btn = QPushButton(ui_text('Bordes…')); border_btn.clicked.connect(self.format_sheet_borders); format_tools.addWidget(border_btn)
        merge_btn = QPushButton(ui_text('Combinar')); merge_btn.clicked.connect(self.merge_sheet_cells); format_tools.addWidget(merge_btn)
        unmerge_btn = QPushButton(ui_text('Separar')); unmerge_btn.clicked.connect(self.unmerge_sheet_cells); format_tools.addWidget(unmerge_btn)
        reset_btn = QPushButton(ui_text('Limpiar formato')); reset_btn.clicked.connect(self.reset_sheet_format); format_tools.addWidget(reset_btn)
        row_menu_btn = QPushButton(ui_text('Filas/columnas') + ' ▾'); row_menu = QMenu(row_menu_btn)
        for label, callback in ((ui_text('Insertar fila'), self.insert_sheet_row), (ui_text('Eliminar fila'), self.delete_sheet_row), (ui_text('Insertar columna'), self.insert_sheet_column), (ui_text('Eliminar columna'), self.delete_sheet_column)):
            act = row_menu.addAction(label); act.triggered.connect(callback)
        row_menu_btn.setMenu(row_menu); format_tools.addWidget(row_menu_btn)
        format_tools.addStretch()
        self.sheet_maximize_btn = QPushButton(ui_text('⛶ Maximizar hoja')); self.sheet_maximize_btn.clicked.connect(self.toggle_sheet_maximize); format_tools.addWidget(self.sheet_maximize_btn)
        sheet_layout.addWidget(self.sheet_format_bar)
        self.sheet = EleutheraSpreadsheet(self._template_rows, self._template_cols)
        self.sheet.setItemDelegate(_TemplateCellDelegate(self.sheet))
        self.sheet.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.sheet.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.sheet.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.sheet.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        hheader = self.sheet.horizontalHeader(); vheader = self.sheet.verticalHeader()
        hheader.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        vheader.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hheader.setStretchLastSection(False); hheader.setMinimumSectionSize(55); hheader.setDefaultSectionSize(110)
        vheader.setMinimumSectionSize(22); vheader.setDefaultSectionSize(28)
        # Motor común EleutheraSpreadsheet: hoja clara dentro del tema oscuro.
        self._sheet_maximized = False
        self._refresh_sheet_headers()
        sheet_layout.addWidget(self.sheet, 1); self.stack.addWidget(sheet_page); layout.addWidget(self.stack, 1)
        self._set_mode(0)

    def _refresh_sheet_headers(self):
        # La plantilla es una hoja libre: la cuadrícula visible NO depende de las celdas con datos.
        for c in range(self.sheet.columnCount()):
            self.sheet.setHorizontalHeaderItem(c, QTableWidgetItem(self._column_name(c)))
        for r in range(self.sheet.rowCount()):
            self.sheet.setVerticalHeaderItem(r, QTableWidgetItem(str(r + 1)))
        for c in range(self.sheet.columnCount()):
            if self.sheet.columnWidth(c) < 55:
                self.sheet.setColumnWidth(c, 110)

    @staticmethod
    def _column_name(index):
        name = ''; n = index + 1
        while n:
            n, rem = divmod(n - 1, 26); name = chr(65 + rem) + name
        return name

    @staticmethod
    def _cell_coords(ref):
        import re
        m = re.fullmatch(r'\s*([A-Za-z]+)(\d+)\s*', ref or '')
        if not m: return None
        col = 0
        for ch in m.group(1).upper(): col = col * 26 + ord(ch) - 64
        return int(m.group(2)) - 1, col - 1

    def _set_mode(self, index):
        self.stack.setCurrentIndex(index)
        self.map_mode_btn.setChecked(index == 0); self.template_mode_btn.setChecked(index == 1)
        self.add_button.setVisible(index == 0); self.color_button.setVisible(index == 0); self.more_button.setVisible(index == 0)
        self.new_sheet_btn.setVisible(index == 1); self.insert_card_btn.setVisible(index == 1); self.export_xlsx_btn.setVisible(index == 1)
        self.insert_all_cards_btn.setVisible(index == 1)
        self.mode_hint.setText(ui_text('Mapa libre: crea, mueve, redimensiona y colorea tarjetas aunque todavía no exista un guion. Vincular una escena es opcional.') if index == 0 else ui_text('Plantilla: hoja libre estilo Excel integrada en Eleuthera. Escribe, formatea, combina celdas y exporta sin salir del programa.'))

    def toggle_sheet_maximize(self):
        self._sheet_maximized = not self._sheet_maximized
        # En modo maximizado conservamos la barra de formato y la hoja; ocultamos navegación auxiliar.
        self.mode_hint.setVisible(not self._sheet_maximized)
        self.map_mode_btn.setVisible(not self._sheet_maximized)
        self.template_mode_btn.setVisible(not self._sheet_maximized)
        self.new_sheet_btn.setVisible(not self._sheet_maximized)
        self.insert_card_btn.setVisible(not self._sheet_maximized)
        self.insert_all_cards_btn.setVisible(not self._sheet_maximized)
        self.export_xlsx_btn.setVisible(not self._sheet_maximized)
        self.sheet_maximize_btn.setText(ui_text('⛶ Restaurar hoja') if self._sheet_maximized else ui_text('⛶ Maximizar hoja'))

    def insert_sheet_row(self):
        row = self.sheet.currentRow() if self.sheet.currentRow() >= 0 else self.sheet.rowCount()
        self.sheet.insertRow(row); self._refresh_sheet_headers()

    def delete_sheet_row(self):
        row = self.sheet.currentRow()
        if row >= 0 and self.sheet.rowCount() > 1: self.sheet.removeRow(row); self._refresh_sheet_headers()

    def insert_sheet_column(self):
        col = self.sheet.currentColumn() if self.sheet.currentColumn() >= 0 else self.sheet.columnCount()
        self.sheet.insertColumn(col); self._refresh_sheet_headers()

    def delete_sheet_column(self):
        col = self.sheet.currentColumn()
        if col >= 0 and self.sheet.columnCount() > 1: self.sheet.removeColumn(col); self._refresh_sheet_headers()

    def _selected_sheet_items(self):
        return self.sheet.selected_items_including_empty()

    def format_sheet_background(self):
        items = self._selected_sheet_items()
        if not items: return
        initial = items[0].background().color() if items[0].background().style() != Qt.BrushStyle.NoBrush else QColor('#ffffff')
        color = QColorDialog.getColor(initial, self, ui_text('Fondo de celda'))
        if color.isValid():
            for item in items: item.setBackground(QBrush(color))

    def format_sheet_text_color(self):
        items = self._selected_sheet_items()
        if not items: return
        color = QColorDialog.getColor(items[0].foreground().color(), self, ui_text('Color del texto'))
        if color.isValid():
            for item in items: item.setForeground(QBrush(color))

    def format_sheet_bold(self, checked):
        for item in self._selected_sheet_items():
            font = item.font(); font.setBold(bool(checked)); item.setFont(font)

    def format_sheet_italic(self, checked):
        for item in self._selected_sheet_items():
            font = item.font(); font.setItalic(bool(checked)); item.setFont(font)

    def format_sheet_font_size(self, value):
        for item in self._selected_sheet_items():
            font = item.font(); font.setPointSize(int(value)); item.setFont(font)

    def format_sheet_alignment(self, horizontal):
        for item in self._selected_sheet_items(): item.setTextAlignment(horizontal | Qt.AlignmentFlag.AlignVCenter)

    def format_sheet_borders(self):
        color = QColorDialog.getColor(QColor('#707070'), self, ui_text('Color de borde'))
        if not color.isValid(): return
        # El delegate dibuja el borde en pantalla y el mismo dato se conserva para exportarlo a Excel.
        for item in self._selected_sheet_items(): item.setData(BORDER_ROLE, color.name())
        self.sheet.viewport().update()

    def merge_sheet_cells(self):
        # Una sola celda no genera warning ni span 1x1.
        self.sheet.merge_selection()

    def unmerge_sheet_cells(self):
        self.sheet.unmerge_selection()

    def reset_sheet_format(self):
        for item in self._selected_sheet_items():
            item.setBackground(QBrush()); item.setForeground(QBrush()); item.setFont(QFont()); item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter); item.setData(BORDER_ROLE, None)

    def new_template(self):
        if any(self.sheet.item(r, c) and self.sheet.item(r, c).text() for r in range(self.sheet.rowCount()) for c in range(self.sheet.columnCount())):
            if QMessageBox.question(self, ui_text('Nueva plantilla'), ui_text('¿Vaciar la plantilla actual y comenzar una nueva?')) != QMessageBox.StandardButton.Yes: return
        self.sheet.clear_all_spans(); self.sheet.clearContents()
        self._refresh_sheet_headers()

    def insert_card_into_template(self):
        cards = self._ordered_cards()
        if not cards:
            QMessageBox.information(self, ui_text('Plantilla'), ui_text('No hay tarjetas en el Mapa libre.')); return
        labels = []
        for i, card in enumerate(cards, 1): labels.append(f'{i}. {card.title_text.toPlainText()}')
        label, ok = QInputDialog.getItem(self, ui_text('Añadir tarjeta'), ui_text('Tarjeta del Mapa libre:'), labels, 0, False)
        if not ok: return
        ref, ok = QInputDialog.getText(self, ui_text('Añadir tarjeta'), ui_text('Celda de destino (por ejemplo A2 o B7):'), text='A1')
        if not ok: return
        coords = self._cell_coords(ref)
        if not coords:
            QMessageBox.warning(self, ui_text('Plantilla'), ui_text('La referencia de celda no es válida.')); return
        row, col = coords
        self._insert_template_card(cards[labels.index(label)], row, col)

    def _insert_template_card(self, card, row, col):
        while row >= self.sheet.rowCount(): self.sheet.insertRow(self.sheet.rowCount())
        while col >= self.sheet.columnCount():
            self.sheet.insertColumn(self.sheet.columnCount()); self.sheet.setHorizontalHeaderItem(self.sheet.columnCount()-1, QTableWidgetItem(self._column_name(self.sheet.columnCount()-1))); self.sheet.setColumnWidth(self.sheet.columnCount()-1, 110)
        title, body = card.title_text.toPlainText(), card.body_text.toPlainText()
        value = title + (('\n' + body) if body else '')
        # La tarjeta conserva su identidad visual al pasar del mapa a la plantilla.
        item = QTableWidgetItem(value)
        card_color = QColor(card.card_color)
        if card_color.isValid():
            item.setBackground(QBrush(card_color))
        self.sheet.setItem(row, col, item); self.sheet.setCurrentCell(row, col)

    def insert_all_cards_into_template(self):
        cards = self._ordered_cards()
        if not cards:
            QMessageBox.information(self, ui_text('Plantilla'), ui_text('No hay tarjetas en el Mapa libre.')); return
        ref, ok = QInputDialog.getText(
            self, ui_text('Agregar todo a plantilla'),
            ui_text('Celda inicial (se insertará hacia abajo, saltando celdas ocupadas):'), text='A1')
        if not ok: return
        coords = self._cell_coords(ref)
        if not coords or coords[0] < 0:
            QMessageBox.warning(self, ui_text('Plantilla'), ui_text('La referencia de celda no es válida.')); return
        row, col = coords
        # Reservar también celdas vacías con formato y todo el área combinada.
        reserved = set()
        for r, c, rs, cs in self.sheet.span_origins():
            if c <= col < c + cs:
                reserved.update(range(r, r + rs))
        updates_enabled = self.sheet.updatesEnabled()
        self.sheet.setUpdatesEnabled(False)
        try:
            for card in cards:
                while row < self.sheet.rowCount() and (
                    row in reserved or self.sheet.item(row, col) is not None
                    or self.sheet.cellWidget(row, col) is not None
                ):
                    row += 1
                self._insert_template_card(card, row, col)
                row += 1
        finally:
            self.sheet.setUpdatesEnabled(updates_enabled)

    def export_template_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, ui_text('Exportar plantilla'), 'mapa_tramas.xlsx', 'Excel (*.xlsx)')
        if not path: return
        if not path.lower().endswith('.xlsx'): path += '.xlsx'
        try:
            from openpyxl import Workbook
            from openpyxl.styles import PatternFill, Font as XLFont, Alignment as XLAlignment, Border, Side
            book = Workbook(); ws = book.active; ws.title = 'Mapa de tramas'
            max_r = max((r for r in range(self.sheet.rowCount()) if any(self.sheet.item(r,c) and self.sheet.item(r,c).text() for c in range(self.sheet.columnCount()))), default=-1)
            max_c = max((c for c in range(self.sheet.columnCount()) if any(self.sheet.item(r,c) and self.sheet.item(r,c).text() for r in range(self.sheet.rowCount()))), default=-1)
            for r in range(max_r + 1):
                for c in range(max_c + 1):
                    item = self.sheet.item(r, c)
                    if item:
                        cell = ws.cell(r + 1, c + 1, item.text())
                        bg = item.background().color(); fg = item.foreground().color(); font = item.font()
                        if bg.isValid() and item.background().style() != Qt.BrushStyle.NoBrush: cell.fill = PatternFill('solid', fgColor=bg.name().replace('#','').upper())
                        if fg.isValid() and item.foreground().style() != Qt.BrushStyle.NoBrush: cell.font = XLFont(name=font.family() or 'Arial', size=font.pointSize() if font.pointSize()>0 else 10, bold=font.bold(), italic=font.italic(), color=fg.name().replace('#','').upper())
                        else: cell.font = XLFont(name=font.family() or 'Arial', size=font.pointSize() if font.pointSize()>0 else 10, bold=font.bold(), italic=font.italic())
                        align = item.textAlignment()
                        horiz = 'center' if align & int(Qt.AlignmentFlag.AlignHCenter) else ('right' if align & int(Qt.AlignmentFlag.AlignRight) else 'left')
                        cell.alignment = XLAlignment(horizontal=horiz, vertical='center', wrap_text=True)
                        border_color = item.data(BORDER_ROLE)
                        if border_color:
                            side = Side(style='thin', color=str(border_color).replace('#','').upper()); cell.border = Border(left=side,right=side,top=side,bottom=side)
            # Respeta anchos/altos de la hoja y combinaciones creadas por el usuario.
            for c in range(self.sheet.columnCount()): ws.column_dimensions[self._column_name(c)].width = max(3, self.sheet.columnWidth(c) / 7.0)
            for r in range(self.sheet.rowCount()): ws.row_dimensions[r+1].height = max(10, self.sheet.rowHeight(r) * 0.75)
            for r,c,rs,cs in self.sheet.span_origins():
                try: ws.merge_cells(start_row=r+1,start_column=c+1,end_row=r+rs,end_column=c+cs)
                except ValueError: pass
            book.save(path)
        except Exception as exc:
            QMessageBox.critical(self, ui_text('Exportar Excel'), str(exc))

    def template_data(self):
        cells = []
        for r in range(self.sheet.rowCount()):
            for c in range(self.sheet.columnCount()):
                item = self.sheet.item(r, c)
                if item:
                    bg = item.background().color(); fg = item.foreground().color(); font = item.font()
                    has_format = item.background().style() != Qt.BrushStyle.NoBrush or item.foreground().style() != Qt.BrushStyle.NoBrush or font.bold() or font.italic() or font.pointSize() not in (-1, 0) or item.data(BORDER_ROLE)
                    if item.text() or has_format:
                        cells.append({'row': r, 'col': c, 'text': item.text(),
                                      'bg': bg.name() if item.background().style() != Qt.BrushStyle.NoBrush else '',
                                      'fg': fg.name() if item.foreground().style() != Qt.BrushStyle.NoBrush else '',
                                      'bold': font.bold(), 'italic': font.italic(), 'size': font.pointSize(),
                                      'align': int(item.textAlignment()), 'border': item.data(BORDER_ROLE) or ''})
        spans = [{'row':r,'col':c,'rows':rs,'cols':cs} for r,c,rs,cs in self.sheet.span_origins()]
        return {'rows': self.sheet.rowCount(), 'cols': self.sheet.columnCount(), 'cells': cells, 'spans': spans,
                'column_widths':[self.sheet.columnWidth(c) for c in range(self.sheet.columnCount())],
                'row_heights':[self.sheet.rowHeight(r) for r in range(self.sheet.rowCount())]}

    def load_template_data(self, data):
        data = data or {}
        # Siempre mostramos una hoja amplia (A..AZ, 1..100), aunque el proyecto viejo haya guardado solo A o pocas filas.
        rows = max(self._template_rows, int(data.get('rows', self._template_rows)))
        cols = max(self._template_cols, int(data.get('cols', self._template_cols)))
        self.sheet.clear_all_spans(); self.sheet.setRowCount(rows); self.sheet.setColumnCount(cols)
        self.sheet.clearContents(); self._refresh_sheet_headers()
        for cell in data.get('cells', []):
            r, c = int(cell.get('row', 0)), int(cell.get('col', 0))
            if 0 <= r < rows and 0 <= c < cols:
                item = QTableWidgetItem(str(cell.get('text', '')))
                if cell.get('bg'): item.setBackground(QBrush(QColor(cell['bg'])))
                if cell.get('fg'): item.setForeground(QBrush(QColor(cell['fg'])))
                font = item.font(); font.setBold(bool(cell.get('bold'))); font.setItalic(bool(cell.get('italic')))
                if int(cell.get('size', -1) or -1) > 0: font.setPointSize(int(cell['size']))
                item.setFont(font)
                if cell.get('align') is not None: item.setTextAlignment(int(cell.get('align')))
                if cell.get('border'): item.setData(BORDER_ROLE, cell.get('border'))
                self.sheet.setItem(r, c, item)
        for c, width in enumerate(data.get('column_widths', [])):
            if c < self.sheet.columnCount(): self.sheet.setColumnWidth(c, max(40, int(width)))
        for r, height in enumerate(data.get('row_heights', [])):
            if r < self.sheet.rowCount(): self.sheet.setRowHeight(r, max(18, int(height)))
        for span in data.get('spans', []):
            r,c = int(span.get('row',0)), int(span.get('col',0)); rs,cs = int(span.get('rows',1)), int(span.get('cols',1))
            if r < rows and c < cols and (rs > 1 or cs > 1): self.sheet.setSpan(r,c,rs,cs)

    def set_scenes(self, scenes):
        self._scenes = list(scenes or []); by_id = {row.get('id'): row for row in self._scenes}
        for item in self.scene.items():
            if isinstance(item, BeatCard) and item.scene_id in by_id:
                row = by_id[item.scene_id]; item.set_scene_link(item.scene_id, self._scene_label(row))

    @staticmethod
    def _scene_label(scene):
        number = scene.get('number', ''); heading = scene.get('heading', '')
        return ui_join([ui_text('Escena '), f'{number}', ui_text(' — '), f'{heading}']) if number else heading

    def selected_cards(self): return [item for item in self.scene.selectedItems() if isinstance(item, BeatCard)]

    def add_card(self, lane=ui_text('Principal'), title=None):
        count = len([item for item in self.scene.items() if isinstance(item, BeatCard)])
        default_title = ui_text('Nueva tarjeta') if lane == 'Personalizado' else (ui_text('Nuevo ') + lane.lower())
        card = BeatCard(title or default_title, lane, (count % 4) * 265, (count // 4) * 145); self.scene.addItem(card); return card

    def _ordered_cards(self): return sorted([item for item in self.scene.items() if isinstance(item, BeatCard)], key=lambda c: (c.y(), c.x()))

    def change_selected_color(self):
        cards = self.selected_cards()
        if not cards: QMessageBox.information(self, ui_text('Mapa de tramas'), ui_text('Selecciona una o más tarjetas.')); return
        chosen = QColorDialog.getColor(QColor(cards[0].card_color), self, ui_text('Color de tarjeta'))
        if chosen.isValid():
            for card in cards: card.set_card_color(chosen.name())

    def _choose_text_color(self, attr, setter, caption):
        cards = self.selected_cards()
        if not cards: QMessageBox.information(self, ui_text('Mapa de tramas'), ui_text('Selecciona una o más tarjetas.')); return
        chosen = QColorDialog.getColor(QColor(getattr(cards[0], attr)), self, ui_text(caption))
        if chosen.isValid():
            for card in cards: getattr(card, setter)(chosen.name())

    def change_selected_title_color(self): self._choose_text_color('title_color', 'set_title_color', 'Color del título')
    def change_selected_text_color(self): self._choose_text_color('text_color', 'set_text_color', 'Color del texto')
    def reset_selected_colors(self):
        for card in self.selected_cards():
            card.set_card_color(card.COLORS.get(card.lane, '#eeeeee')); card.set_title_color('#111111'); card.set_text_color('#222222')

    def link_selected(self):
        cards = self.selected_cards()
        if not cards: QMessageBox.information(self, ui_text('Mapa de tramas'), ui_text('Selecciona una tarjeta para vincularla a una escena.')); return
        if not self._scenes: QMessageBox.information(self, ui_text('Mapa de tramas'), 'No hay escenas disponibles todavía. La tarjeta puede seguir usándose libremente sin vínculo.'); return
        labels = [self._scene_label(row) for row in self._scenes]; label, ok = QInputDialog.getItem(self, ui_text('Vincular escena'), ui_text('Escena del guion:'), labels, 0, False)
        if not ok: return
        row = self._scenes[labels.index(label)]
        for card in cards: card.set_scene_link(row.get('id'), label)

    def unlink_selected(self):
        for card in self.selected_cards(): card.set_scene_link(None, '')

    def open_selected_scene(self):
        cards = self.selected_cards(); linked = next((card for card in cards if card.scene_id), None)
        if not linked: QMessageBox.information(self, ui_text('Mapa de tramas'), ui_text('La tarjeta seleccionada no tiene una escena vinculada.')); return
        self.scene_open_requested.emit(linked.scene_id)

    def remove_selected(self):
        for item in self.scene.selectedItems():
            if isinstance(item, BeatCard): self.scene.removeItem(item)

    def to_data(self): return [item.data_dict() for item in self.scene.items() if isinstance(item, BeatCard)]

    def load_data(self, rows):
        self.scene.clear()
        for row in rows or []:
            self.scene.addItem(BeatCard(row.get('title', ''), row.get('lane', ui_text('Principal')), row.get('x', 0), row.get('y', 0),
                                       row.get('scene_id'), row.get('scene_label', ''), row.get('color'), row.get('width',240), row.get('height',145),
                                       row.get('content', ''), row.get('title_color', '#111111'), row.get('text_color', '#222222')))
        self.set_scenes(self._scenes)

def parse_fdx(path):
    root = ET.parse(path).getroot(); blocks = []
    for paragraph in root.iter():
        if paragraph.tag.split('}')[-1] != 'Paragraph': continue
        kind = paragraph.attrib.get('Type', 'Action').lower()
        mapping = {'scene heading': 'scene', 'action': 'action', 'character': 'character', 'dialogue': 'dialogue', 'parenthetical': 'parenthetical', 'transition': 'transition'}
        text = ''.join(node.text or '' for node in paragraph.iter() if node.tag.split('}')[-1] == 'Text')
        if text.strip(): blocks.append({'type': mapping.get(kind, 'action'), 'text': text.strip()})
    return blocks


def write_fdx(path, blocks):
    reverse = {'scene': 'Scene Heading', 'action': 'Action', 'character': 'Character', 'dialogue': 'Dialogue', 'parenthetical': 'Parenthetical', 'transition': 'Transition'}
    root = ET.Element('FinalDraft', DocumentType='Script', Template='No', Version='3')
    content = ET.SubElement(root, 'Content')
    for block in blocks:
        paragraph = ET.SubElement(content, 'Paragraph', Type=reverse.get(block.get('type'), 'Action'))
        ET.SubElement(paragraph, 'Text').text = block.get('text', '')
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def export_budget_template(template_path, output_path, rows, metadata):
    try:
        from openpyxl import load_workbook
    except ImportError as error:
        raise RuntimeError('Falta openpyxl. Ejecuta pip install -r requirements.txt') from error
    keep_vba = str(template_path).lower().endswith('.xlsm')
    book = load_workbook(template_path, keep_vba=keep_vba)
    sheet = book.active
    markers = {f'{{{{{key.upper()}}}}}': str(value) for key, value in metadata.items()}
    row_marker = None
    fields = {'{{CATEGORIA}}': 'category', '{{CONCEPTO}}': 'concept', '{{CANTIDAD}}': 'quantity', '{{JORNADAS}}': 'days', '{{PRECIO}}': 'unit_price', '{{TOTAL_LINEA}}': 'total', '{{NOTAS}}': 'notes'}
    columns = {}
    for row in sheet.iter_rows():
        for cell in row:
            value = str(cell.value or '').strip()
            if value in fields:
                row_marker = cell.row; columns[cell.column] = fields[value]
            elif value in markers: cell.value = markers[value]
    if row_marker is None: raise ValueError('La plantilla necesita una fila con {{CONCEPTO}} y los marcadores de columnas.')
    template_cells = list(sheet[row_marker])
    for offset, data in enumerate(rows):
        target = row_marker + offset
        if offset: sheet.insert_rows(target)
        for source in template_cells:
            cell = sheet.cell(target, source.column)
            if offset:
                cell._style = copy.copy(source._style); cell.number_format = source.number_format
                cell.alignment = copy.copy(source.alignment); cell.fill = copy.copy(source.fill); cell.border = copy.copy(source.border); cell.font = copy.copy(source.font)
            if source.column in columns: cell.value = data.get(columns[source.column], '')
    book.save(output_path)


# Permite ejecutar esta edición directamente con: python professional.py
if __name__ == '__main__':
    import multiprocessing
    import sys
    multiprocessing.freeze_support()
    if '--check-runtime' in sys.argv:
        from runtime_check import run
        raise SystemExit(run(sys.argv[sys.argv.index('--check-runtime') + 1]))
    from suite import run_app
    raise SystemExit(run_app('professional'))
