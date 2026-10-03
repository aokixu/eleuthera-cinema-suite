"""Development workspace: premise, theme, pitch materials, treatment and characters."""
from ui_i18n import ui_text, ui_join
import uuid
from html import escape
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget)


class TreatmentPage(QWidget):
    """Kept under the historical class name so old Suite integration stays compatible."""
    changed = Signal()
    convert_requested = Signal(str, str)

    SECTIONS = [
        ('premise', ui_text('Premisa'), 'Resume la idea dramática central del proyecto.'),
        ('theme', ui_text('Tema'), '¿Qué explora realmente la obra? Ej. lealtad, culpa, identidad, poder.'),
        ('tagline', 'Tagline', 'Frase breve, memorable y promocional.'),
        ('logline', 'Logline', 'Protagonista + objetivo/conflicto + obstáculo, idealmente en 1–2 frases.'),
        ('synopsis', ui_text('Sinopsis'), 'Resumen breve de la historia.'),
        ('argumental_synopsis', ui_text('Sinopsis argumental'), 'Desarrolla el argumento completo, incluyendo el final.'),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._maximized = False
        self._editors = {}
        self._build()

    @staticmethod
    def _prepare_text_edit(edit):
        """Keep text/placeholder clear of the QTextEdit frame on every DPI/theme."""
        edit.setAcceptRichText(False)
        edit.document().setDocumentMargin(8.0)
        edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return edit

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(18, 16, 18, 18); root.setSpacing(12)
        header = QHBoxLayout()
        hint = QLabel(ui_text('De la premisa al tratamiento: desarrolla el proyecto antes de convertirlo en escenas de guion.'))
        hint.setObjectName('moduleHint'); hint.setWordWrap(True)
        header.addWidget(hint, 1)
        self.maximize_button = QPushButton(ui_text('⛶ Maximizar'))
        self.maximize_button.setToolTip('Maximizar/restaurar el área de Desarrollo')
        self.maximize_button.setMinimumWidth(110)
        self.maximize_button.clicked.connect(self.toggle_maximized)
        header.addWidget(self.maximize_button)
        root.addLayout(header)
        self._header_hint = hint

        self._separator = QFrame(); self._separator.setFrameShape(QFrame.Shape.HLine); self._separator.setFrameShadow(QFrame.Shadow.Sunken); root.addWidget(self._separator)
        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.setUsesScrollButtons(True)
        for key, label, placeholder in self.SECTIONS:
            self.tabs.addTab(self._make_text_page(key, placeholder), label)
        self.tabs.addTab(self._make_treatment_page(), ui_text('Tratamiento'))
        self.tabs.addTab(self._make_characters_page(), ui_text('Personajes'))
        root.addWidget(self.tabs, 1)


    def _make_text_page(self, key, placeholder):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 14, 8, 8); layout.setSpacing(8)
        edit = self._prepare_text_edit(QTextEdit()); edit.setPlaceholderText(placeholder)
        counter = QLabel(ui_text('0 palabras · 0 caracteres')); counter.setObjectName('moduleHint')
        edit.textChanged.connect(lambda k=key, e=edit, c=counter: self._text_changed(k, e, c))
        self._editors[key] = (edit, counter)
        layout.addWidget(edit, 1); layout.addWidget(counter)
        return page

    def _make_treatment_page(self):
        page = QWidget(); root = QVBoxLayout(page); root.setContentsMargins(8, 14, 8, 8); root.setSpacing(10)
        toolbar = QHBoxLayout(); toolbar.setSpacing(8)
        add = QPushButton(ui_text('+ Nuevo bloque')); add.setObjectName('primary'); add.clicked.connect(self.add_block)
        delete = QPushButton(ui_text('Eliminar')); delete.clicked.connect(self.delete_block)
        export = QPushButton(ui_text('Exportar PDF')); export.clicked.connect(self.export_pdf)
        convert = QPushButton(ui_text('Convertir en escena')); convert.clicked.connect(self.convert_current)
        toolbar.addWidget(add); toolbar.addWidget(delete); toolbar.addStretch(1); toolbar.addWidget(export); toolbar.addWidget(convert); root.addLayout(toolbar)
        separator = QFrame(); separator.setFrameShape(QFrame.Shape.HLine); root.addWidget(separator)
        split = QSplitter(Qt.Orientation.Horizontal); split.setChildrenCollapsible(False)
        left = QFrame(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,10,0); ll.setSpacing(7)
        ll.addWidget(QLabel(ui_text('BLOQUES NARRATIVOS')))
        self.blocks = QListWidget(); self.blocks.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove); self.blocks.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.blocks.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); self.blocks.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.blocks.currentRowChanged.connect(self._select); self.blocks.model().rowsMoved.connect(lambda *a: self._emit())
        ll.addWidget(self.blocks, 1); split.addWidget(left)
        right = QFrame(); rl = QVBoxLayout(right); rl.setContentsMargins(10,0,0,0); rl.setSpacing(7)
        rl.addWidget(QLabel(ui_text('Título del bloque')))
        self.block_title = QLineEdit(); self.block_title.setPlaceholderText('Ej. Salida de prisión'); self.block_title.textChanged.connect(self._edit); rl.addWidget(self.block_title)
        rl.addWidget(QLabel(ui_text('Tratamiento')))
        self.text = self._prepare_text_edit(QTextEdit()); self.text.setPlaceholderText(ui_text('Describe acciones, decisiones, atmósfera y progresión dramática en presente. No necesitas encabezados INT./EXT. ni formato de diálogo.'))
        self.text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); self.text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text.textChanged.connect(self._edit); rl.addWidget(self.text, 1)
        self.counter = QLabel(ui_text('0 palabras · 0 caracteres')); self.counter.setObjectName('moduleHint'); rl.addWidget(self.counter)
        split.addWidget(right); split.setSizes([300, 900]); root.addWidget(split, 1)
        self._set_editor_enabled(False)
        return page

    def _make_characters_page(self):
        page = QWidget(); root = QVBoxLayout(page); root.setContentsMargins(8,14,8,8); root.setSpacing(10)
        toolbar = QHBoxLayout(); add = QPushButton(ui_text('+ Nuevo personaje')); add.setObjectName('primary'); delete = QPushButton(ui_text('Eliminar'))
        add.clicked.connect(self.add_character); delete.clicked.connect(self.delete_character); toolbar.addWidget(add); toolbar.addWidget(delete); toolbar.addStretch(1); root.addLayout(toolbar)
        separator = QFrame(); separator.setFrameShape(QFrame.Shape.HLine); root.addWidget(separator)
        split = QSplitter(Qt.Orientation.Horizontal); split.setChildrenCollapsible(False)
        self.characters = QListWidget(); self.characters.setMinimumWidth(220); self.characters.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); self.characters.currentRowChanged.connect(self._select_character); split.addWidget(self.characters)
        form_scroll = QScrollArea(); form_scroll.setWidgetResizable(True); form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); form_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        form = QWidget(); fl = QVBoxLayout(form); fl.setContentsMargins(12,0,12,12); fl.setSpacing(8)
        self.char_name = QLineEdit(); self.char_name.setPlaceholderText(ui_text('Nombre del personaje')); self.char_name.textChanged.connect(self._edit_character)
        fl.addWidget(QLabel(ui_text('Nombre'))); fl.addWidget(self.char_name)
        self.char_fields = {}
        for key, label, ph in [('description',ui_text('Descripción'),'Quién es el personaje y cuál es su situación.'),('objective',ui_text('Objetivo'),'¿Qué quiere conseguir?'),('need',ui_text('Necesidad'),'¿Qué necesita comprender, aceptar o cambiar?'),('conflict',ui_text('Conflicto'),'¿Qué se opone a su objetivo?'),('arc',ui_text('Arco'),'¿Cómo cambia a lo largo de la historia?')]:
            fl.addWidget(QLabel(label)); ed = self._prepare_text_edit(QTextEdit()); ed.setPlaceholderText(ph); ed.setMinimumHeight(85); ed.textChanged.connect(self._edit_character); self.char_fields[key] = ed; fl.addWidget(ed)
        fl.addStretch(1); form_scroll.setWidget(form); split.addWidget(form_scroll); split.setSizes([260, 900]); root.addWidget(split,1)
        self._set_character_enabled(False)
        return page

    def _text_changed(self, key, edit, counter):
        txt = edit.toPlainText(); counter.setText(ui_join([f'{len(txt.split())}', ui_text(' palabras · '), f'{len(txt)}', ui_text(' caracteres')])); self._emit()

    def toggle_maximized(self):
        """Maximiza/restaura el contenido de la sección actual sin alterar sus datos."""
        self._maximized = not self._maximized
        maximized = self._maximized
        self._header_hint.setVisible(not maximized)
        self._separator.setVisible(not maximized)
        self.tabs.tabBar().setVisible(not maximized)
        self.maximize_button.setText(ui_text('↙ Restaurar') if maximized else ui_text('⛶ Maximizar'))
        layout = self.layout()
        if maximized:
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(4)
        else:
            layout.setContentsMargins(18, 16, 18, 18)
            layout.setSpacing(12)

    def _set_editor_enabled(self, enabled): self.block_title.setEnabled(enabled); self.text.setEnabled(enabled)
    def add_block(self):
        item = QListWidgetItem(); item.setData(Qt.ItemDataRole.UserRole, {'id':uuid.uuid4().hex,'title':'Nuevo bloque','text':''}); self.blocks.addItem(item); self._renumber(); self.blocks.setCurrentItem(item); self.block_title.selectAll(); self.block_title.setFocus(); self._emit()
    def delete_block(self):
        row=self.blocks.currentRow()
        if row<0:return
        self.blocks.takeItem(row); self._renumber(); self._emit(); self.blocks.setCurrentRow(min(row,self.blocks.count()-1)) if self.blocks.count() else self._select(-1)
    def _select(self,row):
        self._loading=True; item=self.blocks.item(row) if row>=0 else None; data=item.data(Qt.ItemDataRole.UserRole) if item else {}
        self._set_editor_enabled(bool(item)); self.block_title.setText(data.get('title','')); self.text.setPlainText(data.get('text','')); self._update_counter(); self._loading=False
    def _edit(self):
        if self._loading:return
        item=self.blocks.currentItem()
        if not item:return
        data=dict(item.data(Qt.ItemDataRole.UserRole) or {}); data['title']=self.block_title.text().strip() or ui_text('Sin título'); data['text']=self.text.toPlainText(); item.setData(Qt.ItemDataRole.UserRole,data); self._renumber(); self._update_counter(); self._emit()
    def _renumber(self):
        for i in range(self.blocks.count()):
            item=self.blocks.item(i); data=item.data(Qt.ItemDataRole.UserRole) or {}; item.setText(f"{i+1}. {data.get('title') or 'Sin título'}")
    def _update_counter(self):
        txt=self.text.toPlainText(); self.counter.setText(ui_join([f'{len(txt.split())}', ui_text(' palabras · '), f'{len(txt)}', ui_text(' caracteres')]))

    def _set_character_enabled(self, enabled):
        self.char_name.setEnabled(enabled)
        for ed in self.char_fields.values(): ed.setEnabled(enabled)
    def add_character(self):
        data={'id':uuid.uuid4().hex,'name':'Nuevo personaje','description':'','objective':'','need':'','conflict':'','arc':''}; item=QListWidgetItem(data['name']); item.setData(Qt.ItemDataRole.UserRole,data); self.characters.addItem(item); self.characters.setCurrentItem(item); self.char_name.selectAll(); self.char_name.setFocus(); self._emit()
    def delete_character(self):
        row=self.characters.currentRow()
        if row<0:return
        self.characters.takeItem(row); self._emit(); self.characters.setCurrentRow(min(row,self.characters.count()-1)) if self.characters.count() else self._select_character(-1)
    def _select_character(self,row):
        self._loading=True; item=self.characters.item(row) if row>=0 else None; data=item.data(Qt.ItemDataRole.UserRole) if item else {}; self._set_character_enabled(bool(item)); self.char_name.setText(data.get('name',''))
        for key,ed in self.char_fields.items(): ed.setPlainText(data.get(key,'')); self._loading=False
    def _edit_character(self):
        if self._loading:return
        item=self.characters.currentItem()
        if not item:return
        data=dict(item.data(Qt.ItemDataRole.UserRole) or {}); data['name']=self.char_name.text().strip() or 'Sin nombre'
        for key,ed in self.char_fields.items(): data[key]=ed.toPlainText()
        item.setData(Qt.ItemDataRole.UserRole,data); item.setText(data['name']); self._emit()

    def _emit(self):
        if not self._loading:self.changed.emit()

    def to_data(self):
        data={key:edit.toPlainText() for key,(edit,_) in self._editors.items()}
        data['treatment']=[dict(self.blocks.item(i).data(Qt.ItemDataRole.UserRole) or {}) for i in range(self.blocks.count())]
        data['characters']=[dict(self.characters.item(i).data(Qt.ItemDataRole.UserRole) or {}) for i in range(self.characters.count())]
        return data

    def load_data(self, data):
        # Backward compatibility: Etapa 15 v1 stored treatment directly as a list.
        if isinstance(data,list): data={'treatment':data}
        data=data or {}; self._loading=True
        for key,(edit,counter) in self._editors.items():
            edit.setPlainText(str(data.get(key,'') or '')); txt=edit.toPlainText(); counter.setText(ui_join([f'{len(txt.split())}', ui_text(' palabras · '), f'{len(txt)}', ui_text(' caracteres')]))
        self.blocks.clear()
        for row in data.get('treatment',[]) or []:
            d={'id':str(row.get('id') or uuid.uuid4().hex),'title':str(row.get('title') or ui_text('Sin título')),'text':str(row.get('text') or '')}; item=QListWidgetItem(); item.setData(Qt.ItemDataRole.UserRole,d); self.blocks.addItem(item)
        self._renumber(); self.characters.clear()
        for row in data.get('characters',[]) or []:
            d={'id':str(row.get('id') or uuid.uuid4().hex),'name':str(row.get('name') or 'Sin nombre'),'description':str(row.get('description') or ''),'objective':str(row.get('objective') or ''),'need':str(row.get('need') or ''),'conflict':str(row.get('conflict') or ''),'arc':str(row.get('arc') or '')}; item=QListWidgetItem(d['name']); item.setData(Qt.ItemDataRole.UserRole,d); self.characters.addItem(item)
        self._loading=False
        self.blocks.setCurrentRow(0) if self.blocks.count() else self._select(-1); self.characters.setCurrentRow(0) if self.characters.count() else self._select_character(-1)

    def convert_current(self):
        item=self.blocks.currentItem()
        if not item:return
        data=item.data(Qt.ItemDataRole.UserRole) or {}; title=data.get('title','').strip(); text=data.get('text','').strip()
        if not text: QMessageBox.information(self,ui_text('Convertir en escena'),ui_text('El bloque no contiene tratamiento para convertir.')); return
        self.convert_requested.emit(title,text)

    def export_pdf(self):
        data=self.to_data()
        if not any(str(data.get(k,'')).strip() for k,_,_ in self.SECTIONS) and not data['treatment']:
            QMessageBox.information(self,ui_text('Desarrollo'),ui_text('No hay contenido para exportar.')); return
        filename,_=QFileDialog.getSaveFileName(self,ui_text('Exportar desarrollo del proyecto'),'','PDF (*.pdf)')
        if not filename:return
        if not filename.lower().endswith('.pdf'):filename+='.pdf'
        html='<h1>Desarrollo del proyecto</h1>'
        for key,label,_ in self.SECTIONS:
            txt=str(data.get(key,'')).strip()
            if txt: html+=f'<h2>{escape(label)}</h2><p>{escape(txt).replace(chr(10),"<br>")}</p>'
        if data['treatment']:
            html+='<h2>Tratamiento</h2>'
            for i,row in enumerate(data['treatment'],1): html+=f"<h3>{i}. {escape(row.get('title',''))}</h3><p>{escape(row.get('text','')).replace(chr(10),'<br>')}</p>"
        doc=QTextDocument(); doc.setHtml(html); printer=QPrinter(QPrinter.PrinterMode.HighResolution); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(filename); doc.print_(printer)
        QMessageBox.information(self,ui_text('Desarrollo exportado'),ui_text('PDF guardado correctamente.'))
