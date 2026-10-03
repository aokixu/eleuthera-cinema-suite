"""Estado offline de trial, protegido por DPAPI y persistente fuera del instalador."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import tempfile
import winreg
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager


class ClockInconsistency(ValueError):
    pass


class TrialExpired(ValueError):
    pass


def now_utc():
    return datetime.now(timezone.utc)


def state_directory():
    return Path(os.environ['LOCALAPPDATA']) / 'Team Eleuthera' / 'CinemaProfessionalPlusV1' / 'Activation'


def state_key():
    return r'Software\Team Eleuthera\CinemaProfessionalPlusV1\Activation'


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(raw, decrypt=False):
    source_buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('No se pudo verificar el estado local de activación.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(target.data)


@contextmanager
def locked(identifier):
    # Serialize simultaneous starts before either can choose the first timestamp.
    root = state_directory(); root.mkdir(parents=True, exist_ok=True)
    import msvcrt
    with (root / (identifier + '.lock')).open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        try: yield
        finally:
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def read_copies(identifier):
    copies = []
    path = state_directory() / (identifier + '.dat')
    if path.exists():
        with path.open('rb') as stream: copies.append(stream.read(16385))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, state_key()) as key:
            value, kind = winreg.QueryValueEx(key, identifier)
            if kind != winreg.REG_BINARY: raise ValueError('Estado local de prueba inválido.')
            copies.append(value)
    except FileNotFoundError: pass
    return copies


def write_copies(identifier, value):
    root = state_directory(); root.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(dir=root, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(value); output.flush(); os.fsync(output.fileno())
        os.replace(filename, root / (identifier + '.dat'))
    finally:
        if os.path.exists(filename): os.unlink(filename)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, state_key()) as key:
        winreg.SetValueEx(key, identifier, 0, winreg.REG_BINARY, value)


def check_trial(payload):
    identity = payload['product'] + ':' + payload['machine'] + ':' + payload['license_id']
    identifier = hashlib.sha256(identity.encode()).hexdigest()
    with locked(identifier):
        now = now_utc()
        first, last = [], []
        try:
            for raw in read_copies(identifier):
                if len(raw) > 16384: raise ValueError()
                state = json.loads(protect(raw, decrypt=True))
                if state['identity'] != identity or state['version'] != 1: raise ValueError()
                start = datetime.fromisoformat(state['first_activation'])
                seen = datetime.fromisoformat(state['last_seen'])
                if start.tzinfo is None or seen.tzinfo is None or seen < start: raise ValueError()
                first.append(start); last.append(seen)
        except Exception as exc:
            raise ValueError('Estado de activación de prueba inválido o alterado. No se reinició el periodo.') from exc
        start = min(first) if first else now
        seen = max(last) if last else now
        if now < seen - timedelta(minutes=5):
            raise ClockInconsistency('Se detectó una inconsistencia de fecha/hora. Revisa el reloj del sistema para usar la licencia de prueba.')
        # A tolerated small clock adjustment must never extend the trial.
        effective = max(now, seen)
        state = dict(version=1, identity=identity, first_activation=start.isoformat(), last_seen=effective.isoformat())
        write_copies(identifier, protect(json.dumps(state, sort_keys=True).encode()))
        if effective >= start + timedelta(days=3):
            raise TrialExpired('La licencia de prueba de 3 días ha finalizado.')
        return state
