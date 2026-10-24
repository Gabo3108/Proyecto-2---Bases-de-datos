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
ctk.set_default_color_theme("green")
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
