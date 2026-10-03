"""Motor común de hoja de cálculo para Eleuthera.

Una sola superficie para Mapa libre, fichas estructurales y futuras plantillas.
No implementa lógica narrativa: sólo comportamiento/representación de hoja.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView

BORDER_ROLE = Qt.ItemDataRole.UserRole + 10
ACCENT = QColor('#17616A')

class EleutheraCellDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        # QStyledItemDelegate.paint() vuelve a ejecutar initStyleOption() justo
        # antes de dibujar. Por eso cambiar textElideMode únicamente dentro de
        # paint() no bastaba: Qt lo restauraba y reaparecían los puntos "...".
        super().initStyleOption(option, index)
        option.textElideMode = Qt.TextElideMode.ElideNone

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setContentsMargins(0, 0, 0, 0)
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        fg = index.data(Qt.ItemDataRole.ForegroundRole)
        bgc = bg.color() if hasattr(bg, 'color') and bg.color().isValid() else QColor('#ffffff')
        fgc = fg.color() if hasattr(fg, 'color') and fg.color().isValid() else QColor('#111111')
        editor.setStyleSheet(
            'QLineEdit{border:0;border-radius:0;padding:0 5px;margin:0;'
            f'background:{bgc.name()};color:{fgc.name()};selection-background-color:#17616A;selection-color:#ffffff;}}'
        )
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        # El formato de la celda tiene prioridad sobre el tema oscuro global.
        opt = QStyleOptionViewItem(option)
        # El no-truncado se fija en initStyleOption(), porque paint() de Qt
        # reinicializa esta opción antes de dibujar.
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        fg = index.data(Qt.ItemDataRole.ForegroundRole)
        if hasattr(bg, 'color') and bg.color().isValid():
            opt.palette.setColor(QPalette.ColorRole.Base, bg.color())
            opt.palette.setColor(QPalette.ColorRole.Window, bg.color())
        else:
            opt.palette.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
            opt.palette.setColor(QPalette.ColorRole.Window, QColor('#ffffff'))
        if hasattr(fg, 'color') and fg.color().isValid():
            opt.palette.setColor(QPalette.ColorRole.Text, fg.color())
        else:
            opt.palette.setColor(QPalette.ColorRole.Text, QColor('#111111'))
        # Selección estilo Excel: conservar SIEMPRE el fondo real de la celda.
        # El tema global de Eleuthera usa petróleo como Highlight; lo anulamos
        # sólo para esta vista y representamos la selección únicamente con borde.
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        cell_bg = bg.color() if hasattr(bg, 'color') and bg.color().isValid() else QColor('#ffffff')
        cell_fg = fg.color() if hasattr(fg, 'color') and fg.color().isValid() else QColor('#111111')
        if selected:
            opt.state &= ~QStyle.StateFlag.State_Selected
            opt.palette.setColor(QPalette.ColorRole.Highlight, cell_bg)
            opt.palette.setColor(QPalette.ColorRole.HighlightedText, cell_fg)
        painter.save()
        painter.fillRect(option.rect, cell_bg)
        painter.restore()
        super().paint(painter, opt, index)
        painter.save()
        border = index.data(BORDER_ROLE)
        if border:
            from PySide6.QtGui import QPen
            painter.setPen(QPen(QColor(str(border)), 2))
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
        if selected:
            from PySide6.QtGui import QPen
            painter.setPen(QPen(ACCENT, 2))
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
        painter.restore()

class EleutheraSpreadsheet(QTableWidget):
    """Motor tabular común de Eleuthera.

    mode='free' permite la hoja libre/plantillas. mode='structured' conserva
    el esquema impuesto por módulos como Desglose, Plan de rodaje y Presupuesto,
    pero comparte render, edición y lenguaje visual tipo Excel.
    """
    def __init__(self, rows=0, columns=0, parent=None, mode='free'):
        self.eleuthera_mode = mode

        super().__init__(rows, columns, parent)
        self.setItemDelegate(EleutheraCellDelegate(self))
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setStyleSheet(
            'QTableWidget{background:#ffffff;color:#111111;gridline-color:#d0d4d8;border:1px solid #9aa2a8;}'
            'QTableWidget::item{padding:3px 5px;}'
            'QHeaderView::section{background:#f0f1f2;color:#202428;border:0;border-right:1px solid #c8cdd1;border-bottom:1px solid #b8bec3;padding:4px;}'
            'QTableCornerButton::section{background:#e6e8ea;border:1px solid #c8cdd1;}'
        )

    def ensure_item(self, row, col):
        item = self.item(row, col)
        if item is None:
            item = QTableWidgetItem('')
            self.setItem(row, col, item)
        return item

    def selected_items_including_empty(self):
        out=[]; seen=set()
        for rg in self.selectedRanges():
            for r in range(rg.topRow(), rg.bottomRow()+1):
                for c in range(rg.leftColumn(), rg.rightColumn()+1):
                    if (r,c) not in seen:
                        seen.add((r,c)); out.append(self.ensure_item(r,c))
        if not out and self.currentRow() >= 0 and self.currentColumn() >= 0:
            out.append(self.ensure_item(self.currentRow(), self.currentColumn()))
        return out

    def merge_selection(self):
        if self.eleuthera_mode == 'structured': return False
        ranges=self.selectedRanges()
        if not ranges: return False
        rg=ranges[0]
        if rg.rowCount() == 1 and rg.columnCount() == 1:
            return False
        self.setSpan(rg.topRow(), rg.leftColumn(), rg.rowCount(), rg.columnCount())
        return True

    def unmerge_selection(self):
        if self.eleuthera_mode == 'structured': return False
        ranges=self.selectedRanges()
        if not ranges: return False
        rg=ranges[0]; changed=False
        # removeSpan debe llamarse sobre la celda origen del span.
        for r in range(rg.topRow(), rg.bottomRow()+1):
            for c in range(rg.leftColumn(), rg.rightColumn()+1):
                if self.rowSpan(r,c)>1 or self.columnSpan(r,c)>1:
                    self.removeSpan(r,c); changed=True
        return changed

    def clear_all_spans(self):
        origins=[]
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                if self.rowSpan(r,c)>1 or self.columnSpan(r,c)>1:
                    origins.append((r,c))
        for r,c in origins: self.removeSpan(r,c)

    def span_origins(self):
        spans=[]; covered=set()
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                if (r,c) in covered: continue
                rs,cs=self.rowSpan(r,c),self.columnSpan(r,c)
                if rs>1 or cs>1:
                    spans.append((r,c,rs,cs))
                    for rr in range(r,r+rs):
                        for cc in range(c,c+cs): covered.add((rr,cc))
        return spans

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            ranges=self.selectedRanges()
            if ranges:
                rg=ranges[0]; lines=[]
                for r in range(rg.topRow(),rg.bottomRow()+1):
                    lines.append('\t'.join((self.item(r,c).text() if self.item(r,c) else '') for c in range(rg.leftColumn(),rg.rightColumn()+1)))
                QApplication.clipboard().setText('\n'.join(lines)); return
        if event.matches(QKeySequence.StandardKey.Paste):
            text=QApplication.clipboard().text()
            if text:
                sr=max(0,self.currentRow()); sc=max(0,self.currentColumn())
                matrix=[row.split('\t') for row in text.rstrip('\n').splitlines()]
                nr=sr+len(matrix); nc=sc+max((len(x) for x in matrix),default=0)
                if self.eleuthera_mode == 'free':
                    if nr>self.rowCount(): self.setRowCount(nr)
                    if nc>self.columnCount(): self.setColumnCount(nc)
                for rr,row in enumerate(matrix):
                    for cc,value in enumerate(row):
                        r, c = sr+rr, sc+cc
                        if r >= self.rowCount() or c >= self.columnCount():
                            continue
                        item = self.ensure_item(r,c)
                        if item.flags() & Qt.ItemFlag.ItemIsEditable:
                            item.setText(value)
                return
        if event.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace) and self.selectedRanges():
            for item in self.selected_items_including_empty():
                if self.eleuthera_mode == 'free' or (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    item.setText('')
            return
        super().keyPressEvent(event)


class StructuredSpreadsheet(EleutheraSpreadsheet):
    """Hoja estructurada para Desglose, Plan y Presupuesto.

    Mantiene el motor/datos de esos módulos, pero replica de forma aislada la
    interacción de la hoja de Mapa: selección por celdas, edición plana,
    copiar/pegar rectangular y borrado sólo de celdas editables.  No modifica
    la hoja de Mapa ni su clase.
    """
    def __init__(self, rows=0, columns=0, parent=None):
        super().__init__(rows, columns, parent, mode='structured')
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def keyPressEvent(self, event):
        # Misma semántica rectangular de la hoja de Mapa, sin permitir que un
        # pegado altere la estructura (número de filas/columnas) del módulo.
        if event.matches(QKeySequence.StandardKey.Copy):
            ranges = self.selectedRanges()
            if ranges:
                rg = ranges[0]
                lines = []
                for r in range(rg.topRow(), rg.bottomRow() + 1):
                    vals = []
                    for c in range(rg.leftColumn(), rg.rightColumn() + 1):
                        cell = self.item(r, c)
                        vals.append(cell.text() if cell else '')
                    lines.append('\t'.join(vals))
                QApplication.clipboard().setText('\n'.join(lines))
                return
        if event.matches(QKeySequence.StandardKey.Paste):
            text = QApplication.clipboard().text()
            if text:
                sr, sc = max(0, self.currentRow()), max(0, self.currentColumn())
                matrix = [row.split('\t') for row in text.rstrip('\n').splitlines()]
                for rr, row in enumerate(matrix):
                    for cc, value in enumerate(row):
                        r, c = sr + rr, sc + cc
                        if r >= self.rowCount() or c >= self.columnCount():
                            continue
                        cell = self.ensure_item(r, c)
                        if cell.flags() & Qt.ItemFlag.ItemIsEditable:
                            cell.setText(value)
                return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selectedRanges():
            for cell in self.selected_items_including_empty():
                if cell.flags() & Qt.ItemFlag.ItemIsEditable:
                    cell.setText('')
            return
        # Navegación, Shift/Ctrl y edición quedan en Qt igual que en Mapa.
        QTableWidget.keyPressEvent(self, event)
