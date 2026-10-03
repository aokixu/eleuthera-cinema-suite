"""Globals v1/v2: fórmulas persistentes; resultados y grafo reconstruidos."""
from budget_model import Global, Globals, BudgetError, numeric


def load_globals(data):
    if 'budget_globals' not in data:
        return Globals([Global('DIAS_RODAJE', numeric(data.get('budget_settings', {}).get('shooting_days', 1)), 'Días de rodaje')])
    payload = data['budget_globals']
    if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload['version'] not in (1, 2):
        raise BudgetError('Versión de Globals incompatible.')
    items = payload.get('items')
    if not isinstance(items, list) or len(items) > 10000:
        raise BudgetError('Lista de Globals inválida (máximo 10000).')
    parsed = []
    for item in items:
        if not isinstance(item, dict) or 'name' not in item:
            raise BudgetError('Global inválido en el proyecto.')
        kind = item.get('kind', 'constant') if payload['version'] == 2 else 'constant'
        if kind == 'formula' and isinstance(item.get('formula'), str):
            parsed.append(Global(item['name'], None, item.get('description', ''), formula=item['formula']))
        elif kind == 'constant' and 'value' in item:
            parsed.append(Global(item['name'], numeric(item['value']), item.get('description', '')))
        else:
            raise BudgetError('Valor o fórmula inválidos en el proyecto.')
    # Complete collection first, so valid forward references load in any order.
    return Globals(parsed)


def dump_globals(catalog):
    return {'version': 2, 'items': [
        {'name': item.name, 'description': item.description,
         **({'kind': 'formula', 'formula': item.formula} if item.formula is not None
            else {'kind': 'constant', 'value': str(item.value)})}
        for item in catalog.items()]}
