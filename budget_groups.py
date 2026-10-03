"""Identidad y catálogo de clasificaciones analíticas, sin Qt ni cálculo económico."""
from dataclasses import dataclass
import re
from uuid import uuid4
from budget_values import BudgetError, global_name


@dataclass(frozen=True)
class Group:
    name: str
    description: str = ''
    active: bool = True
    id: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'name', global_name(self.name))
        object.__setattr__(self, 'id', self.id or uuid4().hex)
        if not isinstance(self.id, str) or not re.fullmatch('[a-f0-9]{32}', self.id):
            raise BudgetError('Identificador de Group inválido.')
        if not isinstance(self.description, str) or len(self.description) > 1000:
            raise BudgetError('Descripción de Group inválida (máximo 1000 caracteres).')
        if type(self.active) is not bool: raise BudgetError('Estado de Group inválido.')


class Groups:
    def __init__(self, items=()):
        self._items = {}
        names = set()
        for item in items:
            if item.id in self._items: raise BudgetError('Identificador de Group duplicado.')
            if item.name in names: raise BudgetError('Nombre de Group duplicado: ' + item.name)
            names.add(item.name); self._items[item.id] = item
        if len(self._items) > 10000: raise BudgetError('Máximo 10000 Groups.')

    def items(self): return tuple(self._items.values())

    def get(self, identifier):
        if not isinstance(identifier, str) or identifier not in self._items:
            raise BudgetError('Group inexistente: ' + str(identifier))
        return self._items[identifier]

    def updated(self, item):
        return Groups({**self._items, item.id: item}.values())

    def removed(self, identifier, usage=()):
        item = self.get(identifier)
        if usage: raise BudgetError('No puedes eliminar ' + item.name + '; tiene partidas asignadas: ' + ', '.join(map(str, usage)))
        return Groups(item for item in self.items() if item.id != identifier)

    def assignments(self, identifiers):
        if not isinstance(identifiers, (list, tuple)) or len(identifiers) > 10000:
            raise BudgetError('Asignaciones de Groups inválidas.')
        result, seen = [], set()
        for identifier in identifiers:
            self.get(identifier)
            if identifier not in seen: result.append(identifier); seen.add(identifier)
        return tuple(result)
