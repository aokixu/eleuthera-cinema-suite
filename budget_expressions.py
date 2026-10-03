"""Aritmética Decimal acotada. Nunca eval/exec, ni acceso a Python desde fórmulas."""
import ast
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
from functools import lru_cache
from budget_values import BudgetError, numeric, global_name

FIELDS = ('quantity', 'days', 'unit_price', 'exchange', 'fringe')


@dataclass(frozen=True)
class Expression:
    source: str
    tree: object
    dependencies: frozenset


@lru_cache(maxsize=2048)
def parse_expression(source):
    if not isinstance(source, str) or len(source) > 256:
        raise BudgetError('Expresión demasiado larga (máximo 256 caracteres).')
    source = source.strip()
    if source.upper() == '@DIAS_RODAJE':
        source = 'DIAS_RODAJE'
    # Coma decimal solo en un valor literal; en expresiones usar punto decimal.
    try:
        value = numeric(source)
    except BudgetError:
        pass
    else:
        return Expression(source, value, frozenset())
    try:
        tree = ast.parse(source, mode='eval').body
    except (SyntaxError, RecursionError, ValueError) as error:
        raise BudgetError('Referencia o expresión inválida.') from error
    dependencies = set()
    count = 0
    def check(node, depth=0):
        nonlocal count
        count += 1
        if count > 64 or depth > 16:
            raise BudgetError('Expresión demasiado compleja.')
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            numeric(ast.get_source_segment(source, node))
        elif isinstance(node, ast.Name):
            dependencies.add(global_name(node.id))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            check(node.left, depth + 1); check(node.right, depth + 1)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            check(node.operand, depth + 1)
        else:
            raise BudgetError('Solo se permiten números, Globals, paréntesis y + - * /.')
    check(tree)
    return Expression(source, tree, frozenset(dependencies))


def evaluate(source, values):
    expression = parse_expression(source)
    missing = expression.dependencies - values.keys()
    if missing:
        raise BudgetError('Globals inexistentes: ' + ', '.join(sorted(missing)))
    def visit(node):
        if isinstance(node, Decimal):
            return node
        if isinstance(node, ast.Constant):
            return numeric(ast.get_source_segment(expression.source, node))
        if isinstance(node, ast.Name):
            return numeric(values[global_name(node.id)])
        if isinstance(node, ast.UnaryOp):
            operand = visit(node.operand)
            return operand if isinstance(node.op, ast.UAdd) else -operand
        left, right = visit(node.left), visit(node.right)
        if isinstance(node.op, ast.Add): result = left + right
        elif isinstance(node.op, ast.Sub): result = left - right
        elif isinstance(node.op, ast.Mult): result = left * right
        else:
            if not right: raise BudgetError('División por cero.')
            result = left / right
        return numeric(result)
    try:
        with localcontext() as context:
            context.prec = 28
            return numeric(visit(expression.tree))
    except DecimalException as error:
        raise BudgetError('Resultado numérico inválido.') from error


