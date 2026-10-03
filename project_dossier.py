"""PDF maestro/dossier del proyecto. No sustituye exportadores PDF existentes."""
from ui_i18n import ui_text, ui_join
from html import escape
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QDialogButtonBox, QFileDialog, QMessageBox
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter

SECTIONS = [
    ('development', ui_text('Desarrollo (tagline, logline, sinopsis y tratamiento)')),
    ('characters', ui_text('Personajes y arcos')),
    ('structure', ui_text('Estructura narrativa')),
    ('script', ui_text('Guion')),
    ('breakdown', ui_text('Desglose de producción')),
    ('schedule', ui_text('Plan de rodaje')),
    ('budget', ui_text('Presupuesto')),
    ('story_map', ui_text('Mapa / tramas')),
]

def _txt(v): return escape(str(v or '')).replace('\n','<br>')
LABELS = {
    'initial_state': 'Estado inicial', 'need': ui_text('Necesidad'), 'final_state': 'Estado final',
    'milestones': ui_text('Hitos'), 'moment': ui_text('Momento'), 'title': ui_text('Título'), 'notes': ui_text('Notas'),
    'scene': ui_text('Escena'), 'scene_label': ui_text('Escena vinculada'), 'scene_id': ui_text('Escena vinculada'),
    'category': ui_text('Categoría'), 'element': ui_text('Elemento'), 'approved': ui_text('Aprobado'), 'source': ui_text('Texto de origen'),
    'order': ui_text('Orden'), 'day': ui_text('Jornada'), 'date': ui_text('Fecha'), 'interior': 'Interior / exterior',
    'period': 'Momento del día', 'location': ui_text('Localización'), 'pages': ui_text('Páginas'),
    'synopsis': ui_text('Sinopsis'), 'elements': ui_text('Elementos'), 'status': ui_text('Estado'),
    'level': ui_text('Nivel'), 'block': ui_text('Bloque'), 'code': ui_text('Código'), 'concept': ui_text('Concepto'),
    'quantity': ui_text('Cantidad'), 'unit': ui_text('Unidad'), 'days': ui_text('Jornadas'), 'unit_price': ui_text('Tarifa'),
    'currency': ui_text('Moneda'), 'exchange': 'Tipo de cambio', 'fringe': 'Cargas (%)',
    'total': 'Total', 'lane': 'Trama', 'description': ui_text('Descripción'),
}


def _label(key):
    return LABELS.get(key, str(key).replace('_', ' ').capitalize())


def _value(value):
    if isinstance(value, bool): return 'Sí' if value else 'No'
    return _txt(value)


def _rows_table(rows, max_rows=None):
    """Fichas sin truncamiento: los textos largos usan todo el ancho disponible."""
    if not isinstance(rows, list): return ''
    return ''.join(f'<h3>Registro {i}</h3>' + (_dict_table(row) if isinstance(row, dict) else f'<p>{_value(row)}</p>')
                   for i, row in enumerate(rows, 1))


def _dict_table(d):
    if not isinstance(d, dict): return ''
    out = []
    for key, value in d.items():
        if key in ('id', 'x', 'y') or key.endswith('_ids'): continue
        if key == 'scene_id' and d.get('scene_label'): continue
        if value is None or value == '' or value == [] or value == {}: continue
        if isinstance(value, dict):
            out.append(f'<h3>{_txt(_label(key))}</h3>' + _dict_table(value))
        elif isinstance(value, list):
            out.append(f'<h3>{_txt(_label(key))}</h3>' + _rows_table(value))
        else:
            out.append(f'<p><b>{_txt(_label(key))}:</b> {_value(value)}</p>')
    return ''.join(out)


def _readable(data, scenes):
    if isinstance(data, list): return [_readable(v, scenes) for v in data]
    if not isinstance(data, dict): return data
    result = {k: _readable(v, scenes) for k, v in data.items()}
    if result.get('scene_id'):
        result['scene_label'] = scenes.get(str(result['scene_id'])) or result.get('scene_label') or result.get('scene') or 'Escena no disponible'
        result.pop('scene_id', None)
    return result


def _development(data):
    d=data.get('treatment') or {}
    if not isinstance(d,dict): return ''
    labels={'tagline':'Tagline','logline':'Logline','synopsis':ui_text('Sinopsis'),'argumental_synopsis':ui_text('Sinopsis argumental'),'premise':ui_text('Premisa'),'theme':ui_text('Tema')}
    out=''
    for k,label in labels.items():
        v=str(d.get(k,'') or '').strip()
        if v: out+=f'<h2>{label}</h2><p>{_txt(v)}</p>'
    treatment=d.get('treatment') or []
    if treatment:
        out+='<h2>Tratamiento</h2>'
        for i,r in enumerate(treatment,1):
            if isinstance(r,dict): out+=f'<h3>{i}. {_txt(r.get("title",""))}</h3><p>{_txt(r.get("text",""))}</p>'
    return out

def _scene_labels(data):
    """Mapea el ID interno a una referencia legible para documentos exportados."""
    blocks = data.get('blocks') or []
    labels = {}
    number = 0
    for block in blocks:
        if not isinstance(block, dict) or block.get('type') != 'scene':
            continue
        number += 1
        scene_id = str(block.get('id') or '')
        heading = str(block.get('text') or '').strip()
        if scene_id:
            labels[scene_id] = ui_join([ui_text('Escena '), f'{number}', ui_text(' — '), f'{heading}']) if heading else ui_join([ui_text('Escena '), f'{number}'])
    return labels


def _structure(data):
    d = data.get('dramatic_structure') or {}
    model = d.get('structure_model', '')
    out = f'<p class="model"><b>Modelo:</b> {_txt(model)}</p>' if model else ''
    scene_labels = _scene_labels(data)
    points = d.get('structure_points') or {}
    planned_all = d.get('structure_planned_scenes') or {}
    planned = planned_all.get(model, {}) if model and isinstance(planned_all.get(model), dict) else planned_all
    if not isinstance(planned, dict):
        planned = {}
    names = []
    for n in list(points) + list(planned):
        if n not in names:
            names.append(n)
    if names:
        out += '<table class="structure-summary"><tr><th>Hito</th><th>Escena vinculada</th><th>Planificación</th></tr>'
        for n in names:
            scene_id = str(points.get(n) or '')
            scene = scene_labels.get(scene_id, '')
            plan = str(planned.get(n) or '').strip()
            out += f'<tr><td><b>{_txt(n)}</b></td><td>{_txt(scene or "Sin escena vinculada")}</td><td>{_txt(plan or "—")}</td></tr>'
        out += '</table>'

    dev = (d.get('structure_development') or {}).get(model, {}) if model else {}
    if isinstance(dev, dict) and dev:
        labels = {
            'transformation': 'Transformación',
            'purpose': 'Función dramática',
            'character': ui_text('Personaje'),
            'objective': ui_text('Objetivo'),
            'conflict': ui_text('Conflicto'),
            'value': 'Valor en juego',
            'value_start': 'Valor inicial',
            'value_end': 'Valor final',
            'notes': ui_text('Notas'),
        }
        out += '<h2>Ficha estructural</h2>'
        for beat, vals in dev.items():
            if not isinstance(vals, dict):
                continue
            out += f'<div class="beat"><h3>{_txt(beat)}</h3><table class="beat-table">'
            for key in ('transformation','purpose','character','objective','conflict','value','value_start','value_end'):
                value = vals.get(key, '')
                if str(value).strip():
                    out += f'<tr><th>{labels[key]}</th><td>{_txt(value)}</td></tr>'
            notes = str(vals.get('notes', '') or '').strip()
            if notes:
                # La ubicación orientativa ya pertenece a Notas en proyectos antiguos; se presenta en español.
                out += f'<tr><th>Notas / ubicación orientativa</th><td>{_txt(notes)}</td></tr>'
            linked_id = str(points.get(beat) or '')
            if linked_id:
                out += f'<tr><th>Escena vinculada</th><td>{_txt(scene_labels.get(linked_id, "Sin escena vinculada"))}</td></tr>'
            out += '</table></div>'
    return out

def _script(blocks):
    if not blocks:return ''
    out='<div class="script">'
    for b in blocks:
        if not isinstance(b,dict):continue
        t=str(b.get('text','') or '')
        if not t.strip(): out+='<p>&nbsp;</p>'; continue
        typ=str(b.get('type','') or '').lower()
        cls='scene' if typ in ('scene','scene_heading','heading') else ('character' if typ=='character' else ('dialogue' if typ in ('dialogue','parenthetical') else 'action'))
        out+=f'<p class="{cls}">{_txt(t)}</p>'
    return out+'</div>'

def export_master_pdf(parent, data, blocks):
    dlg=QDialog(parent); dlg.setWindowTitle(ui_text('PDF general del proyecto')); lay=QVBoxLayout(dlg)
    lab=QLabel(ui_text('Elige las secciones del dossier. Los PDF individuales actuales no se modifican.')); lab.setWordWrap(True); lay.addWidget(lab)
    checks={}
    for key,label in SECTIONS:
        c=QCheckBox(label); c.setChecked(True); lay.addWidget(c); checks[key]=c
    bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    bb.button(QDialogButtonBox.StandardButton.Ok).setText(ui_text('Exportar PDF general')); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
    if dlg.exec()!=QDialog.DialogCode.Accepted:return
    filename,_=QFileDialog.getSaveFileName(parent,ui_text('Exportar PDF general del proyecto'),'','PDF (*.pdf)')
    if not filename:return
    if not filename.lower().endswith('.pdf'):filename+='.pdf'
    try:
        write_master_pdf(filename, data, blocks, {k:c.isChecked() for k,c in checks.items()})
    except (OSError, ValueError) as error:
        QMessageBox.critical(parent, ui_text('No se pudo exportar'), str(error))
        return
    QMessageBox.information(parent, ui_text('PDF general'), ui_text('Dossier general exportado correctamente.'))


def write_master_pdf(filename, data, blocks, selected=None):
    from pathlib import Path
    from PySide6.QtGui import QPageSize, QFont
    selected = selected if selected is not None else {key: True for key, _ in SECTIONS}
    data = _readable({**data, 'blocks': blocks}, _scene_labels({'blocks': blocks}))
    title=str((data.get('project_info') or {}).get('title') or data.get('title') or data.get('project_title') or 'Proyecto Eleuthera')
    css='''<style>body{font-family:Arial,sans-serif;font-size:10pt}h1{font-size:22pt}h2{font-size:15pt;margin-top:18px}h3{font-size:11pt}table{border-collapse:collapse;width:100%;margin:8px 0 14px}th,td{border:1px solid #999;padding:6px;vertical-align:top}th{font-weight:bold}.structure-summary th{font-size:10pt}.structure-summary td:first-child{width:22%}.structure-summary td:nth-child(2){width:43%}.beat{page-break-inside:avoid;margin:0 0 14px}.beat h3{margin:10px 0 4px}.beat-table th{width:28%;text-align:left}.model{font-size:11pt;margin-bottom:12px}.page{page-break-before:always}.script{font-family:"Courier New",monospace}.script p{margin:2px 0}.script .scene{font-weight:bold;margin-top:12px}.script .character{margin-left:190px;font-weight:bold}.script .dialogue{margin-left:110px;margin-right:100px}</style>'''
    html=css+f'<h1>{_txt(title)}</h1><p>Dossier general del proyecto · Eleuthera Cinema Suite Professional Plus</p>'
    def section(label,content):
        nonlocal html
        if content and content.strip(): html+=f'<div class="page"><h1>{label}</h1>{content}</div>'
    if selected['development']: section(ui_text('Desarrollo'),_development(data))
    if selected['characters']: section(ui_text('Personajes y arcos'),_dict_table(data.get('character_arcs') or {}))
    if selected['structure']: section(ui_text('Estructura narrativa'),_structure(data))
    if selected['script']: section(ui_text('Guion'),_script(blocks))
    if selected['breakdown']: section(ui_text('Desglose de producción'),_rows_table(data.get('breakdown') or []))
    if selected['schedule']: section(ui_text('Plan de rodaje'),_rows_table(data.get('schedule') or [] ) or _dict_table(data.get('schedule') or {}))
    if selected['budget']:
        budget=data.get('budget') or []
        content=_rows_table(budget) if isinstance(budget,list) else _dict_table(budget)
        section(ui_text('Presupuesto'),content)
    if selected['story_map']:
        sm=data.get('story_map') or {}; section(ui_text('Mapa / tramas'),_rows_table(sm) if isinstance(sm,list) else _dict_table(sm))
    doc=QTextDocument(); doc.setDefaultFont(QFont('Arial', 10)); doc.setHtml(html)
    printer=QPrinter(QPrinter.PrinterMode.HighResolution); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(filename)
    # Qt uses integer layout coordinates: high printer DPI can overflow on large dossiers.
    # Text remains vector-based at screen resolution.
    printer.setResolution(96)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    doc.print_(printer)
    if not Path(filename).is_file() or not Path(filename).stat().st_size:
        raise OSError('No se pudo crear el PDF.')
