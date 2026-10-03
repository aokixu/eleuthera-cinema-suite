"""Project-only poster panel; image bytes travel inside the project file."""
from ui_i18n import ui_text, ui_join
import base64
from pathlib import Path
from PySide6.QtCore import Qt, QByteArray, QBuffer, QIODevice, QSize
from PySide6.QtGui import QImage, QImageReader, QPainter
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QSizePolicy,QPushButton,QLabel,QFileDialog,QMessageBox

class PosterPreview(QWidget):
    def __init__(self):
        super().__init__(); self.image=QImage(); self.setMinimumSize(120,60); self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area=self.rect().adjusted(10,10,-10,-10)
        if self.image.isNull():
            painter.setPen(self.palette().text().color()); painter.drawText(area,Qt.AlignmentFlag.AlignCenter,'Sin poster'); return
        size=self.image.size().scaled(area.size(),Qt.AspectRatioMode.KeepAspectRatio)
        from PySide6.QtCore import QRect
        target=QRect(0,0,size.width(),size.height()); target.moveCenter(area.center()); painter.drawImage(target,self.image)

class ProjectPoster(QWidget):
    def __init__(self,changed,parent=None):
        super().__init__(parent); self.payload=None; self.changed=changed
        layout=QVBoxLayout(self); layout.setContentsMargins(12,12,12,12); layout.setSpacing(14)
        title=QLabel(ui_text('Poster del proyecto')); layout.addWidget(title)
        self.preview=PosterPreview(); layout.addWidget(self.preview,1)
        controls=QWidget(); controls.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)
        actions=QHBoxLayout(controls); actions.setContentsMargins(0,0,0,0); actions.setSpacing(10)
        button=QPushButton(ui_text('Cambiar imagen...')); button.setMinimumHeight(36); button.clicked.connect(self.choose); actions.addWidget(button,1)
        remove=QPushButton(ui_text('Quitar')); remove.setToolTip(ui_text('Quitar imagen del proyecto')); remove.setMinimumHeight(36); remove.clicked.connect(self.remove); actions.addWidget(remove)
        layout.addWidget(controls)
    def set_data(self,payload):
        if payload is None:
            self.payload=None; self.preview.image=QImage(); self.preview.update(); return
        if not isinstance(payload,dict) or not isinstance(payload.get('data'),str) or len(payload['data'])>32*1024*1024:
            raise ValueError('Poster de proyecto invalido.')
        raw=base64.b64decode(payload['data'],validate=True); image=QImage.fromData(raw)
        if image.isNull(): raise ValueError('No se pudo leer el poster del proyecto.')
        self.payload=dict(payload); self.preview.image=image; self.preview.update()
    def load_image(self,path):
        path=Path(path)
        if path.stat().st_size>20*1024*1024: raise ValueError('Selecciona una imagen de hasta 20 MB.')
        reader=QImageReader(str(path)); reader.setAutoTransform(True)
        size=reader.size()
        if size.isValid() and max(size.width(),size.height())>2000:
            reader.setScaledSize(size.scaled(QSize(2000,2000),Qt.AspectRatioMode.KeepAspectRatio))
        image=reader.read()
        if image.isNull():raise ValueError('Selecciona una imagen PNG, JPEG o WebP valida.')
        raw=QByteArray(); buffer=QBuffer(raw); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer,'PNG'):raise ValueError('No se pudo preparar la imagen.')
        buffer.close()
        self.set_data({'name':path.name,'data':base64.b64encode(bytes(raw)).decode('ascii')}); self.changed()
    def choose(self):
        path,_=QFileDialog.getOpenFileName(self,ui_text('Cambiar imagen del proyecto'),'',ui_text('Imagenes (*.png *.jpg *.jpeg *.webp)'))
        if path:
            try:self.load_image(path)
            except (ValueError,OSError) as exc:QMessageBox.warning(self,ui_text('Imagen del proyecto'),str(exc))
    def remove(self):
        if self.payload is not None:self.set_data(None); self.changed()
