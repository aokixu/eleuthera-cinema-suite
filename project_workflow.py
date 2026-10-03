"""Integrated project workflow for both editions."""

from ui_i18n import ui_text, ui_join

import json

import re

import uuid

from datetime import datetime

from pathlib import Path

from PySide6.QtCore import QDate, QSettings, QStandardPaths, Qt, QTimer

from PySide6.QtGui import QAction, QIcon, QPixmap

from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,

    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,

    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget, QFrame, QSizePolicy)

from project_store import atomic_json, fingerprint, snapshots, scenes_from_blocks, scene_snapshot, plan_source, validate_project

from workflow_ui import configure_table, show_guide

from production import analyze_blocks, normalize

import budget_currencies as money





class WorkflowMixin:

    def setup_workflow(self):

        self._loading = False

        self.project_info = {}

        self.breakdown_baseline = {}

        self.plan_baseline = {}

        self.saved_searches = {}

        self.session_id = uuid.uuid4().hex

        self.recovery_root = __import__('plus_runtime').RUNTIME / 'recovery'

        self._last_recovery = ''

        self._last_saved = ''

        self.metadata_page = self.build_metadata_page()

        self.metadata_page.setWindowTitle(ui_text('Proyecto'))

        self.metadata_page.setWindowIcon(self.windowIcon())

        self.metadata_page.resize(1050, 700)

        file_menu = self.menuBar().actions()[0].menu()

        self.project_action = QAction(self.windowIcon(), ui_text('Proyecto'), self)

        self.project_action.setToolTip(ui_text('Datos generales del proyecto'))

        self.project_action.triggered.connect(self.open_project_panel)

        file_menu.addAction(self.project_action)

        self.review_action = QAction(ui_text('Revisiones'), self)

        self.review_action.triggered.connect(self.review_changes)

        file_menu.addAction(self.review_action)

        for table in (self.breakdown, self.budget, self.schedule_page.table): configure_table(table)

        self.schedule_page.export_callback = lambda: self.export_report('schedule', 'xlsx')

        remove_strip = QPushButton(ui_text('Quitar del plan'))

        remove_strip.setToolTip(ui_text('Quita las escenas seleccionadas únicamente del plan de rodaje.'))

        remove_strip.clicked.connect(self.remove_schedule_rows)

        self.schedule_page.report_actions.insertWidget(2, remove_strip)

        for kind, controls in (('budget', self.budget_actions), ('schedule', self.schedule_page.report_actions)):

            pdf = QPushButton('PDF'); pdf.setToolTip(ui_text('Exportar informe PDF'))

            pdf.clicked.connect(lambda checked=False, k=kind: self.export_report(k, 'pdf'))

            controls.insertWidget(controls.count() - 1, pdf)

            if kind == 'schedule':

                maximize_plan = QPushButton(ui_text('⛶ Maximizar plan'))

                maximize_plan.setToolTip('Maximizar la tabla del Plan de rodaje.')

                maximize_plan.clicked.connect(self.schedule_page.toggle_plan_maximized)

                self.schedule_page.maximize_plan_button = maximize_plan

                controls.insertWidget(controls.count() - 1, maximize_plan)

            if kind == 'budget':

                excel = QPushButton('Excel'); excel.setToolTip(ui_text('Exportar presupuesto Excel'))

                excel.clicked.connect(lambda: self.export_report('budget', 'xlsx'))

                controls.insertWidget(controls.count() - 1, excel)

        self.currency_label = QLabel(ui_text('Moneda base: ') + self.base_currency.currentText())

        self.currency_change = QPushButton(ui_text('Cambiar…'))

        self.currency_change.setToolTip(ui_text('Administra las monedas del presupuesto.'))

        self.currency_change.clicked.connect(self.open_currency_settings)

        self.budget_actions.addWidget(self.currency_label); self.budget_actions.addWidget(self.currency_change)

        money.setup(self)

        self.base_currency.currentTextChanged.connect(self.refresh_currency_label)

        for page in (self.breakdown_page, self.budget_page, self.schedule_page):

            page.layout().setContentsMargins(12, 10, 12, 12)

            page.layout().setSpacing(6)

        export_menu = next(a.menu() for a in self.menuBar().actions()[0].menu().actions() if a.menu())

        for label, callback in [('Desglose Excel', self.export_breakdown), ('Desglose PDF', lambda: self.export_report('breakdown', 'pdf')), ('Presupuesto Excel', lambda: self.export_report('budget', 'xlsx')), ('Presupuesto PDF', lambda: self.export_report('budget', 'pdf')), ('Para Movie Magic Scheduling (FDX)…', self.export_scheduling_fdx)]:

            action = QAction(label, self); action.triggered.connect(callback); export_menu.addAction(action)

        if self.edition != 'standard':

            for label, fmt in [('Plan de rodaje Excel', 'xlsx'), ('Plan de rodaje PDF', 'pdf')]:

                action = QAction(label, self); action.triggered.connect(lambda checked=False, f=fmt: self.export_report('schedule', f)); export_menu.addAction(action)

        recover = QAction(ui_text('Recuperar sesión o respaldo…'), self); recover.triggered.connect(self.recover_dialog); self.menuBar().actions()[0].menu().addAction(recover)

        self.poll = QTimer(self); self.poll.setInterval(1500); self.poll.timeout.connect(self.check_workflow); self.poll.start()

        self.autosave.setInterval(60000)

        self._last_saved = fingerprint(self.project_data())

        link = QPushButton(ui_text('Asignar a escena…'))

        link.setToolTip('Asigna los elementos seleccionados a una escena del guion. Cambia su asignación; no los copia.')

        link.clicked.connect(self.link_breakdown)

        self.breakdown_actions.insertWidget(3, link)



    def open_project_panel(self):

        """Abre los datos generales del proyecto sin ocupar una pestaña principal."""

        self.fill_metadata()

        self.metadata_page.show()

        self.metadata_page.raise_()

        self.metadata_page.activateWindow()



    def workflow_data(self):

        return {'project_poster': self.project_poster.payload if hasattr(self, 'project_poster') else None, 'budget_currencies': getattr(self, 'budget_currencies', money.migrate({})['budget_currencies']), 'budget_currency_legacy': getattr(self, 'budget_currency_legacy', {}), 'project_info': getattr(self, 'project_info', {}), 'breakdown_baseline': getattr(self, 'breakdown_baseline', {}),

                'plan_baseline': getattr(self, 'plan_baseline', {}), 'saved_searches': getattr(self, 'saved_searches', {}),

                'metadata_draft': {**{key: field.text() for key, field in getattr(self, 'info_fields', {}).items()}, 'rates_text': self.rates.text() if hasattr(self, 'rates') else ''}}



    def current_scenes(self):

        document=self.editor.document()

        key=(document,document.revision())

        if getattr(self,'_scene_cache_key',None)!=key:

            self._scene_cache=scenes_from_blocks(self.editor.blocks())

            self._scene_cache_key=(document,document.revision())

        return self._scene_cache



    def check_workflow(self):

        if self._loading or getattr(self, '_import_job', None): return

        data = self.project_data()

        signature=fingerprint(data)

        self.dirty = signature != self._last_saved

        if getattr(self, '_last_review_signature', None)==signature: return

        self._last_review_signature=signature

        changes = self.pending_changes()

        if hasattr(self, 'review_action'):

            self.review_action.setText(f'Revisiones ({len(changes)})' if changes else ui_text('Revisiones'))

            self.review_action.setToolTip('\n'.join(c['label'] for c in changes[:12]) or ui_text('No hay cambios pendientes entre módulos.'))



    def save(self):

        if not hasattr(self, 'session_id'): return super().save()

        self.commit_active_cell()

        if self.budget_controller.busy:

            self.statusBar().showMessage('Presupuesto recalculándose. Guarda al terminar.')

            return False

        target = self.path

        if not target:

            filename, _ = QFileDialog.getSaveFileName(self, ui_text('Guardar proyecto'), '', ui_text('Proyecto Eleuthera (*.eguion)'))

            if not filename: return False

            target = Path(filename if filename.lower().endswith('.eguion') else filename + '.eguion')

        try:

            data = self.project_data()

            if target.exists():

                previous = json.loads(target.read_text(encoding='utf-8'))

                if fingerprint(previous) != fingerprint(data):

                    snapshots(target.parent / '.eleuthera-backups' / fingerprint(str(target.resolve()))[:16], previous)

            atomic_json(target, data)

            self.path = target

            self._last_saved = fingerprint(data); self.dirty = False

            self.remember_path(target)

            self.refresh()

            self.statusBar().showMessage(ui_text('Proyecto guardado correctamente.'))

            return True

        except (OSError, ValueError, TypeError) as error:

            QMessageBox.critical(self, ui_text('No se pudo guardar'), str(error)); return False



    def commit_active_cell(self):

        from PySide6.QtWidgets import QApplication

        focused = QApplication.focusWidget()

        if focused:

            focused.clearFocus()

        QApplication.processEvents()



    def auto_save(self):

        if not hasattr(self, 'session_id') or self._loading or getattr(self, '_import_job', None): return

        self.commit_active_cell()

        data = self.project_data(); signature = fingerprint(data)

        if signature == self._last_recovery or signature == self._last_saved: return

        try:

            envelope = {'origin': str(self.path) if self.path else '', 'saved_at': datetime.now().isoformat(timespec='microseconds'), 'data': data}

            snapshots(self.recovery_root / self.session_id, envelope)

            self._last_recovery = signature

            if self.path:

                # The recovery copy already exists if saving the main project fails.

                if not self.save(): self.statusBar().showMessage('Sesión recuperable; no se pudo actualizar el archivo principal.')

            else:

                self.statusBar().showMessage('Recuperación automática guardada. Usa Guardar para elegir el archivo del proyecto.')

        except (OSError, ValueError, TypeError) as error:

            self.statusBar().showMessage('No se pudo guardar la recuperación: ' + str(error))



    def clear_session_recovery(self):

        directory = self.recovery_root / self.session_id

        if directory.is_dir():

            for path in directory.glob('snapshot-*.eguion'):

                try: path.unlink()

                except OSError: pass

            try: directory.rmdir()

            except OSError: pass



    def confirm_discard(self):

        if hasattr(self, '_last_saved'):

            self.commit_active_cell(); self.check_workflow()

        return super().confirm_discard()



    def closeEvent(self, event):

        if getattr(self, '_import_job', None):

            self._import_job.cancel();event.ignore();return

        if hasattr(self, '_last_saved'):

            self.commit_active_cell(); self.check_workflow()

        if self.dirty and not self.confirm_discard(): event.ignore(); return

        if hasattr(self, 'session_id'): self.clear_session_recovery()

        if hasattr(self, 'budget_controller'): self.budget_controller.cancel()

        event.accept()



    def new_document(self):

        if not hasattr(self, 'session_id'): return super().new_document()

        self.commit_active_cell(); self.check_workflow()

        if self.dirty and not self.confirm_discard(): return False

        self.clear_session_recovery()

        self.load_project({'blocks': [{'type': 'scene', 'text': 'INT. LUGAR - DIA'}, {'type': 'action', 'text': ''}]}, None)

        return True



    def open_document(self):

        filename, _ = QFileDialog.getOpenFileName(self, ui_text('Abrir proyecto o guion'), '', ui_text('Guiones (*.eguion *.fdx *.fountain *.txt *.pdf);;Todos (*.*)'))

        if filename: self.open_path(Path(filename))



    def open_path(self, path, asynchronous=True):

        if getattr(self, '_import_job', None): return False

        self.commit_active_cell(); self.check_workflow()

        if self.dirty and not self.confirm_discard(): return False

        if asynchronous:

            from import_job import ImportJob

            self._import_job=ImportJob(self, Path(path))

            self._import_job.start()

            return True

        from script_import import read_import

        previous_data, previous_path, previous_saved = self.project_data(), self.path, self._last_saved

        try:

            data, timings=read_import(path)

            self.load_project(data, Path(path) if Path(path).suffix.lower()=='.eguion' else None)

            self.clear_session_recovery()

            if Path(path).suffix.lower()!='.eguion': self.dirty=True;self._last_saved=''

            self.remember_path(path)

            self.last_import_profile=timings

            return True

        except Exception as error:

            self.load_project(previous_data,previous_path);self._last_saved=previous_saved;self.check_workflow()

            QMessageBox.critical(self,ui_text('No se pudo abrir'),str(error));return False



    def load_project(self, data, path=None, prepared_document=None):

        for _ in self.load_project_steps(data, path, prepared_document): pass



    def load_project_steps(self, data, path=None, prepared_document=None):

        data = money.migrate(data)

        validate_project(data)

        self.budget_controller.load(data)

        self._loading = True

        if hasattr(self, '_refresh_timer'): self._refresh_timer.stop()

        tables=(self.breakdown,self.budget,self.schedule_page.table)

        signal_states=[table.blockSignals(True) for table in tables]

        for table in tables: table.setUpdatesEnabled(False)

        try:

            self.path = path

            if prepared_document is None: self.editor.load_blocks(data['blocks'])

            else: self.editor.install_document(prepared_document)

            self.notes.setPlainText(data.get('notes', ''))

            yield 'Instalando guion', 1, 1

            self.story_map.load_data(data.get('story_map', []))

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

            # Desarrollo del proyecto (premisa, tema, tagline, logline, sinopsis,

            # sinopsis argumental, tratamiento y personajes). project_data() ya lo

            # serializa bajo la clave 'treatment'; faltaba restaurarlo en la ruta

            # normal de apertura (load_project_steps), por eso desaparecía al reabrir.

            self.treatment_data = data.get('treatment', [])

            if hasattr(self, 'treatment_page'):

                self.treatment_page.load_data(self.treatment_data)

            self.scene_versions = {str(key): list(value) for key, value in data.get('scene_versions', {}).items()}

            if hasattr(self, 'scene_versions_page'):

                self.scene_versions_page.set_versions(self.scene_versions)

            self.project_info = dict(data.get('project_info', {}))

            self.project_poster.set_data(data.get('project_poster'))

            self.budget_currencies = data['budget_currencies']

            self.budget_currency_legacy = data.get('budget_currency_legacy', {})

            money.mirror(self)

            self.breakdown_baseline = dict(data.get('breakdown_baseline', {})); self.plan_baseline = dict(data.get('plan_baseline', {}))

            self.saved_searches = dict(data.get('saved_searches', {}))

            if self.edition == 'combined': self.workspace_mode = ({ui_text('Profesional'): 'professional', ui_text('Estándar'): 'standard', 'Estandar': 'standard'}.get(data.get('workspace_mode'), data.get('workspace_mode', self.workspace_mode)))

            self.apply_workspace_mode()

            settings = data.get('budget_settings', {})

            self.budget.setRowCount(0)

            self.budget_controller.mirror_days()

            self.default_fringe.setValue(float(settings.get('default_fringe', 0)))

            currency = self.project_info.get('currency') or settings.get('base_currency', 'USD')

            self.project_info.setdefault('currency', currency)

            self.base_currency.blockSignals(True); self.base_currency.setCurrentText(currency); self.base_currency.blockSignals(False); self._last_base_currency = currency

            for index,row in enumerate(data.get('budget', [])):

                self.add_budget_row(data=row)

                if index%40==0: yield 'Cargando presupuesto',index,len(data['budget'])

            scenes = self.current_scenes(); by_heading = {}

            for scene in scenes: by_heading.setdefault(scene['heading'], []).append(scene['id'])

            def migrated(row, heading_key='scene'):

                row = dict(row)

                if not row.get('scene_id') and len(by_heading.get(row.get(heading_key), [])) == 1: row['scene_id'] = by_heading[row[heading_key]][0]

                return row

            self.breakdown.setRowCount(0)

            for index,row in enumerate(data.get('breakdown', [])):

                self.insert_breakdown(migrated(row))

                if index%80==0: yield 'Cargando desglose',index,len(data['breakdown'])

            # El plan puede superar fácilmente cientos de escenas. Cargarlo fila

            # por fila con insertRow() fuerza relayouts costosos de QTableWidget.

            schedule_rows = [migrated(row) for row in data.get('schedule', [])]

            self.schedule_page.load_data(schedule_rows, data.get('schedule_start_date'))

            yield 'Cargando plan de rodaje', len(schedule_rows), len(schedule_rows)

            self.schedule_page.table.blockSignals(True)

            # Legacy documents have no trustworthy review version: they remain pending.

            self.fill_metadata()

            for key, value in data.get('metadata_draft', {}).items():

                if key in self.info_fields and key != 'currency': self.info_fields[key].setText(str(value))

            yield 'Calculando presupuesto',0,1

            self.update_budget_total(force=True)

            while self.budget_controller.busy:

                self.budget_controller._tick()

                yield 'Calculando presupuesto', 0, 1

            # Desglose y presupuesto pueden necesitar altura variable. El plan de

            # rodaje usa filas compactas de una línea; resizeRowToContents() sobre

            # cientos/miles de strips era una de las partes más caras de la carga.

            for table in (self.breakdown, self.budget):

                for row in range(table.rowCount()):

                    table.resizeRowToContents(row)

                    if row%60==0: yield 'Ajustando tablas',row,table.rowCount()

            # QTextDocument.size() otherwise forces all pages to lay out in one GUI call.

            document=self.editor.document();layout=document.documentLayout()

            for index in range(0,document.blockCount(),100):

                layout.blockBoundingRect(document.findBlockByNumber(index))

                yield 'Preparando páginas',index,document.blockCount()

            layout.blockBoundingRect(document.lastBlock())

            yield 'Actualizando índices y revisiones',0,1

            self._last_saved = fingerprint(self.project_data()); self._last_recovery = ''; self.dirty = False

            self.refresh()

        finally:

            for table,state in zip(tables,signal_states):

                table.blockSignals(state);table.setUpdatesEnabled(True)

            self._loading = False



    def remember_path(self, path):

        settings = QSettings(); recent = settings.value('recent_projects', [], type=list)

        value = str(path); settings.setValue('recent_projects', ([value] + [p for p in recent if p != value])[:10])



    def recovery_candidates(self):

        candidates = []

        if self.recovery_root.exists():

            for path in self.recovery_root.glob('*/*.eguion'):

                try:

                    envelope = json.loads(path.read_text(encoding='utf-8'))

                    if not isinstance(envelope.get('data', {}).get('blocks'), list): continue

                    origin = envelope.get('origin', '')

                    if origin and Path(origin).is_file():

                        try:

                            if fingerprint(json.loads(Path(origin).read_text(encoding='utf-8'))) == fingerprint(envelope['data']): continue

                        except (OSError, ValueError): pass

                    candidates.append((path, envelope))

                except (OSError, ValueError): pass

        return sorted(candidates, key=lambda pair: (pair[1].get('saved_at', ''), pair[0].name), reverse=True)



    def recover_dialog(self):

        dialog = QDialog(self); dialog.setWindowTitle(ui_text('Recuperar sesión o respaldo')); dialog.resize(740, 420)

        layout = QVBoxLayout(dialog); layout.addWidget(QLabel('Elige una versión. Se abrirá como proyecto recuperado para guardar una copia.'))

        listing = QListWidget(); candidates = self.recovery_candidates()

        for path, envelope in candidates:

            listing.addItem(f"{envelope.get('saved_at', '')} · {envelope.get('origin') or 'Proyecto sin nombre'}")

        layout.addWidget(listing)

        tools = QHBoxLayout(); open_button = QPushButton(ui_text('Recuperar seleccionada')); file_button = QPushButton(ui_text('Abrir respaldo .eguion…')); close = QPushButton(ui_text('Cerrar'))

        for button in (open_button, file_button, close): tools.addWidget(button)

        layout.addLayout(tools); close.clicked.connect(dialog.reject)

        def recover(data):

            self.commit_active_cell(); self.check_workflow()

            if self.dirty and not self.confirm_discard(): return

            validate_project(data)

            self.load_project(data, None); self._last_saved = ''; self.dirty = True; dialog.accept()

        def selected():

            if listing.currentRow() >= 0: recover(candidates[listing.currentRow()][1]['data'])

        def browse():

            directory = str(self.path.parent / '.eleuthera-backups') if self.path else ''

            name, _ = QFileDialog.getOpenFileName(dialog, ui_text('Abrir respaldo'), directory, 'Eleuthera (*.eguion)')

            if name:

                try:

                    data = json.loads(Path(name).read_text(encoding='utf-8')); recover(data.get('data', data))

                except (OSError, ValueError, KeyError, TypeError) as error: QMessageBox.critical(dialog, ui_text('Respaldo inválido'), str(error))

        open_button.clicked.connect(selected); file_button.clicked.connect(browse)

        dialog.exec()



    def show_welcome(self):
        """Compact Eleuthera welcome using the same visual language as the main suite."""
        dialog = QDialog(self)
        dialog.setWindowTitle(ui_text('Bienvenido'))
        dialog.resize(960, 640)
        dialog.setMinimumSize(860, 580)

        # Keep the application stylesheet for all working controls.  Only the
        # photographic hero has local styling, so entering the suite no longer
        # feels like switching to a different application.
        root = QVBoxLayout(dialog)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hero = QLabel()
        hero.setFixedHeight(285)
        hero.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Hero limpio: conserva la paleta oscura/cian sin la fotografía del tricahue.
        hero.setStyleSheet(
            'background:qlineargradient(x1:0,y1:0,x2:1,y2:0,'
            'stop:0 #071114, stop:0.58 #0b252b, stop:1 #103b43);'
            'border:0;'
        )
        root.addWidget(hero)

        hero_text = QWidget(hero)
        hero_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hero_text.setStyleSheet('background: transparent;')
        ht = QVBoxLayout(hero_text)
        ht.setContentsMargins(0, 0, 0, 0)
        ht.setSpacing(4)
        brand = QLabel('ELEU<span style="color:#18a9b8">THERA</span>')
        brand.setTextFormat(Qt.TextFormat.RichText)
        brand.setStyleSheet('font-size:38px; font-weight:700; letter-spacing:7px; color:#ffffff;')
        ht.addWidget(brand)
        suite = QLabel('C I N E M A   S U I T E   P R O F E S I O N A L')
        suite.setStyleSheet('font-size:18px; font-weight:500; letter-spacing:6px; color:#ffffff;')
        ht.addWidget(suite)
        accent = QFrame()
        accent.setFixedHeight(2)
        accent.setFixedWidth(440)
        accent.setStyleSheet('background:#18a9b8; border:0;')
        ht.addWidget(accent)
        tag = QLabel('D E S A R R O L L O   ·   P R O D U C C I Ó N   ·   P L A N I F I C A C I Ó N')
        tag.setStyleSheet('font-size:9px; letter-spacing:2px; color:#ffffff;')
        ht.addWidget(tag)
        ht.addStretch()

        def place_hero_text():
            hero_text.setGeometry(60, 52, min(540, max(460, hero.width() // 2)), 170)

        original_resize = hero.resizeEvent
        def hero_resize(event):
            original_resize(event)
            place_hero_text()
        hero.resizeEvent = hero_resize
        place_hero_text()

        body = QWidget()
        body.setObjectName('root')
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 18, 28, 22)
        layout.setSpacing(10)
        root.addWidget(body, 1)

        # Standard suite buttons: no oversized cards and no unsupported glyphs.
        tools = QHBoxLayout()
        tools.setSpacing(8)
        actions = [
            (ui_text('Nuevo proyecto'), self.new_document, True),
            (ui_text('Abrir proyecto'), self.open_document, False),
            (ui_text('Recuperar sesión'), self.recover_dialog, False),
        ]
        for label, callback, primary in actions:
            button = QPushButton(label)
            button.setMinimumHeight(38)
            if primary:
                button.setObjectName('primary')
            button.clicked.connect(lambda checked=False, cb=callback: (dialog.accept(), cb()))
            tools.addWidget(button, 1)
        layout.addLayout(tools)

        pending = self.recovery_candidates()
        if pending:
            recovery = QLabel(f'Hay {len(pending)} versiones de recuperación disponibles, con fecha y hora.')
            recovery.setObjectName('moduleHint')
            layout.addWidget(recovery)

        recent_title = QLabel(ui_text('Proyectos recientes'))
        recent_title.setStyleSheet('font-weight:600;')
        layout.addWidget(recent_title)

        recent = QListWidget()
        paths = [p for p in QSettings().value('recent_projects', [], type=list) if Path(p).is_file()]
        for pth in paths:
            po = Path(pth)
            try:
                stamp = datetime.fromtimestamp(po.stat().st_mtime).strftime('%d/%m/%Y  %H:%M')
            except OSError:
                stamp = ''
            label = po.name if not stamp else f'{po.name}    {stamp}'
            recent.addItem(label)
            recent.item(recent.count() - 1).setData(Qt.ItemDataRole.UserRole, str(po))

        # The recent-project area occupies only what it actually needs.
        row_height = 34
        visible_rows = max(1, min(3, recent.count()))
        recent.setFixedHeight(visible_rows * row_height + 6)
        layout.addWidget(recent)
        recent.itemDoubleClicked.connect(
            lambda item: (dialog.accept(), self.open_path(Path(item.data(Qt.ItemDataRole.UserRole))))
        )

        layout.addStretch(1)
        cont = QPushButton(ui_text('Continuar'))
        cont.setObjectName('primary')
        cont.setMinimumHeight(38)
        cont.clicked.connect(dialog.accept)
        layout.addWidget(cont)
        dialog.exec()

    def build_metadata_page(self):

        page = QDialog(self)

        page.setModal(False)

        page.setWindowFlag(Qt.WindowType.Window, True)

        page.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)

        page.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)

        layout = QVBoxLayout(page)

        layout.setContentsMargins(28, 22, 28, 22)

        layout.setSpacing(18)

        project_font = page.font()

        project_font.setPointSizeF(max(11.0, project_font.pointSizeF() + 1.0))

        page.setFont(project_font)

        heading = QLabel(ui_text('Datos generales del proyecto')); heading.setObjectName('moduleTitle'); layout.addWidget(heading)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); form = QFormLayout(body); self.info_fields = {}

        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        form.setContentsMargins(22, 20, 22, 24)

        form.setHorizontalSpacing(26)

        form.setVerticalSpacing(18)

        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        for key, label in [('title', ui_text('Título')), ('company', ui_text('Productora')), ('director', ui_text('Dirección')), ('producer', ui_text('Producción')), ('writer', ui_text('Guionistas')), ('script_version', ui_text('Versión del guion')), ('script_date', ui_text('Fecha de revisión (DD/MM/AAAA)')), ('currency', ui_text('Moneda base')), ('production_start', ui_text('Inicio de producción (DD/MM/AAAA)')), ('production_end', ui_text('Fin de producción (DD/MM/AAAA)'))]:

            edit = QLineEdit(); edit.setPlaceholderText(ui_text('Opcional')); edit.setMinimumHeight(44); edit.setMinimumWidth(240); self.info_fields[key] = edit; form.addRow(label, edit)

        self.info_fields['currency'].setText(self.base_currency.currentText())

        self.rates = QLineEdit(); self.rates.setMinimumHeight(44); self.rates.setMinimumWidth(240); self.rates.setPlaceholderText('USD=6.96; EUR=7.50')

        form.addRow(ui_text('Tipos de cambio'), self.rates)

        note = QLabel(ui_text('Las monedas se administran desde Presupuesto > Monedas. Las fechas generales no cambian las jornadas del plan.')); note.setWordWrap(True); form.addRow(note)

        from PySide6.QtWidgets import QSplitter

        from project_poster import ProjectPoster

        scroll.setWidget(body)

        panels = QSplitter(Qt.Orientation.Horizontal)

        panels.setChildrenCollapsible(False)

        panels.addWidget(scroll)

        self.project_poster = ProjectPoster(lambda: setattr(self, 'dirty', True), page)

        panels.addWidget(self.project_poster)

        panels.setStretchFactor(0, 3); panels.setStretchFactor(1, 2)

        panels.setSizes([650, 380])

        layout.addWidget(panels, 1)

        self.metadata_feedback = QLabel(); self.metadata_feedback.setWordWrap(True); layout.addWidget(self.metadata_feedback)

        buttons = QHBoxLayout()

        buttons.addStretch(1)

        save = QPushButton(ui_text('Aplicar datos al proyecto'))

        save.setMinimumHeight(44)

        save.clicked.connect(self.apply_metadata)

        close = QPushButton(ui_text('Cerrar'))

        close.setMinimumHeight(44)

        close.clicked.connect(page.close)

        buttons.addWidget(save)

        buttons.addWidget(close)

        layout.addLayout(buttons)

        return page



    @staticmethod

    def _date_iso_to_latam(value):

        value = str(value or '').strip()

        if not value:

            return ''

        try:

            return datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')

        except ValueError:

            return value



    @staticmethod

    def _date_latam_to_iso(value):

        value = str(value or '').strip()

        if not value:

            return ''

        return datetime.strptime(value, '%d/%m/%Y').strftime('%Y-%m-%d')



    def fill_metadata(self):

        self.refresh_currency_label()

        date_keys = {'script_date', 'production_start', 'production_end'}

        for key, field in self.info_fields.items():

            value = self.project_info.get(key, '')

            field.setText(self._date_iso_to_latam(value) if key in date_keys else str(value))

        self.info_fields['currency'].setText(self.project_info.get('currency') or self.base_currency.currentText())

        self.rates.setText('; '.join(f'{currency}={rate}' for currency, rate in self.project_info.get('rates', {}).items()))

        self.metadata_feedback.clear()



    def apply_metadata(self):

        import math

        data = {key: field.text().strip() for key, field in self.info_fields.items()}

        data['currency'] = self.budget_currencies['base']

        rates = {r['code']: r['rate'] for r in self.budget_currencies['currencies'] if r['rate'] is not None}

        try:

            for key in ('script_date', 'production_start', 'production_end'):

                data[key] = self._date_latam_to_iso(data[key]) if data[key] else ''

            if data['production_start'] and data['production_end'] and data['production_end'] < data['production_start']:

                raise ValueError('La fecha final debe ser igual o posterior a la inicial.')

        except ValueError:

            QMessageBox.warning(self, ui_text('Revisar datos'), 'Usa las fechas en formato DD/MM/AAAA (por ejemplo, 14/09/2026).'); return

        data['rates'] = rates

        self.project_info = data

        money.mirror(self)

        self.dirty = True

        self.metadata_feedback.setText(ui_text('Datos aplicados. Los próximos informes usarán esta información.'))



    def change_base_currency(self, currency):

        if not hasattr(self, 'budget_currencies'):

            return self.legacy_change_base_currency(currency)

        # The catalog is authoritative; programmatic updates cannot relabel prices.

        self.base_currency.blockSignals(True)

        self.base_currency.setCurrentText(self.budget_currencies['base'])

        self.base_currency.blockSignals(False)



    def pending_changes(self):

        if not hasattr(self, 'breakdown_baseline'): return []

        scenes = {s['id']: s for s in self.current_scenes()}

        breakdown = self.breakdown_data(); plan = self.schedule_page.to_data(); changes = []

        linked = {r.get('scene_id') for r in breakdown if r.get('scene_id')} | set(self.breakdown_baseline)

        for identity in linked:

            scene = scenes.get(identity); before = self.breakdown_baseline.get(identity)

            after = scene_snapshot(scene) if scene else None

            if identity not in self.breakdown_baseline or before != after:

                title = ui_join([ui_text('Escena '), f"{scene['number']}", ui_text(' modificada — revisar desglose')]) if scene else 'Escena eliminada — revisar desglose'

                changes.append({'id': identity, 'module': 'breakdown', 'label': title, 'before': before, 'after': after})

        from collections import defaultdict

        indexed=defaultdict(list)

        for element in breakdown: indexed[element.get('scene_id')].append(element)

        for row in plan:

            identity = row.get('scene_id'); scene = scenes.get(identity); after = plan_source(scene, indexed[identity]) if scene else None

            if not identity:

                continue

            if identity not in self.plan_baseline or self.plan_baseline[identity] != after:

                changes.append({'id': identity, 'module': 'schedule', 'label': f"{row['scene']} — revisar plan de rodaje", 'before': self.plan_baseline.get(identity), 'after': after})

        for row in breakdown:

            if not row.get('scene_id') and row.get('scene') not in ('General', 'Sin escena'):

                changes.append({'id': '', 'module': 'legacy', 'label': row.get('scene', '') + ' — vínculo antiguo ambiguo; revisar manualmente', 'before': row, 'after': None})

                break

        return changes



    def choose_rows(self, title, records, describe, default=False):

        """Reviewable selection; no mutation occurs before this dialog is accepted."""

        dialog = QDialog(self); dialog.setWindowTitle(title); dialog.resize(920, 650)

        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(ui_text('Selecciona únicamente los cambios que quieres aceptar. Abajo puedes ver el detalle.')))

        table = QTableWidget(len(records), 2); table.setHorizontalHeaderLabels([ui_text('Aceptar'), ui_text('Cambio')]); table.setColumnWidth(0, 80); table.horizontalHeader().setStretchLastSection(True)

        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for index, record in enumerate(records):

            check = QTableWidgetItem(); check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable); check.setCheckState(Qt.CheckState.Checked if default else Qt.CheckState.Unchecked)

            table.setItem(index, 0, check); table.setItem(index, 1, QTableWidgetItem(record['label']))

        layout.addWidget(table)

        details = QTextBrowser(); layout.addWidget(details)

        table.currentCellChanged.connect(lambda row, col, oldrow, oldcol: details.setPlainText(describe(records[row])) if row >= 0 else None)

        if records: table.setCurrentCell(0, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(ui_text('Aceptar seleccionados'))

        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted: return None

        return [r for i, r in enumerate(records) if table.item(i, 0).checkState() == Qt.CheckState.Checked]



    def review_changes(self):

        import difflib

        changes = self.pending_changes()

        if not changes: QMessageBox.information(self, ui_text('Revisiones'), ui_text('No hay cambios pendientes entre módulos.')); return

        def describe(change):

            def readable(value):

                if value is None: return ['Sin escena o sin versión de referencia.']

                if 'blocks' in value: return [b['text'] for b in value['blocks']]

                labels = {'heading': ui_text('Escena'), 'interior': 'Entorno', 'period': 'Luz', 'location': ui_text('Locación'), 'synopsis': ui_text('Sinopsis'), 'elements': ui_text('Elementos'), 'scene': ui_text('Escena'), 'category': ui_text('Categoría'), 'element': ui_text('Elemento'), 'source': ui_text('Texto de origen'), 'approved': ui_text('Aprobado')}

                return [labels[key] + ': ' + (', '.join(text) if isinstance(text, list) else str(text)) for key, text in value.items() if key in labels]

            before = readable(change['before'])

            after = readable(change['after'])

            return ('Aceptar marca la versión como revisada; conserva los datos manuales actuales. Para incorporar propuestas, usa Analizar guion o Actualizar desde guion y desglose.\n\n' + '\n'.join(difflib.unified_diff(before, after, fromfile='Última versión revisada', tofile='Versión actual', lineterm='')))

        accepted = self.choose_rows('Revisar cambios entre módulos', changes, describe)

        if accepted is None: return

        for change in accepted:

            if change['module'] == 'breakdown': self.breakdown_baseline[change['id']] = change['after']

            elif change['module'] == 'schedule': self.plan_baseline[change['id']] = change['after']

        self.check_workflow()



    def analyze_script(self):

        scenes = self.current_scenes(); existing = self.breakdown_data(); proposals = []

        keys = {(r.get('scene_id'), normalize(r['category']), normalize(r['element'])) for r in existing}

        for scene in scenes:

            for row in analyze_blocks(scene['blocks']):

                row['scene_id'] = scene['id']

                if (scene['id'], normalize(row['category']), normalize(row['element'])) not in keys:

                    proposals.append({'label': ui_join([ui_text('Escena '), f"{scene['number']}", ui_text(' · '), f"{row['category']}", ui_text(' · '), f"{row['element']}"]), 'row': row})

        if existing and proposals:

            accepted = self.choose_rows('Nuevas propuestas de desglose', proposals, lambda p: p['row']['scene'] + '\n\n' + p['row']['source'] + '\n\nSe añadirá como pendiente. Los elementos existentes se conservan.')

            if accepted is None: return

        else: accepted = proposals

        for proposal in accepted: self.insert_breakdown(proposal['row'])

        # Only an initial analysis establishes a baseline automatically.

        if not existing: self.breakdown_baseline = {s['id']: scene_snapshot(s) for s in scenes}

        self.modules.setCurrentWidget(self.breakdown_page); self.check_workflow()

        if existing and not proposals: QMessageBox.information(self, ui_text('Desglose'), ui_text('No hay propuestas nuevas. Usa Revisiones para comparar y confirmar los cambios del guion.'))

        self.statusBar().showMessage(f'{len(accepted)} elementos añadidos; las correcciones existentes se conservaron.')



    def sync_schedule(self):

        scenes = self.current_scenes(); breakdown = self.breakdown_data(); old = self.schedule_page.to_data()

        by_id = {r.get('scene_id'): (i, r) for i, r in enumerate(old) if r.get('scene_id')}

        changes = []

        for scene in scenes:

            source = plan_source(scene, breakdown); identity = scene['id']

            if identity not in by_id or self.plan_baseline.get(identity) != source:

                previous = by_id.get(identity, (None, {}))[1]

                changes.append({'label': (ui_text('Añadir: ') if not previous else 'Actualizar: ') + scene['heading'], 'scene': scene, 'source': source, 'previous': previous})

        if old and changes:

            def describe(c):

                lines = ['Se conservarán jornada, orden, páginas y estado. Solo se reemplazarán los siguientes campos si aceptas esta escena:']

                for key in ('scene', 'interior', 'period', 'location', 'synopsis', 'elements'):

                    value = c['source'].get('heading' if key == 'scene' else key, '')

                    if isinstance(value, list): value = ', '.join(value)

                    label = {'scene': ui_text('Escena'), 'interior': 'Entorno', 'period': 'Luz', 'location': ui_text('Locación'), 'synopsis': ui_text('Sinopsis'), 'elements': ui_text('Elementos')}[key]

                    lines.append(f"\n{label}:\nActual: {c['previous'].get(key, '')}\nPropuesto: {value}")

                return '\n'.join(lines)

            accepted = self.choose_rows('Actualizar plan de rodaje', changes, describe)

            if accepted is None: return

        else: accepted = changes

        for change in accepted:

            scene = change['scene']; identity = scene['id']; source = change['source']; previous = dict(change['previous'])

            record = {**previous, 'scene_id': identity, 'scene': source['heading'], 'interior': source['interior'], 'period': source['period'], 'location': source['location'], 'synopsis': source['synopsis'], 'elements': ', '.join(source['elements'])}

            if identity in by_id: old[by_id[identity][0]] = record

            else:

                record.update({'day': '', 'pages': '', 'status': ui_text('Pendiente')}); old.append(record)

            self.plan_baseline[identity] = source

        self.schedule_page.load_data(old)

        self.modules.setCurrentWidget(self.schedule_page); self.check_workflow()

        self.statusBar().showMessage(f'{len(accepted)} escenas incorporadas al plan. Las escenas eliminadas del guion permanecen para revisión.')



    def search_records(self):

        scenes = self.current_scenes(); breakdown = self.breakdown_data(); plan = self.schedule_page.to_data()

        pending = {c['id'] for c in self.pending_changes()}

        from collections import defaultdict

        by_scene=defaultdict(list); plan_by_scene=defaultdict(list)

        for row in breakdown: by_scene[row.get('scene_id')].append(row)

        for row in plan: plan_by_scene[row.get('scene_id')].append(row)

        records = []

        for scene in scenes:

            linked = by_scene[scene['id']]

            strips = plan_by_scene[scene['id']]

            characters = {re.sub(r'\s*\([^)]*\)\s*$', '', c).strip() for c in scene['characters']}

            characters.update(r['element'] for r in linked if normalize(r['category']) == 'reparto')

            records.append({**scene, 'text': ' '.join(b['text'] for b in scene['blocks']) + ' ' + ' '.join(r['element'] for r in linked),

                'character': sorted(characters), 'interior': [scene['interior']], 'period': [scene['period']], 'location': [scene['location']],

                'shoot_location': [r['location'] for r in strips], 'day': [r['day'] or 'Sin jornada' for r in strips] or ['Sin jornada'],

                'category': sorted({r['category'] for r in linked}), 'status': ['Pendiente de revisión' if scene['id'] in pending else 'Sin avisos']})

        return records



    def export_issues(self, kind):

        issues = []; scenes = self.current_scenes()

        if kind in ('breakdown', 'schedule'):

            for scene in scenes:

                if not scene['location'].strip(): issues.append(('Escena sin locación', scene['heading'] or ui_join([ui_text('Escena '), f"{scene['number']}"]), 'script', scene['index']))

        if kind == 'breakdown':

            for index, row in enumerate(self.breakdown_data()):

                if not row['element'].strip(): issues.append(('Elemento sin nombre', row['scene'], 'breakdown', index))

        if kind == 'schedule':

            rows = self.schedule_page.to_data(); ids = {r.get('scene_id') for r in rows}

            for scene in scenes:

                if scene['id'] not in ids: issues.append(('Escena sin jornada', scene['heading'], 'script', scene['index']))

            for index, row in enumerate(rows):

                try:

                    day = float(row['day'])

                    if day < 1 or not day.is_integer(): raise ValueError()

                except ValueError: issues.append(('Escena sin jornada', row['scene'], 'schedule', index))

                if not row['location'].strip(): issues.append(('Escena sin lugar de filmación', row['scene'], 'schedule', index))

        if kind == 'budget':

            import math

            from budget_engine import evaluate

            global_values = self.budget_controller.catalog.values()

            for index, row in enumerate(self.budget_data()):

                if row['level'] == ui_text('Cuenta'): continue

                for key, label in [('unit_price', 'tarifa'), ('quantity', 'cantidad'), ('days', ui_text('jornadas')), ('exchange', 'tipo de cambio'), ('fringe', 'fringe')]:

                    value = row[key].strip()

                    if key == 'days' and value == '@DIAS_RODAJE': continue

                    if not value:

                        issues.append(('Partida sin ' + label, row['concept'], 'budget', index)); continue

                    try:

                        number = evaluate(value, global_values)

                        if not math.isfinite(number) or (key == 'exchange' and number <= 0): raise ValueError()

                    except ValueError: issues.append(('Partida con ' + label + ' inválido', row['concept'], 'budget', index))

                if not row['currency'].strip(): issues.append(('Partida sin moneda', row['concept'], 'budget', index))

        for change in self.pending_changes():

            if (kind == 'breakdown' and change['module'] in ('breakdown', 'legacy')) or (kind == 'schedule' and change['module'] == 'schedule'):

                issues.append(('Revisión pendiente', change['label'], 'review', 0))

        return issues



    def preflight(self, kind):

        from collections import Counter

        self.commit_active_cell()

        issues = self.export_issues(kind)

        if not issues: return True

        dialog = QDialog(self); dialog.setWindowTitle(ui_text('Comprobar antes de exportar')); dialog.resize(730, 400)

        layout = QVBoxLayout(dialog)

        summary = Counter(issue[0] for issue in issues)

        label = QLabel(' · '.join(f'{count} × {name.lower()}' for name, count in summary.items())); label.setWordWrap(True); layout.addWidget(label)

        listing = QListWidget()

        for category, text, module, index in issues: listing.addItem(category + ' — ' + text)

        layout.addWidget(listing); listing.setCurrentRow(0)

        row = QHBoxLayout(); review = QPushButton(ui_text('Revisar')); export = QPushButton(ui_text('Exportar igualmente')); cancel = QPushButton(ui_text('Cancelar'))

        for button in (review, export, cancel): row.addWidget(button)

        layout.addLayout(row)

        def navigate():

            issue = issues[max(0, listing.currentRow())]; module, index = issue[2:]

            dialog.reject()

            if module == 'review': self.review_changes()

            elif module == 'script':

                from PySide6.QtGui import QTextCursor

                self.modules.setCurrentIndex(0); self.editor.setTextCursor(QTextCursor(self.editor.document().findBlockByNumber(index))); self.editor.centerCursor()

            else:

                page, table = {'breakdown': (self.breakdown_page, self.breakdown), 'schedule': (self.schedule_page, self.schedule_page.table), 'budget': (self.budget_page, self.budget)}[module]

                self.modules.setCurrentWidget(page); table.selectRow(index); table.scrollToItem(table.item(index, 0))

        review.clicked.connect(navigate); export.clicked.connect(dialog.accept); cancel.clicked.connect(dialog.reject)

        return dialog.exec() == QDialog.DialogCode.Accepted



    def export_report(self, kind, fmt):

        if self.budget_controller.busy:

            self.statusBar().showMessage('Espera a que termine el recálculo para exportar.'); return

        if not self.preflight(kind): return

        if kind == 'budget' and (self.budget_controller.busy or self.budget_controller.result is None or self.budget_controller.result.errors):

            self.statusBar().showMessage('Termina el rec?lculo y corrige los errores de Globals antes de exportar.'); return

        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Exportar informe'), '', f'{fmt.upper()} (*.{fmt})')

        if not filename: return

        if not filename.lower().endswith('.' + fmt): filename += '.' + fmt

        try:

            from production_reports import write_excel, write_pdf, breakdown_tables, budget_tables, schedule_tables

            info = {**self.project_info, 'currency': self.base_currency.currentText()}; title = info.get('title') or (self.path.stem if self.path else ui_text('Sin título'))

            if kind == 'breakdown': tables = breakdown_tables(self.report_breakdown_data())

            elif kind == 'budget':

                rows = self.budget_data()

                for row in rows:

                    if row['days'] == '@DIAS_RODAJE': row['days'] = str(self.budget_controller.catalog.get('DIAS_RODAJE').value)

                tables = budget_tables(rows, self.total_label.text(), self.workspace_mode == 'professional')

                if any(row.get('fringe_ids') for row in rows):

                    result = self.budget_controller.result

                    details = [[row['concept'], f'{result.bases[i]:.2f}', f'{result.fringe_totals[i]:.2f}', f'{result.totals[i]:.2f}']

                               for i, row in enumerate(rows) if row.get('level') != ui_text('Cuenta')]

                    tables.append(('Base y Fringes', [ui_text('Concepto'), 'Base ' + info['currency'], 'Fringes ' + info['currency'], 'Total ' + info['currency']], details))

                if any(row.get('charge_ids') for row in rows):

                    result = self.budget_controller.result

                    detail = [[row['concept'], f'{result.before_charges[i]:.2f}',

                               '; '.join(self.budget_controller.charges.get(key).name + f': {amount:.2f}'

                                         for key, local, amount in result.charge_details[i]),

                               f'{result.charge_totals[i]:.2f}', f'{result.credit_totals[i]:.2f}', f'{result.totals[i]:.2f}']

                              for i, row in enumerate(rows) if row.get('level') != ui_text('Cuenta')]

                    tables.append(('Contractual Charges', [ui_text('Concepto'), 'Antes de cargos ' + info['currency'], 'Cargos individuales ' + info['currency'],

                                  'Cargos ' + info['currency'], 'Credits ' + info['currency'], 'Total final ' + info['currency']], detail))

                if any(row.get('credit_ids') for row in rows):

                    result = self.budget_controller.result

                    detail = [[row['concept'], f'{result.before_credits[i]:.2f}',

                               '; '.join(self.budget_controller.credits.get(key).name + f': {amount:.2f}'

                                         for key, local, amount in result.credit_details[i]),

                               f'{result.credit_totals[i]:.2f}', f'{result.totals[i]:.2f}']

                              for i, row in enumerate(rows) if row.get('level') != ui_text('Cuenta')]

                    tables.append(('Credits', [ui_text('Concepto'), 'Antes de Credits ' + info['currency'], 'Credits aplicados ' + info['currency'],

                                               'Reducción ' + info['currency'], 'Total final ' + info['currency']], detail))

            else: tables = schedule_tables(self.schedule_page.to_data(), self.schedule_page.report_type.currentIndex())

            if kind == 'breakdown' and fmt == 'xlsx':

                from breakdown_export import export_breakdown_workbook

                export_breakdown_workbook(filename, self.report_breakdown_data(), title, info)

            elif fmt == 'xlsx': write_excel(filename, title, info, tables)

            else: write_pdf(filename, title, info, tables)

            QMessageBox.information(self, ui_text('Exportación completada'), 'Informe guardado en:\n' + filename)

        except (OSError, ValueError, ImportError, TypeError) as error:

            QMessageBox.critical(self, ui_text('No se pudo exportar'), str(error))



    def export_breakdown(self):

        if not self.preflight('breakdown'): return

        filename, selected = QFileDialog.getSaveFileName(self, ui_text('Exportar desglose'), '', 'Excel con fichas por escena (*.xlsx);;CSV (*.csv);;PDF (*.pdf)')

        if not filename: return

        suffix = Path(filename).suffix.lower()

        if suffix not in ('.xlsx', '.csv', '.pdf'):

            suffix = '.csv' if '*.csv' in selected else ('.pdf' if '*.pdf' in selected else '.xlsx'); filename += suffix

        try:

            rows = self.report_breakdown_data(); title = self.project_info.get('title') or (self.path.stem if self.path else ui_text('Sin título'))

            if suffix == '.xlsx':

                from breakdown_export import export_breakdown_workbook

                export_breakdown_workbook(filename, rows, title, self.project_info)

            elif suffix == '.pdf':

                from production_reports import write_pdf, breakdown_tables

                write_pdf(filename, title, self.project_info, breakdown_tables(rows))

            else:

                import csv

                with open(filename, 'w', encoding='utf-8-sig', newline='') as stream:

                    writer = csv.writer(stream, delimiter=';'); writer.writerow((ui_text('Aprobado'), ui_text('Escena'), ui_text('Categoria'), ui_text('Elemento'), ui_text('Texto de origen')))

                    for row in rows: writer.writerow(('Si' if row['approved'] else 'No', row['scene'], row['category'], row['element'], row['source']))

            QMessageBox.information(self, ui_text('Exportación completada'), 'Desglose guardado en:\n' + filename)

        except (OSError, ValueError, ImportError, TypeError) as error: QMessageBox.critical(self, ui_text('No se pudo exportar'), str(error))



    def export_scheduling_fdx(self):

        message = ('Movie Magic Scheduling 10 admite importar un guion FDX: encabezados de escena y personajes con diálogo.\n\nEsta salida no transfiere el desglose manual, las jornadas, el orden de rodaje ni el presupuesto. En Scheduling usa Archivo → Import Script.\n\n¿Exportar el guion FDX?')

        if QMessageBox.question(self, 'Para Movie Magic Scheduling', message) != QMessageBox.StandardButton.Yes: return

        self.export_fdx()





    def link_breakdown(self):

        from PySide6.QtWidgets import QInputDialog

        selected = sorted({item.row() for item in self.breakdown.selectedItems()})

        if not selected:

            QMessageBox.information(self, ui_text('Asignar a escena'), ui_text('Selecciona los elementos del desglose que deseas asignar.')); return

        scenes = self.current_scenes()

        choices = [f"{s['number']} · {s['heading']}" for s in scenes]

        label, ok = QInputDialog.getItem(self, ui_text('Asignar a escena'), ui_text('Escena:'), choices, 0, False)

        if not ok or not choices: return

        scene = scenes[choices.index(label)]

        for row in selected:

            self.breakdown.item(row, 0).setData(Qt.ItemDataRole.UserRole, scene['id'])

            self.breakdown.item(row, 1).setText(scene['heading'])

        self.check_workflow()





    def report_breakdown_data(self):

        headings = {scene['id']: scene['heading'] for scene in self.current_scenes()}

        return [{**row, 'scene': headings.get(row.get('scene_id'), row['scene'])} for row in self.breakdown_data()]



    def export_pdf(self):

        from html import escape

        from PySide6.QtGui import QTextDocument

        from PySide6.QtPrintSupport import QPrinter

        filename, _ = QFileDialog.getSaveFileName(self, ui_text('Exportar guion PDF'), '', 'PDF (*.pdf)')

        if not filename: return

        if not filename.lower().endswith('.pdf'): filename += '.pdf'

        try:

            document = self.editor.document().clone()

            if getattr(self, 'project_info', {}).get('title'):

                from PySide6.QtGui import QTextCursor, QTextBlockFormat, QTextCharFormat, QTextFormat

                cursor = QTextCursor(document); cursor.movePosition(QTextCursor.MoveOperation.Start)

                cursor.insertBlock()

                cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock)

                block_format = QTextBlockFormat(); block_format.setAlignment(Qt.AlignmentFlag.AlignCenter); block_format.setTopMargin(160)

                block_format.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysAfter)

                cursor.setBlockFormat(block_format)

                char = QTextCharFormat(); char.setFontFamilies(['Courier New']); char.setFontPointSize(12)

                from production_reports import metadata_lines

                cursor.insertText(self.project_info['title'] + '\u2028\u2028' + '\u2028'.join(metadata_lines(self.project_info)), char)

            printer = QPrinter(QPrinter.PrinterMode.HighResolution); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(filename)

            document.print_(printer)

            if not Path(filename).is_file() or not Path(filename).stat().st_size: raise OSError('No se pudo crear el PDF.')

        except (OSError, ValueError) as error: QMessageBox.critical(self, ui_text('No se pudo exportar'), str(error))





    def remove_schedule_rows(self):

        table = self.schedule_page.table

        for row in sorted({item.row() for item in table.selectedItems()}, reverse=True): table.removeRow(row)

        self.schedule_page.renumber(); self.check_workflow()





    def refresh_currency_label(self, *args):

        if hasattr(self, 'currency_label'):

            self.currency_label.setText(ui_text('Moneda base: ') + self.base_currency.currentText())



    def open_currency_settings(self):

        money.edit_currencies(self)

