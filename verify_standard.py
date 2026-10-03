import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from suite import SuiteWindow

qt = QApplication([])
window = SuiteWindow('standard')
assert window.windowTitle() == 'Eleuthera Standard'
assert window.workspace_mode == 'standard'
assert not window.modules.isTabVisible(window.modules.indexOf(window.schedule_page))
assert not hasattr(window, 'excel_button')
assert not hasattr(window, 'mode_combo')
assert window.budget.isColumnHidden(0)
assert window.budget.horizontalHeaderItem(4).text() == 'Concepto'
menus = [action.text() for action in window.menuBar().actions()]
assert 'Ayuda' in menus
window.dirty = False; window.close()
print('OK: Eleuthera Standard sin módulos profesionales visibles.')
