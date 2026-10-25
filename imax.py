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
