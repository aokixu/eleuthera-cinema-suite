"""Persistencia de fuentes y asignaciones; los resultados se reconstruyen."""
from ui_i18n import ui_text, ui_join
from budget_fringes import Fringe, Fringes
from budget_values import BudgetError


def load_fringes(data, values):
    payload = data.get('budget_fringes', {'version': 1, 'items': []})
    if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload['version'] != 1:
        raise BudgetError('Versión de Fringes incompatible.')
    items = payload.get('items')
    if not isinstance(items, list) or len(items) > 10000: raise BudgetError('Catálogo de Fringes inválido.')
    parsed = []
    for item in items:
        if not isinstance(item, dict) or not all(key in item for key in ('id', 'name', 'percentage', 'active')) or not item['id']:
            raise BudgetError('Fringe inválido en el proyecto.')
        parsed.append(Fringe(item['name'], item['percentage'], item.get('cap'),
                             item.get('description', ''), item['active'], item['id']))
    catalog = Fringes(parsed, values)
    for index, row in enumerate(data.get('budget', [])):
        ids = catalog.assignments(row.get('fringe_ids', []))
        if ids and row.get('level') == ui_text('Cuenta'):
            raise BudgetError('Fila ' + str(index + 1) + ': asigna Fringes a partidas, no a Cuentas.')
    return catalog


def dump_fringes(catalog):
    return {'version': 1, 'items': [dict(id=item.id, name=item.name, percentage=item.percentage,
             cap=item.cap, description=item.description, active=item.active) for item in catalog.items()]}
