"""Acento azul petróleo autorizado para Professional Plus; fondos existentes."""
ACCENT = '#17616a'
HOVER = '#207580'
SELECTION = '#20535b'
TEXT_ACCENT = '#87c1c5'


def petroleum_stylesheet(source):
    colors = {
        '#7b2638': ACCENT, '#8e354b': ACCENT, '#a3475d': ACCENT,
        '#91364a': HOVER, '#a13f57': HOVER, '#b85a6e': HOVER,
        '#a9445a': ACCENT, '#633743': SELECTION, '#704050': SELECTION,
        '#4c353b': SELECTION, '#e5a1b0': TEXT_ACCENT,
    }
    for old, new in colors.items():
        source = source.replace(old, new)
    return source + f'''
QHeaderView::section {{ border-bottom: 2px solid {ACCENT}; }}
QLineEdit:focus, QPushButton:focus, QToolButton:focus, QComboBox:focus {{ border-color: {HOVER}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {TEXT_ACCENT}; }}
'''
