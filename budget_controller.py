"""Adaptador Qt: recálculo selectivo por Globals y lotes cancelables."""
from ui_i18n import ui_text, ui_join
from time import perf_counter
from decimal import Decimal
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QColor
from budget_model import BudgetError, Globals
from budget_fringes import Fringes, Fringe
from budget_fringe_persistence import load_fringes, dump_fringes

FRINGE_ROLE = 259
CREDIT_ROLE = 262
CHARGE_ROLE = 263
from budget_charges import Charge, Charges
from budget_charge_persistence import load_charges, dump_charges
from budget_credits import Credit, Credits
from budget_credit_persistence import load_credits, dump_credits
from budget_persistence import load_globals, dump_globals
from budget_engine import Calculation, calculation_steps, recalculation_steps, affected_rows

KEYS = ('level', 'block', 'code', 'category', 'concept', 'quantity', 'unit', 'days', 'unit_price', 'currency', 'exchange', 'fringe', 'total', 'notes')


class BudgetController(QObject):
    finished = Signal()
    started = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.catalog = load_globals({'budget_settings': {'shooting_days': window.global_days.value()}})
        self.fringes = Fringes()
        self.credits = Credits()
        self.charges = Charges()
        self.result = None
        self.rows = None
        self.last_run = {}
        self.busy = False
        self._job = None
        self.timer = QTimer(self)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self._tick)
        window.global_days.valueChanged.connect(self._legacy_days_changed)
        from budget_group_controller import GroupsController
        self.groups = GroupsController(self)

    def payload(self):
        return dump_globals(self.catalog)

    def load(self, data):
        catalog = load_globals(data)
        fringes = load_fringes(data, catalog.values())
        from budget_group_persistence import load_groups
        groups = load_groups(data)
        credits = load_credits(data, catalog.values())
        charges = load_charges(data, catalog.values())
        self.cancel()
        self.charges = charges
        self.credits = credits
        self.catalog, self.fringes = catalog, fringes
        self.groups.reset(groups)
        self.result = self.rows = None
        self.mirror_days()

    def mirror_days(self):
        spin = self.window.global_days
        old = spin.blockSignals(True)
        try:
            item = next((x for x in self.catalog.items() if x.name == 'DIAS_RODAJE'), None)
            value = item.value if item else None
            fits = value is not None and spin.minimum() <= value <= spin.maximum() and value == value.quantize(Decimal('0.01'))
            spin.setEnabled(bool(fits and item.formula is None))
            spin.setToolTip('Edita DIAS_RODAJE en Globals.' if not spin.isEnabled() else 'Global DIAS_RODAJE')
            if fits: spin.setValue(float(value))
        finally:
            spin.blockSignals(old)

    def _legacy_days_changed(self, value):
        if getattr(self.window, '_loading', False): return
        try:
            if 'DIAS_RODAJE' in self.catalog.values():
                item = self.catalog.get('DIAS_RODAJE')
                if item.formula is not None:
                    self.mirror_days()
                    return
                self._change_global('edit', item.name, item.name, str(value), item.description)
            else:
                self._change_global('add', 'DIAS_RODAJE', str(value), 'Días de rodaje')
        except BudgetError as error:
            self.mirror_days()
            self.window.statusBar().showMessage(str(error))
            return
        self.window.document_changed()
        self.request(changed_globals=self.catalog.last_changed)

    def mutate(self, action, *args):
        if self.result is None and not self.busy: self.request()
        if self.busy or self.result is None:
            raise BudgetError('Espera a que termine el recálculo del presupuesto.')
        self._change_global(action, *args)
        self.mirror_days()
        self.window.document_changed()
        self.request(changed_globals=self.catalog.last_changed)

    def fringes_payload(self):
        return dump_fringes(self.fringes)

    def _change_global(self, action, *args):
        references = set(self.result.dependents if self.result else ()) | self.fringes.references | self.credits.references | self.charges.references
        from copy import copy
        candidate = copy(self.catalog)
        if action == 'add': candidate.add(*args)
        elif action == 'edit': candidate.edit(*args, references=references)
        elif action == 'remove': candidate.remove(*args, references=references)
        else: raise BudgetError('Operación inválida.')
        fringes = self.fringes.rebind(candidate.values(), candidate.last_changed)
        credits = self.credits.rebind(candidate.values(), candidate.last_changed)
        charges = self.charges.rebind(candidate.values(), candidate.last_changed)
        self.catalog, self.fringes, self.credits, self.charges = candidate, fringes, credits, charges

    def _ready(self):
        if self.result is None and not self.busy: self.request()
        if self.busy or self.result is None:
            raise BudgetError('Espera a que termine el recálculo del presupuesto.')

    def mutate_fringe(self, action, identifier=None, **fields):
        self._ready()
        if action == 'remove':
            usage = [f"fila {i + 1}: {self.rows[i].get('concept', '')}" for i in sorted(self.result.fringe_dependents.get(identifier, ()))]
            candidate = self.fringes.removed(identifier, self.catalog.values(), usage)
        elif action in ('add', 'edit'):
            if action == 'edit': self.fringes.get(identifier)
            item = Fringe(**fields, id=identifier if action == 'edit' else '')
            candidate = self.fringes.updated(item, self.catalog.values())
            identifier = item.id
        else: raise BudgetError('Operación de Fringe inválida.')
        # Changing expression references must refresh the index, even if the
        # numeric result happens to remain equal at this moment.
        affected = self.result.fringe_dependents.get(identifier, ())
        self.fringes = candidate
        self.window.document_changed()
        self.request(changed_globals=(), fringe_rows=affected)
        return identifier

    def assign_fringes(self, indices, identifiers):
        self._ready()
        ids = self.fringes.assignments(identifiers)
        indices = sorted(set(indices))
        if not indices: raise BudgetError(ui_text('Selecciona una partida.'))
        table = self.window.budget
        for index in indices:
            if not 0 <= index < table.rowCount() or table.item(index, 0).text() == ui_text('Cuenta'):
                raise BudgetError('Solo se asignan Fringes directamente a partidas.')
        old = table.blockSignals(True)
        try:
            for index in indices:
                table.item(index, 11).setData(FRINGE_ROLE, list(ids))
                self.rows[index] = {**self.rows[index], 'fringe_ids': list(ids)}
        finally: table.blockSignals(old)
        self.window.document_changed()
        self.request(changed_globals=(), fringe_rows=indices)

    def credits_payload(self): return dump_credits(self.credits)

    def mutate_credit(self, action, identifier=None, **fields):
        self._ready()
        if action == 'remove':
            usage = [f"fila {i+1}: {self.rows[i].get('concept', '')}" for i in sorted(self.result.credit_dependents.get(identifier, ()))]
            candidate = self.credits.removed(identifier, self.catalog.values(), usage)
        elif action in ('add', 'edit'):
            if action == 'edit': self.credits.get(identifier)
            item = Credit(**fields, id=identifier if action == 'edit' else '')
            candidate = self.credits.updated(item, self.catalog.values()); identifier = item.id
        else: raise BudgetError('Operación de Credit inválida.')
        affected = self.result.credit_dependents.get(identifier, ())
        self.credits = candidate
        self.window.document_changed()
        self.request(changed_globals=(), fringe_rows=affected)
        return identifier

    def assign_credits(self, indices, identifiers):
        self._ready()
        ids = self.credits.assignments(identifiers)
        if not isinstance(indices, (list, tuple)) or any(type(i) is not int for i in indices):
            raise BudgetError('Selección de partidas inválida.')
        indices = sorted(set(indices))
        if not indices: raise BudgetError(ui_text('Selecciona una partida.'))
        table = self.window.budget
        for index in indices:
            if not 0 <= index < len(self.rows) or self.rows[index].get('level') == ui_text('Cuenta'):
                raise BudgetError('Solo se asignan Credits directamente a partidas.')
        old = table.blockSignals(True)
        try:
            for index in indices:
                table.item(index, 0).setData(CREDIT_ROLE, list(ids))
                self.rows[index] = {**self.rows[index], 'credit_ids': list(ids)}
        finally: table.blockSignals(old)
        self.window.document_changed()
        self.request(changed_globals=(), fringe_rows=indices)

    def charges_payload(self): return dump_charges(self.charges)

    def mutate_charge(self, action, identifier=None, **fields):
        self._ready()
        if action == 'remove':
            usage = [f"fila {i+1}: {self.rows[i].get('concept', '')}" for i in sorted(self.result.charge_dependents.get(identifier, ()))]
            candidate = self.charges.removed(identifier, self.catalog.values(), usage)
        elif action in ('add', 'edit'):
            if action == 'edit': self.charges.get(identifier)
            item = Charge(**fields, id=identifier if action == 'edit' else '')
            candidate = self.charges.updated(item, self.catalog.values()); identifier = item.id
        else: raise BudgetError('Operación de Charge inválida.')
        affected = self.result.charge_dependents.get(identifier, ())
        self.charges = candidate
        self.window.document_changed()
        self.request(changed_globals=(), fringe_rows=affected)
        return identifier

    def assign_charges(self, indices, identifiers):
        self._ready()
        ids = self.charges.assignments(identifiers)
        if not isinstance(indices, (list, tuple)) or any(type(i) is not int for i in indices):
            raise BudgetError('Selección de partidas inválida.')
        indices = sorted(set(indices))
        if not indices: raise BudgetError(ui_text('Selecciona una partida.'))
        table = self.window.budget
        for index in indices:
            if not 0 <= index < len(self.rows) or self.rows[index].get('level') == ui_text('Cuenta'):
                raise BudgetError('Solo se asignan Charges directamente a partidas.')
        old = table.blockSignals(True)
        try:
            for index in indices:
                table.item(index, 0).setData(CHARGE_ROLE, list(ids))
                self.rows[index] = {**self.rows[index], 'charge_ids': list(ids)}
        finally: table.blockSignals(old)
        self.window.document_changed()
        self.request(changed_globals=(), fringe_rows=indices)

    def item_changed(self, item):
        if getattr(self.window, '_loading', False): return
        if item.column() == 0:
            from budget_group_controller import GROUP_ROLE, GROUP_LEVEL_ROLE
            table = self.window.budget
            old = table.blockSignals(True)
            try:
                if item.text() == ui_text('Cuenta') and (item.data(GROUP_ROLE) or item.data(CREDIT_ROLE) or item.data(CHARGE_ROLE)):
                    item.setText(item.data(GROUP_LEVEL_ROLE) or ui_text('Detalle'))
                    self.window.statusBar().showMessage('Quita las asignaciones de Groups, Credits y cargos contractuales antes de convertir la partida en Cuenta.')
                    return
                item.setData(GROUP_LEVEL_ROLE, item.text())
            finally: table.blockSignals(old)
        if (not self.busy and self.result is not None and self.rows is not None
                and len(self.rows) == self.window.budget.rowCount()
                and item.column() in (5, 7, 8, 11)
                and self.rows[item.row()].get('level') != ui_text('Cuenta')):
            index = item.row()
            self.rows[index] = {**self.rows[index], KEYS[item.column()]: item.text()}
            self.request(changed_globals=(), fringe_rows=(index,))
        else: self.request()

    def cancel(self):
        self.timer.stop()
        self._job = None
        self.busy = False

    def request(self, force=False, changed_globals=None, fringe_rows=()):
        if getattr(self.window, '_loading', False) and not force: return
        # Any pending job can have partially applied cells: fall back to a fresh
        # capture if another edit arrives before it publishes its snapshot.
        incremental = (changed_globals is not None and not self.busy and self.result is not None
                       and self.rows is not None and len(self.rows) == self.window.budget.rowCount())
        affected = affected_rows(self.result, changed_globals) if incremental else None
        if incremental: affected = frozenset(affected) | frozenset(fringe_rows)
        self.cancel()
        if incremental and not affected:
            self.last_run = {'mode': 'unchanged', 'evaluated_rows': 0, 'updated_rows': 0}
            self.finished.emit()
            return
        self.busy = True
        self.started.emit()
        self._job = self._steps(affected)
        size = len(affected) if incremental else self.window.budget.rowCount()
        if size <= 200:
            while self.busy: self._tick(unbounded=True)
        else:
            self.window.total_label.setText('Recalculando presupuesto…')
            self.timer.start()

    def _tick(self, unbounded=False):
        deadline = perf_counter() + .008
        try:
            while self._job is not None and (unbounded or perf_counter() < deadline):
                next(self._job)
        except StopIteration:
            self.cancel()
            self.finished.emit()
        except Exception as error:
            self.cancel()
            self.window.total_label.setText('Error de cálculo: ' + str(error))
            self.result = self.rows = None
            self.finished.emit()

    def _steps(self, affected=None):
        from budget_currencies import synchronize
        w, table = self.window, self.window.budget
        if affected is None:
            rows = []
            for index in range(table.rowCount()):
                if index % 40 == 0: synchronize(w, index, min(index + 40, table.rowCount()))
                rows.append({key: table.item(index, column).text() if table.item(index, column) else ''
                             for column, key in enumerate(KEYS)})
                rows[-1]['fringe_ids'] = table.item(index, 11).data(FRINGE_ROLE) or []
                from budget_group_controller import GROUP_ROLE
                rows[-1]['group_ids'] = table.item(index, 0).data(GROUP_ROLE) or []
                rows[-1]['credit_ids'] = table.item(index, 0).data(CREDIT_ROLE) or []
                rows[-1]['charge_ids'] = table.item(index, 0).data(CHARGE_ROLE) or []
                yield
            if not rows: synchronize(w)
            work = calculation_steps(rows, self.catalog.values(), self.fringes, self.credits, self.charges)
        else:
            rows = self.rows
            work = recalculation_steps(rows, self.catalog.values(), self.result, affected, self.fringes, self.credits, self.charges)
        result = None
        for value in work:
            if isinstance(value, Calculation): result = value
            yield
        indices = range(len(result.totals)) if result.changed_rows is None else result.changed_rows
        for index in indices:
            previous = table.blockSignals(True)
            try:
                item = table.item(index, 12)
                error = result.errors.get(index, '')
                item.setText('ERROR' if error else f'{result.totals[index]:.2f}')
                item.setToolTip(error or ('' if rows[index].get('level') == ui_text('Cuenta') else f'Base: {result.bases[index]:.2f} | Fringes: {result.fringe_totals[index]:.2f} | Cargos contractuales: {result.charge_totals[index]:.2f} | Antes de Credits: {result.before_credits[index]:.2f} | Credits: {result.credit_totals[index]:.2f}'))
                assigned = [self.fringes.get(key).name for key in rows[index].get('fringe_ids', [])]
                table.item(index, 11).setToolTip('Fringe % legado + catálogo: ' + (', '.join(assigned) or 'sin asignaciones'))
                item.setForeground(QColor('#e89a9a' if error else '#e6e2da'))
            finally:
                table.blockSignals(previous)
            yield
        summary = None
        for summary in self.groups.calculation_steps(rows, result):
            yield
        self.groups.analysis = summary
        self.result, self.rows = result, rows
        self.last_run = {'mode': 'full' if affected is None else 'incremental',
                         'evaluated_rows': result.evaluated_rows, 'updated_rows': len(indices)}
        currency = w.base_currency.currentText().strip().upper() or 'USD'
        w.top_sheet_label.setText(f'TOP SHEET   ATL {result.atl:,.2f}   |   BTL {result.btl:,.2f}')
        suffix = f'  |  ERRORES: {len(result.errors)}' if result.errors else ''
        pending = getattr(w, '_pending_currency_rates', 0)
        if pending: suffix += f'  |  TASAS PENDIENTES: {pending}'
        w.total_label.setText(f'TOTAL {currency}  {result.total:,.2f}' + suffix)
