"""Cálculo puro de partidas, índices de referencias y actualización por deltas."""
from ui_i18n import ui_text, ui_join
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
import re
from budget_values import BudgetError, numeric
from budget_expressions import evaluate, parse_expression

FIELDS = ('quantity', 'days', 'unit_price', 'exchange', 'fringe')


def row_dependencies(row, fringes=None, credits=None, contractuals=None):
    references = set()
    for key in FIELDS:
        try:
            references.update(parse_expression(str(row.get(key, ''))).dependencies)
        except BudgetError:
            # Protect identifiers in an expression that is still being edited.
            references.update(x.upper() for x in re.findall(r'\b[A-Za-z][A-Za-z0-9_]*\b', str(row.get(key, ''))))
    if fringes is not None:
        for identifier in fringes.assignments(row.get('fringe_ids', [])):
            references.update(fringes.get(identifier).references)
    if credits is not None:
        for identifier in credits.assignments(row.get('credit_ids', [])):
            references.update(credits.get(identifier).references)
    if contractuals is not None:
        for identifier in contractuals.assignments(row.get('charge_ids', [])):
            references.update(contractuals.get(identifier).references)
    return frozenset(references)


def row_total(row, values, fringes=None, details=False, credits=None, credit_details=False, contractuals=None, contractual_details=False):
    try:
        from budget_fringe_calculation import row_cost
        base, charge, subtotal = row_cost(row, values, fringes)
        from budget_charge_calculation import apply_charges
        before_contract = subtotal
        increment, subtotal, contracts = apply_charges(row, values, subtotal, contractuals)
        from budget_credit_calculation import apply_credits
        before = subtotal
        reduction, subtotal, items = apply_credits(row, values, before, credits)
        payload = (subtotal, '', base, charge, before, reduction, items, before_contract, increment, contracts)
        return payload if contractual_details else payload[:7] if credit_details else payload[:4] if details else payload[:2]
    except (BudgetError, DecimalException) as error:
        payload = (Decimal(0), str(error), Decimal(0), Decimal(0), Decimal(0), Decimal(0), (), Decimal(0), Decimal(0), ())
        return payload if contractual_details else payload[:7] if credit_details else payload[:4] if details else payload[:2]


@dataclass(frozen=True)
class Calculation:
    totals: tuple
    total: Decimal
    atl: Decimal
    btl: Decimal
    errors: dict
    dependents: dict
    owners: tuple = ()
    changed_rows: tuple | None = None
    evaluated_rows: int = 0
    fringe_dependents: dict | None = None
    bases: tuple = ()
    fringe_totals: tuple = ()
    credit_dependents: dict | None = None
    before_credits: tuple = ()
    credit_totals: tuple = ()
    credit_details: tuple = ()
    charge_dependents: dict | None = None
    before_charges: tuple = ()
    charge_totals: tuple = ()
    charge_details: tuple = ()


def calculation_steps(rows, values, fringes=None, credits=None, contractuals=None):
    """Recálculo completo para carga o cambios estructurales, lineal en filas."""
    totals, errors, dependents, owners = [], {}, {}, []
    bases, charges, fringe_dependents = [], [], {}
    before_values, reductions, detail_values, credit_dependents = [], [], [], {}
    contract_before, contract_totals, contract_details, contract_dependents = [], [], [], {}
    total = atl = btl = Decimal(0)
    account = None
    account_total = Decimal(0)
    evaluated = 0
    for index, row in enumerate(rows):
        for identifier in row.get('fringe_ids', []):
            fringe_dependents.setdefault(identifier, set()).add(index)
        for identifier in row.get('credit_ids', []):
            credit_dependents.setdefault(identifier, set()).add(index)
        for identifier in row.get('charge_ids', []):
            contract_dependents.setdefault(identifier, set()).add(index)
        for name in row_dependencies(row, fringes, credits, contractuals):
            dependents.setdefault(name, set()).add(index)
        if row.get('level') == ui_text('Cuenta'):
            if account is not None: totals[account] = account_total
            account, account_total = index, Decimal(0)
            totals.append(Decimal(0)); owners.append(None)
            bases.append(Decimal(0)); charges.append(Decimal(0))
            before_values.append(Decimal(0)); reductions.append(Decimal(0)); detail_values.append(())
            contract_before.append(Decimal(0)); contract_totals.append(Decimal(0)); contract_details.append(())
            yield None
            continue
        subtotal, error, base, charge, before, reduction, items, gross, increment, contracts = row_total(row, values, fringes, credits=credits, contractuals=contractuals, contractual_details=True)
        if error: errors[index] = error
        totals.append(subtotal); owners.append(account)
        bases.append(base); charges.append(charge)
        before_values.append(before); reductions.append(reduction); detail_values.append(items)
        contract_before.append(gross); contract_totals.append(increment); contract_details.append(contracts)
        total += subtotal; account_total += subtotal
        if row.get('block', '').upper() == 'ATL': atl += subtotal
        else: btl += subtotal
        evaluated += 1
        yield None
    if account is not None: totals[account] = account_total
    yield Calculation(tuple(totals), total, atl, btl, errors,
                      {key: frozenset(indices) for key, indices in dependents.items()},
                      tuple(owners), None, evaluated,
                      {key: frozenset(indices) for key, indices in fringe_dependents.items()}, tuple(bases), tuple(charges),
                      {key: frozenset(indices) for key, indices in credit_dependents.items()}, tuple(before_values), tuple(reductions), tuple(detail_values),
                      {key: frozenset(indices) for key, indices in contract_dependents.items()}, tuple(contract_before), tuple(contract_totals), tuple(contract_details))


def affected_rows(previous, changed_globals):
    affected = set()
    for name in changed_globals:
        affected.update(previous.dependents.get(name, ()))
    return frozenset(affected)


def recalculation_steps(rows, values, previous, affected, fringes=None, credits=None, contractuals=None):
    """No recaptura widgets ni evalúa filas ajenas; actualiza cuentas por delta."""
    totals = list(previous.totals)
    errors = dict(previous.errors)
    bases, charges = list(previous.bases), list(previous.fringe_totals)
    before_values, reductions, detail_values = list(previous.before_credits), list(previous.credit_totals), list(previous.credit_details)
    contract_before, contract_totals, contract_details = list(previous.before_charges), list(previous.charge_totals), list(previous.charge_details)
    total, atl, btl = previous.total, previous.atl, previous.btl
    # Rebuild only changed rows in the two inverted indices. Sources may have
    # changed (assignment or Fringe formula edit) without a different value.
    dependents = {key: set(indices) - affected for key, indices in previous.dependents.items()}
    fringe_dependents = {key: set(indices) - affected for key, indices in (previous.fringe_dependents or {}).items()}
    credit_dependents = {key: set(indices) - affected for key, indices in (previous.credit_dependents or {}).items()}
    contract_dependents = {key: set(indices) - affected for key, indices in (previous.charge_dependents or {}).items()}
    for index in affected:
        for identifier in rows[index].get('charge_ids', []): contract_dependents.setdefault(identifier, set()).add(index)
        for identifier in rows[index].get('credit_ids', []): credit_dependents.setdefault(identifier, set()).add(index)
        for name in row_dependencies(rows[index], fringes, credits, contractuals): dependents.setdefault(name, set()).add(index)
        for identifier in rows[index].get('fringe_ids', []): fringe_dependents.setdefault(identifier, set()).add(index)
        yield None
    dependents = {key: frozenset(indices) for key, indices in dependents.items() if indices}
    fringe_dependents = {key: frozenset(indices) for key, indices in fringe_dependents.items() if indices}
    credit_dependents = {key: frozenset(indices) for key, indices in credit_dependents.items() if indices}
    contract_dependents = {key: frozenset(indices) for key, indices in contract_dependents.items() if indices}
    changed, evaluated = set(), 0
    for index in sorted(affected):
        row = rows[index]
        if row.get('level') == ui_text('Cuenta'):
            yield None
            continue
        subtotal, error, base, charge, before, reduction, items, gross, increment, contracts = row_total(row, values, fringes, credits=credits, contractuals=contractuals, contractual_details=True)
        bases[index], charges[index] = base, charge
        before_values[index], reductions[index], detail_values[index] = before, reduction, items
        contract_before[index], contract_totals[index], contract_details[index] = gross, increment, contracts
        delta = subtotal - totals[index]
        totals[index] = subtotal
        if error: errors[index] = error
        else: errors.pop(index, None)
        total += delta
        if row.get('block', '').upper() == 'ATL': atl += delta
        else: btl += delta
        changed.add(index)
        owner = previous.owners[index]
        if owner is not None:
            totals[owner] += delta
            changed.add(owner)
        evaluated += 1
        yield None
    yield Calculation(tuple(totals), total, atl, btl, errors, dependents,
                      previous.owners, tuple(sorted(changed)), evaluated, fringe_dependents, tuple(bases), tuple(charges),
                      credit_dependents, tuple(before_values), tuple(reductions), tuple(detail_values),
                      contract_dependents, tuple(contract_before), tuple(contract_totals), tuple(contract_details))


def calculate(rows, values, fringes=None, credits=None, contractuals=None):
    result = None
    for result in calculation_steps(rows, values, fringes, credits, contractuals): pass
    return result
