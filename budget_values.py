"""Modelo de Globals independiente de Qt y del formato de proyecto."""
from decimal import Decimal, InvalidOperation
import re


class BudgetError(ValueError):
    pass


def global_name(raw):
    if not isinstance(raw, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', raw):
        raise BudgetError('Nombre inválido: usa letras ASCII, números y guion bajo; empieza por una letra.')
    return raw.upper()


def numeric(raw):
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
        raise BudgetError('El valor debe ser numérico.')
    text = str(raw).strip()
    if len(text) > 96:
        raise BudgetError('Valor numérico demasiado largo.')
    if ',' in text:
        if '.' in text or text.count(',') != 1:
            raise BudgetError('Separador decimal inválido.')
        text = text.replace(',', '.')
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise BudgetError('Valor numérico inválido.') from error
    if not value.is_finite() or abs(value) > Decimal('1e18') or (value and value.adjusted() < -18):
        raise BudgetError('Valor fuera de rango: entre -1e18 y 1e18, mínimo decimal 1e-18.')
    if len(value.as_tuple().digits) > 28:
        raise BudgetError('Máximo 28 cifras significativas.')
    return value


