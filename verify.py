import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from app import MainWindow


app = QApplication([])
window = MainWindow()
window.show()
app.processEvents()

blocks = [
    {'type': 'scene', 'text': 'INT. CASA DE ELENA - NOCHE'},
    {'type': 'action', 'text': 'La lluvia golpea las ventanas.'},
    {'type': 'character', 'text': 'ELENA'},
    {'type': 'parenthetical', 'text': '(en voz baja)'},
    {'type': 'dialogue', 'text': 'Esta vez no pienso abrir.'},
    {'type': 'scene', 'text': 'EXT. CALLE - NOCHE'},
    {'type': 'action', 'text': 'Una silueta espera bajo la lluvia.'},
]
window.editor.load_blocks(blocks)
window.notes.setPlainText('La puerta funciona como motivo visual.')
window.dirty = False
window.refresh()
app.processEvents()

assert window.scenes.count() == 2
assert [{k: b[k] for k in ('type', 'text')} for b in window.editor.blocks()] == blocks
assert len({b['id'] for b in window.editor.blocks()}) == len(blocks)
assert '> ' not in window.fountain_text()
assert 'ELENA' in window.fountain_text()

with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / 'prueba.eguion'
    window.path = path
    window.dirty = True
    assert window.save()
    data = json.loads(path.read_text(encoding='utf-8'))
    assert [{k: b[k] for k in ('type', 'text')} for b in data['blocks']] == blocks
    assert data['blocks'] == window.editor.blocks()
    assert data['notes'].startswith('La puerta')

window.resize(1360, 860)
app.processEvents()
window.grab().save(str(Path(__file__).parent / 'vista-editor.png'))
window.dirty = False
window.close()
print('OK: bloques, escenas, guardado, Fountain e interfaz.')
