"""Organización visual de las herramientas existentes; sin reglas de presupuesto."""
from ui_i18n import ui_text, ui_join
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLineEdit, QMenu, QPushButton


def searchable_table(dialog, table):
    search = QLineEdit(dialog)
    search.setPlaceholderText(ui_text('Buscar por nombre, fórmula, descripción o estado…'))
    search.setClearButtonEnabled(True)
    search.setAccessibleName('Buscar en ' + dialog.windowTitle())
    dialog.layout().insertWidget(dialog.layout().indexOf(table), search)
    def apply():
        query = search.text().strip().casefold()
        for row in range(table.rowCount()):
            text = ' '.join(table.item(row, col).text() for col in range(table.columnCount())
                            if table.item(row, col) is not None).casefold()
            table.setRowHidden(row, bool(query) and query not in text)
    search.textChanged.connect(apply)
    # Refreshes can replace cell contents; keep the current search effective.
    timer = QTimer(search); timer.setSingleShot(True); timer.timeout.connect(apply)
    table.itemChanged.connect(lambda *_: timer.start(0) if search.text() else None)
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setMinimumSectionSize(110)
    dialog.search = search


def install_budget_tools(window, actions, professional_tools):
    """Reuse existing action callbacks and menus; replace their visible buttons."""
    button = QPushButton(ui_text('Herramientas de presupuesto'))
    button.setObjectName('primary')
    button.setAccessibleName(ui_text('Herramientas de presupuesto'))
    menu = QMenu(button)
    menu.aboutToShow.connect(window.commit_active_cell)
    menu.addAction('Globals…', window.globals_button.click)
    fringes = menu.addMenu('Fringes')
    fringes.addAction('Administrar…', window.fringes_button.click)
    fringes.addAction('Asignar / consultar en partida…', window.assign_fringes_button.click)
    for source, title in ((window.charges_button, ui_text('Cargos contractuales')),
                          (window.credits_button, 'Credits'), (window.groups_button, 'Groups')):
        submenu = source.menu()
        submenu.setTitle(title)
        menu.addMenu(submenu)
    for source in (window.globals_button, window.fringes_button, window.assign_fringes_button,
                   window.charges_button, window.credits_button, window.groups_button):
        actions.removeWidget(source)
        professional_tools.removeWidget(source)
        source.setParent(window)
        source.hide()
    button.setMenu(menu)
    actions.insertWidget(2, button)
    window.budget_tools_button = button
