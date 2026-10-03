"""Globals constantes/calculados y transacciones de su grafo, sin Qt."""
from dataclasses import dataclass, replace
from decimal import Decimal
from budget_values import BudgetError, numeric, global_name
from budget_expressions import evaluate, parse_expression
from budget_dependencies import DependencyGraph


@dataclass(frozen=True)
class Global:
    name: str
    value: object
    description: str = ''
    formula: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'name', global_name(self.name))
        if not isinstance(self.description, str) or len(self.description) > 1000:
            raise BudgetError('La descripción debe tener hasta 1000 caracteres.')
        if self.formula is not None:
            parse_expression(self.formula)
            object.__setattr__(self, 'formula', self.formula.strip())
            if self.value is not None: object.__setattr__(self, 'value', numeric(self.value))
            return
        try:
            value = numeric(self.value)
        except BudgetError:
            if not isinstance(self.value, str) or self.value.strip().lower().lstrip('+-') in ('nan', 'inf', 'infinity', 'snan'):
                raise
            expression = parse_expression(self.value)
            object.__setattr__(self, 'formula', self.value.strip())
            object.__setattr__(self, 'value', None)
        else:
            object.__setattr__(self, 'value', value)

    @property
    def source(self):
        return self.formula if self.formula is not None else str(self.value)


class Globals:
    def __init__(self, items=()):
        self._items = {}
        self.graph = DependencyGraph({})
        self.last_changed = frozenset()
        self.last_recalculated = ()
        candidate = {}
        for item in items:
            if item.name in candidate: raise BudgetError('Nombre duplicado: ' + item.name)
            candidate[item.name] = item
        self._commit(candidate)

    def _commit(self, candidate):
        if len(candidate) > 10000: raise BudgetError('Máximo 10000 Globals por presupuesto.')
        graph = DependencyGraph({name: parse_expression(item.formula).dependencies if item.formula is not None else ()
                                 for name, item in candidate.items()})
        seeds = {name for name, item in candidate.items()
                 if name not in self._items or item.formula != self._items[name].formula
                 or (item.formula is None and item.value != self._items[name].value)}
        affected = graph.affected(seeds)
        resolved, values, evaluated = {}, {}, []
        for name in graph.order:
            item = candidate[name]
            if item.formula is not None:
                if name in affected:
                    try: value = evaluate(item.formula, values)
                    except BudgetError as error: raise BudgetError('Global ' + name + ': ' + str(error)) from error
                    evaluated.append(name)
                else:
                    value = self._items[name].value
                item = replace(item, value=value)
            values[name] = item.value
            resolved[name] = item
        changed = {name for name, item in resolved.items() if name not in self._items or item.value != self._items[name].value}
        changed.update(self._items.keys() - resolved.keys())
        # All parsing, graph validation and evaluation succeeded: commit once.
        self._items = {name: resolved[name] for name in candidate}
        self.graph = graph
        self.last_changed = frozenset(changed)
        self.last_recalculated = tuple(evaluated)

    def items(self):
        return tuple(self._items.values())

    def values(self):
        return {name: item.value for name, item in self._items.items()}

    def get(self, name):
        name = global_name(name)
        if name not in self._items: raise BudgetError('Global inexistente: ' + name)
        return self._items[name]

    def add(self, name, value, description=''):
        item = Global(name, value, description)
        if item.name in self._items: raise BudgetError('Nombre duplicado: ' + item.name)
        self._commit({**self._items, item.name: item})
        return self.get(item.name)

    def edit(self, old_name, name, value, description='', references=()):
        old = self.get(old_name)
        item = Global(name, value, description)
        if item.name != old.name:
            if item.name in self._items: raise BudgetError('Nombre duplicado: ' + item.name)
            if old.name in references or self.graph.dependents[old.name]:
                raise BudgetError('No puedes renombrar un Global utilizado: ' + old.name)
        candidate = {item.name if key == old.name else key: item if key == old.name else current
                     for key, current in self._items.items()}
        self._commit(candidate)
        return self.get(item.name)

    def remove(self, name, references=()):
        item = self.get(name)
        if item.name in references or self.graph.dependents[item.name]:
            raise BudgetError('No puedes eliminar un Global utilizado: ' + item.name)
        self._commit({key: value for key, value in self._items.items() if key != item.name})
