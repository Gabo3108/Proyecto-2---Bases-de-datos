import os
import re
import uuid
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk
import psycopg2
from PIL import Image, ImageDraw, ImageFont
import qrcode

BASE = Path(__file__).resolve().parent
POSTERS = BASE / 'posters'
POSTERS.mkdir(exist_ok=True)
ctk.set_appearance_mode('System')
ctk.set_default_color_theme('blue')

def columnas_entrada(cur):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='entrada'")
    return {r[0] for r in cur.fetchall()}
def formato_error(ex):
    return (getattr(ex, 'pgerror', None) or str(ex)).strip()[:950]

class IMAX(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.conn_params = {
            "dbname": os.getenv("DB_NAME", "cines_imax"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "caca2"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
        }
        self.title('Cines IMAX')
        self.geometry('1130x785'); self.minsize(900,660)
        self.funciones={}; self.asientos=[]; self.seleccion=None
        self.imagenes=[]
        self.ultimo_tab='Cartelera'
        self._cambiando_tab=False
        self.accesos={'Administración': False, 'Reportes': False}
        self.admin_autorizado_id = None
        self.reportes_autorizado_id = None
        barra=ctk.CTkFrame(self); barra.pack(fill='x',padx=14,pady=10)
        ctk.CTkLabel(barra,text='Cines IMAX',font=ctk.CTkFont(size=22,weight='bold')).pack(side='left',padx=12)
        ctk.CTkButton(barra,text='Actualizar',width=110,command=self.recargar).pack(side='right',padx=8)
        self.tabs=ctk.CTkTabview(self); self.tabs.pack(fill='both',expand=True,padx=14,pady=(0,14))
        self.cart=self.tabs.add('Cartelera'); self.venta=self.tabs.add('Comprar'); self.puerta=self.tabs.add('Validar QR'); self.adm=self.tabs.add('Administración'); self.repor=self.tabs.add('Reportes')
        self.tabs.configure(command=self.al_cambiar_tab)
        self.crear_cartelera();self.crear_venta();self.crear_puerta();self.crear_admin();self.crear_reportes()
        self.after(150,self.recargar)

            #accesos
    def requerir_acceso(self, seccion):
        if self.accesos.get(seccion, False):
            return True
        messagebox.showwarning('Acceso restringido',
            'Verifique un ID de administrador antes de generar reportes.')
        return False
    def al_cambiar_tab(self):
        self.ultimo_tab = self.tabs.get()

    def establecer_acceso_reportes(self, habilitar):
            self.boton_generar_reportes.configure(state='normal' if habilitar else 'deshabilitado')
            self.estado_reportes.configure(text=(
                f'Reportes habilitados: administrador {self.reportes_autorizado_id}'
                if habilitar else 'Introduzca un ID de administrador válido para consultar reportes.'))

    def verificar_id_reportes(self):
        valor = self.entrada_reportes_id.get().strip()
        if not valor.isdigit():
            self.bloquear_reportes()
            messagebox.showwarning('Permiso de reportes', 'Introduzca un ID numérico.')
            return
        try:
            filas = self.consultar('SELECT id_admin FROM administrador WHERE id_admin = %s',
                                  (int(valor),))
            if not filas:
                self.bloquear_reportes()
                messagebox.showerror('Acceso denegado', 'No existe un administrador con ese ID.')
                return
            self.reportes_autorizado_id = int(valor)
            self.accesos['Reportes'] = True
            self.establecer_acceso_reportes(True)
            self.aviso(f'Reportes habilitados para administrador #{valor}.')
        except Exception as ex:
            self.bloquear_reportes()
            self.error(ex)

    def bloquear_reportes(self):
            self.reportes_autorizado_id = None
            self.accesos['Reportes'] = False
            self.establecer_acceso_reportes(False)
            self.entrada_reportes_id.delete(0, 'end')
            self.report_text.configure(state='normal')
            self.report_text.delete('1.0', 'end')
            self.report_text.configure(state='deshabilitado')

    def verificar_id_admin(self):
        valor = self.entrada_admin_id.get().strip()
        if not valor.isdigit():
            messagebox.showwarning('Permiso de administrador', 'Introduzca un ID numérico.')
            return
        try:
            filas = self.consultar(
                'SELECT id_admin FROM administrador WHERE id_admin = %s',
                (int(valor),)
            )
            if not filas:
                self.bloquear_admin()
                messagebox.showerror('Acceso denegado', 'No existe un administrador con ese ID.')
                return
            self.admin_autorizado_id = int(valor)
            self.accesos['Administración'] = True
            self.aviso(f'Edición habilitada para administrador #{valor}.')
        except Exception as ex:
            self.bloquear_admin()
            self.error(ex)