import base64
import hashlib
import json
import os
import re
import winreg
from datetime import datetime, timezone, timedelta
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from suite_license_public import PUBLIC_KEY
from suite_trial_state import TrialExpired, ClockInconsistency, check_trial

PRODUCT = 'eleuthera.cinema.professional.plus.v1'


def machine_code():
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography',
                        0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        value = winreg.QueryValueEx(key, 'MachineGuid')[0]
    if not isinstance(value, str) or not value.strip():
        raise ValueError('No se pudo identificar este equipo.')
    return 'ECPP-' + hashlib.sha256((PRODUCT + ':' + value.strip().lower()).encode()).hexdigest().upper()


def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def verify(raw, expected_machine=None):
    if len(raw) > 16384:
        raise ValueError('Archivo de licencia demasiado grande.')
    try:
        envelope = json.loads(raw)
        payload = envelope['payload']
        signature = base64.b64decode(envelope['signature'], validate=True)
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY)).verify(signature, canonical(payload))
        if payload['version'] != 1 or payload['product'] != PRODUCT or not isinstance(payload.get('customer'), str) or not payload['customer'].strip():
            raise ValueError()
        if payload['seats'] != 1:
            raise ValueError()
        if 'license_type' in payload:
            if type(payload['version']) is not int or type(payload['seats']) is not int:
                raise ValueError()
            import uuid
            if not isinstance(payload.get('license_id'), str) or str(uuid.UUID(payload['license_id'])) != payload['license_id']:
                raise ValueError()
            if not isinstance(payload.get('issued_at'), str) or not payload['issued_at']:
                raise ValueError()
            kind = payload['license_type']
            if kind == 'trial':
                if payload['perpetual'] is not False or type(payload.get('duration_days')) is not int or payload['duration_days'] != 3:
                    raise ValueError()
                if 'expires_at' in payload: raise ValueError()
            elif kind == 'perpetual':
                if payload['perpetual'] is not True or 'duration_days' in payload or 'expires_at' in payload:
                    raise ValueError()
            else: raise ValueError()
        elif payload['perpetual'] is False:
            issued = datetime.fromisoformat(payload['issued_at'])
            expires = datetime.fromisoformat(payload['expires_at'])
            if issued.tzinfo is None or expires.tzinfo is None or expires - issued != timedelta(days=3):
                raise ValueError()
            now = datetime.now(timezone.utc)
            if now < issued:
                raise ValueError('La fecha del equipo es anterior a la emision.')
            if now >= expires:
                raise TrialExpired('La licencia de prueba de tres dias ha caducado. Solicita una nueva licencia.')
        elif payload['perpetual'] is not True:
            raise ValueError()
        if payload['machine'] != (expected_machine if expected_machine is not None else machine_code()):
            raise ValueError('La licencia pertenece a otro equipo.')
        return payload
    except TrialExpired:
        raise
    except Exception as exc:
        raise ValueError('Licencia inválida o no autorizada para este equipo.') from exc


def license_path():
    return Path(os.environ['LOCALAPPDATA']) / 'Team Eleuthera' / 'CinemaProfessionalPlusV1' / 'license.json'


def validate_active(raw, expected_machine=None):
    payload = verify(raw, expected_machine)
    if payload.get('license_type') == 'trial':
        check_trial(payload)
    return payload


def installed_license():
    path = license_path()
    with path.open('rb') as source:
        return validate_active(source.read(16385))


def install_license(raw):
    validate_active(raw)
    target = license_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    fd, name = tempfile.mkstemp(dir=target.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(raw)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)
