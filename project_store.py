"""Project snapshots and stable scene comparisons, independent of the UI."""
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from production import normalize


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def snapshots(directory, data, prefix='snapshot', limit=5):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = f'{prefix}-{datetime.now():%Y%m%d-%H%M%S-%f}-{uuid.uuid4().hex[:6]}.eguion'
    atomic_json(directory / name, data)
    files = sorted(directory.glob(prefix + '-*.eguion'))
    for old in files[:-limit]:
        old.unlink()
    return directory / name


def scene_fields(heading):
    heading = re.sub(r"^\d+[A-Z]?[.\-:)]?\s+(?=(?:INT|EXT|I/E))", "", heading.strip(), flags=re.I)
    match = re.match(r'^(INT\.?\s*/\s*EXT\.?|I/E\.?|INT\.?|EXT\.?)\s+', heading.strip(), re.I)
    environment = ''
    location = heading.strip()
    if match:
        environment = 'INT/EXT' if '/' in match[1] else ('EXT' if match[1].upper().startswith('EXT') else 'INT')
        location = heading[match.end():].strip()
    period = ''
    parts = re.split(r'\s+[-–—]\s+', location)
    if len(parts) > 1 and normalize(parts[-1]).upper() in ('DIA', 'NOCHE', 'AMANECER', 'ATARDECER', 'MADRUGADA', 'TARDE', 'ANOCHECER', 'CONTINUO'):
        period = parts.pop().upper()
        location = ' - '.join(parts)
    return environment, period, location


def scenes_from_blocks(blocks):
    scenes = []
    current = None
    for index, block in enumerate(blocks):
        if block.get('type') == 'scene':
            current = {'id': block['id'], 'heading': block.get('text', ''), 'blocks': [], 'index': index, 'number': len(scenes) + 1}
            scenes.append(current)
        if current:
            current['blocks'].append({'type': block.get('type', 'action'), 'text': block.get('text', '')})
    for scene in scenes:
        scene['interior'], scene['period'], scene['location'] = scene_fields(scene['heading'])
        scene['characters'] = sorted({b['text'].strip() for b in scene['blocks'] if b['type'] == 'character'})
    return scenes


def scene_snapshot(scene):
    return {'heading': scene['heading'], 'blocks': scene['blocks']}


def plan_source(scene, breakdown):
    # Only information used by the plan triggers downstream review.
    return {'heading': scene['heading'], 'interior': scene['interior'], 'period': scene['period'],
            'location': scene['location'], 'synopsis': ' '.join(b['text'] for b in scene['blocks'] if b['type'] == 'action'),
            'elements': sorted({r.get('element', '') for r in breakdown if r.get('scene_id') == scene['id'] and r.get('element')})}

def validate_project(data):
    if not isinstance(data, dict) or not isinstance(data.get('blocks'), list):
        raise ValueError('El archivo no contiene un proyecto válido.')
    for block in data['blocks']:
        if not isinstance(block, dict) or not isinstance(block.get('text', ''), str) or block.get('type', 'action') not in ('scene', 'action', 'character', 'dialogue', 'parenthetical', 'transition'):
            raise ValueError('El proyecto contiene bloques de guion inválidos.')
        if block.get('id') and not isinstance(block['id'], str): raise ValueError('Identificador de bloque inválido.')
    for key in ('breakdown', 'budget', 'schedule', 'story_map'):
        rows = data.get(key, [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError('Datos inválidos en ' + key)
    for key in ('project_info', 'budget_settings', 'breakdown_baseline', 'plan_baseline', 'saved_searches', 'metadata_draft'):
        if not isinstance(data.get(key, {}), dict): raise ValueError('Datos inválidos en ' + key)
    versions = data.get('scene_versions', {})
    if not isinstance(versions, dict):
        raise ValueError('Versiones de escena inválidas.')
    for scene_id, rows in versions.items():
        if not isinstance(scene_id, str) or not isinstance(rows, list):
            raise ValueError('Versiones de escena inválidas.')
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id', ''), str) or not isinstance(row.get('name', ''), str):
                raise ValueError('Versión de escena inválida.')
            blocks = row.get('blocks', [])
            if not isinstance(blocks, list) or any(not isinstance(block, dict) for block in blocks):
                raise ValueError('Contenido de versión de escena inválido.')
    import math
    for key in ('shooting_days', 'default_fringe'):
        value = float(data.get('budget_settings', {}).get(key, 1))
        if not math.isfinite(value): raise ValueError('Configuración numérica inválida.')
    for card in data.get('story_map', []):
        float(card.get('x', 0)); float(card.get('y', 0))
    if not isinstance(data.get('project_info', {}).get('rates', {}), dict): raise ValueError('Tipos de cambio inválidos.')

    from budget_group_persistence import load_groups
    load_groups(data)
    from budget_persistence import load_globals
    from budget_fringe_persistence import load_fringes
    load_fringes(data, load_globals(data).values())
    from budget_credit_persistence import load_credits
    load_credits(data, load_globals(data).values())
    from budget_charge_persistence import load_charges
    load_charges(data, load_globals(data).values())

    if 'budget_currencies' in data:
        from budget_currencies import validate_catalog
        validate_catalog(data['budget_currencies'])
