"""Preferencias y recuperación exclusivas de esta copia de Professional Plus."""
from pathlib import Path
import os
import sys
from PySide6.QtCore import QSettings

ROOT = Path(__file__).resolve().parent
RUNTIME = (Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'Eleuthera Professional Plus'
           if getattr(sys, 'frozen', False) else ROOT / '.runtime')


def configure():
    settings = RUNTIME / 'settings'
    settings.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
        QSettings.setPath(QSettings.Format.IniFormat, scope, str(settings))


configure()
