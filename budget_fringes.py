"""Catálogo de Fringes inmutable por transacción, sin dependencia de Qt."""
from dataclasses import dataclass
from uuid import uuid4
import re
from budget_values import BudgetError, global_name, numeric
from budget_expressions import parse_expression, evaluate
from budget_dependencies import DependencyGraph


@dataclass(frozen=True)
class Fringe:
    name: str
    percentage: str
    cap: str | None = None
    description: str = ''
    active: bool = True
    id: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'name', global_name(self.name))
        object.__setattr__(self, 'id', self.id or uuid4().hex)
        if not isinstance(self.id, str) or not re.fullmatch(r'[a-f0-9]{32}', self.id):
            raise BudgetError('Identificador de Fringe inválido.')
        if type(self.active) is not bool: raise BudgetError('Estado de Fringe inválido.')
        if not isinstance(self.description, str) or len(self.description) > 1000:
            raise BudgetError('Descripción de Fringe inválida (máximo 1000 caracteres).')
        for key in ('percentage', 'cap'):
            value = getattr(self, key)
            if key == 'cap' and value is None: continue
            if not isinstance(value, str): value = str(numeric(value))
            parse_expression(value)
            object.__setattr__(self, key, value.strip())

    @property
    def references(self):
        refs = parse_expression(self.percentage).dependencies
        return refs | (parse_expression(self.cap).dependencies if self.cap is not None else frozenset())


class Fringes:
    def __init__(self, items=(), values=None):
        self._items = {}
        names = set()
        for item in items:
            if item.id in self._items: raise BudgetError('Identificador de Fringe duplicado.')
            if item.name in names: raise BudgetError('Nombre de Fringe duplicado: ' + item.name)
            names.add(item.name); self._items[item.id] = item
        if len(self._items) > 10000: raise BudgetError('Máximo 10000 Fringes.')
        self.resolved = {}
        self._bind(values or {}, None)

    def items(self): return tuple(self._items.values())

    def get(self, identifier):
        if not isinstance(identifier, str) or identifier not in self._items:
            raise BudgetError('Fringe inexistente: ' + str(identifier))
        return self._items[identifier]

    @property
    def references(self):
        return frozenset(ref for item in self.items() for ref in item.references)

    def _bind(self, values, changed):
        graph = DependencyGraph({**{name: () for name in values},
                                 **{'@' + item.id: item.references for item in self.items()}})
        affected = graph.affected(changed) if changed is not None else set(graph.order)
        resolved = dict(self.resolved)
        evaluated = []
        for item in self.items():
            if '@' + item.id not in affected: continue
            try:
                percentage = evaluate(item.percentage, values)
                cap = evaluate(item.cap, values) if item.cap is not None else None
                if percentage < 0: raise BudgetError('El porcentaje no puede ser negativo.')
                if cap is not None and cap < 0: raise BudgetError('El tope no puede ser negativo.')
            except BudgetError as error:
                raise BudgetError('Fringe ' + item.name + ': ' + str(error)) from error
            resolved[item.id] = (percentage, cap, item.active)
            evaluated.append(item.id)
        self.changed = frozenset(key for key in resolved if resolved[key] != self.resolved.get(key))
        self.resolved, self.graph, self.last_evaluated = resolved, graph, tuple(evaluated)

    def rebind(self, values, changed):
        candidate = object.__new__(Fringes)
        candidate._items = dict(self._items)
        candidate.resolved = dict(self.resolved)
        candidate._bind(values, changed)
        return candidate

    def updated(self, item, values):
        items = dict(self._items); items[item.id] = item
        candidate = Fringes(items.values(), values)
        candidate.changed = frozenset(key for key in candidate.resolved
                                     if candidate.resolved[key] != self.resolved.get(key))
        return candidate

    def removed(self, identifier, values, usage=()):
        item = self.get(identifier)
        if usage: raise BudgetError('No puedes eliminar ' + item.name + '; usado en: ' + ', '.join(map(str, usage)))
        return Fringes((item for item in self.items() if item.id != identifier), values)

    def assignments(self, identifiers):
        if not isinstance(identifiers, (list, tuple)) or len(identifiers) > 10000:
            raise BudgetError('Asignaciones de Fringes inválidas.')
        result = []
        for identifier in identifiers:
            self.get(identifier)
            if identifier not in result: result.append(identifier)
        return tuple(result)
