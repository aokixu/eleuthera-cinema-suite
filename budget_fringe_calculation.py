"""Base local -> cargas aditivas con topes locales -> conversión única."""
from decimal import Decimal, localcontext
from budget_values import numeric
from budget_expressions import evaluate


def row_cost(row, values, fringes=None):
    fields = ('quantity', 'days', 'unit_price', 'exchange', 'fringe')
    raw = [str(row.get(key, '')).strip() for key in fields]
    quantity, days, price, exchange, legacy = [evaluate(value or '0', values) for value in raw]
    ids = fringes.assignments(row.get('fringe_ids', [])) if fringes is not None else ()
    if row.get('fringe_ids') and fringes is None:
        from budget_values import BudgetError
        raise BudgetError('Falta el catálogo de Fringes de la partida.')
    with localcontext() as context:
        context.prec = 28
        base = quantity * days * price if all(raw) else Decimal(0)
        charge = base * legacy / 100
        for identifier in ids:
            percentage, cap, active = fringes.resolved[identifier]
            if active:
                taxable = base if cap is None else min(base, cap)
                charge += taxable * percentage / 100
        # Preserve the legacy multiplication order for rows without assignments.
        total = numeric((base + charge) * exchange) if ids else numeric(base * exchange * (1 + legacy / 100))
        return base * exchange, charge * exchange, total
