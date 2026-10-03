"""Agrega resultados finales del motor existente; nunca reevalúa las partidas."""
from ui_i18n import ui_text, ui_join
from dataclasses import dataclass
from decimal import Decimal
from budget_values import BudgetError


@dataclass(frozen=True)
class GroupAnalysis:
    assignments: tuple
    row_totals: tuple
    totals: dict
    members: dict
    changed: frozenset
    visited_rows: int

    def with_catalog(self, catalog):
        ids = [item.id for item in catalog.items()]
        return GroupAnalysis(self.assignments, self.row_totals,
            {key: self.totals.get(key, Decimal(0)) for key in ids},
            {key: self.members.get(key, frozenset()) for key in ids}, frozenset(), 0)

    def visible(self, identifiers, owners):
        if not identifiers: return frozenset(range(len(self.assignments)))
        visible = set()
        for identifier in identifiers:
            if identifier not in self.members: raise BudgetError('Group inexistente en el filtro.')
            visible.update(self.members[identifier])
        # Keep account context; its total still belongs to the whole budget.
        visible.update(owners[index] for index in tuple(visible) if owners[index] is not None)
        return frozenset(visible)


def analysis_steps(rows, row_totals, catalog, previous=None, indices=None):
    full = previous is None or indices is None or len(previous.assignments) != len(rows)
    if full:
        assigned = [frozenset() for _ in rows]
        values = [Decimal(0) for _ in rows]
        totals = {item.id: Decimal(0) for item in catalog.items()}
        members = {item.id: set() for item in catalog.items()}
        indices = range(len(rows))
    else:
        assigned, values = list(previous.assignments), list(previous.row_totals)
        totals = dict(previous.totals)
        # Copy only sets touched by this update, not all assigned memberships.
        members = dict(previous.members)
    touched, visited = set(), 0
    for index in indices:
        row = rows[index]
        new_ids = frozenset(catalog.assignments(row.get('group_ids', [])))
        if row.get('level') == ui_text('Cuenta'):
            if new_ids: raise BudgetError('No se asignan Groups a Cuentas.')
            yield None
            continue
        old_ids, old_value = assigned[index], values[index]
        value = row_totals[index]
        for identifier in old_ids | new_ids:
            delta = (value if identifier in new_ids else Decimal(0)) - (old_value if identifier in old_ids else Decimal(0))
            membership_changed = (identifier in old_ids) != (identifier in new_ids)
            if full or delta or membership_changed:
                if identifier not in touched: members[identifier] = set(members.get(identifier, ()))
                totals[identifier] = totals.get(identifier, Decimal(0)) + delta
                members[identifier].discard(index)
                if identifier in new_ids: members[identifier].add(index)
                touched.add(identifier)
        assigned[index], values[index] = new_ids, value
        visited += 1
        yield None
    for identifier in touched: members[identifier] = frozenset(members[identifier])
    yield GroupAnalysis(tuple(assigned), tuple(values), totals,
                        {key: frozenset(value) for key, value in members.items()}, frozenset(touched), visited)


def analyze(rows, row_totals, catalog, previous=None, indices=None):
    for result in analysis_steps(rows, row_totals, catalog, previous, indices): pass
    return result
