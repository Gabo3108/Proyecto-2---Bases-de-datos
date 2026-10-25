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
            ctk.CTkLabel(
                        self.sidebar_frame,
                        text="Compra de entradas y gestión administrativa",
                        font=ctk.CTkFont(size=11),
                        wraplength=190,
                        justify="left"
                    ).grid(row=1, column=0, padx=20, pady=(0, 25), sticky="w")
            self.botones_nav = {}
            for i, (nombre, icono) in enumerate([
                ("Clientes", "👥"),
                ("Administración", "📋"),
            ], start=2):
                    btn = ctk.CTkButton(
                        self.sidebar_frame, text=f"{icono}  {nombre}",
                        anchor="w", fg_color="transparent",
                        command=lambda n=nombre: self.seleccionar_modulo(n)
                    )
                    btn.grid(row=i, column=0, padx=15, pady=5, sticky="ew")
                    self.botones_nav[nombre] = btn

                    ctk.CTkButton(
                                self.sidebar_frame,
                                text="🔄  Recargar datos",
                                command=self.actualizar_todas_las_tablas
                            ).grid(row=5, column=0, padx=15, pady=(20, 5), sticky="ew")
                    ctk.CTkLabel(self.sidebar_frame, text="APARIENCIA", font=ctk.CTkFont(size=11, weight="bold")).grid(
                                row=11, column=0, padx=20, pady=(10, 5), sticky="w"
                            )
                    self.option_mode = ctk.CTkOptionMenu(
                                self.sidebar_frame,
                                values=["System", "Dark", "Light"],
                                command=ctk.set_appearance_mode
                            )
                    self.option_mode.set("System")
                    self.option_mode.grid(row=12, column=0, padx=15, pady=(0, 25), sticky="ew")

    def crear_area_principal(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self.main_container, command=self.al_cambiar_pestana)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        self.tab_dashboard = self.tabview.add("Dashboard")
        self.tab_funciones = self.tabview.add("Cartelera")
        self.tab_cliente = self.tabview.add("Clientes")
        self.tab_entrada = self.tabview.add("Entradas")

        self.configurar_pestana_dashboard()
        self.configurar_pestana_funciones()
        self.configurar_pestana_cliente()
        self.configurar_pestana_entrada()

    def al_cambiar_pestana(self):
        nombre = self.tabview.get()
        if nombre in self.botones_nav:
            for modulo, boton in self.botones_nav.items():
                boton.configure(fg_color=("gray75", "gray25") if modulo == nombre else "transparent")

    def crear_encabezado(self, parent, titulo, descripcion):
        ctk.CTkLabel(parent, text=titulo, font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", padx=15, pady=(15, 0))
        ctk.CTkLabel(parent, text=descripcion, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=15, pady=(0, 12))

        # ========= ADMINISTRACIÓN ============
    def configurar_pestana_dashboard(self):
        self.crear_encabezado(self.tab_dashboard, "Panel de gestión administrativa")

        cuerpo = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=5)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)

        tabla_frame = ctk.CTkFrame(cuerpo)
        tabla_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form = ctk.CTkScrollableFrame(cuerpo, width=300)
        form.grid(row=0, column=1, sticky="nsew")
        self.tree_usuarios = self.crear_treeview(
            tabla_frame, ("ID", "Función", "Asiento", "Día", "Hora"), (70, 160, 160, 160, 80))
        self.tree_usuarios.bind("<<TreeviewSelect>>", self.cargar_usuario_seleccionado)

        ctk.CTkLabel(form, text="Entrada a comprar", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 15))
        self.entry_nombre = ctk.CTkEntry(form, placeholder_text="Función")
        self.entry_nombre.pack(fill="x", padx=10, pady=6)
        self.entry_apellido = ctk.CTkEntry(form, placeholder_text="Asiento")
        self.entry_apellido.pack(fill="x", padx=10, pady=6)

        self.switch_usuario_activo = ctk.CTkSwitch(form, text="Usuario activo")
        self.switch_usuario_activo.select()
        self.switch_usuario_activo.pack(anchor="w", padx=12, pady=10)

        ctk.CTkButton(form, text="➕ Registrar usuario", command=self.agregar_usuario).pack(fill="x", padx=10, pady=(12, 5))
        ctk.CTkButton(form, text="💾 Actualizar seleccionado", command=self.actualizar_usuario).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🧹 Nuevo / Limpiar", command=self.limpiar_form_usuario, fg_color="gray").pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🗑️ Eliminar seleccionado", command=self.eliminar_usuario, fg_color="#b33939", hover_color="#8f2d2d").pack(fill="x", padx=10, pady=5)

        # =================== CLIENTES ========================
    def configurar_pestana_cliente(self):
        self.crear_encabezado(self.tab_cliente, "Lista de Clientes")      
        self.entry_idcliente = ctk.CTKEntry(self.tab_cliente, placeholder_text = "ID")
        self.entry_idcliente.pack(padx = 10, pady = 5)
                
        self.entry_nombre = ctk.CTKEntry(self.tab_cliente, placeholder_text = "Nombre")
        self.entry_nombre.pack(padx = 10, pady = 5)
        
        self.combo_edad = ctk.CTKComboBox(self.tab_cliente, values = ["Adulto","Niño","Mayor","Estudiante"], state = "readonly")
        self.combo_edad.pack(padx = 10, pady = 5)
        
        ctk.CTKButton(self.tab_cliente, text = "Añadir cliente", command = self.agregar_cliente).pack(padx = 10, pady = 10)

    def agregar_cliente(self):
        id_cliente = self.entry_idcliente.get().strip()
        nombre = self.entry_nombre.get().strip()
        grupo_edad = self.entry_edad.get().strip()
        if not id_cliente or not nombre or not grupo_edad:
            return messagebox.showwarning("Datos incompletos")
        try:
            self.ejecutar_consulta(
                """
                INSERT INTO cliente (id_cliente, nombre, grupo_edad)
                VALUES (%s, %s, %s)"""
                (id_cliente, nombre, grupo_edad)
                )
        except:
            messagebox.showerror("Error con datos")
    #===================== COMPRA / ENTRADAS ======================
    def configurar_pestana_entrada(self):
        self.crear_encabezado(self.tab_entrada, "Compra de entradas para ver funciones")
        self.combo_funcion = ctk.CTkComboBox(self.tab_entrada, values =["Seleccione la función que desea ver"],state = "readonly")
        self.combo_función.pack(padx = 10, pady = 5)
        self.frame_sala = ctk.CTkFrame(self.tab_entrada)    

        
