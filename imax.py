import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime, date

import customtkinter as ctk
import psycopg2

try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None
    

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
class cinesimax(ctk.CTk):
    
    def __init__(self):
        super().__init__()
        self.title("Cines imax")
        self.geometry("1280x760")
        self.minsize(1050, 650)

        self.conn_params = {
            "dbname": "cines_imax",
            "user": "postgres",
            "password": "caca2",
            "host": "localhost",
            "port": "5432",
        }

        self.usuarios_combo = {}
        self.categorias_combo = {}
        self.categorias_padre_combo = {}
        self.eventos_combo = {}
        self.usuarios_disponibilidad_combo = {}
        self.tipo_disponibilidad_combo = {}

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.crear_sidebar()
        self.crear_area_principal()
        self.configurar_estilos()

        self.actualizar_todas_las_tablas()

        if DateEntry is None:
            self.after(500, lambda: messagebox.showwarning(
                "",
                "Para usar los selectores de fecha instala:\n\npip install tkcalendar"
            ))
    def obtener_conexion(self):
            conn = psycopg2.connect(**self.conn_params)
            with conn.cursor() as cur:
                cur.execute("SET search_path TO prototipo, public;")
            return conn
    
    def ejecutar_consulta(self, sql, params=None, fetch=False):
        conn = None
        try:
            conn = self.obtener_conexion()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() if fetch else None
            conn.commit()
            return rows
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    def configurar_estilos(self):
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure("Treeview", rowheight=30, font=("Arial", 10))
            style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
    
    def crear_treeview(self, parent, columnas, widths):
        contenedor = ctk.CTkFrame(parent, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        tree = ttk.Treeview(contenedor, columns=columnas, show="headings")
        for col, width in zip(columnas, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="center")
        scroll_y = ttk.Scrollbar(contenedor, orient="vertical", command=tree.yview)
        scroll_x = ttk.Scrollbar(contenedor, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)
        return tree
    
    def seleccionar_modulo(self, nombre):
            self.tabview.set(nombre)
            for modulo, boton in self.botones_nav.items():
                boton.configure(fg_color=("gray75", "gray25") if modulo == nombre else "transparent")
    def crear_sidebar(self):
            self.sidebar_frame = ctk.CTkFrame(self, width=235, corner_radius=0)
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self.sidebar_frame.grid_propagate(False)
            self.sidebar_frame.grid_rowconfigure(10, weight=1)
        ctk.CTkLabel(
                    self.sidebar_frame,
                    text="Cines IMAX",
                    font=ctk.CTkFont(size=22, weight="bold")
                ).grid(row=0, column=0, padx=20, pady=(28, 5), sticky="w")