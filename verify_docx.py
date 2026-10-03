import tempfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from PySide6.QtWidgets import QApplication
from suite import SuiteWindow
from script_docx import W

qt = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory() as directory:
    for edition in ('standard', 'professional'):
        window = SuiteWindow(edition)
        window.autosave.stop()
        window.poll.stop()
        blocks = [{'type': kind, 'text': 'Español & <texto>\tfin'}
                  for kind in ('scene', 'action', 'character', 'dialogue', 'parenthetical', 'transition')]
        window.editor.load_blocks(blocks)
        target = Path(directory) / (edition + '.docx')
        with patch('suite.QFileDialog.getSaveFileName', return_value=(str(target), '')), \
             patch('suite.QMessageBox.information'), patch('suite.QMessageBox.critical') as error:
            window.docx_action.trigger()
            error.assert_not_called()
        with ZipFile(target) as archive:
            assert archive.testzip() is None
            for name in archive.namelist():
                ET.fromstring(archive.read(name))
            document = ET.fromstring(archive.read('word/document.xml'))
            paragraphs = document.findall('.//{%s}p' % W)
            assert len(paragraphs) == 6
            assert [p.find('{%s}pPr/{%s}pStyle' % (W, W)).get('{%s}val' % W)
                    for p in paragraphs] == [b['type'] for b in blocks]
            assert 'Español' in ''.join(document.itertext())
            assert len(document.findall('.//{%s}tab' % W)) == 6
        window.hide()
        window.deleteLater()
print('OK: DOCX action, six styles, Unicode, line breaks and tabs in both editions.')
