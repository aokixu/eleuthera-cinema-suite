import copy
from decimal import Decimal
import unittest
from budget_model import Global, Globals, BudgetError
from budget_engine import evaluate, parse_expression, calculate
from budget_persistence import load_globals, dump_globals


class GlobalsTests(unittest.TestCase):
    def test_crud(self):
        model = Globals()
        model.add('dias_rodaje', '12', 'Rodaje')
        model.edit('DIAS_RODAJE', 'DIAS', '12.25', 'Días efectivos')
        self.assertEqual(model.get('dias').value, Decimal('12.25'))
        model.remove('DIAS')
        self.assertFalse(model.items())

    def test_invalid(self):
        for name in ('', '1VAR', 'A.B', 'A B', '__X', 'A[0]', 'ÁREA', 'a'*65):
            with self.assertRaises(BudgetError): Global(name, 1)
        for value in (True, None, [], float('inf'), 'NaN', '1e99999', '0.0000000000000000001', '1,2.3', '12 días'):
            with self.assertRaises(BudgetError): Global('A', value)

    def test_duplicates_and_atomicity(self):
        model = Globals([Global('A', 1), Global('B', 2)])
        original = dump_globals(model)
        for operation in (lambda: model.add('a', 3), lambda: model.edit('A', 'B', 4), lambda: model.edit('A', 'C', 'bad')):
            with self.assertRaises(BudgetError): operation()
            self.assertEqual(original, dump_globals(model))

    def test_decimal(self):
        model = Globals([Global('USD_BOB', '6,96')])
        self.assertEqual(evaluate('USD_BOB * 3', model.values()), Decimal('20.88'))
        self.assertEqual(evaluate('0.1 + 0.2', {}), Decimal('0.3'))

    def test_formulas(self):
        values = {'DIAS_RODAJE': Decimal(12), 'NUM_EXTRAS': Decimal(20)}
        self.assertEqual(evaluate('3 * DIAS_RODAJE * 500', values), 18000)
        self.assertEqual(evaluate('NUM_EXTRAS * DIAS_RODAJE * 150', values), 36000)
        self.assertEqual(evaluate('@DIAS_RODAJE', values), 12)
        self.assertEqual(evaluate('-(2 + 3) / 2', {}), Decimal('-2.5'))

    def test_safe(self):
        for expression in ('__import__("os")', 'A.real', 'A[0]', '[x for x in X]', 'lambda: 1', '2**10000', 'True', '1/0', '(1,2)', '"test"', 'open("x")', 'A if B else C', 'A;B', '1+'*200+'1'):
            with self.assertRaises(BudgetError, msg=expression): evaluate(expression, {'A': 1})
        with self.assertRaises(BudgetError): evaluate('INEXISTENTE * 3', {})

    def test_dependencies(self):
        rows = [{'quantity': 'NUM_EXTRAS', 'days': 'DIAS_RODAJE', 'unit_price': '150', 'exchange': '1', 'fringe': '0'}]
        values = {'NUM_EXTRAS': Decimal(20), 'DIAS_RODAJE': Decimal(12)}
        first = calculate(rows, values)
        self.assertEqual(first.dependents['DIAS_RODAJE'], {0})
        values['DIAS_RODAJE'] = Decimal(10)
        self.assertEqual(calculate(rows, values).total, 30000)
        model = Globals([Global(k, v) for k, v in values.items()])
        with self.assertRaises(BudgetError): model.remove('DIAS_RODAJE', first.dependents)
        with self.assertRaises(BudgetError): model.edit('DIAS_RODAJE', 'OTRO', 10, references=first.dependents)

    def test_persistence_legacy(self):
        data = {'blocks': [], 'budget_settings': {'shooting_days': 12}}
        before = copy.deepcopy(data)
        model = load_globals(data)
        self.assertEqual(data, before)
        self.assertEqual(model.get('DIAS_RODAJE').value, 12)
        model.add('USD_BOB', '6.960000000000000001', 'Cambio')
        self.assertEqual(dump_globals(load_globals({'budget_globals': dump_globals(model)})), dump_globals(model))
        self.assertEqual(load_globals({'budget_globals': {'version': 1, 'items': []}}).items(), ())

    def test_invalid_payload(self):
        for payload in (None, {'version': 2}, {'version': True, 'items': []}, {'version': 1, 'items': [{}]}, {'version': 1, 'items': [{'name': 'A', 'value': 1}, {'name': 'a', 'value': 2}]}):
            with self.assertRaises(BudgetError): load_globals({'budget_globals': payload})

    def test_accounts_and_errors(self):
        rows = [{'level': 'Cuenta'}, {'quantity': '2', 'days': '3', 'unit_price': '100', 'exchange': '1', 'fringe': '10', 'block': 'ATL'}, {'level': 'Cuenta'}, {'quantity': 'NO_EXISTE', 'days': '1', 'unit_price': '1', 'exchange': '1', 'fringe': '0'}]
        result = calculate(rows, {})
        self.assertEqual(result.totals[:2], (Decimal(660), Decimal(660)))
        self.assertIn(3, result.errors)
        self.assertEqual(result.atl, 660)


if __name__ == '__main__': unittest.main(verbosity=2)
