# ─────────────────────────────────────────────────────────────────────────────
# ESTADISTICAS TIENDA FELO
# App de escritorio independiente — lee los logs y muestra el dashboard.
# Requiere: pip install reportlab
# ─────────────────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import tempfile
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# ── ReportLab ────────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# ── Google Drive ──────────────────────────────────────────────────────────────
try:
    import drive_manager as drive
    USAR_DRIVE = True
except ImportError:
    USAR_DRIVE = False

# Carpeta local donde se sincronizan los archivos de Drive
CARPETA_SYNC = Path(tempfile.gettempdir()) / "felo_stats_sync"

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE RUTAS
# Si Drive está disponible, los archivos se sincronizan a CARPETA_SYNC.
# Si no, se leen desde CARPETA_LOGS (modo local).
# ─────────────────────────────────────────────────────────────────────────────
CARPETA_LOGS = Path(".")          # ← solo se usa si no hay Drive

def _carpeta_activa():
    return CARPETA_SYNC if USAR_DRIVE else CARPETA_LOGS

LOG_BUSQUEDAS = lambda: _carpeta_activa() / "logs_busquedas.txt"
LOG_CARRITO   = lambda: _carpeta_activa() / "logs_carrito.txt"
LOG_PEDIDOS   = lambda: _carpeta_activa() / "logs_pedidos.txt"
LOG_PRODUCTOS = lambda: _carpeta_activa() / "logs_productos.txt"
LOG_SESIONES  = lambda: _carpeta_activa() / "logs_sesiones.txt"
USUARIOS_JSON = lambda: _carpeta_activa() / "usuarios.json"

# ─────────────────────────────────────────────────────────────────────────────
# PALETA DE COLORES
# ─────────────────────────────────────────────────────────────────────────────
COLOR_FONDO      = "#F5F5F0"
COLOR_PANEL      = "#FFFFFF"
COLOR_ACENTO     = "#1B6CA8"
COLOR_ACENTO2    = "#28A745"
COLOR_TEXTO      = "#1A1A1A"
COLOR_MUTED      = "#6B6B6B"
COLOR_BORDE      = "#DCDCDC"
COLOR_CABECERA   = "#1B6CA8"
COLOR_CABECERA_T = "#FFFFFF"
COLOR_FILA_PAR   = "#F0F4F8"
COLOR_ALERTA     = "#E74C3C"
COLOR_WARN       = "#F39C12"

# ─────────────────────────────────────────────────────────────────────────────
# LECTURA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

def leer_lineas(ruta):
    """Lee un log semicolon-separated y devuelve lista de listas."""
    ruta = ruta() if callable(ruta) else ruta
    if not Path(ruta).exists():
        return []
    filas = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                filas.append(linea.split(";"))
    return filas


def cargar_datos():
    """Parsea todos los logs y devuelve un dict con los datos procesados."""
    d = {}

    # ── USUARIOS REGISTRADOS ─────────────────────────────────────────────────
    try:
        ruta_usr = USUARIOS_JSON()
        with open(ruta_usr, encoding="utf-8") as f:
            usuarios = json.load(f)
    except Exception:
        usuarios = {}
    d["usuarios"] = usuarios  # {cuit: {numero_cliente, email, whatsapp}}

    # ── PEDIDOS ──────────────────────────────────────────────────────────────
    # Formato nuevo: fecha;nro_pedido;nro_cliente;email;tipo;items;total
    # Formato viejo: fecha;nro_pedido;email;items;total  (sin nro_cliente ni tipo)
    pedidos = []
    for cols in leer_lineas(LOG_PEDIDOS):
        try:
            if len(cols) == 7:
                fecha, nro_ped, nro_cli, email, tipo, items, total = cols
            elif len(cols) == 5:
                fecha, nro_ped, email, items, total = cols
                nro_cli, tipo = "0", "minorista"
            else:
                continue
            pedidos.append({
                "fecha":   datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S"),
                "nro_ped": int(nro_ped),
                "nro_cli": int(nro_cli),
                "email":   email,
                "tipo":    tipo,
                "items":   int(items),
                "total":   float(total),
            })
        except Exception:
            continue
    d["pedidos"] = pedidos

    # ── BÚSQUEDAS ────────────────────────────────────────────────────────────
    # Formato nuevo: fecha;nro_cliente;tipo;texto;resultados
    # Formato viejo: fecha;texto;resultados
    busquedas = []
    for cols in leer_lineas(LOG_BUSQUEDAS):
        try:
            if len(cols) == 5:
                fecha, nro_cli, tipo, texto, resultados = cols
            elif len(cols) == 3:
                fecha, texto, resultados = cols
                nro_cli, tipo = "0", "minorista"
            else:
                continue
            busquedas.append({
                "fecha":      datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S"),
                "nro_cli":    int(nro_cli),
                "tipo":       tipo,
                "texto":      texto.strip(),
                "resultados": int(resultados),
            })
        except Exception:
            continue
    d["busquedas"] = busquedas

    # ── CARRITO ──────────────────────────────────────────────────────────────
    # Formato: fecha;nro_cliente;tipo;codigo;nombre;cantidad;precio
    carrito = []
    for cols in leer_lineas(LOG_CARRITO):
        try:
            fecha, nro_cli, tipo, codigo, nombre, cantidad, precio = cols
            carrito.append({
                "fecha":    datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S"),
                "nro_cli":  int(nro_cli),
                "tipo":     tipo,
                "codigo":   codigo.strip(),
                "nombre":   nombre.strip(),
                "cantidad": float(cantidad),
                "precio":   float(precio),
            })
        except Exception:
            continue
    d["carrito"] = carrito

    # ── PRODUCTOS VISTOS ─────────────────────────────────────────────────────
    # Formato: fecha;nro_cliente;tipo;codigo;nombre
    productos = []
    for cols in leer_lineas(LOG_PRODUCTOS):
        try:
            fecha, nro_cli, tipo, codigo, nombre = cols
            productos.append({
                "fecha":   datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S"),
                "nro_cli": int(nro_cli),
                "tipo":    tipo,
                "codigo":  codigo.strip(),
                "nombre":  nombre.strip(),
            })
        except Exception:
            continue
    d["productos"] = productos

    # ── SESIONES ─────────────────────────────────────────────────────────────
    # Formato: fecha;evento;nro_cliente;nombre;tipo
    sesiones = []
    for cols in leer_lineas(LOG_SESIONES):
        try:
            fecha, evento, nro_cli, nombre, tipo = cols
            sesiones.append({
                "fecha":   datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S"),
                "evento":  evento.strip(),
                "nro_cli": int(nro_cli),
                "nombre":  nombre.strip(),
                "tipo":    tipo.strip(),
            })
        except Exception:
            continue
    d["sesiones"] = sesiones

    return d


# ─────────────────────────────────────────────────────────────────────────────
# MÉTRICAS CALCULADAS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_metricas(datos, filtro_desde=None, filtro_hasta=None):
    """Calcula todas las estadísticas aplicando filtro de fechas opcional."""

    def en_rango(dt):
        if filtro_desde and dt < filtro_desde:
            return False
        if filtro_hasta and dt > filtro_hasta:
            return False
        return True

    pedidos   = [p for p in datos["pedidos"]   if en_rango(p["fecha"])]
    busquedas = [b for b in datos["busquedas"] if en_rango(b["fecha"])]
    carrito   = [c for c in datos["carrito"]   if en_rango(c["fecha"])]
    productos = [p for p in datos["productos"] if en_rango(p["fecha"])]
    sesiones  = [s for s in datos["sesiones"]  if en_rango(s["fecha"])]
    usuarios  = datos["usuarios"]

    m = {}

    # ── Usuarios ─────────────────────────────────────────────────────────────
    m["total_registrados"] = len(usuarios)
    nros_con_pedido = {p["nro_cli"] for p in pedidos if p["nro_cli"] != 0}
    m["registrados_compraron"] = len(nros_con_pedido & {int(v["numero_cliente"]) for v in usuarios.values()})
    m["registrados_no_compraron"] = m["total_registrados"] - m["registrados_compraron"]

    # ── Pedidos generales ────────────────────────────────────────────────────
    m["total_pedidos"]    = len(pedidos)
    m["total_facturado"]  = sum(p["total"] for p in pedidos)
    m["ticket_promedio"]  = m["total_facturado"] / len(pedidos) if pedidos else 0
    m["pedidos_may"]      = sum(1 for p in pedidos if p["tipo"] == "mayorista")
    m["pedidos_min"]      = sum(1 for p in pedidos if p["tipo"] == "minorista")
    m["monto_may"]        = sum(p["total"] for p in pedidos if p["tipo"] == "mayorista")
    m["monto_min"]        = sum(p["total"] for p in pedidos if p["tipo"] == "minorista")

    # ── Pedidos por mes ──────────────────────────────────────────────────────
    por_mes = defaultdict(lambda: {"cantidad": 0, "monto": 0.0})
    for p in pedidos:
        clave = p["fecha"].strftime("%Y-%m")
        por_mes[clave]["cantidad"] += 1
        por_mes[clave]["monto"]    += p["total"]
    m["por_mes"] = dict(sorted(por_mes.items()))

    # ── Top clientes ─────────────────────────────────────────────────────────
    por_cliente = defaultdict(lambda: {"email": "", "tipo": "", "pedidos": 0, "monto": 0.0})
    for p in pedidos:
        k = p["nro_cli"] if p["nro_cli"] != 0 else p["email"]
        por_cliente[k]["email"]   = p["email"]
        por_cliente[k]["tipo"]    = p["tipo"]
        por_cliente[k]["pedidos"] += 1
        por_cliente[k]["monto"]  += p["total"]
    m["top_clientes"] = sorted(
        [{"id": k, **v} for k, v in por_cliente.items()],
        key=lambda x: x["monto"], reverse=True
    )[:10]

    # ── Búsquedas más frecuentes ─────────────────────────────────────────────
    conteo_busq = defaultdict(int)
    for b in busquedas:
        conteo_busq[b["texto"]] += 1
    m["top_busquedas"] = sorted(
        [{"texto": k, "veces": v} for k, v in conteo_busq.items()],
        key=lambda x: x["veces"], reverse=True
    )[:15]
    m["total_busquedas"] = len(busquedas)
    m["busquedas_sin_resultado"] = sum(1 for b in busquedas if b["resultados"] == 0)

    # ── Productos más agregados al carrito ───────────────────────────────────
    conteo_carrito = defaultdict(lambda: {"nombre": "", "veces": 0, "unidades": 0.0})
    for c in carrito:
        conteo_carrito[c["codigo"]]["nombre"]   = c["nombre"]
        conteo_carrito[c["codigo"]]["veces"]   += 1
        conteo_carrito[c["codigo"]]["unidades"] += c["cantidad"]
    m["top_carrito"] = sorted(
        [{"codigo": k, **v} for k, v in conteo_carrito.items()],
        key=lambda x: x["veces"], reverse=True
    )[:10]

    # ── Productos más vistos ─────────────────────────────────────────────────
    conteo_vistos = defaultdict(lambda: {"nombre": "", "veces": 0})
    for p in productos:
        conteo_vistos[p["codigo"]]["nombre"] = p["nombre"]
        conteo_vistos[p["codigo"]]["veces"] += 1
    m["top_vistos"] = sorted(
        [{"codigo": k, **v} for k, v in conteo_vistos.items()],
        key=lambda x: x["veces"], reverse=True
    )[:10]

    # ── Sesiones ─────────────────────────────────────────────────────────────
    m["total_logins"]  = sum(1 for s in sesiones if s["evento"] == "login")
    clientes_unicos    = {s["nro_cli"] for s in sesiones if s["evento"] == "login"}
    m["clientes_unicos_activos"] = len(clientes_unicos)

    # ── Tasa conversión: carrito → pedido ────────────────────────────────────
    codigos_carrito = {c["codigo"] for c in carrito}
    m["productos_en_carrito"] = len(codigos_carrito)
    m["total_carrito_eventos"] = len(carrito)

    return m


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTACIÓN PDF
# ─────────────────────────────────────────────────────────────────────────────

def exportar_pdf(metricas, filtro_desde, filtro_hasta, ruta_salida):
    """Genera el reporte PDF con todas las métricas."""

    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm
    )

    ancho_util = A4[0] - 4*cm

    estilos = getSampleStyleSheet()

    def est(nombre, **kw):
        s = ParagraphStyle(nombre, parent=estilos["Normal"], **kw)
        return s

    est_titulo   = est("titulo",   fontSize=18, textColor=colors.HexColor("#1B6CA8"),
                       spaceAfter=4, fontName="Helvetica-Bold", alignment=TA_CENTER)
    est_subtit   = est("subtit",   fontSize=10, textColor=colors.HexColor("#6B6B6B"),
                       spaceAfter=12, alignment=TA_CENTER)
    est_seccion  = est("seccion",  fontSize=13, textColor=colors.HexColor("#1B6CA8"),
                       spaceBefore=16, spaceAfter=6, fontName="Helvetica-Bold")
    est_normal   = est("normal",   fontSize=9,  spaceAfter=3)
    est_pie      = est("pie",      fontSize=7,  textColor=colors.HexColor("#999999"),
                       alignment=TA_CENTER)

    def tabla(datos, cabeceras, col_anchos, col_alinear=None):
        """Arma una tabla estilizada."""
        filas = [cabeceras] + datos
        t = Table(filas, colWidths=col_anchos)
        alineaciones = []
        if col_alinear:
            for i, al in enumerate(col_alinear):
                alin = TA_RIGHT if al == "R" else (TA_CENTER if al == "C" else TA_LEFT)
                alineaciones.append(("ALIGN", (i, 0), (i, -1),
                                     "RIGHT" if al == "R" else ("CENTER" if al == "C" else "LEFT")))
        estilo = TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor("#1B6CA8")),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0),  8),
            ("FONTSIZE",    (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4F8")]),
            ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#DCDCDC")),
            ("LEFTPADDING",  (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ] + alineaciones)
        t.setStyle(estilo)
        return t

    def kpi_tabla(items):
        """Fila de tarjetas KPI (etiqueta + valor lado a lado)."""
        n = len(items)
        ancho = ancho_util / n
        data = [[Paragraph(f"<b>{v}</b>", est("kv", fontSize=14,
                           textColor=colors.HexColor("#1B6CA8"), alignment=TA_CENTER)),
                 ] for _, v in items]
        labels = [[Paragraph(lab, est("kl", fontSize=7,
                             textColor=colors.HexColor("#6B6B6B"), alignment=TA_CENTER)),
                   ] for lab, _ in items]
        filas = [
            [Paragraph(f"<b>{v}</b>", est("kv2", fontSize=13,
                       textColor=colors.HexColor("#1B6CA8"), alignment=TA_CENTER))
             for _, v in items],
            [Paragraph(lab, est("kl2", fontSize=7,
                       textColor=colors.HexColor("#6B6B6B"), alignment=TA_CENTER))
             for lab, _ in items],
        ]
        t = Table(filas, colWidths=[ancho]*n)
        t.setStyle(TableStyle([
            ("BOX",         (0, 0), (-1, -1), 0.5, colors.HexColor("#DCDCDC")),
            ("INNERGRID",   (0, 0), (-1, -1), 0.3, colors.HexColor("#DCDCDC")),
            ("BACKGROUND",  (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0,0), (-1, -1), 6),
        ]))
        return t

    def fmt_pesos(n):
        return f"${n:,.0f}".replace(",", ".")

    def fmt_num(n):
        return f"{int(n):,}".replace(",", ".")

    # ── Armar historia ───────────────────────────────────────────────────────
    historia = []

    historia.append(Paragraph("ACEROS FELO", est_titulo))
    historia.append(Paragraph("Reporte Estadístico de la Tienda Web", est_subtit))

    rango_txt = ""
    if filtro_desde or filtro_hasta:
        d = filtro_desde.strftime("%d/%m/%Y") if filtro_desde else "inicio"
        h = filtro_hasta.strftime("%d/%m/%Y") if filtro_hasta else "hoy"
        rango_txt = f"Período: {d} al {h}"
    else:
        rango_txt = "Período: todos los registros"
    rango_txt += f"   |   Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    historia.append(Paragraph(rango_txt, est_subtit))
    historia.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1B6CA8")))

    # ── KPIs generales ───────────────────────────────────────────────────────
    historia.append(Paragraph("Resumen general", est_seccion))
    historia.append(kpi_tabla([
        ("Usuarios registrados",     fmt_num(metricas["total_registrados"])),
        ("Total de pedidos",         fmt_num(metricas["total_pedidos"])),
        ("Facturado total",          fmt_pesos(metricas["total_facturado"])),
        ("Ticket promedio",          fmt_pesos(metricas["ticket_promedio"])),
    ]))
    historia.append(Spacer(1, 8))
    historia.append(kpi_tabla([
        ("Logins registrados",       fmt_num(metricas["total_logins"])),
        ("Clientes únicos activos",  fmt_num(metricas["clientes_unicos_activos"])),
        ("Búsquedas totales",        fmt_num(metricas["total_busquedas"])),
        ("Búsquedas sin resultado",  fmt_num(metricas["busquedas_sin_resultado"])),
    ]))
    historia.append(Spacer(1, 8))
    historia.append(kpi_tabla([
        ("Pedidos mayorista",        fmt_num(metricas["pedidos_may"])),
        ("Monto mayorista",          fmt_pesos(metricas["monto_may"])),
        ("Pedidos minorista",        fmt_num(metricas["pedidos_min"])),
        ("Monto minorista",          fmt_pesos(metricas["monto_min"])),
    ]))

    # ── Usuarios registrados vs compradores ──────────────────────────────────
    historia.append(Paragraph("Clientes registrados", est_seccion))
    historia.append(kpi_tabla([
        ("Registrados totales",      fmt_num(metricas["total_registrados"])),
        ("Compraron al menos 1 vez", fmt_num(metricas["registrados_compraron"])),
        ("Registrados sin compras",  fmt_num(metricas["registrados_no_compraron"])),
    ]))

    # ── Pedidos por mes ──────────────────────────────────────────────────────
    historia.append(Paragraph("Pedidos por mes", est_seccion))
    if metricas["por_mes"]:
        filas_mes = []
        for mes, vals in metricas["por_mes"].items():
            try:
                label = datetime.strptime(mes, "%Y-%m").strftime("%B %Y").capitalize()
            except Exception:
                label = mes
            filas_mes.append([
                label,
                fmt_num(vals["cantidad"]),
                fmt_pesos(vals["monto"]),
                fmt_pesos(vals["monto"] / vals["cantidad"] if vals["cantidad"] else 0),
            ])
        historia.append(tabla(
            filas_mes,
            ["Mes", "Pedidos", "Monto total", "Ticket promedio"],
            [ancho_util*0.35, ancho_util*0.15, ancho_util*0.25, ancho_util*0.25],
            ["L", "C", "R", "R"]
        ))
    else:
        historia.append(Paragraph("Sin registros en el período.", est_normal))

    # ── Top 10 clientes ──────────────────────────────────────────────────────
    historia.append(Paragraph("Top 10 clientes por monto", est_seccion))
    if metricas["top_clientes"]:
        filas_cli = []
        for i, c in enumerate(metricas["top_clientes"], 1):
            filas_cli.append([
                str(i),
                c["email"],
                c["tipo"].capitalize(),
                fmt_num(c["pedidos"]),
                fmt_pesos(c["monto"]),
                fmt_pesos(c["monto"] / c["pedidos"] if c["pedidos"] else 0),
            ])
        historia.append(tabla(
            filas_cli,
            ["#", "Cliente", "Tipo", "Pedidos", "Total", "Ticket prom."],
            [ancho_util*0.05, ancho_util*0.32, ancho_util*0.13,
             ancho_util*0.10, ancho_util*0.20, ancho_util*0.20],
            ["C", "L", "C", "C", "R", "R"]
        ))
    else:
        historia.append(Paragraph("Sin pedidos en el período.", est_normal))

    # ── Búsquedas más frecuentes ─────────────────────────────────────────────
    historia.append(Paragraph("Términos más buscados", est_seccion))
    if metricas["top_busquedas"]:
        filas_busq = [
            [str(i), b["texto"], fmt_num(b["veces"])]
            for i, b in enumerate(metricas["top_busquedas"], 1)
        ]
        historia.append(tabla(
            filas_busq,
            ["#", "Término buscado", "Veces"],
            [ancho_util*0.07, ancho_util*0.73, ancho_util*0.20],
            ["C", "L", "C"]
        ))
    else:
        historia.append(Paragraph("Sin búsquedas registradas.", est_normal))

    # ── Productos más agregados al carrito ───────────────────────────────────
    if metricas["top_carrito"]:
        historia.append(Paragraph("Productos más agregados al carrito", est_seccion))
        filas_car = [
            [str(i), c["codigo"], c["nombre"][:45], fmt_num(c["veces"])]
            for i, c in enumerate(metricas["top_carrito"], 1)
        ]
        historia.append(tabla(
            filas_car,
            ["#", "Código", "Producto", "Veces al carrito"],
            [ancho_util*0.06, ancho_util*0.14, ancho_util*0.60, ancho_util*0.20],
            ["C", "L", "L", "C"]
        ))

    # ── Productos más vistos ─────────────────────────────────────────────────
    if metricas["top_vistos"]:
        historia.append(Paragraph("Productos más consultados", est_seccion))
        filas_vis = [
            [str(i), v["codigo"], v["nombre"][:45], fmt_num(v["veces"])]
            for i, v in enumerate(metricas["top_vistos"], 1)
        ]
        historia.append(tabla(
            filas_vis,
            ["#", "Código", "Producto", "Consultas"],
            [ancho_util*0.06, ancho_util*0.14, ancho_util*0.60, ancho_util*0.20],
            ["C", "L", "L", "C"]
        ))

    # ── Pie de página ────────────────────────────────────────────────────────
    historia.append(Spacer(1, 16))
    historia.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
    historia.append(Paragraph(
        "Aceros Felo — Reporte generado automáticamente por el sistema de estadísticas",
        est_pie
    ))

    doc.build(historia)


# ─────────────────────────────────────────────────────────────────────────────
# INTERFAZ TKINTER
# ─────────────────────────────────────────────────────────────────────────────

class AppEstadisticas(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Estadísticas Tienda Felo")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg=COLOR_FONDO)
        self.resizable(True, True)

        self.datos    = {}
        self.metricas = {}
        self.filtro_desde = None
        self.filtro_hasta = None

        self._construir_ui()
        self.after(100, self.cargar)

    # ── Construcción de la UI ────────────────────────────────────────────────

    def _construir_ui(self):

        # ── Barra superior ────────────────────────────────────────────────────
        barra = tk.Frame(self, bg=COLOR_ACENTO, padx=16, pady=10)
        barra.pack(fill="x")

        tk.Label(barra, text="ACEROS FELO — Estadísticas de la Tienda",
                 bg=COLOR_ACENTO, fg="white",
                 font=("Arial", 14, "bold")).pack(side="left")

        btn_pdf = tk.Button(barra, text="⬇  Exportar PDF",
                            bg=COLOR_ACENTO2, fg="white",
                            font=("Arial", 10, "bold"),
                            relief="flat", padx=12, pady=4,
                            cursor="hand2", command=self.exportar_pdf)
        btn_pdf.pack(side="right", padx=(0, 4))

        btn_act = tk.Button(barra, text="↺  Actualizar",
                            bg="#1a5f8a", fg="white",
                            font=("Arial", 10),
                            relief="flat", padx=12, pady=4,
                            cursor="hand2", command=self.cargar)
        btn_act.pack(side="right", padx=(0, 8))

        if USAR_DRIVE:
            btn_sync = tk.Button(barra, text="☁  Sincronizar Drive",
                                 bg="#6f42c1", fg="white",
                                 font=("Arial", 10),
                                 relief="flat", padx=12, pady=4,
                                 cursor="hand2", command=self.sincronizar_drive)
            btn_sync.pack(side="right", padx=(0, 8))

        # ── Panel de filtros ─────────────────────────────────────────────────
        filtros = tk.Frame(self, bg=COLOR_PANEL, padx=12, pady=8,
                           relief="flat", bd=0)
        filtros.pack(fill="x", padx=0, pady=(0, 1))

        tk.Label(filtros, text="Filtrar por período:",
                 bg=COLOR_PANEL, fg=COLOR_MUTED,
                 font=("Arial", 9)).pack(side="left")

        tk.Label(filtros, text="Desde (dd/mm/aaaa):",
                 bg=COLOR_PANEL, fg=COLOR_TEXTO,
                 font=("Arial", 9)).pack(side="left", padx=(12, 4))
        self.entry_desde = tk.Entry(filtros, width=12, font=("Arial", 9))
        self.entry_desde.pack(side="left")

        tk.Label(filtros, text="Hasta:",
                 bg=COLOR_PANEL, fg=COLOR_TEXTO,
                 font=("Arial", 9)).pack(side="left", padx=(10, 4))
        self.entry_hasta = tk.Entry(filtros, width=12, font=("Arial", 9))
        self.entry_hasta.pack(side="left")

        tk.Button(filtros, text="Aplicar", font=("Arial", 9),
                  bg=COLOR_ACENTO, fg="white", relief="flat",
                  padx=10, cursor="hand2",
                  command=self.aplicar_filtro).pack(side="left", padx=(10, 4))

        tk.Button(filtros, text="Limpiar", font=("Arial", 9),
                  bg=COLOR_MUTED, fg="white", relief="flat",
                  padx=10, cursor="hand2",
                  command=self.limpiar_filtro).pack(side="left")

        self.lbl_filtro = tk.Label(filtros, text="",
                                   bg=COLOR_PANEL, fg=COLOR_ACENTO,
                                   font=("Arial", 9, "italic"))
        self.lbl_filtro.pack(side="left", padx=16)

        # ── Separador ────────────────────────────────────────────────────────
        tk.Frame(self, bg=COLOR_BORDE, height=1).pack(fill="x")

        # ── Pestañas ─────────────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",         background=COLOR_FONDO, borderwidth=0)
        style.configure("TNotebook.Tab",     background=COLOR_FONDO, foreground=COLOR_MUTED,
                        padding=[14, 6], font=("Arial", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", COLOR_PANEL)],
                  foreground=[("selected", COLOR_ACENTO)])

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=0, pady=0)

        self.tab_resumen   = self._nueva_tab("Resumen")
        self.tab_pedidos   = self._nueva_tab("Pedidos por mes")
        self.tab_clientes  = self._nueva_tab("Top clientes")
        self.tab_busquedas = self._nueva_tab("Búsquedas")
        self.tab_carrito   = self._nueva_tab("Carrito")
        self.tab_productos = self._nueva_tab("Productos vistos")

        # ── Barra de estado ──────────────────────────────────────────────────
        self.barra_estado = tk.Label(self, text="Cargando...",
                                     bg="#E8E8E8", fg=COLOR_MUTED,
                                     font=("Arial", 8), anchor="w", padx=8)
        self.barra_estado.pack(fill="x", side="bottom")

    def _nueva_tab(self, titulo):
        frame = tk.Frame(self.notebook, bg=COLOR_FONDO)
        self.notebook.add(frame, text=titulo)
        canvas = tk.Canvas(frame, bg=COLOR_FONDO, highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        contenedor = tk.Frame(canvas, bg=COLOR_FONDO)
        win_id = canvas.create_window((0, 0), window=contenedor, anchor="nw")
        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        contenedor.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        return contenedor

    # ── Carga y refresco ─────────────────────────────────────────────────────

    def cargar(self):
        try:
            self.datos    = cargar_datos()
            self.metricas = calcular_metricas(self.datos, self.filtro_desde, self.filtro_hasta)
            self._refrescar_todo()
            n_ped = self.metricas["total_pedidos"]
            n_usr = self.metricas["total_registrados"]
            self.barra_estado.config(
                text=f"  Datos actualizados — {n_ped} pedidos · {n_usr} usuarios registrados   "
                     f"[{datetime.now().strftime('%H:%M:%S')}]"
            )
        except Exception as e:
            messagebox.showerror("Error al cargar", str(e))

    def aplicar_filtro(self):
        def parsear(txt):
            txt = txt.strip()
            if not txt:
                return None
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(txt, fmt)
                except ValueError:
                    continue
            return None

        self.filtro_desde = parsear(self.entry_desde.get())
        self.filtro_hasta = parsear(self.entry_hasta.get())

        if self.entry_desde.get().strip() and not self.filtro_desde:
            messagebox.showwarning("Fecha inválida", "Formato incorrecto. Use dd/mm/aaaa")
            return
        if self.entry_hasta.get().strip() and not self.filtro_hasta:
            messagebox.showwarning("Fecha inválida", "Formato incorrecto. Use dd/mm/aaaa")
            return

        partes = []
        if self.filtro_desde:
            partes.append(f"desde {self.filtro_desde.strftime('%d/%m/%Y')}")
        if self.filtro_hasta:
            partes.append(f"hasta {self.filtro_hasta.strftime('%d/%m/%Y')}")
        self.lbl_filtro.config(text="  Filtro: " + " · ".join(partes) if partes else "")
        self.cargar()

    def limpiar_filtro(self):
        self.filtro_desde = None
        self.filtro_hasta = None
        self.entry_desde.delete(0, "end")
        self.entry_hasta.delete(0, "end")
        self.lbl_filtro.config(text="")
        self.cargar()

    def _refrescar_todo(self):
        self._poblar_resumen()
        self._poblar_pedidos_mes()
        self._poblar_clientes()
        self._poblar_busquedas()
        self._poblar_carrito()
        self._poblar_productos()

    # ── Helpers de widgets ───────────────────────────────────────────────────

    def _limpiar(self, tab):
        for w in tab.winfo_children():
            w.destroy()

    def _seccion(self, parent, titulo):
        f = tk.Frame(parent, bg=COLOR_FONDO)
        f.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(f, text=titulo, bg=COLOR_FONDO, fg=COLOR_ACENTO,
                 font=("Arial", 11, "bold")).pack(anchor="w")
        tk.Frame(f, bg=COLOR_ACENTO, height=2).pack(fill="x", pady=(2, 0))
        return f

    def _kpi_fila(self, parent, items):
        """Fila de tarjetas KPI. items = [(label, valor, color_valor), ...]"""
        fila = tk.Frame(parent, bg=COLOR_FONDO)
        fila.pack(fill="x", padx=16, pady=(6, 0))
        for label, valor, color in items:
            card = tk.Frame(fila, bg=COLOR_PANEL, relief="flat",
                            highlightbackground=COLOR_BORDE, highlightthickness=1)
            card.pack(side="left", expand=True, fill="both", padx=4, pady=4, ipadx=8, ipady=8)
            tk.Label(card, text=str(valor), bg=COLOR_PANEL, fg=color,
                     font=("Arial", 16, "bold")).pack()
            tk.Label(card, text=label, bg=COLOR_PANEL, fg=COLOR_MUTED,
                     font=("Arial", 8)).pack()

    def _tabla(self, parent, columnas, filas, anchos=None):
        """Tabla con cabecera coloreada y filas alternas."""
        frame = tk.Frame(parent, bg=COLOR_PANEL,
                         highlightbackground=COLOR_BORDE, highlightthickness=1)
        frame.pack(fill="x", padx=16, pady=(4, 8))

        # Cabecera
        cab = tk.Frame(frame, bg=COLOR_CABECERA)
        cab.pack(fill="x")
        for i, col in enumerate(columnas):
            ancho = anchos[i] if anchos else 15
            tk.Label(cab, text=col, bg=COLOR_CABECERA, fg=COLOR_CABECERA_T,
                     font=("Arial", 8, "bold"), width=ancho,
                     anchor="w", padx=6, pady=4).grid(row=0, column=i, sticky="ew")

        # Filas
        for r, fila in enumerate(filas):
            bg = COLOR_FILA_PAR if r % 2 == 0 else COLOR_PANEL
            for c, celda in enumerate(fila):
                ancho = anchos[c] if anchos else 15
                tk.Label(frame, text=str(celda), bg=bg, fg=COLOR_TEXTO,
                         font=("Arial", 8), width=ancho,
                         anchor="w", padx=6, pady=3).grid(row=r+1, column=c, sticky="ew")

        if not filas:
            tk.Label(frame, text="Sin datos en el período seleccionado.",
                     bg=COLOR_PANEL, fg=COLOR_MUTED,
                     font=("Arial", 9, "italic"), pady=10).pack()

    # ── Poblar pestañas ──────────────────────────────────────────────────────

    def _poblar_resumen(self):
        self._limpiar(self.tab_resumen)
        m = self.metricas

        def fmt(n):   return f"${n:,.0f}".replace(",", ".")
        def fmtn(n):  return f"{int(n):,}".replace(",", ".")

        self._seccion(self.tab_resumen, "Resumen general")
        self._kpi_fila(self.tab_resumen, [
            ("Usuarios registrados",    fmtn(m["total_registrados"]),    COLOR_ACENTO),
            ("Total pedidos",           fmtn(m["total_pedidos"]),         COLOR_ACENTO),
            ("Facturado total",         fmt(m["total_facturado"]),        COLOR_ACENTO2),
            ("Ticket promedio",         fmt(m["ticket_promedio"]),        COLOR_ACENTO2),
        ])
        self._kpi_fila(self.tab_resumen, [
            ("Logins",                  fmtn(m["total_logins"]),          COLOR_ACENTO),
            ("Clientes únicos activos", fmtn(m["clientes_unicos_activos"]),COLOR_ACENTO),
            ("Búsquedas totales",       fmtn(m["total_busquedas"]),       COLOR_MUTED),
            ("Búsq. sin resultado",     fmtn(m["busquedas_sin_resultado"]),COLOR_ALERTA),
        ])

        self._seccion(self.tab_resumen, "Mayorista vs Minorista")
        self._kpi_fila(self.tab_resumen, [
            ("Pedidos mayorista",  fmtn(m["pedidos_may"]),  COLOR_ACENTO),
            ("Monto mayorista",    fmt(m["monto_may"]),     COLOR_ACENTO2),
            ("Pedidos minorista",  fmtn(m["pedidos_min"]),  COLOR_ACENTO),
            ("Monto minorista",    fmt(m["monto_min"]),     COLOR_ACENTO2),
        ])

        self._seccion(self.tab_resumen, "Clientes registrados")
        self._kpi_fila(self.tab_resumen, [
            ("Total registrados",      fmtn(m["total_registrados"]),         COLOR_ACENTO),
            ("Compraron al menos 1 vez",fmtn(m["registrados_compraron"]),    COLOR_ACENTO2),
            ("Sin compras aún",        fmtn(m["registrados_no_compraron"]),  COLOR_WARN),
        ])

        self._seccion(self.tab_resumen, "Actividad de carrito")
        self._kpi_fila(self.tab_resumen, [
            ("Eventos de carrito",     fmtn(m["total_carrito_eventos"]),     COLOR_ACENTO),
            ("Productos distintos",    fmtn(m["productos_en_carrito"]),      COLOR_ACENTO),
        ])

    def _poblar_pedidos_mes(self):
        self._limpiar(self.tab_pedidos)
        self._seccion(self.tab_pedidos, "Pedidos por mes")

        filas = []
        for mes, vals in self.metricas["por_mes"].items():
            try:
                label = datetime.strptime(mes, "%Y-%m").strftime("%B %Y").capitalize()
            except Exception:
                label = mes
            ticket = vals["monto"] / vals["cantidad"] if vals["cantidad"] else 0
            filas.append([
                label,
                f"{vals['cantidad']}",
                f"${vals['monto']:,.0f}".replace(",", "."),
                f"${ticket:,.0f}".replace(",", "."),
            ])

        self._tabla(self.tab_pedidos,
                    ["Mes", "Cantidad de pedidos", "Monto total", "Ticket promedio"],
                    filas, anchos=[22, 22, 22, 22])

    def _poblar_clientes(self):
        self._limpiar(self.tab_clientes)
        self._seccion(self.tab_clientes, "Top 10 clientes — filtrar por:")

        # Mini filtros dentro de la pestaña
        controles = tk.Frame(self.tab_clientes, bg=COLOR_FONDO)
        controles.pack(fill="x", padx=16, pady=(0, 6))

        tk.Label(controles, text="Ordenar por:", bg=COLOR_FONDO,
                 fg=COLOR_TEXTO, font=("Arial", 9)).pack(side="left")

        self._orden_clientes = tk.StringVar(value="monto")

        for txt, val in [("Monto total", "monto"), ("Cantidad de pedidos", "pedidos")]:
            tk.Radiobutton(controles, text=txt, variable=self._orden_clientes,
                           value=val, bg=COLOR_FONDO, fg=COLOR_TEXTO,
                           font=("Arial", 9), activebackground=COLOR_FONDO,
                           command=self._poblar_clientes).pack(side="left", padx=8)

        orden = self._orden_clientes.get()
        top = sorted(self.metricas["top_clientes"],
                     key=lambda x: x[orden], reverse=True)[:10]

        filas = []
        for i, c in enumerate(top, 1):
            ticket = c["monto"] / c["pedidos"] if c["pedidos"] else 0
            filas.append([
                str(i),
                c["email"],
                c["tipo"].capitalize(),
                str(c["pedidos"]),
                f"${c['monto']:,.0f}".replace(",", "."),
                f"${ticket:,.0f}".replace(",", "."),
            ])

        self._tabla(self.tab_clientes,
                    ["#", "Cliente / Email", "Tipo", "Pedidos", "Total facturado", "Ticket prom."],
                    filas, anchos=[3, 30, 10, 8, 16, 16])

    def _poblar_busquedas(self):
        self._limpiar(self.tab_busquedas)
        self._seccion(self.tab_busquedas, "Términos más buscados (top 15)")

        filas = [
            [str(i), b["texto"], str(b["veces"])]
            for i, b in enumerate(self.metricas["top_busquedas"], 1)
        ]
        self._tabla(self.tab_busquedas,
                    ["#", "Término buscado", "Búsquedas"],
                    filas, anchos=[4, 50, 12])

    def _poblar_carrito(self):
        self._limpiar(self.tab_carrito)
        self._seccion(self.tab_carrito, "Productos más agregados al carrito (top 10)")

        filas = [
            [str(i), c["codigo"], c["nombre"][:50],
             str(c["veces"]), f"{c['unidades']:.0f}"]
            for i, c in enumerate(self.metricas["top_carrito"], 1)
        ]
        self._tabla(self.tab_carrito,
                    ["#", "Código", "Producto", "Veces agregado", "Unidades"],
                    filas, anchos=[3, 14, 40, 14, 10])

    def _poblar_productos(self):
        self._limpiar(self.tab_productos)
        self._seccion(self.tab_productos, "Productos más consultados (top 10)")

        filas = [
            [str(i), v["codigo"], v["nombre"][:50], str(v["veces"])]
            for i, v in enumerate(self.metricas["top_vistos"], 1)
        ]
        self._tabla(self.tab_productos,
                    ["#", "Código", "Producto", "Consultas"],
                    filas, anchos=[3, 14, 50, 12])

    def sincronizar_drive(self):
        """Descarga los archivos frescos desde Google Drive y recarga las estadísticas."""
        self.barra_estado.config(text="  Sincronizando con Google Drive...")
        self.update_idletasks()
        try:
            descargados = drive.descargar_todos(CARPETA_SYNC)
            self.cargar()
            self.barra_estado.config(
                text=f"  ✓ Sincronización completa — {len(descargados)} archivos descargados "
                     f"[{datetime.now().strftime('%H:%M:%S')}]"
            )
        except Exception as e:
            messagebox.showerror("Error de sincronización",
                                 f"No se pudo conectar con Google Drive:\n\n{e}")
            self.barra_estado.config(text="  Error al sincronizar con Drive.")

    # ── Exportar PDF ─────────────────────────────────────────────────────────

    def exportar_pdf(self):
        if not self.metricas:
            messagebox.showwarning("Sin datos", "Primero cargá los datos.")
            return

        ruta = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"estadisticas_felo_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            title="Guardar reporte PDF"
        )
        if not ruta:
            return

        try:
            exportar_pdf(self.metricas, self.filtro_desde, self.filtro_hasta, ruta)
            messagebox.showinfo("PDF generado",
                                f"Reporte guardado en:\n{ruta}")
            os.startfile(ruta) if os.name == "nt" else os.system(f'xdg-open "{ruta}"')
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AppEstadisticas()
    app.mainloop()