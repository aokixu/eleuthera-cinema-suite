"""Compact help, scene filters, and cell editors that occupy the full cell."""
from ui_i18n import ui_text, ui_join
import re
from eleuthera_spreadsheet import EleutheraCellDelegate
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QAbstractItemDelegate, QAbstractItemView, QComboBox, QDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QStyledItemDelegate, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget, QHeaderView)
from production import normalize


class CellEditor(EleutheraCellDelegate):
    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setFrameStyle(0)
        editor.setTabChangesFocus(True)
        editor.setStyleSheet('QPlainTextEdit { padding: 1px; margin: 0; border: 1px solid #b45b70; border-radius: 0; background: #fffaf5; color: #242424; }')
        editor.document().setDocumentMargin(2)
        def fit():
            if not index.isValid(): return
            width = max(30, option.rect.width() - 12)
            metrics = editor.fontMetrics()
            import math
            lines = sum(max(1, math.ceil(metrics.horizontalAdvance(part) / width)) for part in editor.toPlainText().split('\n'))
            table = self.parent()
            table.setRowHeight(index.row(), min(420, max(44, lines * metrics.lineSpacing() + 12)))
            editor.setGeometry(table.visualRect(index).adjusted(1, 1, -1, -1))
        editor.textChanged.connect(fit)
        return editor

    def setEditorData(self, editor, index):
        editor.setPlainText(str(index.data(Qt.ItemDataRole.EditRole) or ''))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.adjusted(1, 1, -1, -1))

    def eventFilter(self, editor, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)
                return True
            if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.EditPreviousItem if event.key() == Qt.Key.Key_Backtab else QAbstractItemDelegate.EndEditHint.EditNextItem)
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.RevertModelCache)
                return True
        return super().eventFilter(editor, event)


def configure_table(table):
    table.setItemDelegate(CellEditor(table))
    table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.AnyKeyPressed)
    table.setWordWrap(True)
    table.verticalHeader().setMinimumSectionSize(38)
    table.verticalHeader().setDefaultSectionSize(44)
    table.horizontalHeader().setMinimumSectionSize(85)
    # Long text columns must not collapse when many numeric columns are visible.
    widths = {5: {1: 280, 2: 190, 3: 230, 4: 460},
              14: {3: 160, 4: 300, 13: 320},
              11: {3: 280, 6: 220, 8: 320, 9: 320}}
    for column, width in widths.get(table.columnCount(), {}).items():
        table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(column, width)
    table.setStyleSheet(table.styleSheet() + ' QTableWidget::item { padding: 2px; }')
    table.itemChanged.connect(lambda item: table.resizeRowToContents(item.row()) if item and item.row() >= 0 else None)


GUIDES = {
    ui_text('Guion'): ('Escribe por bloques', 'Selecciona Escena, Acción, Personaje o Diálogo en Formato y escribe. Usa el navegador izquierdo para ir a una escena. Guarda el proyecto .eguion para conservar todos los módulos; Fountain, FDX y PDF son salidas para compartir. Los cambios posteriores al desglose se señalan en Revisiones.'),
    'Mapa': ('Organiza la historia', 'Agrega tarjetas de trama, personaje o giro. Escribe en cada tarjeta y arrástrala para organizarla. Selecciona las tarjetas que quieras quitar. El mapa se guarda dentro del proyecto.'),
    ui_text('Desglose'): ('Revisa las necesidades de cada escena', 'Analizar guion propone elementos. Las propuestas nuevas se pueden incorporar sin borrar tus correcciones. Revisa categoría, elemento y texto de origen; marca Aprobado cuando corresponda. Enviar aprobados al presupuesto añade conceptos, sin asignarles tarifas. Exporta fichas en Excel o PDF. Usa Revisiones cuando cambie el guion.'),
    'Plan': ('Organiza el rodaje', 'Actualizar desde guion y desglose permite revisar cambios antes de aplicarlos. Las escenas nuevas llegan sin jornada. Selecciona escenas y asigna una jornada; usa Subir/Bajar para ordenar. Inicio determina las fechas consecutivas de las jornadas: compruébalas antes de exportar. Los cambios manuales y el orden se conservan salvo aceptación explícita.'),
    ui_text('Presupuesto'): ('Completa los costos', 'Agrega conceptos o recibe elementos aprobados del desglose. Completa cantidad, jornadas y tarifa: una tarifa vacía está pendiente; cero significa sin costo. El total usa cantidad × jornadas × tarifa × cambio y, cuando existe, fringe. Exporta Excel o PDF; la plantilla Excel personalizada requiere marcadores. La moneda y los cambios se administran en Proyecto. En una plantilla, usa {{TITULO}} y {{MONEDA}} para el encabezado; en una fila de detalle: {{CONCEPTO}}, {{CATEGORIA}}, {{CANTIDAD}}, {{JORNADAS}}, {{PRECIO}}, {{TOTAL_LINEA}} y {{NOTAS}}.'),
    ui_text('Proyecto'): ('Información compartida', 'Completa los datos disponibles; los campos son opcionales. Guarda los datos para incorporarlos a los próximos informes. Las fechas generales no mueven jornadas. Si cambias moneda o tasas, revisa y acepta el efecto sobre el presupuesto.'),
}


def show_guide(window):
    label = window.modules.tabText(window.modules.currentIndex())
    key = next((key for key in GUIDES if key in label), ui_text('Guion'))
    title, text = GUIDES[key]
    if key == ui_text('Presupuesto') and window.workspace_mode == 'professional':
        text += ' En Profesional, Cuenta agrupa detalles; ATL/BTL separa bloques y @DIAS_RODAJE toma las jornadas globales. El cambio expresa cuántas unidades de moneda base equivale una unidad de la moneda de la partida.'
    dialog = QDialog(window)
    dialog.setWindowTitle('Guía · ' + label)
    dialog.resize(610, 340)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser()
    browser.setPlainText(title + '\n\n' + text + '\n\nEdición de tablas: escribe sobre la celda seleccionada para reemplazar; doble clic para corregir. Enter confirma, Tab avanza, Escape cancela. Shift+Enter añade una línea.')
    layout.addWidget(browser)
    close = QPushButton(ui_text('Cerrar')); close.clicked.connect(dialog.accept); layout.addWidget(close)
    dialog.exec()


