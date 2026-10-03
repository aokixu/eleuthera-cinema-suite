"""Solo persiste catálogo y relaciones por ID; los resúmenes son derivables."""
from ui_i18n import ui_text, ui_join
from budget_groups import Group, Groups
from budget_values import BudgetError


def load_groups(data):
    payload = data.get('budget_groups', {'version': 1, 'items': []})
    if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload['version'] != 1:
        raise BudgetError('Versión de Groups incompatible.')
    raw = payload.get('items')
    if not isinstance(raw, list) or len(raw) > 10000: raise BudgetError('Catálogo de Groups inválido.')
    items = []
    for item in raw:
        if not isinstance(item, dict) or not all(key in item for key in ('id', 'name', 'active')) or not item['id']:
            raise BudgetError('Group inválido en el proyecto.')
        items.append(Group(item['name'], item.get('description', ''), item['active'], item['id']))
    catalog = Groups(items)
    for index, row in enumerate(data.get('budget', [])):
        ids = catalog.assignments(row.get('group_ids', []))
        if ids and row.get('level') == ui_text('Cuenta'):
            raise BudgetError('Fila ' + str(index + 1) + ': los Groups solo se asignan a partidas.')
    return catalog


def dump_groups(catalog):
    return {'version': 1, 'items': [dict(id=item.id, name=item.name, description=item.description, active=item.active)
                                    for item in catalog.items()]}
