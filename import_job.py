"""Background parsing and cooperative GUI installation, without nested event loops."""
from ui_i18n import ui_text, ui_join
from time import perf_counter
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import QProgressDialog, QMessageBox
from script_import import read_import, ImportCancelled


class Reader(QThread):
    progress=Signal(str,int,int)
    ready=Signal(object,object)
    failed=Signal(str)
    def __init__(self,path,parent):super().__init__(parent);self.path=path
    def report(self,label,current,total):
        if self.isInterruptionRequested():raise ImportCancelled()
        self.progress.emit(label,current,total)
    def run(self):
        try:
            data,timings=read_import(self.path,self.report)
            self.report('Preparando editor',0,0);self.ready.emit(data,timings)
        except ImportCancelled:self.failed.emit('')
        except Exception as error:self.failed.emit(str(error))


class ImportJob(QObject):
    def __init__(self,window,path):
        super().__init__(window);self.window=window;self.path=path;self.cancelled=False;self.installed=False
        self.previous=(window.project_data(),window.path,window._last_saved,window.editor.textCursor().position())
        self.started=perf_counter();self.timings={};self.generator=None;self.document=None
        self.dialog=QProgressDialog('Leyendo archivo…',ui_text('Cancelar'),0,0,window)
        self.dialog.setWindowTitle(ui_text('Importar guion'));self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.dialog.setMinimumDuration(0);self.dialog.setAutoClose(False);self.dialog.setAutoReset(False)
        self.dialog.canceled.connect(self.cancel)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.step)
        self.reader=Reader(path,self);self.reader.progress.connect(self.report);self.reader.ready.connect(self.prepare);self.reader.failed.connect(self.fail)
        self.reader.finished.connect(self.reader_stopped)
        self.done=False
    def start(self):self.dialog.show();self.reader.start()
    def report(self,label,current,total):
        self.dialog.setLabelText(label+(f' · {current}/{total}' if total else ''))
        self.dialog.setRange(0,total);self.dialog.setValue(current if total else 0)
    def cancel(self):
        if self.done: return
        self.cancelled=True;self.reader.requestInterruption()
        self.dialog.setLabelText('Cancelando…');self.dialog.setCancelButton(None);self.dialog.show()
        if self.generator is not None:self.timer.start(0)
    def prepare(self,data,timings):
        if self.cancelled:self.finish(False);return
        self.data=data;self.timings=timings;self.phase='editor';self.phase_start=perf_counter()
        self.generator=self.window.editor.build_document(data['blocks']);self.timer.start(0)
    def step(self):
        if self.done: return
        if self.cancelled:
            if self.generator:self.generator.close()
            self.restore();self.finish(False);return
        try:
            batch_started=perf_counter()
            result=next(self.generator)
            duration=perf_counter()-batch_started
            self.timings['max_ui_batch_ms']=max(self.timings.get('max_ui_batch_ms',0),duration*1000)
            if self.phase!='editor':
                batches=self.timings.setdefault('module_batches',{})
                batches[result[0]]=batches.get(result[0],0)+duration
            if self.phase=='editor':
                self.document,current,total,scenes,scene_total=result
                self.report(f'Cargando editor · escena {scenes}/{scene_total}',current,total)
            else:
                self.report(*result)
            self.timer.start(0)
        except StopIteration:
            self.timings[self.phase]=perf_counter()-self.phase_start
            if self.phase=='editor':
                self.phase='modules';self.phase_start=perf_counter();self.installed=True
                self.generator=self.window.load_project_steps(self.data,self.path if self.path.suffix.lower()=='.eguion' else None,self.document)
                self.timer.start(0)
            else:
                self.window.clear_session_recovery()
                if self.path.suffix.lower()!='.eguion':self.window.dirty=True;self.window._last_saved=''
                self.window.remember_path(self.path);self.finish(True)
        except Exception as error:
            if self.generator:self.generator.close()
            self.restore();self.fail(str(error))
    def restore(self):
        if self.installed:
            data,path,saved,position=self.previous
            self.window.load_project(data,path);self.window._last_saved=saved
            from project_store import fingerprint
            self.window.dirty=fingerprint(self.window.project_data())!=saved
            cursor=self.window.editor.textCursor();cursor.setPosition(min(position,self.window.editor.document().characterCount()-1));self.window.editor.setTextCursor(cursor)
        elif self.document is not None:self.document.deleteLater()
    def fail(self,message):
        self.finish(False)
        if message:QMessageBox.critical(self.window,ui_text('No se pudo abrir'),message)
    def finish(self,success):
        if self.done:return
        self.done=True;self.timer.stop();self.dialog.close();self.dialog.deleteLater()
        self.timings['total']=perf_counter()-self.started;self.timings['success']=success
        self.window.last_import_profile=self.timings
        self.window.statusBar().showMessage('Guion cargado.' if success else 'Importación cancelada o no completada; se conserva el proyecto anterior.')
        if not self.reader.isRunning():self.reader_stopped()
    def reader_stopped(self):
        if self.done:
            self.window._import_job=None;self.deleteLater()
