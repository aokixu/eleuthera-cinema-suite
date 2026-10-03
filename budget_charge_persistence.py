"""Charges v1: fuentes y asignaciones; sin cachés derivadas persistentes."""
from ui_i18n import ui_text, ui_join
from budget_charges import Charge, Charges
from budget_values import BudgetError


def load_charges(data, values):
    payload = data.get('budget_charges', {'version':1,'items':[]})
    if not isinstance(payload,dict) or type(payload.get('version')) is not int or payload['version'] != 1:
        raise BudgetError('Versión de Charges incompatible.')
    raw = payload.get('items')
    if not isinstance(raw,list) or len(raw)>10000: raise BudgetError('Catálogo de Charges inválido.')
    items=[]
    for item in raw:
        if not isinstance(item,dict) or not all(key in item for key in ('id','name','amount','active')) or not item['id']:
            raise BudgetError('Charge inválido en el proyecto.')
        items.append(Charge(item['name'],item['amount'],item.get('description',''),item['active'],item['id']))
    catalog=Charges(items,values)
    for index,row in enumerate(data.get('budget',[])):
        ids=catalog.assignments(row.get('charge_ids',[]))
        if ids and row.get('level')==ui_text('Cuenta'):
            raise BudgetError(f'Fila {index+1}: los Charges solo se asignan a partidas.')
    return catalog


def dump_charges(catalog):
    return {'version':1,'items':[dict(id=item.id,name=item.name,amount=item.amount,description=item.description,active=item.active)
                                 for item in catalog.items()]}
