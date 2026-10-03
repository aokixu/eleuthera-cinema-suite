from pathlib import Path
p=Path('suite.py');s=p.read_text(encoding='utf-8-sig')
a=s.index("            self.budget_title.setText("); b=s.index('    def module_header',a); s=s[:a]+s[b:]
s=s.replace("        layout.addLayout(self.module_header(\n            'Desglose de produccion',\n            'El analisis propone elementos encontrados en el guion. Revisa, corrige y aprueba antes de presupuestar.'\n        ))\n        actions = QHBoxLayout()", "        actions = QHBoxLayout()\n        self.breakdown_actions = actions")
s=s.replace("        header = self.module_header('Presupuesto preliminar', 'Calcula conceptos sencillos por cantidad, jornadas y precio unitario.')\n        self.budget_title = header.itemAt(0).widget(); self.budget_hint = header.itemAt(1).widget()\n        layout.addLayout(header)\n        actions = QHBoxLayout()", "        actions = QHBoxLayout()\n        self.budget_actions = actions")
s=s.replace("QPushButton('Exportar con plantilla Excel')", "QPushButton('Plantilla Excel…')")
s=s.replace("QPushButton('Enviar aprobados al presupuesto')", "QPushButton('Presupuestar aprobados')")
s=s.replace("self.default_fringe, QLabel('Moneda base:'), self.base_currency):", "self.default_fringe):")
s=s.replace("        self._last_base_currency = self.base_currency.currentText()", "        self.base_currency.setParent(self)\n        self.base_currency.hide()\n        self._last_base_currency = self.base_currency.currentText()",1)
p.write_text(s,encoding='utf-8')
p=Path('scheduling.py');s=p.read_text(encoding='utf-8-sig');a=s.index("        title = QLabel('Plan de rodaje')");b=s.index('        tools = QHBoxLayout()',a);s=s[:a]+s[b:]
s=s.replace("QPushButton('Actualizar desde guion y desglose')", "QPushButton('Actualizar…')")
s=s.replace("        self.day = QSpinBox()", "        self.sync_button.setToolTip('Revisar actualizaciones desde el guion y el desglose.')\n        self.day = QSpinBox()",1)
s=s.replace("QPushButton('Exportar informes Excel')", "QPushButton('Excel')")
s=s.replace("        tools.addStretch(); tools.addWidget(self.report_type); tools.addWidget(export); layout.addLayout(tools)", "        tools.addStretch(); layout.addLayout(tools)\n        self.report_actions = QHBoxLayout()\n        self.report_actions.addWidget(self.report_type); self.report_actions.addWidget(export); self.report_actions.addStretch()\n        layout.addLayout(self.report_actions)")
p.write_text(s,encoding='utf-8')
p=Path('project_workflow.py');s=p.read_text(encoding='utf-8');a=s.index("        remove_strip = QPushButton(");b=s.index('        export_menu = ',a)
s=s[:a]+'''        remove_strip = QPushButton('Quitar del plan')
        remove_strip.setToolTip('Quita las escenas seleccionadas únicamente del plan de rodaje.')
        remove_strip.clicked.connect(self.remove_schedule_rows)
        self.schedule_page.report_actions.insertWidget(2, remove_strip)
        for kind, controls in (('budget', self.budget_actions), ('schedule', self.schedule_page.report_actions)):
            pdf = QPushButton('PDF'); pdf.setToolTip('Exportar informe PDF')
            pdf.clicked.connect(lambda checked=False, k=kind: self.export_report(k, 'pdf'))
            controls.insertWidget(controls.count() - 1, pdf)
            if kind == 'budget':
                excel = QPushButton('Excel'); excel.setToolTip('Exportar presupuesto Excel')
                excel.clicked.connect(lambda: self.export_report('budget', 'xlsx'))
                controls.insertWidget(controls.count() - 1, excel)
        self.currency_label = QLabel('Moneda base: ' + self.base_currency.currentText())
        self.currency_change = QPushButton('Cambiar…')
        self.currency_change.setToolTip('Abre Proyecto para cambiar la moneda base y revisar las tasas antes de recalcular.')
        self.currency_change.clicked.connect(self.open_currency_settings)
        self.budget_actions.addWidget(self.currency_label); self.budget_actions.addWidget(self.currency_change)
        self.base_currency.currentTextChanged.connect(self.refresh_currency_label)
        for page in (self.breakdown_page, self.budget_page, self.schedule_page):
            page.layout().setContentsMargins(12, 10, 12, 12)
            page.layout().setSpacing(6)
''' +s[b:]
s=s.replace("link = QPushButton('Vincular seleccionados a escena…')", "link = QPushButton('Asignar a escena…')\n        link.setToolTip('Asigna los elementos seleccionados a una escena del guion. Cambia su asignación; no los copia.')")
s=s.replace('self.breakdown_page.layout().insertWidget(2, link)', 'self.breakdown_actions.insertWidget(3, link)')
s=s.replace("'Vincular elementos'", "'Asignar a escena'").replace('que deseas vincular.', 'que deseas asignar.')
s=s.replace('    def fill_metadata(self):\n', '    def fill_metadata(self):\n        self.refresh_currency_label()\n')
s=s.replace("        self.metadata_feedback.setText('Datos aplicados.", "        self.refresh_currency_label()\n        self.metadata_feedback.setText('Datos aplicados.")
s+='''

    def refresh_currency_label(self, *args):
        if hasattr(self, 'currency_label'):
            self.currency_label.setText('Moneda base: ' + self.base_currency.currentText())

    def open_currency_settings(self):
        self.modules.setCurrentWidget(self.metadata_page)
        self.info_fields['currency'].setFocus()
        self.info_fields['currency'].selectAll()
'''
p.write_text(s,encoding='utf-8')
