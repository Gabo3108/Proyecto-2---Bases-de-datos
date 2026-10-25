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

    def bloquear_admin(self):
        self.admin_autorizado_id = None
        self.accesos['Administración'] = False
        self.entrada_admin_id.delete(0, 'end')

    def obtener_conexion(self):
        conn = psycopg2.connect(**self.conn_params)
        try:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO public;")
            return conn
        except Exception:
            conn.close()
            raise

    def ejecutar_consulta(self, sql, params=None, fetch=False):
        conn = None
        try:
            conn = self.obtener_conexion()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                resultado = cur.fetchall() if fetch else None
            conn.commit()
            return resultado
        except Exception:
            if conn is not None:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()

    def consultar(self, sql, params=None):
        return self.ejecutar_consulta(sql, params, fetch=True)

    @contextmanager
    def conexion_transaccional(self):

        conn = self.obtener_conexion()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    def error(self,ex): messagebox.showerror('IMAX — Error',formato_error(ex))
    def aviso(self,txt): messagebox.showinfo('IMAX',txt)
    def campo(self,parent,titulo,default=''):
        ctk.CTkLabel(parent,text=titulo).pack(anchor='w',padx=8)
        e=ctk.CTkEntry(parent);e.pack(fill='x',padx=8,pady=(0,8))
        if default: e.insert(0,default)
        return e

    def encabezado(self,p,t): ctk.CTkLabel(p,text=t,font=ctk.CTkFont(size=19,weight='bold')).pack(anchor='w',padx=10,pady=9)
    def crear_cartelera(self):
        self.encabezado(self.cart,'Cartelera')
        self.cart_scroll=ctk.CTkScrollableFrame(self.cart)
        self.cart_scroll.pack(fill='both',expand=True,padx=8,pady=6)

    def crear_venta(self):
        self.encabezado(self.venta,'Comprar una entrada — un asiento por compra')
        cuerpo=ctk.CTkFrame(self.venta);cuerpo.pack(fill='both',expand=True,padx=8)
        left=ctk.CTkScrollableFrame(cuerpo,width=290);left.pack(side='left',fill='y',padx=7,pady=7)
        self.cli_nombre=self.campo(left,'Nombre del cliente nuevo')
        self.cli_edad=ctk.CTkOptionMenu(left,values=['adulto','niño','mayor','estudiante']);self.cli_edad.pack(fill='x',padx=8,pady=5)
        ctk.CTkButton(left,text='Registrar cliente',command=self.registrar_cliente).pack(fill='x',padx=8,pady=7)
        self.cliente_id=self.campo(left,'ID de cliente registrado')
        ctk.CTkLabel(left,text='Función').pack(anchor='w',padx=8)
        self.funcion_combo=ctk.CTkComboBox(left,values=['Sin funciones'],command=lambda _:self.ver_asientos())
        self.funcion_combo.pack(fill='x',padx=8,pady=7)
        ctk.CTkLabel(left,text='Asiento').pack(anchor='w',padx=8)
        self.asiento_combo=ctk.CTkComboBox(left,values=['Sin asientos'],command=lambda _:self.dibujar_mapa());self.asiento_combo.pack(fill='x',padx=8,pady=7)
        ctk.CTkButton(left,text='Actualizar mapa',command=self.ver_asientos).pack(fill='x',padx=8,pady=5)
        ctk.CTkButton(left,text='Pagar',command=lambda:self.comprar(True)).pack(fill='x',padx=8,pady=5)
        self.map_frame=ctk.CTkScrollableFrame(cuerpo);self.map_frame.pack(side='left',fill='both',expand=True,padx=7,pady=7)
        self.map_label=ctk.CTkLabel(self.map_frame,text='Seleccione una función para ver el mapa')
        self.map_label.pack(padx=8,pady=10)
    
