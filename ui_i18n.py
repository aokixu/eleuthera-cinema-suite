"""Runtime UI localization with canonical Spanish values for application logic.

Only explicitly marked authored UI strings are translated. Editor text and project
values remain ordinary strings. Qt getters return canonical values where the app
uses visible labels as keys; Qt itself paints the localized labels.
"""
import weakref
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid
from ui_catalog import EN

_language='es'
_installed=False
_records=[]
ROLE=int(QtCore.Qt.ItemDataRole.UserRole)+1740
_settings=lambda: QtCore.QSettings('Equipo Eleuthera','Eleuthera UI')


def english(text):
    if text in EN:return EN[text]
    stripped=text.strip()
    if stripped in EN:return text.replace(stripped,EN[stripped],1)
    for suffix in ('…','...',':'):
        if stripped.endswith(suffix) and stripped[:-len(suffix)] in EN:
            return text.replace(stripped,EN[stripped[:-len(suffix)]]+suffix,1)
    return text


class UiText(str):
    def __new__(cls, source, parts=None):
        obj=super().__new__(cls,source);obj.parts=parts;return obj
    def display(self):
        if _language=='es':return str(self)
        if self.parts is not None:return ''.join(display(part) for part in self.parts)
        return english(str(self))
    def __add__(self,other):return ui_join([self,other])
    def __radd__(self,other):return ui_join([other,self])
    def format(self,*args,**kwargs):
        # Values remain original; only the authored format template is localized.
        value=str(self).format(*args,**kwargs)
        out=UiText(value);out.parts=None
        out._format=(self,args,kwargs)
        return out


def ui_text(value):return value if isinstance(value,UiText) else UiText(value)
def ui_join(parts):return UiText(''.join(str(p) for p in parts),parts)
def display(value):
    if not isinstance(value,UiText):return value
    if hasattr(value,'_format'):
        template,args,kwargs=value._format
        return display(template).format(*args,**kwargs)
    return value.display()


def _remember(obj,key,source,setter):
    records=getattr(obj,'_ui_sources',None)
    if records is None and not isinstance(source,UiText):return
    if records is None:
        records={};obj._ui_sources=records
        _records.append(obj)
    if isinstance(source,UiText):records[key]=(source,setter)
    else:records.pop(key,None)


def _property(cls,setter_name,getter_name):
    setter=getattr(cls,setter_name);getter=getattr(cls,getter_name)
    def set_value(obj,value):
        _remember(obj,setter_name,value,lambda o,v:setter(o,v))
        result=setter(obj,display(value))
        if cls is QtWidgets.QMenu and setter_name=='setTitle':obj.menuAction().setText(value)
        return result
    def get_value(obj):
        record=getattr(obj,'_ui_sources',{}).get(setter_name)
        return record[0] if record else getter(obj)
    setattr(cls,setter_name,set_value);setattr(cls,getter_name,get_value)


def _constructor(cls,setter_name):
    original=cls.__init__
    def init(obj,*args,**kwargs):
        original(obj,*[display(v) for v in args],**{k:display(v) for k,v in kwargs.items()})
        marked=next((v for v in args if isinstance(v,UiText)),None)
        if marked is None:marked=kwargs.get('text')
        if isinstance(marked,UiText):getattr(obj,setter_name)(marked)
    cls.__init__=init


def install():
    global _installed,_language
    if _installed:return
    _installed=True;_language=str(_settings().value('language','es'))
    if _language not in ('es','en'):_language='es'
    for cls,setter,getter in [
        (QtWidgets.QWidget,'setWindowTitle','windowTitle'),
        (QtWidgets.QWidget,'setToolTip','toolTip'),
        (QtWidgets.QWidget,'setStatusTip','statusTip'),
        (QtWidgets.QLabel,'setText','text'),
        (QtWidgets.QAbstractButton,'setText','text'),
        (QtWidgets.QLineEdit,'setPlaceholderText','placeholderText'),
        (QtWidgets.QTextEdit,'setPlaceholderText','placeholderText'),
        (QtWidgets.QPlainTextEdit,'setPlaceholderText','placeholderText'),
        (QtWidgets.QGroupBox,'setTitle','title'),
        (QtGui.QAction,'setText','text'),
        (QtGui.QAction,'setToolTip','toolTip'),
        (QtGui.QAction,'setStatusTip','statusTip'),
        (QtWidgets.QMenu,'setTitle','title'),
        (QtWidgets.QTableWidgetItem,'setText','text'),
        (QtWidgets.QListWidgetItem,'setText','text'),
        (QtWidgets.QGraphicsSimpleTextItem,'setText','text')]:
        _property(cls,setter,getter)
    for cls,setter in [(QtWidgets.QLabel,'setText'),(QtWidgets.QPushButton,'setText'),
                        (QtWidgets.QCheckBox,'setText'),(QtWidgets.QRadioButton,'setText'),
                        (QtWidgets.QGroupBox,'setTitle'),(QtGui.QAction,'setText'),
                        (QtWidgets.QMenu,'setTitle'),(QtWidgets.QTableWidgetItem,'setText'),
                        (QtWidgets.QListWidgetItem,'setText'),(QtWidgets.QGraphicsSimpleTextItem,'setText')]:
        _constructor(cls,setter)
    _install_combos();_install_containers();_install_dialogs()
    original_message=QtWidgets.QStatusBar.showMessage
    QtWidgets.QStatusBar.showMessage=lambda obj,text,*args:original_message(obj,display(text),*args)
    original_draw=QtGui.QPainter.drawText
    QtGui.QPainter.drawText=lambda obj,*args:original_draw(obj,*[display(v) for v in args])


def _install_combos():
    cls=QtWidgets.QComboBox
    add=cls.addItem;insert=cls.insertItem;set_text=cls.setItemText
    current=cls.currentText;item=cls.itemText;find=cls.findText;select=cls.setCurrentText
    def register(obj,index,text):
        if isinstance(text,UiText):
            sources=getattr(obj,'_ui_combo_sources',{})
            token=max(sources,default=0)+1;sources[token]=text;obj._ui_combo_sources=sources
            obj.setItemData(index,token,ROLE)
            _remember(obj,'combo',ui_text(''),lambda o,v:None)
    def add_item(obj,*args,**kwargs):
        # addItem supports both (text, data) and (icon, text, data).
        text=next((v for v in args if isinstance(v,str)),kwargs.get('text',''))
        add(obj,*[display(v) if isinstance(v,UiText) else v for v in args],**kwargs)
        register(obj,obj.count()-1,text)
    def insert_item(obj,index,*args,**kwargs):
        text=next((v for v in args if isinstance(v,str)),kwargs.get('text',''))
        insert(obj,index,*[display(v) if isinstance(v,UiText) else v for v in args],**kwargs)
        register(obj,max(0,min(index,obj.count()-1)),text)
    def set_item(obj,index,text):
        obj.setItemData(index,None,ROLE);set_text(obj,index,display(text));register(obj,index,text)
    def item_text(obj,index):return getattr(obj,'_ui_combo_sources',{}).get(obj.itemData(index,ROLE)) or item(obj,index)
    def current_text(obj):
        index=obj.currentIndex();source=getattr(obj,'_ui_combo_sources',{}).get(obj.itemData(index,ROLE)) if index>=0 else None
        if source is not None and current(obj)==display(source):return source
        return current(obj)
    def find_text(obj,text,*args):
        for index in range(obj.count()):
            if item_text(obj,index)==text:return index
        return find(obj,text,*args)
    def select_text(obj,text):
        index=find_text(obj,text)
        if index>=0:obj.setCurrentIndex(index)
        else:select(obj,text)
    cls.addItem=add_item;cls.insertItem=insert_item;cls.setItemText=set_item
    cls.addItems=lambda obj,values:[add_item(obj,value) for value in values] and None
    cls.insertItems=lambda obj,index,values:[insert_item(obj,index+i,value) for i,value in enumerate(values)] and None
    cls.currentText=current_text;cls.itemText=item_text;cls.findText=find_text;cls.setCurrentText=select_text
    cls._localized_set_item=set_text
    signal=cls.currentTextChanged
    class SignalProxy:
        def __init__(self,obj):self.obj=obj;self.bound=obj.__dict__.get('_ui_text_signal') or signal.__get__(obj,cls)
        def connect(self,slot,*args,**kwargs):
            wrapper=lambda _text:slot(self.obj.currentText())
            links=getattr(self.obj,'_ui_connections',[]);links.append((slot,wrapper));self.obj._ui_connections=links
            return self.bound.connect(wrapper,*args,**kwargs)
        def disconnect(self,slot=None):
            if slot is None:return self.bound.disconnect()
            links=getattr(self.obj,'_ui_connections',[])
            wrappers=[wrapper for original,wrapper in links if original==slot]
            for wrapper in wrappers:self.bound.disconnect(wrapper)
        def emit(self,text):return self.bound.emit(text)
    cls.currentTextChanged=property(lambda obj:SignalProxy(obj),lambda obj,value:obj.__dict__.__setitem__('_ui_text_signal',value))


def _install_containers():
    for cls,method in [(QtWidgets.QMenuBar,'addMenu'),(QtWidgets.QMenu,'addMenu'),
                       (QtWidgets.QMenu,'addAction'),(QtWidgets.QToolBar,'addAction')]:
        original=getattr(cls,method)
        def wrapper(obj,*args,_original=original,_method=method,**kwargs):
            result=_original(obj,*[display(v) for v in args],**kwargs)
            source=next((v for v in args if isinstance(v,UiText)),None)
            if source is not None and result is not None:
                getattr(result,'setTitle' if _method=='addMenu' else 'setText')(source)
            return result
        setattr(cls,method,wrapper)
    cls=QtWidgets.QTabWidget;original=cls.addTab;set_tab=cls.setTabText;get_tab=cls.tabText
    def add_tab(obj,*args,_original=original):
        index=_original(obj,*[display(v) for v in args])
        text=args[-1]
        if isinstance(text,UiText):
            obj.widget(index)._ui_tab_source=text
            _remember(obj,'tabs',ui_text(''),lambda o,v:None)
        return index
    def set_tab_text(obj,index,text):
        if obj.widget(index):obj.widget(index)._ui_tab_source=text if isinstance(text,UiText) else None
        set_tab(obj,index,display(text));_remember(obj,'tabs',ui_text(''),lambda o,v:None)
    cls.addTab=add_tab;cls.setTabText=set_tab_text
    cls.tabText=lambda obj,index:getattr(obj.widget(index),'_ui_tab_source',None) or get_tab(obj,index)
    cls._localized_set_tab=set_tab
    for name,item_get in [('setHorizontalHeaderLabels','horizontalHeaderItem'),('setVerticalHeaderLabels','verticalHeaderItem')]:
        original=getattr(QtWidgets.QTableWidget,name)
        def set_headers(obj,labels,_original=original,_get=item_get):
            labels=list(labels);_original(obj,[display(v) for v in labels])
            for i,text in enumerate(labels):
                cell=getattr(obj,_get)(i)
                if cell is not None and isinstance(text,UiText):cell.setText(text)
        setattr(QtWidgets.QTableWidget,name,set_headers)
    original=QtWidgets.QFormLayout.addRow
    def add_row(obj,*args):
        original(obj,*[display(v) for v in args])
        if args and isinstance(args[0],UiText):
            item=obj.itemAt(obj.rowCount()-1,QtWidgets.QFormLayout.ItemRole.LabelRole)
            if item and isinstance(item.widget(),QtWidgets.QLabel):item.widget().setText(args[0])
    QtWidgets.QFormLayout.addRow=add_row


def _install_dialogs():
    for cls,names in [(QtWidgets.QMessageBox,('information','warning','critical','question','about')),
                      (QtWidgets.QFileDialog,('getOpenFileName','getOpenFileNames','getSaveFileName','getExistingDirectory')),
                      (QtWidgets.QInputDialog,('getText','getMultiLineText','getInt','getDouble','getItem'))]:
        for name in names:
            original=getattr(cls,name)
            def dialog(*args,_original=original,_name=name,**kwargs):
                convert=lambda v:[display(x) for x in v] if isinstance(v,(list,tuple)) else display(v)
                result=_original(*[convert(v) for v in args],**{k:convert(v) for k,v in kwargs.items()})
                if _name=='getItem' and isinstance(result,tuple):
                    choices=args[3] if len(args)>3 else kwargs.get('items',[])
                    canonical=next((str(v) for v in choices if display(v)==result[0]),result[0])
                    return canonical,result[1]
                return result
            setattr(cls,name,staticmethod(dialog))


def set_language(code,persist=True):
    global _language,_records
    if code not in ('es','en'):raise ValueError(code)
    _language=code
    if persist:_settings().setValue('language',code)
    live=[]
    for obj in _records:
        if not isValid(obj):continue
        live.append(obj)
        blocker=QtCore.QSignalBlocker(obj) if isinstance(obj,QtCore.QObject) else None
        for key,(source,setter) in list(getattr(obj,'_ui_sources',{}).items()):
            if key=='combo':
                for i in range(obj.count()):
                    text=getattr(obj,'_ui_combo_sources',{}).get(obj.itemData(i,ROLE))
                    if text is not None:obj._localized_set_item(i,display(text))
            elif key=='tabs':
                for i in range(obj.count()):
                    text=getattr(obj.widget(i),'_ui_tab_source',None)
                    if text is not None:obj._localized_set_tab(i,display(text))
            else:setter(obj,display(source))
        del blocker
    _records=live
    qt=QtWidgets.QApplication.instance()
    if qt:
        translator=getattr(qt,'_ui_qt_translator',None)
        if translator:qt.removeTranslator(translator)
        translator=QtCore.QTranslator(qt)
        if code=='es':
            translator.load('qtbase_es',QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.TranslationsPath))
            qt.installTranslator(translator)
        qt._ui_qt_translator=translator
        QtCore.QLocale.setDefault(QtCore.QLocale('es_ES' if code=='es' else 'en_US'))
        for window in qt.topLevelWidgets():window.update()


def add_language_menu(window):
    install()
    menu=window.menuBar().addMenu(ui_text('Idioma / Language'))
    group=QtGui.QActionGroup(window);group.setExclusive(True)
    for code,label in [('es','Español'),('en','English')]:
        action=QtGui.QAction(label,group);action.setCheckable(True);action.setChecked(_language==code)
        action.triggered.connect(lambda checked=False,c=code:set_language(c))
        menu.addAction(action)
    window.language_menu=menu;window.language_actions=group
    set_language(_language,persist=False)
