from dataclasses import replace
from decimal import Decimal
import json,copy,unittest
from unittest.mock import patch
from budget_values import BudgetError
from budget_charges import Charge,Charges
from budget_charge_persistence import load_charges,dump_charges
from budget_engine import calculate,recalculation_steps,row_total,affected_rows
from budget_fringes import Fringe,Fringes
from budget_groups import Group,Groups
from budget_group_analysis import analyze

def row(ids=(),**changes):
    return dict(dict(level='Detalle',block='BTL',quantity='1',days='1',unit_price='10000',exchange='1',fringe='0',charge_ids=list(ids)),**changes)

class ChargeTests(unittest.TestCase):
    def setUp(self):self.item=Charge('PROVEEDOR','1500');self.cat=Charges([self.item])
    def test_create(self):self.assertEqual(self.cat.get(self.item.id),self.item)
    def test_edit(self):self.assertEqual(self.cat.updated(replace(self.item,amount='2000'),{}).resolved[self.item.id][0],2000)
    def test_rename(self):self.assertEqual(self.cat.updated(replace(self.item,name='OTRO'),{}).get(self.item.id).name,'OTRO')
    def test_remove(self):self.assertFalse(self.cat.removed(self.item.id,{}).items())
    def test_remove_used(self):
        with self.assertRaisesRegex(BudgetError,'fila 1'):self.cat.removed(self.item.id,{},['fila 1'])
    def test_active(self):
        inactive=self.cat.updated(replace(self.item,active=False),{})
        self.assertEqual(calculate([row([self.item.id])],{},contractuals=inactive).total,10000)
        self.assertEqual(calculate([row([self.item.id])],{},contractuals=self.cat).total,11500)
    def test_simple(self):self.assertEqual(calculate([row([self.item.id])],{},contractuals=self.cat).total,11500)
    def test_multiple(self):
        other=Charge('BONO','250.50');cat=Charges([self.item,other])
        result=calculate([row([self.item.id,other.id])],{},contractuals=cat)
        self.assertEqual(result.total,Decimal('11750.50'));self.assertEqual(len(result.charge_details[0]),2)
    def test_dedup(self):self.assertEqual(calculate([row([self.item.id]*3)],{},contractuals=self.cat).total,11500)
    def test_unassign(self):
        before=calculate([row([self.item.id])],{},contractuals=self.cat)
        for after in recalculation_steps([row()],{},before,{0},contractuals=self.cat):pass
        self.assertEqual(after.total,10000);self.assertFalse(after.charge_dependents)
    def test_source_unchanged(self):
        rows=[row([self.item.id])];original=copy.deepcopy(rows);calculate(rows,{},contractuals=self.cat)
        self.assertEqual(rows,original)
    def test_global(self):
        item=replace(self.item,amount='P * 2');cat=Charges([item],{'P':Decimal(500)})
        updated=cat.rebind({'P':Decimal(750)},{'P'})
        self.assertEqual(calculate([row([item.id])],{},contractuals=updated).total,11500)
        self.assertEqual(updated.last_evaluated,(item.id,))
    def test_atomic_rebind(self):
        item=replace(self.item,amount='1/P');cat=Charges([item],{'P':Decimal(2)})
        with self.assertRaises(BudgetError):cat.rebind({'P':Decimal(0)},{'P'})
        self.assertEqual(cat.resolved[item.id][0],Decimal('.5'))
    def test_currency(self):
        result=calculate([row([self.item.id],exchange='6.96')],{},contractuals=self.cat)
        self.assertEqual(result.before_charges[0],69600);self.assertEqual(result.charge_totals[0],10440);self.assertEqual(result.total,80040)
    def test_fringes_first(self):
        fringe=Fringe('SEGURO','10');fr=Fringes([fringe])
        result=calculate([row([self.item.id],fringe_ids=[fringe.id])],{},fr,contractuals=self.cat)
        self.assertEqual(result.before_charges[0],11000);self.assertEqual(result.total,12500)
    def test_groups_final(self):
        group=Group('A');rows=[row([self.item.id],group_ids=[group.id])]
        result=calculate(rows,{},contractuals=self.cat)
        self.assertEqual(analyze(rows,result.totals,Groups([group])).totals[group.id],11500)
    def test_persistence(self):
        cat=Charges([replace(self.item,amount='P + 1',active=False)],{'P':Decimal(10)})
        data=json.loads(json.dumps({'budget_charges':dump_charges(cat),'budget':[row([self.item.id])]}))
        self.assertEqual(load_charges(data,{'P':Decimal(10)}).items(),cat.items())
    def test_old(self):self.assertFalse(load_charges({'budget':[row()]},{}).items())
    def test_bad_references(self):
        for data in ({'budget':[row(['missing'])]}, {'budget_charges':None},
                     {'budget_charges':dump_charges(self.cat),'budget':[row([self.item.id],level='Cuenta')]}):
            with self.assertRaises(BudgetError):load_charges(data,{})
    def test_invalid_amount(self):
        for source in ('','-1','1/0','NO_EXISTE','NaN','inf','print(1)','1**2','10%'):
            with self.subTest(source=source),self.assertRaises(BudgetError):Charges([replace(self.item,amount=source)])
    def test_duplicates(self):
        with self.assertRaises(BudgetError):Charges([self.item,Charge('proveedor','1')])
        with self.assertRaises(BudgetError):Charges([self.item,self.item])
    def test_selective(self):
        rows=[row([self.item.id] if i<25 else []) for i in range(1025)]
        before=calculate(rows,{},contractuals=self.cat);cat=self.cat.updated(replace(self.item,amount='2000'),{})
        with patch('budget_engine.row_total',wraps=row_total) as spy:
            for after in recalculation_steps(rows,{},before,before.charge_dependents[self.item.id],contractuals=cat):pass
            self.assertEqual(spy.call_count,25)
        self.assertEqual(after.totals[25:],before.totals[25:]);self.assertEqual(after.total,calculate(rows,{},contractuals=cat).total)
    def test_reference_switch(self):
        item=replace(self.item,amount='P');cat=Charges([item],{'P':Decimal(10),'Q':Decimal(10)})
        rows=[row([item.id])];before=calculate(rows,{},contractuals=cat)
        cat=cat.updated(replace(item,amount='Q'),{'P':Decimal(10),'Q':Decimal(10)})
        for after in recalculation_steps(rows,{},before,{0},contractuals=cat):pass
        self.assertFalse(affected_rows(after,{'P'}));self.assertEqual(affected_rows(after,{'Q'}),{0})
    def test_amount_not_scaled_by_base(self):self.assertEqual(calculate([row([self.item.id],unit_price='1000')],{},contractuals=self.cat).total,2500)
    def test_incomplete(self):self.assertEqual(calculate([row([self.item.id],unit_price='',exchange=' ')],{},contractuals=self.cat).total,0)



    def test_charges_credits(self):
        from budget_credits import Credit,Credits
        credit=Credit('REDUCCION','1500');charge=Charge('CARGO','500')
        result=calculate([row([charge.id],credit_ids=[credit.id])],{},credits=Credits([credit]),contractuals=Charges([charge]))
        self.assertEqual((result.before_charges[0],result.charge_totals[0],result.before_credits[0],result.credit_totals[0],result.total),(10000,500,10500,1500,9000))
    def test_all_layers_currency(self):
        from budget_credits import Credit,Credits
        credit=Credit('REDUCCION','1500');charge=Charge('CARGO','500');fringe=Fringe('SEGURO','10')
        for code,rate in [('BOB','1'),('USD','6.96'),('XYZ','2.5')]:
            with self.subTest(currency=code):
                r=Decimal(rate)
                result=calculate([row([charge.id],currency=code,exchange=rate,fringe_ids=[fringe.id],credit_ids=[credit.id])],{},Fringes([fringe]),Credits([credit]),Charges([charge]))
                self.assertEqual((result.before_charges[0],result.charge_totals[0],result.before_credits[0],result.credit_totals[0],result.total),tuple(x*r for x in (11000,500,11500,1500,10000)))
    def test_no_charges_stage5(self):
        from budget_credits import Credit,Credits
        credit=Credit('REDUCCION','1500');cat=Credits([credit]);fringe=Fringe('SEGURO','10');fr=Fringes([fringe])
        rows=[row(credit_ids=[credit.id],fringe_ids=[fringe.id],exchange='6.96')]
        before=calculate(rows,{},fr,cat);after=calculate(rows,{},fr,cat,Charges())
        self.assertEqual(before,after)

if __name__=='__main__':unittest.main()
