import plus_runtime

import ui_i18n

ui_i18n.install()

from ui_i18n import ui_text, ui_join

import plus_runtime



import json



import uuid



import sys



from pathlib import Path







from PySide6.QtCore import QSettings, QSize, QSizeF, Qt, QTimer, Signal



from PySide6.QtGui import QAction, QColor, QFont, QPainter, QKeySequence, QTextBlockFormat, QTextCharFormat, QTextCursor



from PySide6.QtPrintSupport import QPrinter



from PySide6.QtWidgets import (



    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget,



    QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter, QStatusBar, QTextEdit,



    QToolBar, QToolButton, QVBoxLayout, QWidget,



)



import qtawesome as qta











APP_NAME = 'Eleuthera Cinema Suite Profesional'



VERSION = '0.1 Dev'



BLOCK_TYPES = ('scene', 'action', 'character', 'dialogue', 'parenthetical', 'transition')



TYPE_LABELS = {



    'scene': ui_text('ESCENA'), 'action': ui_text('ACCION'), 'character': ui_text('PERSONAJE'),



    'dialogue': ui_text('DIALOGO'), 'parenthetical': ui_text('PARENTETICO'), 'transition': ui_text('TRANSICION'),



}



TYPE_IDS = {name: index + 1 for index, name in enumerate(BLOCK_TYPES)}



ID_TYPES = {value: key for key, value in TYPE_IDS.items()}











LIGHT = """



* { font-family: 'Segoe UI'; font-size: 10pt; color: #242424; }



QMainWindow, QWidget#root { background: #e9e7e3; }



QMenuBar, QToolBar { background: #f8f8f7; border: 0; }



QMenuBar { border-bottom: 1px solid #d7d4cf; }



QToolBar { border-bottom: 1px solid #d7d4cf; padding: 7px 12px; spacing: 6px; }



QToolButton, QPushButton, QComboBox { background: #ffffff; border: 1px solid #c9c6c0; border-radius: 5px; padding: 6px 10px; }



QToolButton:hover, QPushButton:hover { background: #f0eeea; }



QComboBox { min-width: 145px; }



QFrame#side { background: #f7f6f3; border: 0; }



QLabel#section { color: #5a554e; font-size: 9pt; font-weight: 700; }



QLabel#brand { font-family: Georgia; font-size: 14pt; font-weight: 700; color: #171717; }



QListWidget { background: transparent; border: 0; outline: 0; }



QListWidget::item { padding: 9px; border-radius: 4px; }



QListWidget::item:selected { background: #ded9d1; color: #111111; }



QTextEdit#script { background: #ffffff; color: #171717; border: 1px solid #d5d1cb; padding: 0px; selection-background-color: #b9d8ec; }



QTextEdit#notes { background: #ffffff; border: 1px solid #d5d1cb; border-radius: 4px; padding: 8px; }



QStatusBar { background: #f8f8f7; border-top: 1px solid #d7d4cf; color: #615c55; }



"""







DARK = """



* { font-family: 'Segoe UI'; font-size: 10.5pt; color: #e8e4dd; }



QMainWindow, QWidget#root { background: #1e1f22; }



QMenuBar, QToolBar, QStatusBar { background: #25262a; border: 0; }



QMenuBar { border-bottom: 1px solid #3b3c42; }



QToolBar { border-bottom: 1px solid #3b3c42; padding: 8px 12px; spacing: 7px; }



QMenu { background: #292a2e; border: 1px solid #44454c; padding: 4px; }



QMenu::item { padding: 7px 24px; border-radius: 4px; }



QMenu::item:selected { background: #633743; color: #f7f3ed; }



QToolButton, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QLineEdit { background: #303136; border: 1px solid #4a4b52; border-radius: 5px; padding: 6px 10px; selection-background-color: #704050; selection-color: #f7f3ed; }



QToolButton:hover, QPushButton:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover { background: #3a3b41; border-color: #5b5c64; }



QToolButton:pressed, QPushButton:pressed { background: #24252a; }



QComboBox { min-width: 145px; }



QComboBox QAbstractItemView { background: #303136; color: #e8e4dd; border: 1px solid #4a4b52; selection-background-color: #633743; selection-color: #f7f3ed; }



QFrame#side { background: #25262a; border: 0; }



QLabel#section { color: #b6b0a7; font-size: 9pt; font-weight: 700; }



QLabel#brand { font-family: Georgia; font-size: 14pt; font-weight: 700; color: #f0ece5; }



QListWidget { background: transparent; border: 0; outline: 0; }



QListWidget::item { padding: 10px; border-radius: 4px; }



QListWidget::item:hover { background: #303136; }



QListWidget::item:selected { background: #4c353b; color: #f7f3ed; }



QTextEdit#script { background: #292a2e; color: #e8e4dd; border: 1px solid #414248; padding: 0px; selection-background-color: #704050; selection-color: #f7f3ed; }



QTextEdit#notes { background: #292a2e; color: #e8e4dd; border: 1px solid #414248; border-radius: 5px; padding: 9px; }



QStatusBar { border-top: 1px solid #3b3c42; color: #b6b0a7; }



QToolTip { background: #34353a; color: #f0ece5; border: 1px solid #55565e; padding: 5px; }



QScrollBar:vertical { background: #25262a; width: 12px; margin: 0; }



QScrollBar::handle:vertical { background: #505158; min-height: 28px; border-radius: 5px; margin: 2px; }



QScrollBar::handle:vertical:hover { background: #62636b; }



QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }



QScrollBar:horizontal { background: #25262a; height: 12px; margin: 0; }



QScrollBar::handle:horizontal { background: #505158; min-width: 28px; border-radius: 5px; margin: 2px; }



QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }



"""











class ScriptEditor(QTextEdit):



    structure_changed = Signal()



    viewport_changed = Signal()







    def __init__(self):



        super().__init__()



        self.setObjectName('script')



        self.setCursorWidth(0)



        self._caret_visible = True



        self._caret_timer = QTimer(self)



        self._caret_timer.timeout.connect(self._blink_caret)



        self.cursorPositionChanged.connect(self._reset_caret)



        self.textChanged.connect(self._reset_caret)



        self._page_timer = QTimer(self)



        self._page_timer.setSingleShot(True)



        self._page_timer.timeout.connect(self.restore_page_layout)



        self.textChanged.connect(lambda: self._page_timer.start(0))



        self.setAcceptRichText(False)



        self.setLineWrapMode(QTextEdit.LineWrapMode.FixedPixelWidth)



        self.setLineWrapColumnOrWidth(760)



        self.configure_pages(self.document())



        self.setUndoRedoEnabled(True)



        self.setTabChangesFocus(False)



        self.document().setDefaultFont(QFont('Courier New', 11))



        self.cursorPositionChanged.connect(self.ensure_block_type)



        self.textChanged.connect(self.structure_changed)







    PAGE_WIDTH = 760



    PAGE_HEIGHT = 984



    PAGE_MARGIN = 64



    CARET_COLOR = QColor('#FFFF00')



    CARET_WIDTH = 4







    def _reset_caret(self):



        self._caret_visible = True



        self._caret_timer.stop()



        interval = QApplication.cursorFlashTime()



        if self.hasFocus() and not self.isReadOnly() and interval > 0:



            self._caret_timer.start(max(1, interval // 2))



        self.viewport().update()







    def _blink_caret(self):



        self._caret_visible = not self._caret_visible



        self.viewport().update(self.cursorRect().adjusted(-1, 0, self.CARET_WIDTH + 1, 1))







    def focusInEvent(self, event):



        super().focusInEvent(event)



        self._reset_caret()







    def focusOutEvent(self, event):



        self._caret_timer.stop()



        self._caret_visible = False



        super().focusOutEvent(event)



        self.viewport().update()







    def configure_pages(self, document):



        document.setDocumentMargin(self.PAGE_MARGIN)



        document.setPageSize(QSizeF(self.PAGE_WIDTH, self.PAGE_HEIGHT))







    def restore_page_layout(self):



        if self.document().pageSize() != QSizeF(self.PAGE_WIDTH, self.PAGE_HEIGHT):



            self.configure_pages(self.document())



            self.ensureCursorVisible()







    def resizeEvent(self, event):



        super().resizeEvent(event)



        self.configure_pages(self.document())



        self._page_timer.start(0)



        self.viewport_changed.emit()







    def paintEvent(self, event):



        super().paintEvent(event)



        # Qt paginates text within the page margins; only visible separators are painted.



        painter = QPainter(self.viewport())



        offset = self.verticalScrollBar().value()



        horizontal = self.horizontalScrollBar().value()



        first = max(1, offset // self.PAGE_HEIGHT)



        last = (offset + self.viewport().height()) // self.PAGE_HEIGHT + 1



        painter.setPen(QColor('#888888'))



        for number in range(first, last + 1):



            y = number * self.PAGE_HEIGHT - offset



            painter.fillRect(-horizontal, y - 5, self.PAGE_WIDTH, 10, QColor("#777777"))



            painter.drawText(self.PAGE_WIDTH - self.PAGE_MARGIN - 35 - horizontal, y - 18, str(number))



        if self._caret_visible and self.hasFocus() and not self.isReadOnly() and not self.textCursor().hasSelection():



            rect = self.cursorRect()



            painter.fillRect(rect.left(), rect.top(), self.CARET_WIDTH, max(1, rect.height()), self.CARET_COLOR)



        painter.end()







    def block_type(self, block=None):



        block = block or self.textCursor().block()



        return ID_TYPES.get(block.userState(), 'action')







    def ensure_block_type(self):



        if getattr(self, '_editing_block', False): return



        block = self.textCursor().block()



        if block.userState() < 1:



            self.apply_type('action', transform=False)







    def apply_type(self, block_type, transform=True):



        original = self.textCursor()



        cursor = QTextCursor(original)



        self._editing_block = True



        cursor.beginEditBlock()



        block = cursor.block()



        block.setUserState(TYPE_IDS[block_type])



        fmt = QTextBlockFormat()



        fmt.setProperty(1001, block.blockFormat().property(1001) or uuid.uuid4().hex)



        fmt.setTopMargin(7 if block_type == 'scene' else 2)



        fmt.setBottomMargin(2)



        left, right = {



            'scene': (0, 0), 'action': (0, 0), 'character': (267, 25),



            'dialogue': (160, 160), 'parenthetical': (205, 205), 'transition': (310, 0),



        }[block_type]



        fmt.setLeftMargin(left)



        fmt.setRightMargin(right)



        fmt.setAlignment(Qt.AlignmentFlag.AlignRight if block_type == 'transition' else Qt.AlignmentFlag.AlignLeft)



        cursor.setBlockFormat(fmt)



        char = QTextCharFormat()



        char.setFontFamily('Courier New')



        char.setFontPointSize(11)



        char.setFontWeight(QFont.Weight.Bold if block_type == 'scene' else QFont.Weight.Normal)



        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)



        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)



        value = cursor.selectedText().replace('\u2029', '')



        if transform and block_type in ('scene', 'character', 'transition') and value:



            cursor.insertText(value.upper(), char)



        else:



            cursor.mergeCharFormat(char)



            cursor.clearSelection()



        cursor.endEditBlock()



        self.setTextCursor(original)



        self._editing_block = False







    def keyPressEvent(self, event):



        self._reset_caret()



        if event.key() == Qt.Key.Key_Tab:



            current = self.block_type()



            self.apply_type(BLOCK_TYPES[(BLOCK_TYPES.index(current) + 1) % len(BLOCK_TYPES)])



            return



        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):



            current = self.block_type()



            self._editing_block = True



            cursor = self.textCursor()



            cursor.beginEditBlock()



            cursor.insertBlock()



            self.setTextCursor(cursor)



            next_type = {



                'scene': 'action', 'action': 'action', 'character': 'dialogue',



                'dialogue': 'action', 'parenthetical': 'dialogue', 'transition': 'scene',



            }[current]



            self.apply_type(next_type, transform=False)



            cursor.endEditBlock()



            self.ensureCursorVisible()



            return



        if self.block_type() in ('scene', 'character', 'transition') and event.text().isalpha():



            event = type(event)(event.type(), event.key(), event.modifiers(), event.text().upper(), event.isAutoRepeat(), event.count())



        super().keyPressEvent(event)







    def blocks(self):



        result = []



        block = self.document().firstBlock()



        seen = set()



        while block.isValid():



            fmt = block.blockFormat()



            identity = fmt.property(1001)



            if not identity or identity in seen:



                identity = uuid.uuid4().hex



                fmt.setProperty(1001, identity)



                cursor = QTextCursor(block)



                previous = self.blockSignals(True)



                cursor.setBlockFormat(fmt)



                self.blockSignals(previous)



            seen.add(identity)



            result.append({'type': self.block_type(block), 'text': block.text(), 'id': identity})



            block = block.next()



        return result







    def build_document(self, blocks):



        """Yield after bounded batches; the live editor remains untouched."""



        from PySide6.QtGui import QTextDocument



        from time import perf_counter



        document = QTextDocument(self)



        document.setDefaultFont(self.document().defaultFont())



        self.configure_pages(document)



        document.setUndoRedoEnabled(False)



        document.setLayoutEnabled(False)



        cursor = QTextCursor(document)



        values = blocks or [{'type': 'scene', 'text': ''}]



        formats = {}



        for kind in BLOCK_TYPES:



            fmt = QTextBlockFormat(); fmt.setTopMargin(7 if kind == 'scene' else 2); fmt.setBottomMargin(2)



            left, right = {'scene': (0,0), 'action': (0,0), 'character': (267,25), 'dialogue': (160,160), 'parenthetical': (205,205), 'transition': (310,0)}[kind]



            fmt.setLeftMargin(left);fmt.setRightMargin(right)



            fmt.setAlignment(Qt.AlignmentFlag.AlignRight if kind == 'transition' else Qt.AlignmentFlag.AlignLeft)



            char = QTextCharFormat();char.setFontFamilies(['Courier New']);char.setFontPointSize(11)



            char.setFontWeight(QFont.Weight.Bold if kind == 'scene' else QFont.Weight.Normal)



            formats[kind]=(fmt,char)



        scene_total=sum(item.get('type')=='scene' for item in values); scenes=0; start=perf_counter()



        try:



            for index,item in enumerate(values):



                kind=item.get('type','action');fmt,char=formats[kind]



                if index: cursor.insertBlock(*formats['action'])



                else: cursor.setBlockFormat(formats['action'][0]);cursor.setCharFormat(formats['action'][1])



                cursor.block().setUserState(TYPE_IDS['action'])



                cursor.insertText(item.get('text',''))



                block=cursor.block();block.setUserState(TYPE_IDS[kind])



                copy=QTextBlockFormat(fmt);copy.setProperty(1001,item.get('id') or uuid.uuid4().hex);cursor.setBlockFormat(copy)



                cursor.select(QTextCursor.SelectionType.BlockUnderCursor);cursor.mergeCharFormat(char);cursor.clearSelection();cursor.movePosition(QTextCursor.MoveOperation.End)



                scenes+=kind=='scene'



                if perf_counter()-start>=0.008 or index==len(values)-1:



                    yield document,index+1,len(values),scenes,scene_total



                    start=perf_counter()



        finally:



            document.setLayoutEnabled(True)







    def install_document(self, document):



        previous=self.blockSignals(True)



        old=self.document()



        self.setDocument(document)



        self.configure_pages(document)



        document.setUndoRedoEnabled(True)



        self.moveCursor(QTextCursor.MoveOperation.Start)



        self.blockSignals(previous)



        self.structure_changed.emit()







    def load_blocks(self, blocks):



        for document, *_ in self.build_document(blocks): pass



        self.install_document(document)











class MainWindow(QMainWindow):



    def __init__(self):



        super().__init__()



        self.path = None



        self.dirty = False



        self.dark = QSettings().value('dark', False, type=bool)



        self.focused = False



        self.resize(1360, 860)



        self.setMinimumSize(940, 620)



        self.build_actions()



        self.build_ui()



        self.apply_theme()



        self.new_document()



        self.autosave = QTimer(self)



        self.autosave.setInterval(2500)



        self.autosave.timeout.connect(self.auto_save)



        self.autosave.start()







    def icon(self, name, color='#57534e'):



        return qta.icon(name, color=color)







    def action(self, label, icon, callback, shortcut=None):



        action = QAction(self.icon(icon), label, self)



        action.triggered.connect(callback)



        if shortcut:



            action.setShortcut(QKeySequence(shortcut))



        return action







    def build_actions(self):



        self.new_action = self.action(ui_text('Nuevo'), 'fa6s.file', self.new_document, 'Ctrl+N')



        self.open_action = self.action(ui_text('Abrir'), 'fa6s.folder-open', self.open_document, 'Ctrl+O')



        self.save_action = self.action(ui_text('Guardar'), 'fa6s.floppy-disk', self.save, 'Ctrl+S')



        self.pdf_action = self.action(ui_text('Exportar PDF'), 'fa6s.file-pdf', self.export_pdf)



        self.fountain_action = self.action(ui_text('Exportar Fountain'), 'fa6s.file-export', self.export_fountain)



        self.dark_action = self.action(ui_text('Modo oscuro'), 'fa6s.moon', self.toggle_dark, 'Ctrl+D')



        self.focus_action = self.action(ui_text('Concentracion'), 'fa6s.expand', self.toggle_focus, 'F11')







    def build_ui(self):



        file_menu = self.menuBar().addMenu(ui_text('Archivo'))



        file_menu.addActions((self.new_action, self.open_action, self.save_action))



        export = file_menu.addMenu(ui_text('Exportar'))



        export.addActions((self.pdf_action, self.fountain_action))



        view = self.menuBar().addMenu(ui_text('Ver'))



        view.addActions((self.dark_action, self.focus_action))







        toolbar = QToolBar(ui_text('Principal'))



        toolbar.setMovable(False)



        toolbar.setIconSize(QSize(17, 17))



        brand = QLabel(APP_NAME)



        brand.setObjectName('brand')



        brand.setContentsMargins(4, 0, 18, 0)



        brand.deleteLater()



        toolbar.addActions((self.new_action, self.open_action, self.save_action))



        toolbar.addSeparator()



        toolbar.addWidget(QLabel(ui_text('Formato')))



        self.format_combo = QComboBox()



        self.format_combo.addItems([TYPE_LABELS[name].title() for name in BLOCK_TYPES])



        self.format_combo.currentIndexChanged.connect(self.format_selected)



        toolbar.addWidget(self.format_combo)



        spacer = QWidget()



        spacer.setMinimumWidth(15)



        toolbar.addWidget(spacer)



        toolbar.addActions((self.dark_action, self.focus_action))



        self.addToolBar(toolbar)







        root = QWidget()



        root.setObjectName('root')



        root_layout = QHBoxLayout(root)



        root_layout.setContentsMargins(0, 0, 0, 0)



        splitter = QSplitter()



        splitter.setChildrenCollapsible(False)



        root_layout.addWidget(splitter)







        self.left = QFrame()



        self.left.setObjectName('side')



        left_layout = QVBoxLayout(self.left)



        left_layout.setContentsMargins(14, 18, 10, 14)



        heading = QLabel(ui_text('ESCENAS'))



        heading.setObjectName('section')



        left_layout.addWidget(heading)



        self.scenes = QListWidget()



        self.scenes.currentRowChanged.connect(self.go_to_scene)



        left_layout.addWidget(self.scenes, 1)



        splitter.addWidget(self.left)







        editor_wrap = QWidget()



        editor_layout = QVBoxLayout(editor_wrap)



        editor_layout.setContentsMargins(8, 8, 8, 8)



        self.editor = ScriptEditor()



        self.editor.setMinimumWidth(400)



        self.editor.setMaximumWidth(780)



        self.editor.structure_changed.connect(self.document_changed)



        self.editor.cursorPositionChanged.connect(self.sync_format)



        editor_layout.addWidget(self.editor, 1)



        splitter.addWidget(editor_wrap)







        self.right = QFrame()



        self.right.setObjectName('side')



        right_layout = QVBoxLayout(self.right)



        right_layout.setContentsMargins(12, 18, 14, 14)



        heading = QLabel(ui_text('NOTAS DEL GUION'))



        heading.setObjectName('section')



        right_layout.addWidget(heading)



        self.notes = QTextEdit()



        self.notes.setObjectName('notes')



        self.notes.setPlaceholderText(ui_text('Ideas, pendientes, ritmo, referencias...'))



        self.notes.textChanged.connect(self.document_changed)



        right_layout.addWidget(self.notes, 1)



        splitter.addWidget(self.right)



        splitter.setSizes((225, 860, 250))



        splitter.setStretchFactor(1, 1)



        self.setCentralWidget(root)



        self.setStatusBar(QStatusBar())







    def new_document(self):



        if hasattr(self, 'dirty') and self.dirty and not self.confirm_discard():



            return



        self.path = None



        if hasattr(self, 'editor'):



            self.editor.load_blocks([



                {'type': 'scene', 'text': 'INT. LUGAR - DIA'},



                {'type': 'action', 'text': ''},



            ])



            self.notes.clear()



            self.dirty = False



            self.refresh()







    def document_changed(self):



        if getattr(self, '_loading', False): return



        self.dirty = True



        self.refresh_timer_start()







    def refresh_timer_start(self):



        if getattr(self, '_loading', False): return



        if not hasattr(self, '_refresh_timer'):



            self._refresh_timer=QTimer(self);self._refresh_timer.setSingleShot(True);self._refresh_timer.timeout.connect(self.refresh)



        self._refresh_timer.start(120)







    def refresh(self):



        selected = self.scenes.currentRow()



        self.scenes.blockSignals(True)



        self.scenes.clear()



        words = 0



        scene_count = 0



        for index, block in enumerate(self.editor.blocks()):



            words += len(block['text'].split())



            if block['type'] == 'scene' and block['text'].strip():



                self.scenes.addItem('{:02d}  {}'.format(scene_count + 1, block['text']))



                self.scenes.item(scene_count).setData(Qt.ItemDataRole.UserRole, index)



                scene_count += 1



        self.scenes.setCurrentRow(min(selected, self.scenes.count() - 1))



        self.scenes.blockSignals(False)



        pages = max(1, self.editor.document().pageCount())



        self.statusBar().showMessage(ui_text('{} escenas   |   {} palabras   |   ~{} paginas{}').format(



            scene_count, words, pages, '   |   Guardado automatico' if self.path else ''))



        name = self.path.stem if self.path else 'Sin titulo'



        self.setWindowTitle('{}{} - {}'.format('*' if self.dirty else '', name, APP_NAME))







    def format_selected(self, index):



        if index >= 0:



            self.editor.apply_type(BLOCK_TYPES[index])



            self.editor.setFocus()







    def sync_format(self):



        block_type = self.editor.block_type()



        self.format_combo.blockSignals(True)



        self.format_combo.setCurrentIndex(BLOCK_TYPES.index(block_type))



        self.format_combo.blockSignals(False)







    def go_to_scene(self, row):



        if row < 0:



            return



        target = self.scenes.item(row).data(Qt.ItemDataRole.UserRole)



        block = self.editor.document().findBlockByNumber(target)



        cursor = QTextCursor(block)



        self.editor.setTextCursor(cursor)



        self.editor.ensureCursorVisible()



        self.editor.setFocus()







    def project_data(self):



        return {'format': 1, 'application': APP_NAME, 'blocks': self.editor.blocks(), 'notes': self.notes.toPlainText()}







    def save(self):



        if not self.path:



            filename, _ = QFileDialog.getSaveFileName(self, ui_text('Guardar guion'), '', ui_text('Proyecto de guion (*.eguion)'))



            if not filename:



                return False



            self.path = Path(filename if filename.lower().endswith('.eguion') else filename + '.eguion')



        self.path.write_text(json.dumps(self.project_data(), ensure_ascii=False, indent=2), encoding='utf-8')



        self.dirty = False



        self.refresh()



        return True







    def auto_save(self):



        if self.path and self.dirty:



            try:



                self.save()



            except OSError:



                self.statusBar().showMessage('No se pudo realizar el guardado automatico.')







    def open_document(self):



        if self.dirty and not self.confirm_discard():



            return



        filename, _ = QFileDialog.getOpenFileName(self, ui_text('Abrir guion'), '', ui_text('Guiones (*.eguion *.fountain);;Todos (*.*)'))



        if not filename:



            return



        path = Path(filename)



        try:



            if path.suffix.lower() == '.fountain':



                blocks = self.parse_fountain(path.read_text(encoding='utf-8'))



                self.path = None



                self.notes.clear()



            else:



                data = json.loads(path.read_text(encoding='utf-8'))



                blocks = data['blocks']



                self.notes.setPlainText(data.get('notes', ''))



                self.path = path



            self.editor.load_blocks(blocks)



            self.dirty = False



            self.refresh()



        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:



            QMessageBox.critical(self, ui_text('No se pudo abrir'), str(error))







    def parse_fountain(self, source):



        from script_import import parse_fountain



        return parse_fountain(source)







    def fountain_text(self):



        lines = []



        for block in self.editor.blocks():



            value = block['text']



            if block['type'] == 'transition' and value:



                value = '> ' + value



            lines.append(value)



            if block['type'] in ('scene', 'action', 'dialogue', 'transition'):



                lines.append('')



        return '\n'.join(lines).rstrip() + '\n'







    def export_fountain(self):



        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Exportar Fountain'), '', 'Fountain (*.fountain)')



        if filename:



            path = Path(filename if filename.lower().endswith('.fountain') else filename + '.fountain')



            path.write_text(self.fountain_text(), encoding='utf-8')







    def export_pdf(self):



        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Exportar PDF'), '', 'PDF (*.pdf)')



        if filename:



            printer = QPrinter(QPrinter.PrinterMode.HighResolution)



            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)



            printer.setOutputFileName(filename if filename.lower().endswith('.pdf') else filename + '.pdf')



            self.editor.document().print_(printer)







    def toggle_dark(self):



        self.dark = not self.dark



        QSettings().setValue('dark', self.dark)



        self.apply_theme()







    def apply_theme(self):



        QApplication.instance().setStyleSheet(DARK if self.dark else LIGHT)







    def exit_focus(self):



        if self.focused:



            self.toggle_focus()







    def toggle_focus(self):



        if not hasattr(self, 'exit_focus_button'):



            self.exit_focus_button = QPushButton(ui_text('Salir de pantalla completa (Esc / F11)'), self)



            self.exit_focus_button.clicked.connect(self.exit_focus)



            self.statusBar().addPermanentWidget(self.exit_focus_button)



            self.exit_focus_action = QAction(self)



            self.exit_focus_action.setShortcut(QKeySequence('Esc'))



            self.exit_focus_action.triggered.connect(self.exit_focus)



            self.addAction(self.exit_focus_action)



            self.addAction(self.focus_action)



        self.focused = not self.focused



        if self.focused:



            self._focus_previous = [(widget, not widget.isHidden()) for widget in



                                    [self.left, self.right, self.menuBar(), *self.findChildren(QToolBar)]]



            self._focus_maximized = self.isMaximized()



            for widget, visible in self._focus_previous:



                widget.hide()



            self.showFullScreen()



        else:



            for widget, visible in self._focus_previous:



                widget.setVisible(visible)



            if self._focus_maximized:



                self.showMaximized()



            else:



                self.showNormal()



        self.exit_focus_button.setVisible(self.focused)



        self.exit_focus_action.setEnabled(self.focused)



        self.statusBar().show()







    def confirm_discard(self):



        answer = QMessageBox.question(self, ui_text('Cambios sin guardar'), ui_text('Hay cambios sin guardar. ¿Quieres guardarlos?'),



                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)



        if answer == QMessageBox.StandardButton.Save:



            return self.save()



        return answer == QMessageBox.StandardButton.Discard







    def closeEvent(self, event):



        if self.dirty and not self.confirm_discard():



            event.ignore()



        else:



            event.accept()











def main():



    app = QApplication(sys.argv)



    app.setApplicationName(APP_NAME)



    app.setOrganizationName('Equipo Eleuthera')



    app.setStyle('Fusion')



    window = MainWindow()



    window.show()



    return app.exec()











if __name__ == '__main__':



    raise SystemExit(main())



