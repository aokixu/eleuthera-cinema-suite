"""Regression: names in PDF text without preceding blank lines."""
from script_import import parse_fountain

sample = '''1. EXT. CARRETERA DEL ALTIPLANO - DIA
El equipo investiga una emisora.
INES QUISPE
La roca debajo de este lugar esta
vibrando. No deberia hacerlo.
DARIO SALAS
Recogemos el equipo y nos vamos.
2. INT. CAMIONETA - DIA
Una interferencia grave.
LUCAS MENA
No hay energia en esta linea.'''

blocks = parse_fountain(sample, relaxed=True)
assert [b['type'] for b in blocks] == [
    'scene', 'action', 'character', 'dialogue', 'dialogue',
    'character', 'dialogue', 'scene', 'action', 'character', 'dialogue']
assert '\n'.join(b['text'] for b in blocks) == sample
assert parse_fountain('ANA\nHola.\n\nLa puerta se abre.')[-1]['type'] == 'action'
print('PASS: PDF speaker cues, dialogue continuation, text preservation and blank-line boundary.')
