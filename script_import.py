"""Pure import parsing. No widgets or project state are accessed here."""
from ui_i18n import ui_text, ui_join
import json
import re
from pathlib import Path
from time import perf_counter
import xml.etree.ElementTree as ET
from project_store import validate_project


class ImportCancelled(Exception):
    pass


SCENE_HEADING = re.compile(r"^(?:\d+[A-Z]?[.\-:)]?\s+)?(?:INT\.?\s*/\s*EXT\.?|EXT\.?\s*/\s*INT\.?|I/E\.?|INT\.|EXT\.)(?=\s|$)", re.IGNORECASE)


def character_cue(text):
    # PDF extraction often drops blank lines. Restrict cues to short name-like lines.
    name = re.sub(r'\s*\([^)]*\)\s*$', '', text).strip()
    return (bool(name) and name == name.upper() and any(c.isalpha() for c in name)
            and len(name.split()) <= 4 and len(text) < 55
            and not any(c in name for c in '.:!?;0123456789')
            and not SCENE_HEADING.match(name))


def parse_fountain(source, progress=lambda *args: None, relaxed=False):
    result=[]; previous_blank=True; lines=source.splitlines(); scenes=0
    for index,line in enumerate(lines):
        clean=line.strip()
        if not clean:
            previous_blank=True; continue
        upper=clean.upper()
        if SCENE_HEADING.match(clean): kind='scene';scenes+=1
        elif clean.startswith('(') and clean.endswith(')'): kind='parenthetical'
        elif clean.startswith('>'): kind,clean='transition',clean.strip('> ').upper()
        elif clean.startswith('@'): kind,clean='character',clean[1:].strip()
        elif (previous_blank or relaxed) and character_cue(clean) and index + 1 < len(lines) and lines[index + 1].strip(): kind='character'
        elif not previous_blank and result and result[-1]['type'] in ('character','parenthetical','dialogue'): kind='dialogue'
        else: kind='action'
        result.append({'type':kind,'text':clean});previous_blank=False
        if index%200==0: progress(ui_join([ui_text('Reconociendo bloques · '), f'{scenes}', ui_text(' escenas')]),index,len(lines))
    progress(ui_join([ui_text('Reconociendo bloques · '), f'{scenes}', ui_text(' escenas')]),len(lines),len(lines))
    return result


def read_import(path, progress=lambda *args: None):
    path=Path(path); timings={}; total=perf_counter()
    def stage(name, function):
        start=perf_counter(); result=function();timings[name]=perf_counter()-start;return result
    suffix=path.suffix.lower();progress('Leyendo archivo',0,0)
    if suffix=='.pdf':
        from script_pdf import extract_pdf
        def extract(): return extract_pdf(path,progress)
        text=stage('pdf_extraction',extract);data={'blocks':stage('block_recognition',lambda:parse_fountain(text,progress,relaxed=True))}
    elif suffix=='.fdx':
        root=stage('fdx_read',lambda:ET.parse(path).getroot())
        def parse():
            blocks=[];count=0
            mapping={'scene heading':'scene','action':'action','character':'character','dialogue':'dialogue','parenthetical':'parenthetical','transition':'transition'}
            paragraphs=[p for p in root.iter() if p.tag.split('}')[-1]=='Paragraph']
            for index,p in enumerate(paragraphs):
                kind=p.attrib.get('Type','Action').lower();text=''.join(n.text or '' for n in p.iter() if n.tag.split('}')[-1]=='Text')
                if text.strip():
                    block_type=mapping.get(kind,'action');blocks.append({'type':block_type,'text':text.strip()});count+=block_type=='scene'
                if index%200==0:progress(ui_join([ui_text('Leyendo FDX · '), f'{count}', ui_text(' escenas')]),index,len(paragraphs))
            return blocks
        data={'blocks':stage('fdx_recognition',parse)}
    elif suffix in ('.txt','.fountain'):
        def read():
            raw=path.read_bytes()
            for encoding in ('utf-8-sig','utf-16','cp1252','latin-1'):
                try:return raw.decode(encoding)
                except UnicodeError:pass
            raise ValueError('No se pudo reconocer la codificación del TXT.')
        text=stage('text_read',read);data={'blocks':stage('block_recognition',lambda:parse_fountain(text,progress))}
    else:data=stage('project_read',lambda:json.loads(path.read_text(encoding='utf-8')))
    progress('Validando proyecto',0,0);stage('validation',lambda:validate_project(data));timings['read_total']=perf_counter()-total
    return data,timings
