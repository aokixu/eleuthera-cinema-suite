"""Etapa 2: grafo, transacciones, persistencia y cálculo selectivo puro."""
import copy
from decimal import Decimal
import unittest
from unittest.mock import patch
from budget_model import Global, Globals, BudgetError
from budget_engine import calculate, recalculation_steps, affected_rows, row_total
from budget_expressions import evaluate
from budget_persistence import load_globals, dump_globals


def row(**changes):
    return dict(level='Detalle', block='BTL', quantity='1', days='1', unit_price='1', exchange='1', fringe='0', **changes)


class FormulaTests(unittest.TestCase):
    def test_constant_and_calculated(self):
        model = Globals([Global('A', 10), Global('B', 'A * 2')])
        self.assertIsNone(model.get('A').formula)
        self.assertEqual(model.get('B').formula, 'A * 2')
        self.assertEqual(model.get('B').value, 20)

    def test_chain_ten_and_multiple(self):
        items = [Global('A0', 1)] + [Global('A' + str(i), 'A' + str(i-1) + ' + 1') for i in range(1, 11)]
        items += [Global('TOTAL', 'A10 + A0'), Global('INDEPENDIENTE', 7), Global('OTRO', 'INDEPENDIENTE * 2')]
        model = Globals(reversed(items))
        self.assertEqual(model.get('TOTAL').value, 12)
        model.edit('A0', 'A0', 5)
        self.assertEqual(model.get('TOTAL').value, 20)
        self.assertEqual(len(model.last_recalculated), 11)
        self.assertNotIn('OTRO', model.last_recalculated)
        self.assertIn('TOTAL', model.graph.dependents['A0'])
        self.assertIn('A1', model.graph.dependents['A0'])

    def test_graph_cycle_direct(self):
        with self.assertRaisesRegex(BudgetError, 'circular'): Globals([Global('A', 'A + 1')])

    def test_graph_cycle_indirect(self):
        for items in ([Global('A', 'B + 1'), Global('B', 'A + 1')],
                      [Global('A', 'B'), Global('B', 'C'), Global('C', 'A')]):
            with self.assertRaisesRegex(BudgetError, 'circular'): Globals(items)

    def test_failed_edits_atomic(self):
        model = Globals([Global('A', 2), Global('B', '10 / A'), Global('C', 'B + 1')])
        original = dump_globals(model)
        values = model.values()
        graph = model.graph
        for value in ('C', 'A + 1', '0', 'DESCONOCIDO', '1/0', '5 +', 'True', '1e999', ''):
            with self.assertRaises(BudgetError, msg=value): model.edit('A', 'A', value)
            self.assertEqual(dump_globals(model), original)
            self.assertEqual(model.values(), values)
            self.assertIs(model.graph, graph)

    def test_missing_and_invalid(self):
        for expression in ('NO_EXISTE + 1', '__import__("os")', 'A.real', 'A[0]', '2 ** 3', '1 // 2', '1 % 2', '"hello"', 'nan', 'inf', '1,2 + 3'):
            with self.assertRaises(BudgetError, msg=expression): Globals([Global('A', 1), Global('B', expression)])

    def test_decimal_and_unary(self):
        model = Globals([Global('BASE', '0,1'), Global('SUMA', 'BASE + 0.2'), Global('OTRO', '-(SUMA / 2)')])
        self.assertEqual(model.get('SUMA').value, Decimal('0.3'))
        self.assertEqual(model.get('OTRO').value, Decimal('-0.15'))

    def test_rename_delete_global_used_by_global(self):
        model = Globals([Global('A', 1), Global('B', 'A + 1')])
        with self.assertRaises(BudgetError): model.remove('A')
        with self.assertRaises(BudgetError): model.edit('A', 'OTRO', 1)
        model.remove('B'); model.edit('A', 'OTRO', 1)
        self.assertEqual(model.get('OTRO').value, 1)

    def test_description_no_evaluation(self):
        model = Globals([Global('A', 1), Global('B', 'A * 2')])
        model.edit('B', 'B', 'A * 2', 'Nueva descripción')
        self.assertEqual(model.last_recalculated, ())
        self.assertFalse(model.last_changed)

    def test_change_dependency_same_result(self):
        model = Globals([Global('A', 2), Global('B', 2), Global('C', 'A * 2')])
        model.edit('C', 'C', 'B * 2')
        self.assertFalse(model.last_changed)
        model.edit('A', 'A', 10)
        self.assertNotIn('C', model.last_recalculated)
        model.edit('B', 'B', 3)
        self.assertEqual(model.get('C').value, 6)

    def test_persistence_formula_rebuild(self):
        model = Globals([Global('A', '6.96'), Global('B', 'A * 2', 'Calculado')])
        data = {'budget_globals': dump_globals(model)}
        data['budget_globals']['items'].reverse()
        for item in data['budget_globals']['items']:
            if item.get('kind') == 'formula': item['value'] = '9999'  # stale cache is not authoritative
        restored = load_globals(data)
        self.assertEqual(restored.values(), model.values())
        self.assertEqual(restored.get('B').description, 'Calculado')
        self.assertEqual(restored.graph.dependencies['B'], {'A'})

    def test_legacy_and_stage_one(self):
        self.assertEqual(load_globals({'budget_settings': {'shooting_days': 12}}).get('DIAS_RODAJE').value, 12)
        old = {'budget_globals': {'version': 1, 'items': [{'name': 'A', 'value': '6.96'}]}}
        self.assertEqual(load_globals(old).get('A').value, Decimal('6.96'))
        self.assertEqual(evaluate('@DIAS_RODAJE', {'DIAS_RODAJE': Decimal(12)}), 12)

    def test_fields_and_multiple_globals(self):
        values = {'NUM_EXTRAS': Decimal(20), 'DIAS_RODAJE': Decimal(15), 'TARIFA_EXTRA': Decimal(150)}
        data = row(); data.update(quantity='NUM_EXTRAS', days='DIAS_RODAJE + 2', unit_price='TARIFA_EXTRA * 1.15')
        result = calculate([data], values)
        self.assertEqual(result.total, Decimal('58650'))
        self.assertEqual(set(result.dependents), set(values))

    def test_selective_rows_and_accounts(self):
        model = Globals([Global('A', 2), Global('B', 'A * 2'), Global('OTRO', 7)])
        rows = [row(), row(), row(), row(), row()]
        rows[0]['level'] = 'Cuenta'; rows[1].update(quantity='B', block='ATL')
        rows[2].update(quantity='OTRO'); rows[3]['level'] = 'Cuenta'; rows[4].update(quantity='A + B')
        previous = calculate(rows, model.values())
        model.edit('A', 'A', 3)
        affected = affected_rows(previous, model.last_changed)
        self.assertEqual(affected, {1, 4})
        with patch('budget_engine.row_total', wraps=row_total) as evaluate_row:
            for result in recalculation_steps(rows, model.values(), previous, affected): pass
            self.assertEqual(evaluate_row.call_count, 2)
        full = calculate(rows, model.values())
        self.assertEqual(result.totals, full.totals)
        self.assertEqual((result.total, result.atl, result.btl), (full.total, full.atl, full.btl))
        self.assertEqual(result.changed_rows, (0, 1, 3, 4))

    def test_invalid_row_recovers_selectively(self):
        data = row(); data['unit_price'] = '10 / A'
        previous = calculate([data], {'A': Decimal(0)})
        self.assertIn(0, previous.errors)
        for result in recalculation_steps([data], {'A': Decimal(2)}, previous, {0}): pass
        self.assertFalse(result.errors)
        self.assertEqual(result.total, 5)


if __name__ == '__main__': unittest.main(verbosity=2)
