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