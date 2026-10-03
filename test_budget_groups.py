from dataclasses import replace
from decimal import Decimal
import json
import unittest
from unittest.mock import patch
from budget_groups import Group, Groups
from budget_group_persistence import load_groups,dump_groups
from budget_group_analysis import analyze
from budget_values import BudgetError
from budget_engine import calculate
from budget_fringes import Fringe,Fringes


def row(ids=(),**changes):
    return dict(dict(level='Detalle',block='BTL',quantity='1',days='1',unit_price='100',exchange='1',fringe='0',group_ids=list(ids)),**changes)


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.a,self.b=Group('UNIDAD_A'),Group('UNIDAD_B')
        self.cat=Groups([self.a,self.b])

    def test_create(self):self.assertEqual(self.cat.get(self.a.id),self.a)
    def test_edit(self):self.assertEqual(self.cat.updated(replace(self.a,description='Equipo')).get(self.a.id).description,'Equipo')
    def test_rename(self):self.assertEqual(self.cat.updated(replace(self.a,name='OTRO')).assignments([self.a.id]),(self.a.id,))
    def test_active(self):self.assertFalse(self.cat.updated(replace(self.a,active=False)).get(self.a.id).active)
    def test_remove(self):self.assertEqual(self.cat.removed(self.a.id).items(),(self.b,))
    def test_used(self):
        with self.assertRaisesRegex(BudgetError,'fila 2'):self.cat.removed(self.a.id,['fila 2'])
    def test_duplicates(self):
        with self.assertRaises(BudgetError):self.cat.updated(Group('unidad_a'))
        with self.assertRaises(BudgetError):Groups([self.a,self.a])
    def test_invalid(self):
        for name in ('','1A','A B'):
            with self.assertRaises(BudgetError):Group(name)
        with self.assertRaises(BudgetError):Group('A',active='false')
    def test_assignment(self):self.assertEqual(self.cat.assignments([self.a.id]),(self.a.id,))
    def test_multiple_dedup(self):self.assertEqual(self.cat.assignments([self.a.id,self.b.id,self.a.id]),(self.a.id,self.b.id))
    def test_missing(self):
        for ids in (['missing'],[None],'A'):
            with self.assertRaises(BudgetError):self.cat.assignments(ids)
    def test_total_overlap(self):
        summary=analyze([row([self.a.id,self.b.id]),row([self.b.id])],(Decimal(100),Decimal(50)),self.cat)
        self.assertEqual(summary.totals,{self.a.id:100,self.b.id:150})
        self.assertEqual(len(summary.members[self.b.id]),2)
    def test_no_evaluator(self):
        with patch('budget_engine.calculate',side_effect=AssertionError('Second engine')):
            self.assertEqual(analyze([row([self.a.id])],(Decimal('123.45'),),self.cat).totals[self.a.id],Decimal('123.45'))
    def test_selective(self):
        rows=[row([self.a.id]),row([self.b.id])]
        before=analyze(rows,(Decimal(10),Decimal(20)),self.cat)
        after=analyze(rows,(Decimal(15),Decimal(20)),self.cat,before,[0])
        self.assertEqual(after.changed,{self.a.id});self.assertEqual(after.visited_rows,1)
        self.assertEqual(after.totals[self.b.id],20)
    def test_reassign(self):
        before=analyze([row([self.a.id])],(Decimal(10),),self.cat)
        after=analyze([row([self.b.id])],(Decimal(10),),self.cat,before,[0])
        self.assertEqual(after.totals,{self.a.id:0,self.b.id:10})
        self.assertEqual(after.changed,{self.a.id,self.b.id})
    def test_filter_union_and_context(self):
        rows=[row(level='Cuenta'),row([self.a.id]),row([self.b.id]),row()]
        summary=analyze(rows,(0,10,20,30),self.cat)
        self.assertEqual(summary.visible([self.a.id],(None,0,0,0)),{0,1})
        self.assertEqual(summary.visible([self.a.id,self.b.id],(None,0,0,0)),{0,1,2})
        self.assertEqual(summary.visible([],(None,0,0,0)),set(range(4)))
    def test_inactive_retains(self):
        cat=self.cat.updated(replace(self.a,active=False))
        self.assertEqual(analyze([row([self.a.id])],(Decimal(10),),cat).totals[self.a.id],10)
    def test_persistence(self):
        data=json.loads(json.dumps({'budget_groups':dump_groups(self.cat),'budget':[row([self.a.id])]}))
        restored=load_groups(data);self.assertEqual(restored.items(),self.cat.items())
    def test_legacy(self):self.assertEqual(load_groups({'budget':[row()]}).items(),())
    def test_corrupt(self):
        for data in ({'budget_groups':None},{'budget':[row(['missing'])]},
                     {'budget_groups':dump_groups(self.cat),'budget':[row([self.a.id],level='Cuenta')]}):
            with self.assertRaises(BudgetError):load_groups(data)
    def test_globals_fringe_currency(self):
        fringe=Fringe('SEGURO','P');fc=Fringes([fringe],{'P':Decimal(10)})
        rows=[row([self.a.id],quantity='N',fringe_ids=[fringe.id],exchange='6.96')]
        result=calculate(rows,{'N':Decimal(2)},fc)
        self.assertEqual(analyze(rows,result.totals,self.cat).totals[self.a.id],Decimal('1531.2'))
    def test_zero_membership_change(self):
        before=analyze([row([self.a.id])],(Decimal(0),),self.cat)
        after=analyze([row([self.b.id])],(Decimal(0),),self.cat,before,[0])
        self.assertEqual(after.changed,{self.a.id,self.b.id});self.assertEqual(after.members[self.a.id],frozenset())

if __name__=='__main__':unittest.main(verbosity=2)
