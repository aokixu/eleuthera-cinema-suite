import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from app import MainWindow
from script_import import parse_fountain
from pathlib import Path
q=QApplication([]);w=MainWindow();w.show();q.processEvents()
blocks=parse_fountain('1. EXT. CARRETERA DEL ALTIPLANO - DIA\n\nUna camioneta recorre la carretera.\n\nPEDRO\nVamos a casa.\n\n2A INT. CASA - NOCHE\n\n'+ ('Una accion larga en la casa. '*20+'\n\n')*60)
w.editor.load_blocks(blocks);w.refresh();q.processEvents()
print('pages',w.editor.document().pageSize(),w.editor.document().pageCount(),'viewport',w.editor.viewport().size(),'scenes',w.scenes.count())
w.grab().save('perf-import/paged-preview.png')
assert w.scenes.count()==2
assert w.editor.document().pageSize().height()==984
assert w.editor.document().pageCount()>1
for b in (w.editor.document().findBlockByNumber(i) for i in range(w.editor.document().blockCount())):
 r=w.editor.document().documentLayout().blockBoundingRect(b)
 assert r.width()>200, r
from project_store import scene_fields
from production import analyze_blocks
from PySide6.QtGui import QTextCursor
assert scene_fields('1. EXT. CARRETERA DEL ALTIPLANO - DIA') == ('EXT', 'DIA', 'CARRETERA DEL ALTIPLANO')
assert any(r['element']=='Carretera Del Altiplano' for r in analyze_blocks(blocks))
for value in ['1. EXT. CASA - DIA', '14A INT. CASA - NOCHE', '27) INT/EXT. AUTO - DIA', 'EXT. CALLE - DIA']:
 assert parse_fountain(value)[0]['type']=='scene', value
for value in ['1. Comprar un auto', 'EXTENSION DEL PROYECTO', 'INTERIOR DEL ARMARIO']:
 assert parse_fountain(value)[0]['type']!='scene', value
w.editor.verticalScrollBar().setValue(850);q.processEvents()
w.grab().save('perf-import/paged-boundary.png')
cursor=w.editor.textCursor();cursor.movePosition(QTextCursor.MoveOperation.End);cursor.insertText(' Texto nuevo.');q.processEvents()
assert w.editor.document().pageSize().height()==984
w.editor.undo();q.processEvents()
assert w.editor.document().pageSize().height()==984
assert w.editor.viewport().width() > 700
print('OK: numbered scenes, location, page layout, full width and editing/undo')
w.dirty=False;w.close()
