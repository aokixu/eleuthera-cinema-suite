"""Reglas económicas, referencias, persistencia y cálculo selectivo de Fringes."""
from dataclasses import replace
from decimal import Decimal
import json
import unittest
from budget_values import BudgetError
from budget_fringes import Fringe, Fringes
from budget_fringe_calculation import row_cost
from budget_fringe_persistence import load_fringes, dump_fringes
from budget_engine import calculate, recalculation_steps, affected_rows


def row(**changes):
    return dict(dict(level='Detalle', block='BTL', quantity='1', days='1', unit_price='1000',
                     exchange='1', fringe='0', fringe_ids=[]), **changes)


class FringeTests(unittest.TestCase):
    def cost(self, percentage='10', cap=None, **changes):
        item = Fringe('CARGA', percentage, cap)
        return row_cost(row(fringe_ids=[item.id], **changes), {}, Fringes([item]))

    def test_legacy_small_component(self):
        base, charge, total = row_cost(row(unit_price='1e-18', fringe='1'), {})
        self.assertEqual(charge, Decimal('1e-20'))
        self.assertEqual(total, Decimal('1.01e-18'))

    def test_legacy_large_local_base(self):
        base, charge, total = row_cost(row(quantity='1e9', days='1e9', unit_price='1e9', exchange='1e-9'), {})
        self.assertEqual(total, Decimal('1e18'))

    def test_simple(self): self.assertEqual(self.cost(), (1000, 100, 1100))
    def test_decimal(self): self.assertEqual(self.cost('12,5'), (1000, 125, 1125))
    def test_no_cap(self): self.assertEqual(self.cost(cap=None, unit_price='10000')[1], 1000)
    def test_cap(self): self.assertEqual(self.cost(cap='5000', unit_price='10000')[1], 500)
    def test_zero_cap(self): self.assertEqual(self.cost(cap='0')[1], 0)

    def test_multiple_additive(self):
        a, b = Fringe('A', '10'), Fringe('B', '5')
        self.assertEqual(row_cost(row(fringe_ids=[a.id, b.id]), {}, Fringes([a,b])), (1000,150,1150))

    def test_duplicate_assignment(self):
        item = Fringe('A', '10'); cat = Fringes([item])
        self.assertEqual(cat.assignments([item.id]*3), (item.id,))
        self.assertEqual(row_cost(row(fringe_ids=[item.id]*3), {}, cat)[2], 1100)

    def test_names_and_ids(self):
        item = Fringe('A', '10')
        for other in (Fringe('a', '20'), replace(item, name='B')):
            with self.assertRaises(BudgetError): Fringes([item, other])

    def test_rename_stable(self):
        item = Fringe('A', '10'); cat = Fringes([item])
        cat = cat.updated(replace(item, name='B'), {})
        self.assertEqual(cat.get(item.id).name, 'B')
        self.assertEqual(row_cost(row(fringe_ids=[item.id]), {}, cat)[2], 1100)

    def test_remove_in_use(self):
        item = Fringe('A', '10'); cat = Fringes([item])
        with self.assertRaisesRegex(BudgetError, 'fila 4'): cat.removed(item.id, {}, ['fila 4'])
        self.assertEqual(len(cat.items()), 1)
        self.assertEqual(cat.removed(item.id, {}).items(), ())

    def test_active(self):
        item = Fringe('A', '10', active=False); cat = Fringes([item])
        self.assertEqual(row_cost(row(fringe_ids=[item.id]), {}, cat)[2], 1000)
        cat = cat.updated(replace(item, active=True), {})
        self.assertEqual(row_cost(row(fringe_ids=[item.id]), {}, cat)[2], 1100)

    def test_globals_and_rebind(self):
        a = Fringe('A', 'P * 2', 'TOPE'); b = Fringe('B', '7')
        cat = Fringes([a,b], {'P':Decimal(5), 'TOPE':Decimal(500)})
        new = cat.rebind({'P':Decimal(10), 'TOPE':Decimal(500)}, {'P'})
        self.assertEqual(new.last_evaluated, (a.id,))
        self.assertEqual(new.changed, {a.id})
        self.assertEqual(row_cost(row(fringe_ids=[a.id]), {}, new)[1], 100)
        self.assertEqual(cat.resolved[a.id][0], 10)

    def test_atomic_error(self):
        item = Fringe('A', '1 / P'); cat = Fringes([item], {'P':Decimal(2)})
        with self.assertRaises(BudgetError): cat.rebind({'P':Decimal(0)}, {'P'})
        self.assertEqual(cat.resolved[item.id][0], Decimal('.5'))

    def test_invalid(self):
        for value in ('', '-1', 'NO_EXISTE', '1/0', 'open(1)', '1**2', 'NaN', 'inf', '1e99'):
            with self.subTest(value=value), self.assertRaises(BudgetError): Fringes([Fringe('A', value)])
        for cap in ('', '-1', 'NO_EXISTE', '1/0', 'NaN'):
            with self.subTest(cap=cap), self.assertRaises(BudgetError): Fringes([Fringe('A', '10', cap)])

    def test_missing_assignment(self):
        with self.assertRaises(BudgetError): Fringes().assignments(['missing'])
        self.assertTrue(calculate([row(fringe_ids=['missing'])], {}).errors)

    def test_no_fringe(self): self.assertEqual(row_cost(row(), {}), (1000, 0, 1000))
    def test_legacy(self): self.assertEqual(row_cost(row(fringe='12.5'), {}), (1000, 125, 1125))
    def test_legacy_additive(self): self.assertEqual(self.cost(fringe='5')[2], 1150)

    def test_currency_cap_order(self):
        # Local base 10000, capped charge 500, converted once at 6.96.
        self.assertEqual(self.cost(cap='5000', unit_price='10000', exchange='6.96'), (69600,3480,73080))

    def test_persistence(self):
        item = Fringe('A', 'P', 'TOPE', 'Seguro', False)
        values = {'P':Decimal('12.5'), 'TOPE':Decimal(500)}
        cat = Fringes([item], values)
        data = json.loads(json.dumps({'budget_fringes':dump_fringes(cat), 'budget':[row(fringe_ids=[item.id])]}))
        restored = load_fringes(data, values)
        self.assertEqual(restored.items(), cat.items())
        self.assertEqual(restored.resolved, cat.resolved)
        self.assertEqual(data['budget'][0]['fringe_ids'], [item.id])

    def test_old_project(self): self.assertEqual(load_fringes({'budget':[row(fringe='10')]}, {}).items(), ())

    def test_corrupt_project(self):
        item = Fringe('A', '10'); payload = dump_fringes(Fringes([item]))
        for assignments in (['missing'], 'not-a-list', [None]):
            with self.assertRaises(BudgetError): load_fringes({'budget_fringes':payload, 'budget':[row(fringe_ids=assignments)]}, {})
        with self.assertRaises(BudgetError): load_fringes({'budget_fringes':payload, 'budget':[row(level='Cuenta', fringe_ids=[item.id])]}, {})

    def test_selective_twenty_and_new_reference(self):
        item = Fringe('A', 'P'); cat = Fringes([item], {'P':Decimal(10), 'Q':Decimal(10)})
        rows = [row(fringe_ids=[item.id] if i < 20 else []) for i in range(1020)]
        result = calculate(rows, {'P':Decimal(10)}, cat)
        self.assertEqual(affected_rows(result, {'P'}), set(range(20)))
        new = cat.updated(replace(item, percentage='Q'), {'P':Decimal(10), 'Q':Decimal(10)})
        for updated in recalculation_steps(rows, {}, result, frozenset(range(20)), new): pass
        self.assertEqual(updated.evaluated_rows, 20)
        self.assertFalse(affected_rows(updated, {'P'}))
        self.assertEqual(affected_rows(updated, {'Q'}), set(range(20)))
        self.assertEqual(updated.totals[20:], result.totals[20:])


if __name__ == '__main__': unittest.main(verbosity=2)
