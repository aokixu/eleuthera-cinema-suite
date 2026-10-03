"""Catálogo transaccional de reducciones de importe, independiente de Qt."""
from dataclasses import dataclass
from uuid import uuid4
import re
from budget_values import BudgetError, global_name, numeric
from budget_expressions import parse_expression, evaluate
from budget_dependencies import DependencyGraph


@dataclass(frozen=True)
class Credit:
    name: str
    amount: str
    description: str = ''
    active: bool = True
    id: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'name', global_name(self.name))
        object.__setattr__(self, 'id', self.id or uuid4().hex)
        if not isinstance(self.id, str) or not re.fullmatch('[a-f0-9]{32}', self.id):
            raise BudgetError('Identificador de Credit inválido.')
        if not isinstance(self.description, str) or len(self.description) > 1000:
            raise BudgetError('Descripción de Credit inválida (máximo 1000 caracteres).')
        if type(self.active) is not bool: raise BudgetError('Estado de Credit inválido.')
        source = self.amount if isinstance(self.amount, str) else str(numeric(self.amount))
        parse_expression(source)
        object.__setattr__(self, 'amount', source.strip())

    @property
    def references(self): return parse_expression(self.amount).dependencies


class Credits:
    def __init__(self, items=(), values=None):
        self._items, names = {}, set()
        for item in items:
            if item.id in self._items: raise BudgetError('Identificador de Credit duplicado.')
            if item.name in names: raise BudgetError('Nombre de Credit duplicado: ' + item.name)
            self._items[item.id] = item; names.add(item.name)
        if len(self._items) > 10000: raise BudgetError('Máximo 10000 Credits.')
        self.resolved = {}
        self._bind(values or {}, None)

    def items(self): return tuple(self._items.values())

    def get(self, identifier):
        if not isinstance(identifier, str) or identifier not in self._items:
            raise BudgetError('Credit inexistente: ' + str(identifier))
        return self._items[identifier]

    @property
    def references(self): return frozenset(ref for item in self.items() for ref in item.references)

    def _bind(self, values, changed):
        graph = DependencyGraph({**{name: () for name in values}, **{'@'+item.id: item.references for item in self.items()}})
        affected = graph.affected(changed) if changed is not None else set(graph.order)
        resolved, evaluated = dict(self.resolved), []
        for item in self.items():
            if '@'+item.id not in affected: continue
            try:
                amount = evaluate(item.amount, values)
                if amount < 0: raise BudgetError('El importe de un Credit no puede ser negativo.')
            except BudgetError as error: raise BudgetError('Credit '+item.name+': '+str(error)) from error
            resolved[item.id] = (amount, item.active); evaluated.append(item.id)
        self.changed = frozenset(key for key in resolved if resolved[key] != self.resolved.get(key))
        self.resolved, self.graph, self.last_evaluated = resolved, graph, tuple(evaluated)

    def rebind(self, values, changed):
        from copy import copy
        candidate = copy(self); candidate._bind(values, changed); return candidate

    def updated(self, item, values):
        return Credits({**self._items, item.id:item}.values(), values)

    def removed(self, identifier, values, usage=()):
        item = self.get(identifier)
        if usage:
            raise BudgetError('No puedes eliminar '+item.name+'; usado en: '+', '.join(map(str,usage[:10]))+
                              (f' y {len(usage)-10} partidas más.' if len(usage)>10 else ''))
        return Credits((item for item in self.items() if item.id != identifier), values)

    def assignments(self, identifiers):
        if not isinstance(identifiers, (list,tuple)) or len(identifiers)>10000:
            raise BudgetError('Asignaciones de Credits inválidas.')
        result, seen = [], set()
        for identifier in identifiers:
            self.get(identifier)
            if identifier not in seen: result.append(identifier); seen.add(identifier)
        return tuple(result)
