import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from suite_license import machine_code, installed_license, install_license, TrialExpired, ClockInconsistency


def activate():
    import plus_runtime
    import ui_i18n
    ui_i18n.install()
    def tr(value):
        return ui_i18n.english(value) if ui_i18n._language == 'en' else value
    localized=[]
    def label(parent, **kwargs):
        source=kwargs.get('text','');kwargs['text']=tr(source)
        widget=ttk.Label(parent, **kwargs);localized.append((widget,source));return widget
    def button(parent, **kwargs):
        source=kwargs.get('text','');kwargs['text']=tr(source)
        widget=ttk.Button(parent, **kwargs);localized.append((widget,source));return widget
    expired = ''
    try:
        installed_license()
        return True
    except (TrialExpired, ClockInconsistency, ValueError) as exc:
        expired = str(exc)
    except Exception:
        pass
    from suite_license_public import PUBLIC_KEY
    if not PUBLIC_KEY:
        raise RuntimeError('Primero ejecuta preparar_licencias_pro.py antes de distribuir o compilar.')
    root = tk.Tk()
    root.title('Activar · Eleuthera Professional Plus')
    root.configure(bg='#202328')
    root.resizable(False, False)
    root.option_add('*Font', ('Segoe UI', 10))
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('TFrame', background='#202328')
    style.configure('TLabel', background='#202328', foreground='#edf0f4')
    style.configure('TButton', padding=10, background='#17616a', foreground='#fffaf5')
    style.map('TButton', background=[('active', '#207580'), ('pressed', '#20535b')])
    try:
        root.iconbitmap(str(Path(__file__).parent / 'assets' / 'eleuthera-clapperboard.ico'))
    except Exception:
        pass
    frame = ttk.Frame(root, padding=26)
    frame.pack()
    label(frame, text='Eleuthera Cinema Suite', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
    label(frame, text='Eleuthera Professional Plus - Activación offline').pack(anchor='w', pady=(8, 8))
    label(frame, text='Admite licencia perpetua o prueba de 72 horas desde la primera activación.').pack(anchor='w', pady=(0, 20))
    if expired:
        label(frame, text=expired, wraplength=500).pack(anchor='w', pady=(0, 12))
    label(frame, text='1. Envía este código ECPP- a Francisco Contreras.\n2. Recibirás una licencia de prueba o perpetua.\n3. Importa el archivo .ecplic.').pack(anchor='w')
    try:
        code = machine_code()
    except Exception as exc:
        messagebox.showerror('Identificación del equipo', str(exc), parent=root)
        root.destroy()
        return False
    field = ttk.Entry(frame, width=72)
    field.insert(0, code)
    field.configure(state='readonly')
    field.pack(fill='x', pady=14)
    def copy():
        root.clipboard_clear()
        root.clipboard_append(code)
        root.update()
    button(frame, text='Copiar código del equipo', command=copy).pack(fill='x')
    accepted = [False]
    def load():
        filename = filedialog.askopenfilename(parent=root, title=tr('Seleccionar licencia'), filetypes=[(tr('Licencia Eleuthera Professional Plus'), '*.ecplic'), (tr('Todos'), '*.*')])
        if not filename:
            return
        try:
            with open(filename, 'rb') as source:
                install_license(source.read(16385))
        except Exception as exc:
            messagebox.showerror(tr('No se pudo activar'), str(exc), parent=root)
            return
        try:
            payload = installed_license()
            if payload.get('license_type') == 'trial':
                detail = 'Prueba activada: 72 horas desde esta primera activación.'
            else:
                detail = 'Licencia perpetua activada correctamente.'
            messagebox.showinfo('Activación completada', detail, parent=root)
        except Exception:
            pass
        accepted[0] = True
        root.destroy()
    button(frame, text='Importar licencia', command=load).pack(fill='x', pady=(10, 20))
    label(frame, text='Team Eleuthera\nFrancisco Contreras', font=('Segoe UI', 9)).pack(anchor='w')
    root.mainloop()
    return accepted[0]
