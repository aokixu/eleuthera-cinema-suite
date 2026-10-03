"""Adaptador Qt de la capa analítica Groups; sin segundo motor económico."""
from ui_i18n import ui_text, ui_join
from PySide6.QtCore import QObject, Signal
from budget_groups import Group
from budget_group_persistence import load_groups, dump_groups
from budget_group_analysis import analyze, analysis_steps
from budget_values import BudgetError

GROUP_ROLE = 260
GROUP_LEVEL_ROLE = 261

class GroupsController(QObject):
    changed = Signal()

    def __init__(self, budget):
        super().__init__(budget)
        self.budget = budget
        self.reset(load_groups({}))
        budget.finished.connect(self.on_finished)
        budget.started.connect(self.changed.emit)

    def payload(self): return dump_groups(self.catalog)

    def reset(self, catalog):
        self.catalog, self.analysis = catalog, None
        self.selected_filter, self._visible = (), set()

    def calculation_steps(self, rows, result):
        return analysis_steps(rows, result.totals, self.catalog, self.analysis, result.changed_rows)

    def on_finished(self):
        if self.budget.result is None: self.analysis = None
        if self.analysis is not None: self.apply_filter(force=self.budget.last_run.get('mode') == 'full')
        self.changed.emit()

    def ready(self):
        self.budget._ready()
        if self.analysis is None: raise BudgetError('El resumen de Groups todavía no está disponible.')

    def mutate(self, action, identifier=None, **fields):
        self.ready()
        if action == 'remove':
            usage = [f"fila {i+1}: {self.budget.rows[i].get('concept', '')}" for i in sorted(self.analysis.members.get(identifier, ()))]
            candidate = self.catalog.removed(identifier, usage)
        elif action in ('add', 'edit'):
            if action == 'edit': self.catalog.get(identifier)
            item = Group(**fields, id=identifier if action == 'edit' else '')
            candidate = self.catalog.updated(item); identifier = item.id
        else: raise BudgetError('Operación de Group inválida.')
        summary = self.analysis.with_catalog(candidate)
        self.catalog, self.analysis = candidate, summary
        self.selected_filter = tuple(key for key in self.selected_filter if key in summary.members)
        self.budget.window.document_changed()
        self.apply_filter(); self.changed.emit()
        return identifier

    def assign(self, indices, identifiers):
        self.ready()
        ids = self.catalog.assignments(identifiers)
        if not isinstance(indices, (list, tuple)) or any(type(i) is not int for i in indices):
            raise BudgetError('Selección de partidas inválida.')
        indices = sorted(set(indices))
        if not indices: raise BudgetError(ui_text('Selecciona una partida.'))
        budget, table = self.budget, self.budget.window.budget
        for index in indices:
            if not 0 <= index < len(budget.rows) or budget.rows[index].get('level') == ui_text('Cuenta'):
                raise BudgetError('Solo se asignan Groups directamente a partidas.')
        rows = list(budget.rows)
        for index in indices: rows[index] = {**rows[index], 'group_ids': list(ids)}
        summary = analyze(rows, budget.result.totals, self.catalog, self.analysis, indices)
        old = table.blockSignals(True)
        try:
            for index in indices: table.item(index, 0).setData(GROUP_ROLE, list(ids))
        finally: table.blockSignals(old)
        budget.rows, self.analysis = rows, summary
        budget.window.document_changed()
        self.apply_filter(); self.changed.emit()

    def set_filter(self, identifiers):
        self.ready()
        self.selected_filter = self.catalog.assignments(identifiers)
        self.apply_filter(); self.changed.emit()

    def apply_filter(self, force=False):
        if self.analysis is None: return
        budget, table = self.budget, self.budget.window.budget
        visible = set(self.analysis.visible(self.selected_filter, budget.result.owners))
        indices = range(table.rowCount()) if force else self._visible ^ visible
        for index in indices:
            if index < table.rowCount(): table.setRowHidden(index, index not in visible)
        self._visible = visible
        label = getattr(budget.window, 'groups_filter_label', None)
        if label is not None:
            names = ', '.join(self.catalog.get(key).name for key in self.selected_filter)
            label.setText('Filtro Groups: ' + names + ' · cuentas y totales generales incluyen filas ocultas' if names else ui_text('Groups: todo el presupuesto'))
        button = getattr(budget.window, 'show_all_groups_button', None)
        if button is not None: button.setVisible(bool(self.selected_filter))

    def summary_rows(self):
        self.ready()
        if self.budget.result.errors or getattr(self.budget.window, '_pending_currency_rates', 0):
            raise BudgetError('Corrige los errores o tipos de cambio pendientes antes de exportar Groups.')
        return [[item.name, len(self.analysis.members[item.id]), f'{self.analysis.totals[item.id]:.2f}'] for item in self.catalog.items()]
