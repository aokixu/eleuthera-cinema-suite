from dataclasses import replace
from decimal import Decimal
import json,copy,unittest
from unittest.mock import patch
from budget_values import BudgetError
from budget_credits import Credit,Credits
from budget_credit_persistence import load_credits,dump_credits
from budget_engine import calculate,recalculation_steps,row_total,affected_rows
from budget_fringes import Fringe,Fringes
from budget_groups import Group,Groups
from budget_group_analysis import analyze

def row(ids=(),**changes):
    return dict(dict(level='Detalle',block='BTL',quantity='1',days='1',unit_price='10000',exchange='1',fringe='0',credit_ids=list(ids)),**changes)

class CreditTests(unittest.TestCase):
    def setUp(self):self.item=Credit('PROVEEDOR','1500');self.cat=Credits([self.item])
    def test_create(self):self.assertEqual(self.cat.get(self.item.id),self.item)
    def test_edit(self):self.assertEqual(self.cat.updated(replace(self.item,amount='2000'),{}).resolved[self.item.id][0],2000)
    def test_rename(self):self.assertEqual(self.cat.updated(replace(self.item,name='OTRO'),{}).get(self.item.id).name,'OTRO')
    def test_remove(self):self.assertFalse(self.cat.removed(self.item.id,{}).items())
    def test_remove_used(self):
        with self.assertRaisesRegex(BudgetError,'fila 1'):self.cat.removed(self.item.id,{},['fila 1'])
    def test_active(self):
        inactive=self.cat.updated(replace(self.item,active=False),{})
        self.assertEqual(calculate([row([self.item.id])],{},credits=inactive).total,10000)
        self.assertEqual(calculate([row([self.item.id])],{},credits=self.cat).total,8500)
    def test_simple(self):self.assertEqual(calculate([row([self.item.id])],{},credits=self.cat).total,8500)
    def test_multiple(self):
        other=Credit('BONO','250.50');cat=Credits([self.item,other])
        result=calculate([row([self.item.id,other.id])],{},credits=cat)
        self.assertEqual(result.total,Decimal('8249.50'));self.assertEqual(len(result.credit_details[0]),2)
    def test_dedup(self):self.assertEqual(calculate([row([self.item.id]*3)],{},credits=self.cat).total,8500)
    def test_unassign(self):
        before=calculate([row([self.item.id])],{},credits=self.cat)
        for after in recalculation_steps([row()],{},before,{0},credits=self.cat):pass
        self.assertEqual(after.total,10000);self.assertFalse(after.credit_dependents)
    def test_source_unchanged(self):
        rows=[row([self.item.id])];original=copy.deepcopy(rows);calculate(rows,{},credits=self.cat)
        self.assertEqual(rows,original)
    def test_global(self):
        item=replace(self.item,amount='P * 2');cat=Credits([item],{'P':Decimal(500)})
        updated=cat.rebind({'P':Decimal(750)},{'P'})
        self.assertEqual(calculate([row([item.id])],{},credits=updated).total,8500)
        self.assertEqual(updated.last_evaluated,(item.id,))
    def test_atomic_rebind(self):
        item=replace(self.item,amount='1/P');cat=Credits([item],{'P':Decimal(2)})
        with self.assertRaises(BudgetError):cat.rebind({'P':Decimal(0)},{'P'})
        self.assertEqual(cat.resolved[item.id][0],Decimal('.5'))
    def test_currency(self):
        result=calculate([row([self.item.id],exchange='6.96')],{},credits=self.cat)
        self.assertEqual(result.before_credits[0],69600);self.assertEqual(result.credit_totals[0],10440);self.assertEqual(result.total,59160)
    def test_fringes_first(self):
        fringe=Fringe('SEGURO','10');fr=Fringes([fringe])
        result=calculate([row([self.item.id],fringe_ids=[fringe.id])],{},fr,self.cat)
        self.assertEqual(result.before_credits[0],11000);self.assertEqual(result.total,9500)
    def test_groups_final(self):
        group=Group('A');rows=[row([self.item.id],group_ids=[group.id])]
        result=calculate(rows,{},credits=self.cat)
        self.assertEqual(analyze(rows,result.totals,Groups([group])).totals[group.id],8500)
    def test_persistence(self):
        cat=Credits([replace(self.item,amount='P + 1',active=False)],{'P':Decimal(10)})
        data=json.loads(json.dumps({'budget_credits':dump_credits(cat),'budget':[row([self.item.id])]}))
        self.assertEqual(load_credits(data,{'P':Decimal(10)}).items(),cat.items())
    def test_old(self):self.assertFalse(load_credits({'budget':[row()]},{}).items())
    def test_bad_references(self):
        for data in ({'budget':[row(['missing'])]}, {'budget_credits':None},
                     {'budget_credits':dump_credits(self.cat),'budget':[row([self.item.id],level='Cuenta')]}):
            with self.assertRaises(BudgetError):load_credits(data,{})
    def test_invalid_amount(self):
        for source in ('','-1','1/0','NO_EXISTE','NaN','inf','print(1)','1**2','10%'):
            with self.subTest(source=source),self.assertRaises(BudgetError):Credits([replace(self.item,amount=source)])
    def test_duplicates(self):
        with self.assertRaises(BudgetError):Credits([self.item,Credit('proveedor','1')])
        with self.assertRaises(BudgetError):Credits([self.item,self.item])
    def test_selective(self):
        rows=[row([self.item.id] if i<20 else []) for i in range(1020)]
        before=calculate(rows,{},credits=self.cat);cat=self.cat.updated(replace(self.item,amount='2000'),{})
        with patch('budget_engine.row_total',wraps=row_total) as spy:
            for after in recalculation_steps(rows,{},before,before.credit_dependents[self.item.id],credits=cat):pass
            self.assertEqual(spy.call_count,20)
        self.assertEqual(after.totals[20:],before.totals[20:]);self.assertEqual(after.total,calculate(rows,{},credits=cat).total)
    def test_reference_switch(self):
        item=replace(self.item,amount='P');cat=Credits([item],{'P':Decimal(10),'Q':Decimal(10)})
        rows=[row([item.id])];before=calculate(rows,{},credits=cat)
        cat=cat.updated(replace(item,amount='Q'),{'P':Decimal(10),'Q':Decimal(10)})
        for after in recalculation_steps(rows,{},before,{0},credits=cat):pass
        self.assertFalse(affected_rows(after,{'P'}));self.assertEqual(affected_rows(after,{'Q'}),{0})
    def test_excess_not_clipped(self):self.assertEqual(calculate([row([self.item.id],unit_price='1000')],{},credits=self.cat).total,-500)
    def test_incomplete(self):self.assertEqual(calculate([row([self.item.id],unit_price='',exchange=' ')],{},credits=self.cat).total,0)

if __name__=='__main__':unittest.main(verbosity=2)
