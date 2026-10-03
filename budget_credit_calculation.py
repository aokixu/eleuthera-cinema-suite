"""Reducción aditiva tras Fringes: importes locales convertidos una sola vez."""
from decimal import Decimal, localcontext
from budget_values import BudgetError, numeric
from budget_expressions import evaluate


def apply_credits(row, values, before, catalog=None):
    raw = row.get('credit_ids', [])
    if catalog is None:
        if raw: raise BudgetError('Falta el catálogo de Credits de la partida.')
        return Decimal(0), before, ()
    ids = catalog.assignments(raw)
    if not ids: return Decimal(0), before, ()
    complete = all(str(row.get(key,'')).strip() for key in ('quantity','days','unit_price','exchange','fringe'))
    exchange = evaluate(str(row.get('exchange','')).strip() or '0', values)
    total, details = Decimal(0), []
    with localcontext() as context:
        context.prec=28
        for identifier in ids:
            amount, active = catalog.resolved[identifier]
            local = amount if active and complete else Decimal(0)
            converted = local * exchange
            total += converted
            details.append((identifier, local, converted))
        final = numeric(before-total)
    return total, final, tuple(details)
