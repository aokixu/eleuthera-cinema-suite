from ui_i18n import ui_text, ui_join

from plus_theme import ACCENT, SELECTION, petroleum_stylesheet



import plus_runtime  # Preferencias aisladas de Professional.



import json



import os



import csv



import sys



import tempfile



import wave



from pathlib import Path







from PySide6.QtCore import QProcess, QSettings, Qt, QTimer, QSize



from PySide6.QtGui import QColor, QFont, QIcon, QPalette, QBrush



from PySide6.QtWidgets import (



    QApplication, QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,



    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QColorDialog, QInputDialog, QMenu,



    QVBoxLayout, QWidget,



)



import qtawesome as qta







import app



from production import analyze_blocks



from professional import StoryMapPage, WorkspaceModeDialog, parse_fdx, write_fdx



from scheduling import SchedulingPage
from eleuthera_spreadsheet import EleutheraSpreadsheet, StructuredSpreadsheet



from project_workflow import WorkflowMixin



from script_development import DialogueTunerPage, SceneNavigatorPage, SceneVersionsPage, CharacterArcPage, AnalysisPage, normalize_character_name



from treatment import TreatmentPage











SUITE_NAME = 'Eleuthera Cinema Suite Profesional'



SUITE_STYLE = """



QTabWidget::pane { border: 0; background: #eceae6; }



QTabBar::tab { background: transparent; padding: 11px 22px; border-bottom: 3px solid transparent; font-weight: 600; }



QTabBar::tab:selected { color: #7b2638; border-bottom-color: #7b2638; }



QTabBar::tab:hover { background: rgba(120, 100, 90, 0.08); }



QFrame#workspace { background: #f5f3ef; border: 0; }



QLabel#moduleTitle { font-family: "Georgia"; font-size: 19pt; font-weight: 700; }



QLabel#moduleHint { color: #6e6962; }



QTableWidget { background: #ffffff; alternate-background-color: #faf9f7; border: 1px solid #d7d2cb; gridline-color: #ece8e2; outline: 0; }



QTableWidget::item { padding: 7px; }



QTableWidget::item:selected { background: #eadde0; color: #241c1e; }



QHeaderView::section { background: #efede9; border: 0; border-bottom: 1px solid #d7d2cb; padding: 9px; font-weight: 650; }



QPushButton#primary { background: #7b2638; color: white; border-color: #7b2638; font-weight: 650; }



QPushButton#primary:hover { background: #91364a; }



QLabel#total { font-family: "Georgia"; font-size: 17pt; font-weight: 700; color: #7b2638; }



QFrame#voicePanel { background: #ffffff; border: 1px solid #d7d2cb; border-radius: 6px; }



QTextEdit#script { font-family: "Courier New"; font-size: 11pt; }



"""







DARK_ADDITION = """



QTabWidget::pane, QFrame#workspace { background: #1e1f22; }



QTabBar::tab { color: #c8c2b9; padding: 12px 22px; }



QTabBar::tab:hover { background: #292a2e; }



QTabBar::tab:selected { color: #e5a1b0; border-bottom-color: #a9445a; }



QLabel#moduleHint { color: #b6b0a7; }



QTableWidget { background: #27282c; alternate-background-color: #2c2d31; border-color: #414248; gridline-color: #37383d; }



QTableWidget::item { padding: 8px; }



QTableWidget::item:selected { background: #633743; color: #f7f3ed; }



QHeaderView::section { background: #313238; color: #ded9d1; border: 0; border-bottom: 1px solid #484950; padding: 9px; }



QFrame#voicePanel { background: #27282c; border-color: #414248; }



QLabel#total { color: #e5a1b0; }



QPushButton#primary { background: #8e354b; color: #fffaf5; border-color: #a3475d; }



QPushButton#primary:hover { background: #a13f57; border-color: #b85a6e; }



"""











def warm_dark_palette():



    palette = QPalette()



    palette.setColor(QPalette.ColorRole.Window, QColor('#1e1f22'))



    palette.setColor(QPalette.ColorRole.WindowText, QColor('#e8e4dd'))



    palette.setColor(QPalette.ColorRole.Base, QColor('#292a2e'))



    palette.setColor(QPalette.ColorRole.Text, QColor('#e8e4dd'))



    palette.setColor(QPalette.ColorRole.Button, QColor('#303136'))



    palette.setColor(QPalette.ColorRole.ButtonText, QColor('#e8e4dd'))



    palette.setColor(QPalette.ColorRole.Highlight, QColor(SELECTION))



    palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#f7f3ed'))



    return palette











def table_item(value='', editable=True):



    item = QTableWidgetItem(str(value))



    if not editable:



        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)



    return item











class SuiteWindow(WorkflowMixin, app.MainWindow):



    def __init__(self, edition='combined'):



        self.edition = edition



        self.scene_versions = {}



        self.character_arcs = {}



        self.scene_development = {}



        self.analysis_markers = {'characters': {}, 'scenes': {}, 'show_in_script': False}



        self.dramatic_structure = {}



        self.treatment_data = []



        self.breakdown_rows = []



        self.workspace_mode = QSettings().value('workspace_mode', 'professional') if edition == 'combined' else edition



        super().__init__()



        self.dark = True



        QSettings().setValue('dark', True)



        self.dark_action.setVisible(False)



        titles = {'professional': SUITE_NAME, 'standard': 'Eleuthera Cinema Suite Profesional', 'combined': SUITE_NAME + ' · Pruebas'}



        self.setWindowTitle(titles[edition])



        icon_path = Path(__file__).parent / 'assets' / 'eleuthera-clapperboard.svg'



        self.setWindowIcon(QIcon(str(icon_path)))



        QApplication.instance().setWindowIcon(QIcon(str(icon_path)))



        self.build_suite()



        self.setup_workflow()



        if edition in ('professional', 'combined'):



            self.add_professional_actions(edition == 'combined')



        else:



            self.add_standard_actions()



        self.apply_workspace_mode()



        self.apply_theme()



        # Cursor de escritura de alto contraste para el editor de guion.



        # Amarillo/dorado: visible sobre el fondo oscuro sin alterar texto ni selección.



        self.editor.setCursorWidth(0)



        self._highlight_timer = QTimer(self)



        self._highlight_timer.setSingleShot(True)



        self._highlight_timer.setInterval(20)



        self._highlight_timer.timeout.connect(self.apply_analysis_highlights)



        self.editor.verticalScrollBar().valueChanged.connect(lambda: self._highlight_timer.start())



        self.editor.viewport_changed.connect(lambda: self._highlight_timer.start())



        self.editor.textChanged.connect(lambda: self._highlight_timer.start())



        self.setup_shortcuts()



        self.docx_action = app.QAction(ui_text('Exportar Word (.docx)'), self)



        self.docx_action.triggered.connect(self.export_docx)



        file_menu = self.menuBar().actions()[0].menu()



        export_menu = next((item.menu() for item in file_menu.actions() if item.menu() and item.text() == ui_text('Exportar')), file_menu)



        export_menu.addAction(self.docx_action)



        self.master_pdf_action = app.QAction(ui_text('PDF general del proyecto'), self)



        self.master_pdf_action.triggered.connect(self.export_master_pdf)



        export_menu.addSeparator()



        export_menu.addAction(self.master_pdf_action)



        self.master_excel_action = app.QAction(ui_text('Excel general del proyecto (.xlsx)'), self)



        self.master_excel_action.triggered.connect(self.export_master_excel)



        export_menu.addAction(self.master_excel_action)

        from ui_i18n import add_language_menu

        add_language_menu(self)







    def export_master_excel(self):



        from project_excel import export_master_excel



        export_master_excel(self, self.project_data(), self.editor.blocks())







    def export_master_pdf(self):



        from project_dossier import export_master_pdf



        export_master_pdf(self, self.project_data(), self.editor.blocks())







    def export_docx(self):



        if getattr(self, '_import_job', None):



            QMessageBox.information(self, ui_text('Importacion en curso'), ui_text('Espera a que termine la importacion del guion.'))



            return



        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Exportar guion editable a Word'), '', 'Word (*.docx)')



        if not filename:



            return



        target = Path(filename if filename.lower().endswith('.docx') else filename + '.docx')



        try:



            if self.path and target.resolve() == self.path.resolve():



                raise ValueError('El destino no puede ser el proyecto abierto.')



            from script_docx import export_script_docx



            export_script_docx(target, self.editor.blocks())



        except Exception as error:



            QMessageBox.critical(self, ui_text('No se pudo exportar Word'), str(error))



            return



        QMessageBox.information(self, ui_text('Word exportado'), 'Guion editable guardado. Word puede cambiar los saltos de pagina; usa PDF para conservar la presentacion fija.')







    def repair_imported_format(self):



        from script_import import parse_fountain



        from PySide6.QtGui import QTextCursor



        blocks = self.editor.blocks()



        # Keep stored paragraph boundaries, IDs and all text unchanged.



        source = '\n'.join(b['text'].replace('\n', ' ') for b in blocks)



        parsed = parse_fountain(source, relaxed=True)



        nonempty = [(i, b) for i, b in enumerate(blocks) if b['text'].strip()]



        if len(parsed) != len(nonempty):



            QMessageBox.information(self, ui_text('Revisar formato'), 'No se pudo proponer un formato seguro. Selecciona cada bloque y usa Ctrl+1 a Ctrl+6.')



            return



        changes = [(i, b, proposed['type']) for (i, b), proposed in zip(nonempty, parsed)



                   if b['type'] == 'action' and proposed['type'] in ('character', 'dialogue', 'parenthetical')]



        if not changes:



            QMessageBox.information(self, ui_text('Revisar formato'), 'No se encontraron cambios de formato para proponer.')



            return



        preview = '\n'.join(f"{app.TYPE_LABELS[kind]}: {b['text'][:70]}" for i, b, kind in changes[:16])



        answer = QMessageBox.question(self, ui_text('Revisar formato importado'),



            f'Se proponen {len(changes)} cambios de formato. La deteccion es aproximada; revisa los nombres y dialogos.\n\n'



            + preview + '\n\nAplicar sin cambiar textos ni identificadores? Guarda una copia del proyecto antes de aplicar.')



        if answer != QMessageBox.StandardButton.Yes:



            return



        original = self.editor.textCursor()



        cursor = QTextCursor(self.editor.document())



        cursor.beginEditBlock()



        try:



            for index, block, kind in changes:



                self.editor.setTextCursor(QTextCursor(self.editor.document().findBlockByNumber(index)))



                self.editor.apply_type(kind, transform=False)



        finally:



            cursor.endEditBlock()



            self.editor.setTextCursor(original)



        self.document_changed()







    def setup_shortcuts(self):



        self.format_shortcuts = []



        file_menu = self.menuBar().actions()[0].menu()



        menu = file_menu.addMenu(ui_text('Formato de guion'))



        repair = app.QAction(ui_text('Revisar formato de texto importado...'), self)



        repair.triggered.connect(self.repair_imported_format)



        menu.addAction(repair)



        menu.addSeparator()



        for index, kind in enumerate(app.BLOCK_TYPES, 1):



            action = app.QAction(app.TYPE_LABELS[kind].title(), self.editor)



            action.setShortcut(app.QKeySequence('Ctrl+' + str(index)))



            action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)



            action.triggered.connect(lambda checked=False, value=kind: self.editor.apply_type(value))



            self.editor.addAction(action)



            menu.addAction(action)



            self.format_shortcuts.append(action)



        edit = file_menu.addMenu(ui_text('Edición de guion'))



        for label, key, callback in ((ui_text('Deshacer'), 'Ctrl+Z', self.editor.undo),



                                     (ui_text('Rehacer'), 'Ctrl+Y', self.editor.redo),



                                     (ui_text('Cortar'), 'Ctrl+X', self.editor.cut),



                                     (ui_text('Copiar'), 'Ctrl+C', self.editor.copy),



                                     (ui_text('Pegar'), 'Ctrl+V', self.editor.paste),



                                     (ui_text('Seleccionar todo'), 'Ctrl+A', self.editor.selectAll)):



            action = app.QAction(label, self.editor)



            action.setShortcut(app.QKeySequence(key))



            action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)



            action.triggered.connect(callback)



            self.editor.addAction(action)



            edit.addAction(action)



        self.pdf_action.setShortcut(app.QKeySequence('Ctrl+Shift+E'))



        help_action = app.QAction(ui_text('Atajos de teclado'), self)



        help_action.setShortcut(app.QKeySequence('F1'))



        help_action.triggered.connect(lambda: QMessageBox.information(self, ui_text('Atajos de teclado'),



            'Ctrl+1 Escena\nCtrl+2 Accion\nCtrl+3 Personaje\nCtrl+4 Dialogo\nCtrl+5 Parentetico\nCtrl+6 Transicion\n\n'



            'Tab: siguiente formato\nEnter: siguiente bloque de guion\n'



            'Ctrl+Z / Ctrl+Y: deshacer / rehacer\nCtrl+X / C / V: cortar / copiar / pegar\n'



            'Ctrl+A: seleccionar todo\nCtrl+N: nuevo\nCtrl+O: abrir\nCtrl+S: guardar\n'



            'Ctrl+Shift+E: exportar PDF\nF11: concentracion\n\nLos atajos de formato y edicion actuan en el editor de guion.'))



        self._keyboard_shortcuts_action = help_action







    def toggle_dark(self):



        self.dark = True



        QSettings().setValue('dark', True)



        self.apply_theme()



    def apply_theme(self):



        base = app.DARK if getattr(self, 'dark', False) else app.LIGHT



        base = base.replace("font-family: 'Segoe UI'", 'font-family: "Segoe UI"')



        base = base.replace('font-family: Georgia', 'font-family: "Georgia"')



        qt = QApplication.instance()



        if getattr(self, 'dark', False):



            qt.setPalette(warm_dark_palette())



        qt.setStyleSheet(petroleum_stylesheet(base + SUITE_STYLE + (DARK_ADDITION if getattr(self, 'dark', False) else '') + ' QTabBar::tab { padding: 8px 7px; }'))







    def build_suite(self):



        script_workspace = self.takeCentralWidget()



        self.modules = QTabWidget()



        self.modules.setDocumentMode(True)



        self.modules.setIconSize(QSize(14, 14))



        tab_bar = self.modules.tabBar()



        tab_bar.setUsesScrollButtons(False)



        tab_bar.setElideMode(Qt.TextElideMode.ElideRight)



        tab_bar.setExpanding(False)



        self.modules.addTab(script_workspace, qta.icon('fa6s.pen-nib', color=ACCENT), ui_text('Guion'))



        self.treatment_page = TreatmentPage()



        self.treatment_page.load_data(self.treatment_data)



        self.treatment_page.changed.connect(self.treatment_changed)



        self.treatment_page.convert_requested.connect(self.convert_treatment_to_scene)



        self.modules.addTab(self.treatment_page, qta.icon('fa6s.file-lines', color=ACCENT), ui_text('Desarrollo'))



        self.scene_navigator = SceneNavigatorPage()



        self.scene_navigator.scene_activated.connect(self.open_scene_from_navigator)



        self.scene_navigator.development_changed.connect(self.scene_development_changed)



        self.scene_navigator.set_development_data(self.scene_development)



        self.modules.addTab(self.scene_navigator, qta.icon('fa6s.list', color=ACCENT), ui_text('Navegador'))



        self.scene_navigator.set_scenes(self.current_scenes())



        self.scene_versions_page = SceneVersionsPage()



        self.scene_versions_page.save_requested.connect(self.save_scene_version)



        self.scene_versions_page.restore_requested.connect(self.restore_scene_version)



        self.scene_versions_page.delete_requested.connect(self.delete_scene_version)



        self.scene_versions_page.scene_selected.connect(self.open_scene_from_versions)



        self.modules.addTab(self.scene_versions_page, qta.icon('fa6s.clock-rotate-left', color=ACCENT), ui_text('Versiones'))



        self.scene_versions_page.set_scenes(self.current_scenes())



        self.scene_versions_page.set_versions(self.scene_versions)



        self.dialogue_tuner = DialogueTunerPage()



        self.dialogue_tuner.dialogue_activated.connect(self.open_dialogue_from_tuner)



        self.modules.addTab(self.dialogue_tuner, qta.icon('fa6s.comments', color=ACCENT), ui_text('Diálogos'))



        self.dialogue_tuner.set_entries(self.dialogue_entries())



        self.character_page = CharacterArcPage()



        self.character_page.set_scenes(self.current_scenes())



        self.character_page.set_data(self.character_arcs)



        self.character_page.scene_open_requested.connect(self.open_scene_from_navigator)



        self.character_page.data_changed.connect(self.character_development_changed)



        self.modules.addTab(self.character_page, qta.icon('fa6s.user-pen', color=ACCENT), ui_text('Personajes'))



        self.story_map = StoryMapPage()



        self.story_map.set_scenes(self.current_scenes())



        self.story_map.scene_open_requested.connect(self.open_scene_from_versions)



        self.modules.addTab(self.story_map, qta.icon('fa6s.diagram-project', color=ACCENT), ui_text('Mapa de tramas'))



        self.analysis_page = AnalysisPage()



        self.analysis_page.scene_open_requested.connect(self.open_scene_from_navigator)



        self.analysis_page.character_open_requested.connect(self.open_character_from_analysis)



        self.analysis_page.markers_changed.connect(self.analysis_markers_changed)



        self.analysis_page.dramatic_structure_changed.connect(self.dramatic_structure_changed)



        self.analysis_page.set_markers(self.analysis_markers)



        self.analysis_page.set_dramatic_structure(self.dramatic_structure)



        self.modules.addTab(self.analysis_page, qta.icon('fa6s.chart-line', color=ACCENT), ui_text('Análisis'))



        self.breakdown_page = self.build_breakdown_page()



        self.modules.addTab(self.breakdown_page, qta.icon('fa6s.clapperboard', color=ACCENT), ui_text('Desglose'))



        self.schedule_page = SchedulingPage()



        self.schedule_page.sync_button.clicked.connect(self.sync_schedule)



        self.modules.addTab(self.schedule_page, qta.icon('fa6s.calendar-days', color=ACCENT), ui_text('Plan de rodaje'))



        self.budget_page = self.build_budget_page()



        self.modules.addTab(self.budget_page, qta.icon('fa6s.calculator', color=ACCENT), ui_text('Presupuesto'))



        self.refresh_analysis_page()



        self.setCentralWidget(self.modules)







    def treatment_changed(self):



        self.treatment_data = self.treatment_page.to_data()



        self.dirty = True







    def convert_treatment_to_scene(self, title, text):



        heading = (title or 'NUEVA ESCENA').strip().upper()



        if not (heading.startswith('INT.') or heading.startswith('EXT.') or heading.startswith('I/E')):



            heading = 'INT. ' + heading + ' - DIA'



        blocks = self.editor.blocks()



        blocks.extend([{'type': 'scene', 'text': heading}, {'type': 'action', 'text': text}])



        self.editor.load_blocks(blocks)



        self.document_changed()



        self.modules.setCurrentIndex(0)



        QMessageBox.information(self, ui_text('Tratamiento'), ui_text('El bloque se agregó al guion como una nueva escena. El tratamiento original se conserva.'))







    def new_document(self):



        super().new_document()



        if hasattr(self, 'treatment_page'):



            self.treatment_data = []



            self.treatment_page.load_data([])







    def refresh(self):



        """Refresca el editor base y las vistas derivadas de desarrollo."""



        super().refresh()



        if hasattr(self, 'scene_navigator') and hasattr(self, 'editor'):



            scenes = self.current_scenes()



            self.scene_navigator.set_scenes(scenes)



            self.scene_navigator.set_development_data(self.scene_development)



            if hasattr(self, 'scene_versions_page'):



                self.scene_versions_page.set_scenes(scenes)



                self.scene_versions_page.set_versions(self.scene_versions)



            if hasattr(self, 'dialogue_tuner'):



                self.dialogue_tuner.set_entries(self.dialogue_entries())



            if hasattr(self, 'character_page'):



                self.character_page.set_scenes(scenes)



            if hasattr(self, 'story_map'):



                self.story_map.set_scenes(scenes)



            if hasattr(self, 'analysis_page'):



                self.refresh_analysis_page()







    def scene_development_changed(self):



        """Guarda los datos Objetivo / Obstáculo / Resultado del Navegador."""



        self.scene_development = self.scene_navigator.development_data()



        self.dirty = True



        if hasattr(self, 'analysis_page'):



            self.refresh_analysis_page()







    def character_development_changed(self):



        """Marca el proyecto como modificado al editar datos del arco de personaje."""



        self.character_arcs = self.character_page.to_data()



        self.dirty = True



        if hasattr(self, 'analysis_page'):



            self.refresh_analysis_page()







    def refresh_analysis_page(self):



        if not hasattr(self, 'analysis_page'):



            return



        story_data = self.story_map.to_data() if hasattr(self, 'story_map') and hasattr(self.story_map, 'to_data') else []



        self.analysis_page.set_project_data(



            scenes=self.current_scenes(),



            dialogues=self.dialogue_entries(),



            story_map=story_data,



            scene_development=self.scene_development,



            character_arcs=self.character_arcs,



            breakdown=self.breakdown_data() if hasattr(self, 'breakdown') else [],



        )



        self.analysis_page.set_markers(self.analysis_markers)



        self.analysis_page.set_dramatic_structure(self.dramatic_structure)



        self.apply_analysis_highlights()







    def dramatic_structure_changed(self, data):



        self.dramatic_structure = dict(data or {})



        self.dirty = True







    def analysis_markers_changed(self, data):



        self.analysis_markers = {



            'characters': dict((data or {}).get('characters', {})),



            'scenes': dict((data or {}).get('scenes', {})),



            'show_in_script': bool((data or {}).get('show_in_script', False)),



        }



        self.dirty = True



        self.apply_analysis_highlights()







    def apply_analysis_highlights(self):



        """Aplica resaltados temporales al editor sin modificar el texto ni el .FDX."""



        if not hasattr(self, 'editor'):



            return



        data = self.analysis_markers or {}



        if not data.get('show_in_script'):



            self.editor.setExtraSelections([])



            return







        char_colors = dict(data.get('characters', {}))



        scene_colors = dict(data.get('scenes', {}))



        if not char_colors and not scene_colors:



            self.editor.setExtraSelections([])



            return







        # Only materialize selections for visible blocks. Walking backwards recovers



        # scene/dialogue context when the viewport starts in the middle of a scene.



        document = self.editor.document()



        layout = document.documentLayout()



        top = self.editor.verticalScrollBar().value()



        bottom = top + self.editor.viewport().height()



        # cursorForPosition can jump to the end of a page inside page margins.



        # Search actual block rectangles so margins and long blocks are handled.



        lo, hi = 0, document.blockCount()



        while lo < hi:



            mid = (lo + hi) // 2



            if layout.blockBoundingRect(document.findBlockByNumber(mid)).bottom() < top:



                lo = mid + 1



            else:



                hi = mid



        first = document.findBlockByNumber(min(lo, document.blockCount() - 1))



        lo, hi = first.blockNumber(), document.blockCount()



        while lo < hi:



            mid = (lo + hi) // 2



            if layout.blockBoundingRect(document.findBlockByNumber(mid)).top() <= bottom:



                lo = mid + 1



            else:



                hi = mid



        last = document.findBlockByNumber(max(first.blockNumber(), lo - 1))



        active_scene_color = None



        active_character_color = None



        previous = first.previous()



        find_character = self.editor.block_type(first) in ('dialogue', 'parenthetical')



        while previous.isValid():



            kind = self.editor.block_type(previous)



            if find_character and kind == 'character':



                active_character_color = char_colors.get(normalize_character_name(previous.text()))



                find_character = False



            elif find_character and kind not in ('dialogue', 'parenthetical'):



                find_character = False



            if kind == 'scene':



                active_scene_color = scene_colors.get(str(previous.blockFormat().property(1001) or ''))



                break



            previous = previous.previous()



        selections = []



        block = first



        while block.isValid() and block.position() <= last.position():



            kind = self.editor.block_type(block)



            if kind == 'scene':



                active_scene_color = scene_colors.get(str(block.blockFormat().property(1001) or ''))



            if kind == 'character':



                active_character_color = char_colors.get(normalize_character_name(block.text()))



            elif kind not in ('dialogue', 'parenthetical'):



                active_character_color = None



            for value, alpha in ((active_scene_color, 72 if kind == 'scene' else 36),



                                 (active_character_color, 92)):



                color = QColor(value) if value else QColor()



                if not color.isValid(): continue



                color.setAlpha(alpha)



                selection = app.QTextEdit.ExtraSelection()



                selection.cursor = app.QTextCursor(block)



                selection.cursor.select(app.QTextCursor.SelectionType.BlockUnderCursor)



                selection.format.setBackground(color)



                selections.append(selection)



            block = block.next()







        self.editor.setExtraSelections(selections)







    def open_character_from_analysis(self, character):



        if not hasattr(self, 'character_page'):



            return



        index = self.modules.indexOf(self.character_page)



        if index >= 0:



            self.modules.setCurrentIndex(index)



        combo = getattr(self.character_page, 'character_combo', None)



        if combo is not None:



            combo.setCurrentText(character)







    def dialogue_entries(self):



        """Extrae intervenciones por personaje conservando el índice real del guion."""



        blocks = self.editor.blocks()



        entries = []



        scene_id = ''



        scene_heading = ''



        scene_number = 0



        index = 0



        while index < len(blocks):



            block = blocks[index]



            kind = block.get('type', 'action')



            if kind == 'scene':



                scene_id = block.get('id', '')



                scene_heading = block.get('text', '')



                scene_number += 1



                index += 1



                continue



            if kind != 'character' or not scene_id:



                index += 1



                continue







            character = block.get('text', '').strip()



            cue_index = index



            parentheticals = []



            dialogue_parts = []



            index += 1



            while index < len(blocks):



                following = blocks[index]



                following_kind = following.get('type', 'action')



                if following_kind == 'parenthetical':



                    text = following.get('text', '').strip()



                    if text:



                        parentheticals.append(text)



                    index += 1



                    continue



                if following_kind == 'dialogue':



                    text = following.get('text', '').strip()



                    if text:



                        dialogue_parts.append(text)



                    index += 1



                    continue



                break







            dialogue = '\n'.join(dialogue_parts).strip()



            if character and dialogue:



                entries.append({



                    'character': character,



                    'character_normalized': normalize_character_name(character),



                    'dialogue': dialogue,



                    'parenthetical': ' '.join(parentheticals),



                    'scene_id': scene_id,



                    'scene_number': scene_number,



                    'heading': scene_heading,



                    'block_index': cue_index,



                    'word_count': len(dialogue.split()),



                })



        return entries







    def open_dialogue_from_tuner(self, scene_id, block_index):



        """Salta al parlamento seleccionado sin alterar el guion."""



        document = self.editor.document()



        block = document.findBlockByNumber(block_index)



        if not block.isValid():



            return



        self.modules.setCurrentIndex(0)



        cursor = app.QTextCursor(block)



        self.editor.setTextCursor(cursor)



        self.editor.ensureCursorVisible()



        self.editor.setFocus()







    def _scene_slice(self, scene_id):



        blocks = self.editor.blocks()



        start = next((index for index, block in enumerate(blocks) if block.get('type') == 'scene' and block.get('id') == scene_id), -1)



        if start < 0:



            return blocks, -1, -1



        end = next((index for index in range(start + 1, len(blocks)) if blocks[index].get('type') == 'scene'), len(blocks))



        return blocks, start, end







    def save_scene_version(self, scene_id, name):



        import uuid



        from datetime import datetime



        blocks, start, end = self._scene_slice(scene_id)



        if start < 0:



            QMessageBox.warning(self, ui_text('Versiones de escena'), ui_text('No se encontró la escena en el guion actual.'))



            return False



        snapshot = [{key: block.get(key, '') for key in ('type', 'text', 'id')} for block in blocks[start:end]]



        version = {



            'id': uuid.uuid4().hex,



            'name': name.strip() or 'Versión',



            'created_at': datetime.now().isoformat(timespec='seconds'),



            'heading': blocks[start].get('text', ''),



            'blocks': snapshot,



        }



        self.scene_versions.setdefault(scene_id, []).append(version)



        self.dirty = True



        self.scene_versions_page.set_versions(self.scene_versions)



        self.scene_versions_page.select_scene(scene_id)



        self.statusBar().showMessage(f"Versión guardada: {version['name']}")



        return True







    def restore_scene_version(self, scene_id, version_id):



        import uuid



        versions = self.scene_versions.get(scene_id, [])



        version = next((row for row in versions if row.get('id') == version_id), None)



        if not version:



            QMessageBox.warning(self, ui_text('Versiones de escena'), ui_text('La versión seleccionada ya no existe.'))



            return False



        blocks, start, end = self._scene_slice(scene_id)



        if start < 0:



            QMessageBox.warning(self, ui_text('Versiones de escena'), ui_text('La escena original ya no existe en el guion.'))



            return False



        replacement = []



        for index, block in enumerate(version.get('blocks', [])):



            kind = block.get('type', 'action')



            replacement.append({



                'type': kind,



                'text': block.get('text', ''),



                'id': scene_id if index == 0 and kind == 'scene' else uuid.uuid4().hex,



            })



        if not replacement or replacement[0].get('type') != 'scene':



            QMessageBox.warning(self, ui_text('Versiones de escena'), ui_text('La versión guardada no contiene una escena válida.'))



            return False



        self._loading = True



        try:



            self.editor.load_blocks(blocks[:start] + replacement + blocks[end:])



        finally:



            self._loading = False



        self.dirty = True



        self.refresh()



        self.scene_versions_page.select_scene(scene_id)



        self.open_scene_from_versions(scene_id)



        self.statusBar().showMessage(f"Versión restaurada: {version.get('name', 'Versión')}")



        return True







    def delete_scene_version(self, scene_id, version_id):



        rows = self.scene_versions.get(scene_id, [])



        remaining = [row for row in rows if row.get('id') != version_id]



        if len(remaining) == len(rows):



            return False



        if remaining:



            self.scene_versions[scene_id] = remaining



        else:



            self.scene_versions.pop(scene_id, None)



        self.dirty = True



        self.scene_versions_page.set_versions(self.scene_versions)



        self.scene_versions_page.select_scene(scene_id)



        self.statusBar().showMessage('Versión eliminada del historial.')



        return True







    def open_scene_from_versions(self, scene_id):



        scene = next((row for row in self.current_scenes() if row.get('id') == scene_id), None)



        if scene:



            self.open_scene_from_navigator(scene_id, scene.get('index', -1))







    def open_scene_from_navigator(self, scene_id, block_index):



        """Abre en el editor la escena activada desde el Navegador."""



        document = self.editor.document()



        block = document.findBlockByNumber(block_index)



        if not block.isValid():



            # El índice puede haber cambiado entre el filtrado y el doble clic.



            for scene in self.current_scenes():



                if scene.get('id') == scene_id:



                    block = document.findBlockByNumber(scene.get('index', -1))



                    break



        if not block.isValid():



            return



        self.modules.setCurrentIndex(0)



        cursor = app.QTextCursor(block)



        self.editor.setTextCursor(cursor)



        self.editor.ensureCursorVisible()



        self.editor.setFocus()







    def add_professional_actions(self, allow_mode=False):



        file_menu = self.menuBar().actions()[0].menu()



        export_menu = next((item.menu() for item in file_menu.actions() if item.menu() and item.text() == ui_text('Exportar')), file_menu)



        fdx_action = app.QAction(qta.icon('fa6s.file-export', color=ACCENT), 'Final Draft (FDX)', self)



        fdx_action.triggered.connect(self.export_fdx); export_menu.addAction(fdx_action)



        help_menu = self.menuBar().addMenu(ui_text('Ayuda'))



        if hasattr(self, '_keyboard_shortcuts_action'):



            help_menu.addAction(self._keyboard_shortcuts_action)



        guide_action = app.QAction(ui_text('Guía'), self)



        guide_action.triggered.connect(lambda: __import__('workflow_ui').show_guide(self)); help_menu.addAction(guide_action)



        help_menu.addSeparator()



        about_action = app.QAction(ui_text('Acerca de'), self)



        about_action.triggered.connect(self.show_about); help_menu.addAction(about_action)



    def add_standard_actions(self):



        help_menu = self.menuBar().addMenu(ui_text('Ayuda'))



        if hasattr(self, '_keyboard_shortcuts_action'):



            help_menu.addAction(self._keyboard_shortcuts_action)



        guide_action = app.QAction(ui_text('Guía'), self)



        guide_action.triggered.connect(lambda: __import__('workflow_ui').show_guide(self)); help_menu.addAction(guide_action)



        help_menu.addSeparator()



        about_action = app.QAction('Acerca de Eleuthera Standard', self)



        about_action.triggered.connect(self.show_about); help_menu.addAction(about_action)



    def show_about(self):



        QMessageBox.about(



            self,



            ui_text('Acerca de'),



            '<b>Eleuthera Cinema Suite Profesional</b>'



            '<br>Desarrollado por Francisco Contreras'



            '<br><span style="font-size: 8pt;">Con asistencia de OpenAI Codex</span>'



        )



    def add_workspace_selector(self):



        toolbar = self.findChild(app.QToolBar)



        if not toolbar:



            return



        toolbar.addSeparator(); toolbar.addWidget(QLabel(ui_text('Espacio:')))



        self.mode_combo = QComboBox(); self.mode_combo.addItem(ui_text('Estándar'), 'standard'); self.mode_combo.addItem(ui_text('Profesional'), 'professional')



        self.mode_combo.setCurrentIndex(1 if self.workspace_mode == 'professional' else 0)



        self.mode_combo.currentIndexChanged.connect(self.workspace_mode_changed); toolbar.addWidget(self.mode_combo)







    def choose_workspace_mode(self):



        dialog = WorkspaceModeDialog(self.workspace_mode, self)



        if dialog.exec():



            self.set_workspace_mode(dialog.selected_mode())



            QSettings().setValue('workspace_mode_chosen', True)







    def workspace_mode_changed(self, index):



        self.set_workspace_mode(self.mode_combo.itemData(index))







    def set_workspace_mode(self, mode):



        self.workspace_mode = mode if self.edition == 'combined' else self.edition



        if self.edition == 'combined': QSettings().setValue('workspace_mode', self.workspace_mode)



        self.apply_workspace_mode()







    def apply_workspace_mode(self):



        if not hasattr(self, 'modules'):



            return



        professional = self.workspace_mode == 'professional'



        self.modules.setTabText(self.modules.indexOf(self.breakdown_page), ui_text('Desglose'))



        self.modules.setTabText(self.modules.indexOf(self.budget_page), ui_text('Presupuesto'))



        self.modules.setTabVisible(self.modules.indexOf(self.schedule_page), professional)



        if hasattr(self, 'professional_budget_tools'):



            self.professional_budget_tools.setVisible(professional)



            self.standard_budget_add.setVisible(not professional)



            for column in (0, 1, 2, 6, 9, 10, 11):



                self.budget.setColumnHidden(column, not professional)



            self.budget.horizontalHeaderItem(4).setText(ui_text('Cuenta / concepto') if professional else ui_text('Concepto'))



    def module_header(self, title, hint):



        box = QVBoxLayout()



        description = QLabel(hint)



        description.setObjectName('moduleHint')



        description.setWordWrap(True)



        box.addWidget(description)



        return box







    def build_breakdown_page(self):



        page = QFrame()



        page.setObjectName('workspace')



        layout = QVBoxLayout(page)



        layout.setContentsMargins(30, 25, 30, 28)



        actions = QHBoxLayout()



        self.breakdown_actions = actions



        analyze = QPushButton(ui_text('Analizar guion'))



        analyze.setObjectName('primary')



        analyze.setIcon(qta.icon('fa6s.wand-magic-sparkles', color='white'))



        analyze.clicked.connect(self.analyze_script)



        add = QPushButton(ui_text('Agregar elemento'))



        add.setIcon(qta.icon('fa6s.plus', color='#57534e'))



        add.clicked.connect(self.add_breakdown_row)



        remove = QPushButton(ui_text('Quitar'))



        remove.clicked.connect(self.remove_breakdown_rows)



        export = QPushButton(ui_text('Exportar desglose'))



        export.setIcon(qta.icon('fa6s.file-export', color='#57534e'))



        export.clicked.connect(self.export_breakdown)



        to_budget = QPushButton(ui_text('Presupuestar aprobados'))



        to_budget.setIcon(qta.icon('fa6s.arrow-right', color='#57534e'))



        to_budget.clicked.connect(self.approved_to_budget)



        actions.addWidget(analyze)



        actions.addWidget(add)



        actions.addWidget(remove)



        actions.addWidget(export)



        actions.addStretch()



        actions.addWidget(to_budget)



        layout.addLayout(actions)



        approval_actions = QHBoxLayout()



        self.approve_all_button = QPushButton(ui_text('Aprobar todos'))



        self.approve_all_button.setToolTip('Marca todos los elementos del desglose para presupuestarlos.')



        self.approve_all_button.clicked.connect(lambda: self.set_all_breakdown_approved(True))



        self.unapprove_all_button = QPushButton(ui_text('Desmarcar todos'))



        self.unapprove_all_button.clicked.connect(lambda: self.set_all_breakdown_approved(False))



        approval_actions.addWidget(self.approve_all_button)



        approval_actions.addWidget(self.unapprove_all_button)



        approval_actions.addStretch()



        approval_actions.addWidget(QLabel(ui_text('Enviar al presupuesto como:')))



        self.breakdown_budget_block = QComboBox()



        self.breakdown_budget_block.addItems(('BTL', 'ATL'))



        approval_actions.addWidget(self.breakdown_budget_block)



        layout.addLayout(approval_actions)

        # FASE 2 DESGLOSE: ordenar las herramientas ya existentes sin cambiar
        # su comportamiento. La barra queda compacta y agrupada por tarea.
        excel_tools = QHBoxLayout()
        self.breakdown_excel_tools = excel_tools
        excel_tools.setSpacing(6)

        def tool_separator():
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.VLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            return separator

        # Edición
        edit_btn = QPushButton(ui_text('Edición') + ' ▾')
        edit_menu = QMenu(edit_btn)
        for label, callback in ((ui_text('Cortar'), self.breakdown_cut),
                                (ui_text('Copiar'), self.breakdown_copy),
                                (ui_text('Pegar'), self.breakdown_paste)):
            action = edit_menu.addAction(label)
            action.triggered.connect(callback)
        edit_btn.setMenu(edit_menu)
        excel_tools.addWidget(edit_btn)
        excel_tools.addWidget(tool_separator())

        # Formato de texto y celda
        excel_tools.addWidget(QLabel(ui_text('Formato:')))
        bold_btn = QPushButton('B')
        bold_btn.setCheckable(True)
        bold_btn.setMaximumWidth(34)
        bold_btn.setToolTip(ui_text('Negrita'))
        bold_btn.clicked.connect(lambda checked: self.breakdown_format_font('bold', checked))
        excel_tools.addWidget(bold_btn)

        italic_btn = QPushButton('I')
        italic_btn.setCheckable(True)
        italic_btn.setMaximumWidth(34)
        italic_btn.setToolTip(ui_text('Cursiva'))
        italic_btn.clicked.connect(lambda checked: self.breakdown_format_font('italic', checked))
        excel_tools.addWidget(italic_btn)

        underline_btn = QPushButton('U')
        underline_btn.setCheckable(True)
        underline_btn.setMaximumWidth(34)
        underline_btn.setToolTip(ui_text('Subrayado'))
        underline_btn.clicked.connect(lambda checked: self.breakdown_format_font('underline', checked))
        excel_tools.addWidget(underline_btn)

        self.breakdown_font_size = QComboBox()
        self.breakdown_font_size.addItems(tuple(str(n) for n in (8, 9, 10, 11, 12, 14, 16, 18, 20, 24)))
        self.breakdown_font_size.setCurrentText('10')
        self.breakdown_font_size.setMaximumWidth(62)
        self.breakdown_font_size.setToolTip(ui_text('Tamaño de fuente'))
        self.breakdown_font_size.currentTextChanged.connect(self.breakdown_format_font_size)
        excel_tools.addWidget(self.breakdown_font_size)

        text_btn = QPushButton(ui_text('Texto'))
        text_btn.setToolTip(ui_text('Color del texto'))
        text_btn.clicked.connect(self.breakdown_format_text_color)
        excel_tools.addWidget(text_btn)

        bg_btn = QPushButton(ui_text('Fondo'))
        bg_btn.setToolTip(ui_text('Color de fondo'))
        bg_btn.clicked.connect(self.breakdown_format_background)
        excel_tools.addWidget(bg_btn)

        border_btn = QPushButton(ui_text('Bordes'))
        border_btn.clicked.connect(self.breakdown_format_borders)
        excel_tools.addWidget(border_btn)

        align_btn = QPushButton(ui_text('Alinear') + ' ▾')
        align_menu = QMenu(align_btn)
        for label, alignment in ((ui_text('Izquierda'), Qt.AlignmentFlag.AlignLeft),
                                 (ui_text('Centro'), Qt.AlignmentFlag.AlignHCenter),
                                 (ui_text('Derecha'), Qt.AlignmentFlag.AlignRight)):
            action = align_menu.addAction(label)
            action.triggered.connect(lambda checked=False, a=alignment: self.breakdown_format_alignment(a))
        align_btn.setMenu(align_menu)
        excel_tools.addWidget(align_btn)

        clear_fmt_btn = QPushButton(ui_text('Limpiar'))
        clear_fmt_btn.setToolTip(ui_text('Limpiar formato'))
        clear_fmt_btn.clicked.connect(self.breakdown_clear_format)
        excel_tools.addWidget(clear_fmt_btn)
        excel_tools.addWidget(tool_separator())

        # Búsqueda separada de edición para que sea localizable de inmediato.
        search_btn = QPushButton(ui_text('Buscar') + ' ▾')
        search_menu = QMenu(search_btn)
        for label, callback in ((ui_text('Buscar…'), self.breakdown_find),
                                (ui_text('Buscar y reemplazar…'), self.breakdown_replace)):
            action = search_menu.addAction(label)
            action.triggered.connect(callback)
        search_btn.setMenu(search_menu)
        excel_tools.addWidget(search_btn)

        # Operaciones que afectan la presentación/conjunto de filas.
        data_btn = QPushButton(ui_text('Datos') + ' ▾')
        data_menu = QMenu(data_btn)
        for label, callback in ((ui_text('Orden ascendente'), lambda: self.breakdown_sort(True)),
                                (ui_text('Orden descendente'), lambda: self.breakdown_sort(False)),
                                (ui_text('Filtrar por texto…'), self.breakdown_filter),
                                (ui_text('Mostrar todas las filas'), self.breakdown_show_all)):
            action = data_menu.addAction(label)
            action.triggered.connect(callback)
        data_btn.setMenu(data_menu)
        excel_tools.addWidget(data_btn)
        excel_tools.addStretch()
        layout.addLayout(excel_tools)

        self.breakdown = EleutheraSpreadsheet(0, 5)

        # Desglose: la seleccion no debe tapar el fondo propio de la celda.
        # El delegate dibuja el borde de seleccion; aqui anulamos unicamente
        # el background de QSS para el estado selected de esta tabla.
        self.breakdown.setStyleSheet(
            self.breakdown.styleSheet()
            + 'QTableWidget::item:selected{background:transparent;}'
        )



        self.breakdown.setHorizontalHeaderLabels((ui_text('Aprobado'), ui_text('Escena'), ui_text('Categoria'), ui_text('Elemento'), ui_text('Texto de origen')))



        self.breakdown.setAlternatingRowColors(False)



        self.breakdown.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)



        self.breakdown.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)



        self.breakdown.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)



        self.breakdown.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)



        layout.addWidget(self.breakdown, 1)



        return page







    def _breakdown_selected_cells(self):
        if not hasattr(self, 'breakdown'):
            return []
        return self.breakdown.selected_items_including_empty()

    def breakdown_format_background(self):
        items = self._breakdown_selected_cells()
        if not items: return
        initial = items[0].background().color() if items[0].background().style() != Qt.BrushStyle.NoBrush else QColor('#ffffff')
        color = QColorDialog.getColor(initial, self, ui_text('Fondo de celda'))
        if color.isValid():
            for item in items: item.setBackground(QBrush(color))

    def breakdown_format_text_color(self):
        items = self._breakdown_selected_cells()
        if not items: return
        initial = items[0].foreground().color() if items[0].foreground().style() != Qt.BrushStyle.NoBrush else QColor('#111111')
        color = QColorDialog.getColor(initial, self, ui_text('Color del texto'))
        if color.isValid():
            for item in items: item.setForeground(QBrush(color))

    def breakdown_format_font(self, kind, enabled):
        for item in self._breakdown_selected_cells():
            font = item.font()
            if kind == 'bold': font.setBold(bool(enabled))
            elif kind == 'italic': font.setItalic(bool(enabled))
            elif kind == 'underline': font.setUnderline(bool(enabled))
            item.setFont(font)

    def breakdown_format_font_size(self, value):
        try: size = int(value)
        except (TypeError, ValueError): return
        for item in self._breakdown_selected_cells():
            font = item.font(); font.setPointSize(size); item.setFont(font)

    def breakdown_format_alignment(self, horizontal):
        for item in self._breakdown_selected_cells():
            item.setTextAlignment(horizontal | Qt.AlignmentFlag.AlignVCenter)

    def breakdown_format_borders(self):
        from eleuthera_spreadsheet import BORDER_ROLE
        items = self._breakdown_selected_cells()
        if not items: return
        color = QColorDialog.getColor(QColor('#707070'), self, ui_text('Color de borde'))
        if not color.isValid(): return
        for item in items: item.setData(BORDER_ROLE, color.name())
        self.breakdown.viewport().update()

    def breakdown_clear_format(self):
        from eleuthera_spreadsheet import BORDER_ROLE
        for item in self._breakdown_selected_cells():
            item.setBackground(QBrush()); item.setForeground(QBrush())
            item.setFont(QFont())
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item.setData(BORDER_ROLE, None)
        self.breakdown.viewport().update()

    def breakdown_copy(self):
        ranges = self.breakdown.selectedRanges()
        if not ranges: return
        rg = ranges[0]; lines = []
        for row in range(rg.topRow(), rg.bottomRow() + 1):
            lines.append('\t'.join(self.breakdown.item(row, col).text() if self.breakdown.item(row, col) else ''
                                   for col in range(rg.leftColumn(), rg.rightColumn() + 1)))
        QApplication.clipboard().setText('\n'.join(lines))

    def breakdown_cut(self):
        self.breakdown_copy()
        for item in self._breakdown_selected_cells():
            if item.flags() & Qt.ItemFlag.ItemIsEditable:
                item.setText('')

    def breakdown_paste(self):
        text = QApplication.clipboard().text()
        if not text: return
        sr, sc = self.breakdown.currentRow(), self.breakdown.currentColumn()
        if sr < 0 or sc < 0: return
        matrix = [row.split('\t') for row in text.rstrip('\n').splitlines()]
        for rr, row in enumerate(matrix):
            for cc, value in enumerate(row):
                r, c = sr + rr, sc + cc
                if r >= self.breakdown.rowCount() or c >= self.breakdown.columnCount(): continue
                item = self.breakdown.ensure_item(r, c)
                if item.flags() & Qt.ItemFlag.ItemIsEditable: item.setText(value)

    def breakdown_find(self):
        query, ok = QInputDialog.getText(self, ui_text('Buscar'), ui_text('Texto a buscar:'))
        if not ok or not query: return
        start = max(0, self.breakdown.currentRow() * self.breakdown.columnCount() + self.breakdown.currentColumn() + 1)
        total = self.breakdown.rowCount() * self.breakdown.columnCount()
        for offset in range(total):
            pos = (start + offset) % max(1, total); row, col = divmod(pos, self.breakdown.columnCount())
            item = self.breakdown.item(row, col)
            if item and query.casefold() in item.text().casefold():
                self.breakdown.setCurrentCell(row, col); self.breakdown.scrollToItem(item); return
        QMessageBox.information(self, ui_text('Buscar'), ui_text('No se encontraron coincidencias.'))

    def breakdown_replace(self):
        find, ok = QInputDialog.getText(self, ui_text('Buscar y reemplazar'), ui_text('Buscar:'))
        if not ok or not find: return
        replacement, ok = QInputDialog.getText(self, ui_text('Buscar y reemplazar'), ui_text('Reemplazar por:'))
        if not ok: return
        changed = 0
        for item in self._breakdown_selected_cells():
            if item.flags() & Qt.ItemFlag.ItemIsEditable and find.casefold() in item.text().casefold():
                import re
                item.setText(re.sub(re.escape(find), lambda m: replacement, item.text(), flags=re.IGNORECASE)); changed += 1
        self.statusBar().showMessage(ui_text('Reemplazos: ') + str(changed))

    def breakdown_sort(self, ascending=True):
        column = self.breakdown.currentColumn()
        if column < 0: return
        self.breakdown.sortItems(column, Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder)

    def breakdown_filter(self):
        query, ok = QInputDialog.getText(self, ui_text('Filtrar desglose'), ui_text('Mostrar filas que contengan:'))
        if not ok: return
        needle = query.casefold().strip()
        for row in range(self.breakdown.rowCount()):
            haystack = ' '.join(self.breakdown.item(row, col).text() if self.breakdown.item(row, col) else ''
                               for col in range(self.breakdown.columnCount())).casefold()
            self.breakdown.setRowHidden(row, bool(needle) and needle not in haystack)

    def breakdown_show_all(self):
        for row in range(self.breakdown.rowCount()): self.breakdown.setRowHidden(row, False)


    def set_all_breakdown_approved(self, approved):



        table = self.breakdown



        blocked = table.blockSignals(True)



        table.setUpdatesEnabled(False)



        try:



            state = Qt.CheckState.Checked if approved else Qt.CheckState.Unchecked



            for row in range(table.rowCount()):



                item = table.item(row, 0)



                if item is not None:



                    item.setCheckState(state)



        finally:



            table.blockSignals(blocked)



            table.setUpdatesEnabled(True)



        self.document_changed()







    def build_budget_page(self):



        page = QFrame()



        page.setObjectName('workspace')



        layout = QVBoxLayout(page)



        layout.setContentsMargins(30, 25, 30, 28)



        actions = QHBoxLayout()



        self.budget_actions = actions



        self.standard_budget_add = QPushButton(ui_text('Agregar concepto'))



        self.standard_budget_add.setObjectName('primary')



        self.standard_budget_add.clicked.connect(lambda: self.add_budget_row(block=self.budget_block.currentText()))



        remove = QPushButton(ui_text('Quitar'))



        remove.clicked.connect(self.remove_budget_rows)



        actions.addWidget(self.standard_budget_add)



        actions.addWidget(remove)



        actions.addStretch()



        layout.addLayout(actions)







        self.professional_budget_tools = QFrame(); professional_tools = QHBoxLayout(self.professional_budget_tools)



        professional_tools.setContentsMargins(0, 0, 0, 0)



        self.budget_block = QComboBox(); self.budget_block.addItems(('ATL', 'BTL'))



        account = QPushButton(ui_text('+ Cuenta')); account.clicked.connect(lambda: self.add_budget_row(level=ui_text('Cuenta'), block=self.budget_block.currentText()))



        detail = QPushButton(ui_text('+ Detalle')); detail.setObjectName('primary'); detail.clicked.connect(lambda: self.add_budget_row(level=ui_text('Detalle'), block=self.budget_block.currentText()))



        subdetail = QPushButton(ui_text('+ Subdetalle')); subdetail.clicked.connect(lambda: self.add_budget_row(level=ui_text('Subdetalle'), block=self.budget_block.currentText()))



        self.global_days = QDoubleSpinBox(); self.global_days.setRange(0, 9999); self.global_days.setValue(1); self.global_days.setPrefix('Días rodaje: ')



        self.default_fringe = QDoubleSpinBox(); self.default_fringe.setRange(0, 999); self.default_fringe.setSuffix(' %'); self.default_fringe.setPrefix('Fringe: ')



        self.base_currency = QComboBox(); self.base_currency.setEditable(True); self.base_currency.addItems(('USD', 'EUR', 'BOB', 'MXN', 'ARS', 'CLP', 'COP', 'PEN'))



        self.base_currency.setParent(self)



        self.base_currency.hide()



        self._last_base_currency = self.base_currency.currentText()



        self.base_currency.currentTextChanged.connect(self.change_base_currency)



        self.budget_block_tools = QFrame()



        block_tools = QHBoxLayout(self.budget_block_tools)



        block_tools.setContentsMargins(0, 0, 0, 0)



        block_tools.addWidget(QLabel(ui_text('Bloque para nuevas partidas:')))



        block_tools.addWidget(self.budget_block)



        self.apply_budget_block_button = QPushButton(ui_text('Aplicar a seleccionadas'))



        self.apply_budget_block_button.clicked.connect(self.apply_selected_budget_block)



        block_tools.addWidget(self.apply_budget_block_button)



        block_tools.addStretch()



        layout.addWidget(self.budget_block_tools)

        # PRESUPUESTO · FASE 1: herramientas de hoja de cálculo.
        # Se mantienen separadas de las herramientas contractuales/financieras;
        # la organización visual definitiva corresponde a la Fase 2.
        budget_excel = QHBoxLayout()
        self.budget_excel_tools = budget_excel
        budget_excel.setSpacing(6)

        edit_btn = QPushButton(ui_text('Edición') + ' ▾')
        edit_menu = QMenu(edit_btn)
        for label, callback in ((ui_text('Cortar'), self.budget_cut),
                                (ui_text('Copiar'), self.budget_copy),
                                (ui_text('Pegar'), self.budget_paste)):
            action = edit_menu.addAction(label); action.triggered.connect(callback)
        edit_btn.setMenu(edit_menu); budget_excel.addWidget(edit_btn)

        budget_excel.addWidget(QLabel(ui_text('Formato:')))
        for label, kind, tip in (('B', 'bold', ui_text('Negrita')),
                                 ('I', 'italic', ui_text('Cursiva')),
                                 ('U', 'underline', ui_text('Subrayado'))):
            button = QPushButton(label); button.setCheckable(True); button.setMaximumWidth(34); button.setToolTip(tip)
            button.clicked.connect(lambda checked, k=kind: self.budget_format_font(k, checked))
            budget_excel.addWidget(button)
        self.budget_font_size = QComboBox(); self.budget_font_size.addItems(tuple(str(n) for n in (8,9,10,11,12,14,16,18,20,24)))
        self.budget_font_size.setCurrentText('10'); self.budget_font_size.setMaximumWidth(62)
        self.budget_font_size.currentTextChanged.connect(self.budget_format_font_size); budget_excel.addWidget(self.budget_font_size)
        text_btn = QPushButton(ui_text('Texto')); text_btn.clicked.connect(self.budget_format_text_color); budget_excel.addWidget(text_btn)
        bg_btn = QPushButton(ui_text('Fondo')); bg_btn.clicked.connect(self.budget_format_background); budget_excel.addWidget(bg_btn)
        border_btn = QPushButton(ui_text('Bordes')); border_btn.clicked.connect(self.budget_format_borders); budget_excel.addWidget(border_btn)

        align_btn = QPushButton(ui_text('Alinear') + ' ▾'); align_menu = QMenu(align_btn)
        for label, alignment in ((ui_text('Izquierda'), Qt.AlignmentFlag.AlignLeft),
                                 (ui_text('Centro'), Qt.AlignmentFlag.AlignHCenter),
                                 (ui_text('Derecha'), Qt.AlignmentFlag.AlignRight)):
            action = align_menu.addAction(label); action.triggered.connect(lambda checked=False, a=alignment: self.budget_format_alignment(a))
        align_btn.setMenu(align_menu); budget_excel.addWidget(align_btn)
        clear_btn = QPushButton(ui_text('Limpiar')); clear_btn.setToolTip(ui_text('Limpiar formato')); clear_btn.clicked.connect(self.budget_clear_format); budget_excel.addWidget(clear_btn)

        search_btn = QPushButton(ui_text('Buscar') + ' ▾'); search_menu = QMenu(search_btn)
        for label, callback in ((ui_text('Buscar…'), self.budget_find), (ui_text('Buscar y reemplazar…'), self.budget_replace)):
            action = search_menu.addAction(label); action.triggered.connect(callback)
        search_btn.setMenu(search_menu); budget_excel.addWidget(search_btn)

        data_btn = QPushButton(ui_text('Datos') + ' ▾'); data_menu = QMenu(data_btn)
        # No se ofrece ordenar filas: Presupuesto es jerárquico (Cuenta/Detalle/Subdetalle)
        # y un sort plano rompería esa estructura. Filtrar sí es reversible y seguro.
        for label, callback in ((ui_text('Filtrar por texto…'), self.budget_filter),
                                (ui_text('Mostrar todas las filas'), self.budget_show_all)):
            action = data_menu.addAction(label); action.triggered.connect(callback)
        data_btn.setMenu(data_menu); budget_excel.addWidget(data_btn); budget_excel.addStretch()



        # FASE 2: primero las herramientas propias del presupuesto;
        # la barra tipo Excel queda inmediatamente encima de la hoja.
        for widget in (account, detail, subdetail, self.global_days, self.default_fringe): professional_tools.addWidget(widget)



        professional_tools.addStretch(); layout.addWidget(self.professional_budget_tools)
        layout.addLayout(budget_excel)







        self.budget = StructuredSpreadsheet(0, 14)



        self.budget.setHorizontalHeaderLabels((ui_text('Nivel'), ui_text('Bloque'), ui_text('Código'), ui_text('Categoría'), ui_text('Cuenta / concepto'), ui_text('Cantidad'), ui_text('Unidad'), ui_text('Jornadas'), ui_text('Tarifa'), ui_text('Moneda'), ui_text('Cambio'), 'Fringe %', 'Total', ui_text('Notas')))



        self.budget.setAlternatingRowColors(False)



        self.budget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)



        self.budget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)



        self.budget.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)



        self.budget.horizontalHeader().setSectionResizeMode(13, QHeaderView.ResizeMode.Stretch)



        for column, width in ((5, 85), (7, 130), (8, 105), (9, 90), (10, 105), (11, 100), (12, 115)):



            self.budget.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)



            self.budget.setColumnWidth(column, width)



        self.budget.itemChanged.connect(self.update_budget_total)



        layout.addWidget(self.budget, 1)



        footer = QHBoxLayout()



        self.top_sheet_label = QLabel('TOP SHEET   ATL 0.00   |   BTL 0.00')



        self.top_sheet_label.setObjectName('moduleHint'); footer.addWidget(self.top_sheet_label)



        footer.addStretch()



        self.total_label = QLabel('TOTAL  0.00')



        self.total_label.setObjectName('total')



        footer.addWidget(self.total_label)



        layout.addLayout(footer)



        from budget_controller import BudgetController



        from budget_globals_ui import open_globals



        self.budget_controller = BudgetController(self)



        from budget_fringes_ui import open_fringes, open_assignment



        self.fringes_button = QPushButton('Fringes')



        self.fringes_button.clicked.connect(lambda: open_fringes(self))



        professional_tools.addWidget(self.fringes_button)



        self.assign_fringes_button = QPushButton(ui_text('Asignar Fringes'))



        self.assign_fringes_button.clicked.connect(lambda: open_assignment(self))



        professional_tools.addWidget(self.assign_fringes_button)



        self.globals_button = QPushButton('Globals')



        self.globals_button.clicked.connect(lambda: open_globals(self))



        actions.insertWidget(2, self.globals_button)



        from budget_groups_ui import install_groups_controls



        install_groups_controls(self, actions, layout)



        from budget_credits_ui import install_credits_controls



        install_credits_controls(self, actions)



        from budget_charges_ui import install_charges_controls



        install_charges_controls(self, actions)



        from budget_tools_ui import install_budget_tools



        install_budget_tools(self, actions, professional_tools)



        return page















    def legacy_analyze_script(self):



        self.breakdown.setRowCount(0)



        for suggestion in analyze_blocks(self.editor.blocks()):



            self.insert_breakdown(suggestion)



        self.modules.setCurrentWidget(self.breakdown_page)



        self.statusBar().showMessage('{} elementos encontrados en el guion.'.format(self.breakdown.rowCount()))







    def legacy_sync_schedule(self):



        self.schedule_page.sync_from_project(self.editor.blocks(), self.breakdown_data())



        self.modules.setCurrentWidget(self.schedule_page)



        self.statusBar().showMessage('{} escenas actualizadas en el plan de rodaje.'.format(self.schedule_page.table.rowCount()))







    def insert_breakdown(self, data):



        row = self.breakdown.rowCount()



        self.breakdown.insertRow(row)



        approved = table_item('', editable=False)



        approved.setData(Qt.ItemDataRole.UserRole, data.get('scene_id', ''))



        approved.setFlags(approved.flags() | Qt.ItemFlag.ItemIsUserCheckable)



        approved.setCheckState(Qt.CheckState.Checked if data.get('approved') else Qt.CheckState.Unchecked)



        self.breakdown.setItem(row, 0, approved)



        for column, key in enumerate(('scene', 'category', 'element', 'source'), 1):



            item = table_item(data.get(key, ''), editable=column in (2, 3, 4))
            # Conserva fondos personalizados del desglose al guardar/cargar el proyecto.
            bg = (data.get('backgrounds') or {}).get(key, '')
            if bg and QColor(bg).isValid():
                item.setBackground(QBrush(QColor(bg)))
            self.breakdown.setItem(row, column, item)







    def add_breakdown_row(self):



        self.insert_breakdown({'approved': False, 'scene': 'General', 'category': 'Otro', 'element': '', 'source': 'Agregado manualmente'})







    def remove_breakdown_rows(self):



        for index in sorted({item.row() for item in self.breakdown.selectedItems()}, reverse=True):



            self.breakdown.removeRow(index)







    def apply_selected_budget_block(self):



        rows = sorted({item.row() for item in self.budget.selectedItems()})
        if not rows and self.budget.currentRow() >= 0:
            rows = [self.budget.currentRow()]



        if not rows:



            self.statusBar().showMessage('Selecciona las partidas que quieres cambiar de bloque.')



            return



        block = self.budget_block.currentText()



        previous = self.budget.blockSignals(True)



        try:



            for row in rows:



                self.budget.item(row, 1).setText(block)



        finally:



            self.budget.blockSignals(previous)



        self.update_budget_total()



        self.document_changed()



        self.statusBar().showMessage(f'{len(rows)} partidas cambiadas a {block}.')







    def approved_to_budget(self):



        existing = {(self.budget.item(row, 3).text(), self.budget.item(row, 4).text()) for row in range(self.budget.rowCount())}



        added = 0



        for row in range(self.breakdown.rowCount()):



            if self.breakdown.item(row, 0).checkState() != Qt.CheckState.Checked:



                continue



            category = self.breakdown.item(row, 2).text()



            element = self.breakdown.item(row, 3).text()



            if (category, element) not in existing:



                self.add_budget_row(category, element, level=ui_text('Detalle'), block=self.breakdown_budget_block.currentText())



                # Conserva los colores de organización del Desglose. Las columnas
                # equivalentes son Categoría -> Categoría y Elemento -> Cuenta/concepto.
                budget_row = self.budget.rowCount() - 1
                for source_col, target_col in ((2, 3), (3, 4)):
                    source_item = self.breakdown.item(row, source_col)
                    target_item = self.budget.item(budget_row, target_col)
                    if source_item is not None and target_item is not None and source_item.background().style() != Qt.BrushStyle.NoBrush:
                        target_item.setBackground(QBrush(source_item.background()))



                existing.add((category, element))



                added += 1



        self.modules.setCurrentWidget(self.budget_page)



        self.statusBar().showMessage('{} elementos agregados al presupuesto.'.format(added))







    def add_budget_row(self, category='Otro', concept='', level=None, block='BTL', data=None):



        data = data or {}



        level = level or data.get('level') or (ui_text('Detalle') if self.workspace_mode == 'professional' else ui_text('Concepto'))



        previous_signal_state = self.budget.blockSignals(True)



        row = self.budget.rowCount()



        self.budget.insertRow(row)



        default_days = '@DIAS_RODAJE' if self.workspace_mode == 'professional' and level in (ui_text('Detalle'), ui_text('Subdetalle')) else '1'



        if '@DIAS_RODAJE' == default_days and 'DIAS_RODAJE' not in self.budget_controller.catalog.values(): default_days = '1'



        values = (



            level, data.get('block', block), data.get('code', ''), data.get('category', category), data.get('concept', concept),



            data.get('quantity', '1'), data.get('unit', 'unidad'), data.get('days', default_days), data.get('unit_price', ''),



            data.get('currency', self.base_currency.currentText()), data.get('exchange', '1'),



            data.get('fringe', str(self.default_fringe.value())), data.get('total', '0.00'), data.get('notes', ''),



        )



        for column, value in enumerate(values):



            self.budget.setItem(row, column, table_item(value, editable=column != 12))



        from budget_group_controller import GROUP_ROLE, GROUP_LEVEL_ROLE



        self.budget.item(row, 0).setData(GROUP_LEVEL_ROLE, level)



        self.budget.item(row, 0).setData(GROUP_ROLE, list(data.get('group_ids', [])))



        from budget_controller import CREDIT_ROLE



        self.budget.item(row, 0).setData(CREDIT_ROLE, list(data.get('credit_ids', [])))



        from budget_controller import CHARGE_ROLE



        self.budget.item(row, 0).setData(CHARGE_ROLE, list(data.get('charge_ids', [])))



        from budget_controller import FRINGE_ROLE



        self.budget.item(row, 11).setData(FRINGE_ROLE, list(data.get('fringe_ids', [])))



        if 'legacy_exchange' in data:



            from budget_currencies import ROLE



            self.budget.item(row, 10).setData(ROLE, data['legacy_exchange'])



        if level == ui_text('Cuenta'):



            font = self.budget.item(row, 4).font(); font.setBold(True)



            for column in range(self.budget.columnCount()): self.budget.item(row, column).setFont(font)



        self.budget.blockSignals(previous_signal_state)



        if not getattr(self, '_loading', False): self.update_budget_total()







    def _budget_selected_cells(self):
        if not hasattr(self, 'budget'):
            return []
        return self.budget.selected_items_including_empty()

    def budget_format_background(self):
        items = self._budget_selected_cells()
        if not items: return
        initial = items[0].background().color() if items[0].background().style() != Qt.BrushStyle.NoBrush else QColor('#ffffff')
        color = QColorDialog.getColor(initial, self, ui_text('Fondo de celda'))
        if color.isValid():
            for item in items: item.setBackground(QBrush(color))

    def budget_format_text_color(self):
        items = self._budget_selected_cells()
        if not items: return
        initial = items[0].foreground().color() if items[0].foreground().style() != Qt.BrushStyle.NoBrush else QColor('#111111')
        color = QColorDialog.getColor(initial, self, ui_text('Color del texto'))
        if color.isValid():
            for item in items: item.setForeground(QBrush(color))

    def budget_format_font(self, kind, enabled):
        for item in self._budget_selected_cells():
            font = item.font()
            if kind == 'bold': font.setBold(bool(enabled))
            elif kind == 'italic': font.setItalic(bool(enabled))
            elif kind == 'underline': font.setUnderline(bool(enabled))
            item.setFont(font)

    def budget_format_font_size(self, value):
        try: size = int(value)
        except (TypeError, ValueError): return
        for item in self._budget_selected_cells():
            font = item.font(); font.setPointSize(size); item.setFont(font)

    def budget_format_alignment(self, horizontal):
        for item in self._budget_selected_cells(): item.setTextAlignment(horizontal | Qt.AlignmentFlag.AlignVCenter)

    def budget_format_borders(self):
        from eleuthera_spreadsheet import BORDER_ROLE
        items = self._budget_selected_cells()
        if not items: return
        color = QColorDialog.getColor(QColor('#707070'), self, ui_text('Color de borde'))
        if not color.isValid(): return
        for item in items: item.setData(BORDER_ROLE, color.name())
        self.budget.viewport().update()

    def budget_clear_format(self):
        from eleuthera_spreadsheet import BORDER_ROLE
        rows = set()
        for item in self._budget_selected_cells():
            rows.add(item.row())
            item.setBackground(QBrush()); item.setForeground(QBrush()); item.setFont(QFont())
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item.setData(BORDER_ROLE, None)
        # Cuenta tiene negrita semántica propia del presupuesto: restaurarla.
        for row in rows:
            level_item = self.budget.item(row, 0)
            if level_item and level_item.text() == ui_text('Cuenta'):
                for col in range(self.budget.columnCount()):
                    cell = self.budget.item(row, col)
                    if cell:
                        font = cell.font(); font.setBold(True); cell.setFont(font)
        self.budget.viewport().update()

    def budget_copy(self):
        ranges = self.budget.selectedRanges()
        if not ranges: return
        rg = ranges[0]; lines=[]
        for row in range(rg.topRow(), rg.bottomRow()+1):
            lines.append('\t'.join(self.budget.item(row,col).text() if self.budget.item(row,col) else '' for col in range(rg.leftColumn(),rg.rightColumn()+1)))
        QApplication.clipboard().setText('\n'.join(lines))

    def budget_cut(self):
        self.budget_copy()
        for item in self._budget_selected_cells():
            if item.flags() & Qt.ItemFlag.ItemIsEditable: item.setText('')

    def budget_paste(self):
        text = QApplication.clipboard().text()
        if not text: return
        sr, sc = self.budget.currentRow(), self.budget.currentColumn()
        if sr < 0 or sc < 0: return
        matrix=[row.split('\t') for row in text.rstrip('\n').splitlines()]
        for rr,rowdata in enumerate(matrix):
            for cc,value in enumerate(rowdata):
                r,c=sr+rr,sc+cc
                if r>=self.budget.rowCount() or c>=self.budget.columnCount(): continue
                item=self.budget.ensure_item(r,c)
                if item.flags() & Qt.ItemFlag.ItemIsEditable: item.setText(value)

    def budget_find(self):
        query, ok = QInputDialog.getText(self, ui_text('Buscar'), ui_text('Texto a buscar:'))
        if not ok or not query: return
        cols=self.budget.columnCount(); total=self.budget.rowCount()*cols
        start=max(0,self.budget.currentRow()*cols+self.budget.currentColumn()+1)
        for offset in range(total):
            pos=(start+offset)%max(1,total); row,col=divmod(pos,cols); item=self.budget.item(row,col)
            if item and query.casefold() in item.text().casefold():
                self.budget.setCurrentCell(row,col); self.budget.scrollToItem(item); return
        QMessageBox.information(self, ui_text('Buscar'), ui_text('No se encontraron coincidencias.'))

    def budget_replace(self):
        find,ok=QInputDialog.getText(self,ui_text('Buscar y reemplazar'),ui_text('Buscar:'))
        if not ok or not find:return
        replacement,ok=QInputDialog.getText(self,ui_text('Buscar y reemplazar'),ui_text('Reemplazar por:'))
        if not ok:return
        changed=0
        for item in self._budget_selected_cells():
            if item.flags() & Qt.ItemFlag.ItemIsEditable and find.casefold() in item.text().casefold():
                item.setText(re.sub(re.escape(find),lambda m:replacement,item.text(),flags=re.IGNORECASE)); changed+=1
        self.statusBar().showMessage(ui_text('Reemplazos: ')+str(changed))

    def budget_filter(self):
        query,ok=QInputDialog.getText(self,ui_text('Filtrar presupuesto'),ui_text('Mostrar filas que contengan:'))
        if not ok:return
        needle=query.casefold().strip()
        for row in range(self.budget.rowCount()):
            haystack=' '.join(self.budget.item(row,col).text() if self.budget.item(row,col) else '' for col in range(self.budget.columnCount())).casefold()
            self.budget.setRowHidden(row,bool(needle) and needle not in haystack)

    def budget_show_all(self):
        for row in range(self.budget.rowCount()): self.budget.setRowHidden(row,False)


    def remove_budget_rows(self):



        for index in sorted({item.row() for item in self.budget.selectedItems()}, reverse=True):



            self.budget.removeRow(index)



        self.update_budget_total()







    def legacy_change_base_currency(self, currency):



        new_currency = currency.strip().upper()



        if not new_currency:



            return



        old_currency = getattr(self, '_last_base_currency', '').strip().upper()



        self.budget.blockSignals(True)



        for row in range(self.budget.rowCount()):



            row_currency = self.budget.item(row, 9).text().strip().upper()



            if not row_currency or row_currency == old_currency:



                self.budget.item(row, 9).setText(new_currency)



                self.budget.item(row, 10).setText('1')



        self.budget.blockSignals(False)



        self._last_base_currency = new_currency



        self.update_budget_total()







    def update_budget_total(self, *args, force=False):



        if hasattr(self, 'budget_controller'):



            if args and hasattr(args[0], 'row') and not force:



                self.budget_controller.item_changed(args[0])



            else:



                self.budget_controller.request(force=force)







    def breakdown_data(self):



        return [{



            'approved': self.breakdown.item(row, 0).checkState() == Qt.CheckState.Checked,



            'scene': self.breakdown.item(row, 1).text(), 'category': self.breakdown.item(row, 2).text(),



            'element': self.breakdown.item(row, 3).text(), 'source': self.breakdown.item(row, 4).text(),



            'scene_id': self.breakdown.item(row, 0).data(Qt.ItemDataRole.UserRole) or '',



            'backgrounds': {
                key: (self.breakdown.item(row, column).background().color().name()
                      if self.breakdown.item(row, column) is not None
                      and self.breakdown.item(row, column).background().style() != Qt.BrushStyle.NoBrush else '')
                for column, key in enumerate(('scene', 'category', 'element', 'source'), 1)
            },



        } for row in range(self.breakdown.rowCount())]







    def legacy_export_breakdown(self):



        filename, _ = QFileDialog.getSaveFileName(



            self, ui_text('Exportar desglose'), '', 'Excel con fichas por escena (*.xlsx);;Valores separados por comas (*.csv)'



        )



        if not filename:



            return



        if not filename.lower().endswith(('.xlsx', '.csv')):



            filename += '.csv' if '*.csv' in _ else '.xlsx'



        try:



            if filename.lower().endswith('.xlsx'):



                from breakdown_export import export_breakdown_workbook



                export_breakdown_workbook(filename, self.breakdown_data(),



                                          self.path.stem if self.path else ui_text('Sin título'))



                self.statusBar().showMessage('Desglose exportado: {}'.format(filename))



                QMessageBox.information(self, ui_text('Exportar desglose'), ui_text('Excel exportado con resumen y fichas por escena.'))



                return



            with open(filename, 'w', encoding='utf-8-sig', newline='') as output:



                writer = csv.writer(output, delimiter=';')



                writer.writerow((ui_text('Aprobado'), ui_text('Escena'), ui_text('Categoria'), ui_text('Elemento'), ui_text('Texto de origen')))



                for row in self.breakdown_data():



                    writer.writerow((



                        'Si' if row['approved'] else 'No', row['scene'], row['category'],



                        row['element'], row['source'],



                    ))



            self.statusBar().showMessage('Desglose exportado: {}'.format(filename))



            QMessageBox.information(self, ui_text('Exportar desglose'), ui_text('El desglose se exportó correctamente.'))



        except (OSError, ValueError, ImportError) as error:



            QMessageBox.critical(self, ui_text('Exportar desglose'), str(error))







    def budget_data(self):



        keys = ('level', 'block', 'code', 'category', 'concept', 'quantity', 'unit', 'days', 'unit_price', 'currency', 'exchange', 'fringe', 'total', 'notes')



        from budget_currencies import ROLE



        from budget_controller import FRINGE_ROLE, CREDIT_ROLE, CHARGE_ROLE



        from budget_group_controller import GROUP_ROLE



        return [{**{key: self.budget.item(row, col).text() for col, key in enumerate(keys)}, 'fringe_ids': self.budget.item(row, 11).data(FRINGE_ROLE) or [], 'group_ids': self.budget.item(row, 0).data(GROUP_ROLE) or [], 'credit_ids': self.budget.item(row, 0).data(CREDIT_ROLE) or [], 'charge_ids': self.budget.item(row, 0).data(CHARGE_ROLE) or [], **({'legacy_exchange': self.budget.item(row, 10).data(ROLE)} if self.budget.item(row, 10).data(ROLE) is not None else {})} for row in range(self.budget.rowCount())]







    def legacy_save(self):



        result = super().save()



        if result and self.path:



            try:



                import shutil, time



                backup_dir = self.path.parent / '.eleuthera-backups'; backup_dir.mkdir(exist_ok=True)



                backups = sorted(backup_dir.glob(self.path.stem + '-*.eguion'), key=lambda item: item.stat().st_mtime)



                if not backups or time.time() - backups[-1].stat().st_mtime >= 300:



                    stamp = time.strftime('%Y%m%d-%H%M%S')



                    shutil.copy2(self.path, backup_dir / f'{self.path.stem}-{stamp}.eguion')



                    for old in backups[:-19]: old.unlink()



            except OSError:



                pass



        return result



    def project_data(self):



        data = super().project_data()



        if hasattr(self, 'breakdown'):



            data.update({



                'breakdown': self.breakdown_data(), 'budget': self.budget_data(), 'story_map': self.story_map.to_data(),
                'story_map_template': self.story_map.template_data() if hasattr(self.story_map, 'template_data') else {},



                'scene_versions': self.scene_versions,



                'character_arcs': self.character_page.to_data() if hasattr(self, 'character_page') else self.character_arcs,



                'scene_development': self.scene_navigator.development_data() if hasattr(self, 'scene_navigator') else self.scene_development,



                'analysis_markers': self.analysis_page.marker_data() if hasattr(self, 'analysis_page') else self.analysis_markers,



                'dramatic_structure': self.analysis_page.dramatic_structure_data() if hasattr(self, 'analysis_page') else self.dramatic_structure,



                'treatment': self.treatment_page.to_data() if hasattr(self, 'treatment_page') else self.treatment_data,



                'workspace_mode': self.workspace_mode, 'suite_format': 5,



                'budget_settings': {'shooting_days': self.global_days.value(), 'default_fringe': self.default_fringe.value(), 'base_currency': self.base_currency.currentText()},



                'budget_globals': self.budget_controller.payload(),



                'budget_fringes': self.budget_controller.fringes_payload(),



                'budget_groups': self.budget_controller.groups.payload(),



                'budget_credits': self.budget_controller.credits_payload(),



                'budget_charges': self.budget_controller.charges_payload(),



                'schedule': self.schedule_page.to_data(),



                'schedule_start_date': self.schedule_page.start_date.date().toString(Qt.DateFormat.ISODate),



                **self.workflow_data(),



            })



        return data







    def legacy_open_document(self):



        if self.dirty and not self.confirm_discard():



            return



        filename, _ = QFileDialog.getOpenFileName(self, ui_text('Abrir guion'), '', 'Guiones compatibles (*.eguion *.fdx *.fountain *.txt *.pdf);;Final Draft (*.fdx);;PDF (*.pdf);;Texto (*.txt);;Todos (*.*)')



        if not filename:



            return



        path = Path(filename)



        try:



            suffix = path.suffix.lower()



            if suffix in ('.fountain', '.txt'):



                blocks, data = self.parse_fountain(self.read_text_file(path)), {}



                self.path = None



            elif suffix == '.fdx':



                blocks, data = parse_fdx(path), {}



                self.path = None



            elif suffix == '.pdf':



                blocks, data = self.parse_fountain(self.read_pdf(path)), {}



                self.path = None



            else:



                data = json.loads(path.read_text(encoding='utf-8'))



                blocks, self.path = data['blocks'], path



            self.editor.load_blocks(blocks)



            self.story_map.load_data(data.get('story_map', []))
            if hasattr(self.story_map, 'load_template_data'):
                self.story_map.load_template_data(data.get('story_map_template', {}))



            self.character_arcs = data.get('character_arcs', {})



            if hasattr(self, 'character_page'):



                self.character_page.set_data(self.character_arcs)



            self.scene_development = data.get('scene_development', {})



            if hasattr(self, 'scene_navigator'):



                self.scene_navigator.set_development_data(self.scene_development)



            self.analysis_markers = data.get('analysis_markers', {'characters': {}, 'scenes': {}, 'show_in_script': False})



            if hasattr(self, 'analysis_page'):



                self.analysis_page.set_markers(self.analysis_markers)



            self.dramatic_structure = data.get('dramatic_structure', {})



            if hasattr(self, 'analysis_page'):



                self.analysis_page.set_dramatic_structure(self.dramatic_structure)



            self.treatment_data = data.get('treatment', [])



            if hasattr(self, 'treatment_page'):



                self.treatment_page.load_data(self.treatment_data)



            self.workspace_mode = ({ui_text('Profesional'): 'professional', ui_text('Estándar'): 'standard', 'Estandar': 'standard'}.get(data.get('workspace_mode'), data.get('workspace_mode', self.workspace_mode))) if self.edition == 'combined' else self.edition



            self.apply_workspace_mode()



            self.notes.setPlainText(data.get('notes', ''))



            self.breakdown.setRowCount(0)



            for row in data.get('breakdown', []):



                self.insert_breakdown(row)



            self.schedule_page.load_data(data.get('schedule', []), data.get('schedule_start_date'))



            settings = data.get('budget_settings', {})



            self.global_days.setValue(float(settings.get('shooting_days', 1)))



            self.default_fringe.setValue(float(settings.get('default_fringe', 0)))



            self.base_currency.setCurrentText(settings.get('base_currency', 'USD'))



            self.budget.setRowCount(0)



            for row in data.get('budget', []):



                self.add_budget_row(data=row)



            self.dirty = False



            self.refresh()



            self.update_budget_total()



        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:



            QMessageBox.critical(self, ui_text('No se pudo abrir'), str(error))







    def legacy_export_excel_template(self):



        template, _ = QFileDialog.getOpenFileName(self, ui_text('Seleccionar plantilla Excel'), '', 'Excel (*.xlsx *.xlsm)')



        if not template:



            return



        output, _ = QFileDialog.getSaveFileName(self, ui_text('Guardar presupuesto'), '', 'Excel (*.xlsx *.xlsm)')



        if not output:



            return



        try:



            metadata = {'titulo': self.path.stem if self.path else ui_text('Sin título'), 'moneda': 'Configurable', 'total': self.total_label.text().replace('TOTAL', '').strip()}



            export_budget_template(template, output, self.budget_data(), metadata)



            QMessageBox.information(self, ui_text('Plantilla Excel'), ui_text('Presupuesto exportado conservando el diseño de la plantilla.'))



        except Exception as error:



            QMessageBox.critical(self, ui_text('Plantilla Excel'), str(error))







    def export_fdx(self):



        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Exportar Final Draft'), '', 'Final Draft (*.fdx)')



        if filename:



            write_fdx(filename if filename.lower().endswith('.fdx') else filename + '.fdx', self.editor.blocks())



    @staticmethod



    def read_text_file(path):



        for encoding in ('utf-8-sig', 'utf-16', 'cp1252', 'latin-1'):



            try:



                return path.read_text(encoding=encoding)



            except UnicodeError:



                pass



        raise ValueError('No se pudo reconocer la codificacion del TXT.')







    @staticmethod



    def read_pdf(path):



        try:



            from pypdf import PdfReader



        except ImportError as error:



            raise ValueError('Falta pypdf. Ejecuta: pip install -r requirements.txt') from error



        text = '\n\n'.join((page.extract_text() or '').strip() for page in PdfReader(str(path)).pages).strip()



        if not text:



            raise ValueError('El PDF no contiene texto seleccionable. Si es escaneado, necesita OCR.')



        return text































def run_app(edition='combined'):



    import multiprocessing



    multiprocessing.freeze_support()



    if sys.platform == 'win32':



        import ctypes



        app_id = {'professional': 'Eleuthera.CinemaSuite.ProfessionalPlus', 'standard': 'Eleuthera.Standard', 'combined': 'Eleuthera.CinemaSuite.Test'}[edition]



        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)



    qt = QApplication(sys.argv)



    qt.setApplicationName({'professional': SUITE_NAME, 'standard': SUITE_NAME, 'combined': SUITE_NAME + ' Tests'}[edition])



    qt.setOrganizationName('Equipo Eleuthera')



    qt.setStyle('Fusion')



    window = SuiteWindow(edition)



    if '--check-import' in sys.argv:



        index=sys.argv.index('--check-import');source=Path(sys.argv[index+1]);target=Path(sys.argv[index+2])



        window.autosave.stop();window.poll.stop()



        check_timer=QTimer(window);check_timer.setInterval(20)



        def finish_import_check():



            if getattr(window,'_import_job',None) is not None:return



            check_timer.stop()



            from project_store import fingerprint



            content=[{key:block[key] for key in ('type','text')} for block in window.editor.blocks()]



            target.parent.mkdir(parents=True,exist_ok=True)



            target.write_text(json.dumps({**window.last_import_profile,'blocks':len(content),'scenes':sum(b['type']=='scene' for b in content),'content_hash':fingerprint(content)},ensure_ascii=False,indent=2),encoding='utf-8')



            qt.quit()



        window.open_path(source);check_timer.timeout.connect(finish_import_check);check_timer.start()



        return qt.exec()



    if '--check-startup' in sys.argv:



        target = Path(sys.argv[sys.argv.index('--check-startup') + 1])



        window.autosave.stop(); window.poll.stop()



        from production_reports import write_excel, write_pdf



        from breakdown_export import export_breakdown_workbook



        target.parent.mkdir(parents=True, exist_ok=True)



        sample = [('Comprobación', [ui_text('Estado')], [['Inicio correcto']])]



        write_excel(target.with_suffix('.xlsx'), 'Eleuthera', {}, sample)



        write_pdf(target.with_suffix('.pdf'), 'Eleuthera', {}, sample)



        target.write_text(json.dumps({'edition': edition, 'tabs': [window.modules.tabText(i) for i in range(window.modules.count()) if window.modules.isTabVisible(i)], 'excel_template': False, 'recovery': hasattr(window, 'recovery_root')}, ensure_ascii=False), encoding='utf-8')



        return 0



    available = qt.primaryScreen().availableGeometry()



    width = max(window.minimumWidth(), min(1360, int(available.width() * 0.92)))



    height = max(window.minimumHeight(), min(860, int(available.height() * 0.88)))



    window.resize(width, height)



    window.move(available.center() - window.rect().center())



    window.show()



    QTimer.singleShot(0, window.show_welcome)



    return qt.exec()











def main():



    return run_app('combined')











if __name__ == '__main__':



    raise SystemExit(main())















































