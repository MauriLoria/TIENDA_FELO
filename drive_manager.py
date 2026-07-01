# ─────────────────────────────────────────────────────────────────────────────
# DRIVE MANAGER — Aceros Felo
# Módulo compartido para leer y escribir archivos en Google Drive.
# Usado por tienda_felo.py (escritura) y estadisticas_tienda.py (lectura).
#
# IMPORTANTE — Autenticación por OAuth (no Service Account):
# Las Service Accounts no tienen cuota de almacenamiento propia en Gmail
# personal, así que las escrituras/actualizaciones fallan con
# "storageQuotaExceeded". Por eso este módulo se autentica con una cuenta
# de Gmail real (la tuya), que sí tiene cuota.
#
# Antes de usar esto por primera vez, corré UNA SOLA VEZ el script
# autorizar_drive.py (ver instrucciones dentro de ese archivo). Eso genera
# oauth_token.json (uso local) o los valores para las variables de entorno
# OAUTH_CLIENT_ID / OAUTH_CLIENT_SECRET / OAUTH_REFRESH_TOKEN (uso en Render).
#
# Requiere: pip install google-api-python-client google-auth
# ─────────────────────────────────────────────────────────────────────────────

import os
import io
import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
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

# ── Conexión (OAuth con cuenta personal) ───────────────────────────────────────

def _ruta_token_local():
    import sys
    if getattr(sys, "frozen", False):
        # Ejecutable PyInstaller — buscar junto al .exe
        base = Path(sys.executable).parent
    else:
        # Script Python normal — buscar junto al .py
        base = Path(__file__).parent
    return base / "oauth_token.json"


def _get_service():
    client_id     = os.environ.get("OAUTH_CLIENT_ID")
    client_secret = os.environ.get("OAUTH_CLIENT_SECRET")
    refresh_token = os.environ.get("OAUTH_REFRESH_TOKEN")

    if not (client_id and client_secret and refresh_token):
        # No están en variables de entorno (caso típico: corriendo local) —
        # buscar el archivo generado por autorizar_drive.py
        ruta = _ruta_token_local()
        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encontraron credenciales OAuth de Drive.\n"
                f"Faltan las variables de entorno OAUTH_CLIENT_ID / "
                f"OAUTH_CLIENT_SECRET / OAUTH_REFRESH_TOKEN, y tampoco existe:\n"
                f"{ruta}\n\n"
                "Corré primero 'python autorizar_drive.py' (una sola vez) "
                "para generar las credenciales."
            )
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        client_id     = datos["client_id"]
        client_secret = datos["client_secret"]
        refresh_token = datos["refresh_token"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())

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
    Si el archivo NO existe, lo CREA dentro de FOLDER_ID (esto ya es
    posible porque ahora autenticamos con una cuenta real con cuota,
    a diferencia del Service Account anterior).
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
            archivo_nuevo = service.files().create(
                body={"name": nombre, "parents": [FOLDER_ID]},
                media_body=media,
                fields="id",
                supportsAllDrives=True
            ).execute()
            _cache_ids[nombre] = archivo_nuevo["id"]
            print(f"[Drive] '{nombre}' no existía — se creó en Drive.")

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