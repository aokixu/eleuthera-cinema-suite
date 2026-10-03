"""Non-interactive packaged dependency and bilingual UI check."""
import json
from pathlib import Path

def run(output):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from suite import SuiteWindow
    from ui_i18n import set_language
    from project_excel import write_master_excel
    from project_dossier import write_master_pdf
    from openpyxl import load_workbook
    from pypdf import PdfReader
    from suite_license_public import PUBLIC_KEY
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    qt=QApplication([]);qt.setOrganizationName('Equipo Eleuthera');qt.setApplicationName('Eleuthera Professional Plus')
    window=SuiteWindow('professional');window.autosave.stop();window.poll.stop()
    blocks=[{'id':'sample-scene','type':'scene','text':'INT. OFICINA - DÍA'}, {'type':'character','text':'PERSONAJE'}, {'type':'dialogue','text':'El guion conserva su idioma original.'}]
    window.editor.load_blocks(blocks)
    snapshot=json.dumps(window.project_data(),ensure_ascii=False,sort_keys=True)
    set_language('en',persist=False)
    assert any(a.property('text')=='File' for a in window.menuBar().actions())
    assert window.modules.tabBar().tabText(0)=='Screenplay'
    assert window.analysis_page.marker_type.currentText()=='Personaje'
    assert window.analysis_page.marker_type.model().index(0,0).data()=='Character'
    assert json.dumps(window.project_data(),ensure_ascii=False,sort_keys=True)==snapshot
    set_language('es',persist=False)
    assert window.modules.tabBar().tabText(0)=='Guion'
    data={'project_info':{'title':'Prueba de compilación'},'budget':[{'concept':'Prueba','total':'125.50'}]}
    write_master_excel(output.with_suffix('.xlsx'),data,blocks)
    assert load_workbook(output.with_suffix('.xlsx'))['Resumen']['B4'].value=='Prueba de compilación'
    write_master_pdf(str(output.with_suffix('.pdf')),data,blocks)
    assert len(PdfReader(output.with_suffix('.pdf')).pages)>0
    assert not QIcon(str(Path(__file__).parent/'assets'/'eleuthera-clapperboard.svg')).pixmap(64,64).isNull()
    report={'startup':True,'spanish':True,'english':True,'canonical_values':True,'project_unchanged':True,'excel':True,'pdf':True,'icon':True,'public_key_valid':True}
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0
