# ─────────────────────────────────────────────────────────────────────────────
# DRIVE MANAGER — Aceros Felo
# Módulo compartido para leer y escribir archivos en Google Drive.
# Usado por tienda_felo.py (escritura) y estadisticas_tienda.py (lectura).
#
# Requiere: pip install google-api-python-client google-auth
# ─────────────────────────────────────────────────────────────────────────────

import os
import io
import json
import tempfile
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# ── Configuración ─────────────────────────────────────────────────────────────

FOLDER_ID = "1xk9e94QAUPzlBWK8oZt6yzNpioHCNLVY"
SCOPES    = ["https://www.googleapis.com/auth/drive"]

ARCHIVOS = [
    "logs_busquedas.txt",
    "logs_carrito.txt",
    "logs_pedidos.txt",
    "logs_productos.txt",
    "logs_sesiones.txt",
    "usuarios.json",
]

# ── Conexión ──────────────────────────────────────────────────────────────────

def _get_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        info = json.loads(creds_json)
    else:
        # Cuando corre como .exe (PyInstaller), sys.executable apunta al .exe.
        # Cuando corre como .py normal, usamos la carpeta del script.
        import sys
        if getattr(sys, "frozen", False):
            # Ejecutable PyInstaller — buscar junto al .exe
            base = Path(sys.executable).parent
        else:
            # Script Python normal — buscar junto al .py
            base = Path(__file__).parent

        ruta = base / "credentials_drive.json"
        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encontró credentials_drive.json en:\n{ruta}\n\n"
                "Copiá el archivo junto al ejecutable."
            )
        with open(ruta, encoding="utf-8") as f:
            info = json.load(f)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ── Caché de IDs ──────────────────────────────────────────────────────────────

_cache_ids = {}

def _buscar_id(service, nombre):
    if nombre in _cache_ids:
        return _cache_ids[nombre]
    resultado = service.files().list(
        q=f"name='{nombre}' and '{FOLDER_ID}' in parents and trashed=false",
        fields="files(id, name)",
        spaces="drive",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    archivos = resultado.get("files", [])
    if archivos:
        _cache_ids[nombre] = archivos[0]["id"]
        return _cache_ids[nombre]
    return None


# ── Operaciones principales ───────────────────────────────────────────────────

def leer_archivo(nombre):
    """Lee un archivo de Drive y devuelve su contenido como string."""
    try:
        service = _get_service()
        file_id = _buscar_id(service, nombre)
        if not file_id:
            return ""
        buffer = io.BytesIO()
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        descargador = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = descargador.next_chunk()
        return buffer.getvalue().decode("utf-8")
    except Exception as e:
        print(f"[Drive] Error leyendo {nombre}: {e}")
        return ""


def escribir_archivo(nombre, contenido):
    """
    Actualiza un archivo existente en Drive con el contenido dado.
    Si el archivo NO existe, muestra instrucciones para crearlo manualmente.
    La Service Account no puede crear archivos nuevos (sin cuota propia),
    pero SÍ puede actualizar archivos que el usuario creó y compartió.
    """
    try:
        service = _get_service()
        file_id = _buscar_id(service, nombre)
        media   = MediaIoBaseUpload(
            io.BytesIO(contenido.encode("utf-8")),
            mimetype="text/plain",
            resumable=False
        )

        if file_id:
            service.files().update(
                fileId=file_id,
                media_body=media,
                supportsAllDrives=True
            ).execute()
        else:
            print(f"[Drive] '{nombre}' no existe en Drive.")
            print(f"[Drive] Ejecutá: python crear_archivos_drive.py")

    except Exception as e:
        print(f"[Drive] Error escribiendo {nombre}: {e}")


def agregar_linea(nombre, linea):
    """Agrega una línea al final de un archivo de texto en Drive."""
    contenido_actual = leer_archivo(nombre)
    if contenido_actual and not contenido_actual.endswith("\n"):
        contenido_actual += "\n"
    nuevo_contenido = contenido_actual + linea.rstrip("\n") + "\n"
    escribir_archivo(nombre, nuevo_contenido)


def descargar_todos(carpeta_local, errores=None):
    """
    Descarga todos los archivos de Drive a una carpeta local.
    Si algo falla, agrega el error a la lista `errores` (si se pasa).
    """
    carpeta_local = Path(carpeta_local)
    carpeta_local.mkdir(parents=True, exist_ok=True)
    descargados = []
    try:
        # Probar conexión antes de descargar
        service = _get_service()
    except Exception as e:
        msg = str(e)
        print(f"[Drive] Error de conexión: {msg}")
        if errores is not None:
            errores.append(msg)
        return descargados

    for nombre in ARCHIVOS:
        try:
            contenido = leer_archivo(nombre)
            ruta = carpeta_local / nombre
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
            descargados.append(nombre)
            print(f"[Drive] Descargado: {nombre} ({len(contenido)} chars)")
        except Exception as e:
            print(f"[Drive] Error descargando {nombre}: {e}")
    return descargados