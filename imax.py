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
    
    def crear_puerta(self):
        self.encabezado(self.puerta,'Control de puerta — códigos QR de un solo uso')
        self.qr_input=self.campo(self.puerta,'ID numérico de entrada o código UUID')
        self.operador_id=self.campo(self.puerta,'ID del operador registrado')
        ctk.CTkButton(self.puerta,text='Validar entrada',command=self.validar).pack(anchor='w',padx=8,pady=10)
        ctk.CTkLabel(self.puerta,text='Registra primero un operador en la tabla operador (SQL).',justify='left').pack(anchor='w',padx=8)
    def crear_admin(self):
        self.encabezado(self.adm, 'Administración')
        frame = ctk.CTkScrollableFrame(self.adm)
        frame.pack(fill='both', expand=True, padx=8, pady=6)

        permiso = ctk.CTkFrame(frame)
        permiso.pack(fill='x', padx=6, pady=(4, 12))
        ctk.CTkLabel(permiso, text='ID de administrador para editar:').pack(
            side='left', padx=(10, 6), pady=10)

        self.entrada_admin_id = ctk.CTkEntry(permiso, width=115, placeholder_text='ID')
        self.entrada_admin_id.pack(side='left', padx=5)
        ctk.CTkButton(permiso, text='Verificar ID', width=110,
                      command=self.verificar_id_admin).pack(side='left', padx=5)
        self.estado_admin = ctk.CTkLabel(frame, text='')
        self.estado_admin.pack(anchor='w', padx=10, pady=(0, 8))
        grid=ctk.CTkFrame(frame,fg_color='transparent');grid.pack(fill='x')
        p=ctk.CTkFrame(grid);p.grid(row=0,column=0,padx=6,pady=6,sticky='nsew')
        self.p_titulo=self.campo(p,'Película: título');self.p_sinopsis=self.campo(p,'Sinopsis');self.p_clas=self.campo(p,'Clasificación','TP');self.p_dur=self.campo(p,'Duración (minutos)','120')
        boton_pelicula=ctk.CTkButton(p,text='Crear película',command=self.crear_pelicula)
        boton_pelicula.pack(fill='x',padx=8,pady=8)
        s=ctk.CTkFrame(grid);s.grid(row=0,column=1,padx=6,pady=6,sticky='nsew')
        self.s_nombre=self.campo(s,'Sala: nombre');self.s_ubi=self.campo(s,'Ubicación');self.s_filas=self.campo(s,'Filas (A, B, C...)','4');self.s_cols=self.campo(s,'Asientos por fila','6')
        boton_sala=ctk.CTkButton(s,text='Crear sala y asientos',command=self.crear_sala)
        boton_sala.pack(fill='x',padx=8,pady=8)
        f=ctk.CTkFrame(grid);f.grid(row=0,column=2,padx=6,pady=6,sticky='nsew')
        self.f_pelicula=self.campo(f,'ID de película');self.f_sala=self.campo(f,'ID de sala');self.f_fecha=self.campo(f,'Fecha y hora (AAAA-MM-DD HH:MM)','2026-12-01 19:00');self.f_precio=self.campo(f,'Precio base','3500')
        boton_funcion=ctk.CTkButton(f,text='Crear función',command=self.crear_funcion)
        boton_funcion.pack(fill='x',padx=8,pady=8)
        for i in range(3):grid.grid_columnconfigure(i,weight=1)
        self.campos_admin = [self.p_titulo,self.p_sinopsis,self.p_clas,self.p_dur,
                             self.s_nombre,self.s_ubi,self.s_filas,self.s_cols,
                             self.f_pelicula,self.f_sala,self.f_fecha,self.f_precio]
        self.botones_edicion_admin = [boton_pelicula,boton_sala,boton_funcion]
        ctk.CTkLabel(frame,text='Consulta de IDs existentes',font=ctk.CTkFont(weight='bold')).pack(anchor='w',padx=8,pady=(16,0))
        self.admin_datos=ctk.CTkTextbox(frame,height=190)
        self.admin_datos.pack(fill='x',padx=8,pady=5)
        self.admin_datos.configure(state='disabled')
        ctk.CTkButton(frame,text='Actualizar listado',command=self.listado_admin).pack(anchor='w',padx=8,pady=8)

    def crear_reportes(self):
        self.encabezado(self.repor, 'Reportes')
        permiso = ctk.CTkFrame(self.repor)
        permiso.pack(fill='x', padx=8, pady=7)
        ctk.CTkLabel(permiso, text='ID de administrador para consultar reportes:').pack(
            side='left', padx=8, pady=8)
        self.entrada_reportes_id = ctk.CTkEntry(permiso, width=115, placeholder_text='ID')
        self.entrada_reportes_id.pack(side='left', padx=5)
        ctk.CTkButton(permiso, text='Verificar ID',
                      command=self.verificar_id_reportes).pack(side='left', padx=5)
        self.estado_reportes = ctk.CTkLabel(self.repor, text='')
        self.estado_reportes.pack(anchor='w', padx=10, pady=5)
        self.boton_generar_reportes = ctk.CTkButton(
            self.repor, text='Generar reportes', command=self.reportes)
        self.boton_generar_reportes.pack(anchor='w', padx=8, pady=6)
        self.report_text = ctk.CTkTextbox(self.repor)
        self.report_text.pack(fill='both', expand=True, padx=8, pady=8)
        self.report_text.configure(state='disabled')
        self.establecer_acceso_reportes(False)
    def recargar(self):
        try:
            filas=self.consultar('''SELECT f.id_funcion,p.titulo,p.sinopsis,p.clasificacion,s.nombre,s.ubicacion,
              f.fecha_hora,f.precio_base,f.id_sala FROM funcion f JOIN pelicula p ON p.id_pelicula=f.id_pelicula
              JOIN sala s ON s.id_sala=f.id_sala WHERE f.activa AND p.activa AND f.fecha_hora>NOW() ORDER BY f.fecha_hora''')
            self.funciones={};self.imagenes=[]
            for w in self.cart_scroll.winfo_children():w.destroy()
            for idf,titulo,sinopsis,clasi,sala,ubi,fecha,precio,idsala in filas:
                clave=f'{idf} | {titulo} | {fecha:%d/%m %H:%M}'
                self.funciones[clave]=(idf,idsala,precio,fecha)
                bloque=ctk.CTkFrame(self.cart_scroll);bloque.pack(fill='x',padx=8,pady=7)
                
                texto=f'{titulo}\n{clasi}  •  {sala}  •  {ubi}\n{fecha:%d/%m/%Y %H:%M}  •  ₡{precio:,.0f}\n{sinopsis[:160]}'
                ctk.CTkLabel(bloque,text=texto,justify='left',wraplength=620).pack(side='left',padx=8)
            valores=list(self.funciones) or ['Sin funciones futuras']
            self.funcion_combo.configure(values=valores);self.funcion_combo.set(valores[0])
            if not filas:ctk.CTkLabel(self.cart_scroll,text='Aún no hay funciones futuras. Créalas en Administración.').pack(pady=18)
            self.ver_asientos()
            self.listado_admin()
        except Exception as e:self.error(e)

    def ir_a_venta(self,k):self.tabs.set('Comprar');self.funcion_combo.set(k);self.ver_asientos()
    def registrar_cliente(self):
        try:
            nom=self.cli_nombre.get().strip()
            if not nom:raise ValueError('Escribe el nombre.')
            r=self.consultar('INSERT INTO cliente(nombre,grupo_edad) VALUES (%s,%s) RETURNING id_cliente',(nom,self.cli_edad.get()))
            self.cliente_id.delete(0,'end');self.cliente_id.insert(0,str(r[0][0]));self.aviso('Cliente registrado: ID '+str(r[0][0]))
        except Exception as e:self.error(e)
    def datos_asiento(self,cur,idf,idsala):
        cur.execute('''SELECT a.numero,a.habilitado FROM asiento a WHERE a.id_sala=%s ORDER BY a.numero''',(idsala,))
        filas=cur.fetchall()
        cur.execute('''SELECT numero_asiento FROM bloqueo_asiento WHERE id_funcion=%s AND id_sala=%s AND estado='activo' AND vence_en>NOW()''',(idf,idsala))
        bloqueados={x[0] for x in cur.fetchall()}
        cs=columnas_entrada(cur)
        if {'id_funcion','id_sala','numero_asiento'} <= cs:
            filtro="AND estado IN ('emitida','usada')" if 'estado' in cs else ''
            cur.execute('SELECT numero_asiento FROM entrada WHERE id_funcion=%s AND id_sala=%s '+filtro,(idf,idsala))
            vendidos={x[0] for x in cur.fetchall()}
        else: vendidos=set()
        return [(numero,'deshabilitado' if not habilitado else 'vendido' if numero in vendidos else 'bloqueado' if numero in bloqueados else 'disponible') for numero,habilitado in filas]
=