from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog,QPushButton
from PySide6.QtGui import QImage
from suite import SuiteWindow
from project_store import fingerprint
from PIL import Image

app=QApplication([]);out=Path('test-results/final');w=SuiteWindow('professional');w.poll.stop();w.autosave.stop()
assert QImage('assets/eleuthera-clapperboard-256.png').pixelColor(128,10).name()=='#17616a'
assert len(Image.open('assets/eleuthera-clapperboard.ico').ico.sizes())==7
def inspect(dialog):
    dialog.show();app.processEvents()
    primary={b.text() for b in dialog.findChildren(QPushButton) if b.objectName()=='primary'}
    assert primary=={'Nuevo proyecto','Continuar'}
    dialog.grab().save(str(out/'welcome-petroleum.png'));dialog.reject();return 0
with patch.object(QDialog,'exec',inspect):w.show_welcome()
w._last_saved=fingerprint(w.project_data());w.dirty=False;w.close()

import tkinter as tk
from tkinter import ttk
import suite_activation
def inspect_activation(root):
    assert ttk.Style(root).lookup('TButton','background')=='#17616a'
    assert Path(suite_activation.__file__).with_name("assets").joinpath("eleuthera-clapperboard.ico").is_file()
    root.destroy()
with patch.object(suite_activation,'installed_license',side_effect=ValueError('QA')),patch.object(tk.Tk,'mainloop',inspect_activation):
    assert not suite_activation.activate()
print('PASS: petroleum SVG/PNG/7-size ICO, welcome buttons and activation theme; callbacks retained.')
