"""Editable screenplay DOCX using standard OOXML; no external dependency."""
from ui_i18n import ui_text, ui_join
import os
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ET.register_namespace('w', W)


def node(parent, name, **attrs):
    return ET.SubElement(parent, '{%s}%s' % (W, name),
                         {'{%s}%s' % (W, key): str(value) for key, value in attrs.items()})


def export_script_docx(path, blocks):
    document = ET.Element('{%s}document' % W)
    body = node(document, 'body')
    styles = ET.Element('{%s}styles' % W)
    definitions = {
        'scene': (ui_text('Escena'), 0, 0), 'action': (ui_text('Accion'), 0, 0),
        'character': (ui_text('Personaje'), 3528, 0), 'dialogue': ('Dialogo', 1800, 2160),
        'parenthetical': ('Parentetico', 2520, 2880), 'transition': ('Transicion', 6200, 0),
    }
    for kind, (label, left, right) in definitions.items():
        style = node(styles, 'style', type='paragraph', styleId=kind)
        node(style, 'name', val=label)
        props = node(style, 'pPr')
        node(props, 'ind', left=left, right=right)
        node(props, 'spacing', before=140 if kind == 'scene' else 40, after=40, line=240, lineRule='auto')
        if kind in ('scene', 'character', 'parenthetical'):
            node(props, 'keepNext')
        if kind == 'transition':
            node(props, 'jc', val='right')
        run = node(style, 'rPr')
        node(run, 'rFonts', ascii='Courier New', hAnsi='Courier New', cs='Courier New')
        node(run, 'sz', val=22)
        if kind == 'scene':
            node(run, 'b')
    for block in blocks:
        kind = block.get('type', 'action')
        paragraph = node(body, 'p')
        node(node(paragraph, 'pPr'), 'pStyle', val=kind if kind in definitions else 'action')
        run = node(paragraph, 'r')
        for index, line in enumerate(block.get('text', '').split('\n')):
            if index:
                node(run, 'br')
            parts = line.split('\t')
            for part_index, part in enumerate(parts):
                if part_index:
                    node(run, 'tab')
                t = node(run, 't')
                t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                t.text = part
    section = node(body, 'sectPr')
    node(section, 'pgSz', w=12240, h=15840)
    node(section, 'pgMar', top=1440, bottom=1440, left=1800, right=1440, header=720, footer=720, gutter=0)
    content_types = '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'''
    rels = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    document_rels = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    fd, temporary = tempfile.mkstemp(dir=Path(path).resolve().parent, suffix='.docx')
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as output:
            output.writestr('[Content_Types].xml', content_types)
            output.writestr('_rels/.rels', rels)
            output.writestr('word/_rels/document.xml.rels', document_rels)
            output.writestr('word/document.xml', ET.tostring(document, encoding='utf-8', xml_declaration=True))
            output.writestr('word/styles.xml', ET.tostring(styles, encoding='utf-8', xml_declaration=True))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
