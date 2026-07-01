# ─────────────────────────────────────────────────────────────────────────────
# AUTORIZAR DRIVE — Aceros Felo
# Script de autorización ÚNICA. Se corre UNA SOLA VEZ en tu PC (no en Render).
#
# QUÉ HACE:
# Te pide iniciar sesión con tu cuenta de Gmail real (la misma donde está la
# carpeta "Felo_Datos" en Drive) y autorizar el acceso. Genera un
# "refresh_token" que tienda_felo.py y estadisticas_tienda.py van a usar
# (a través de drive_manager.py) para escribir/leer en Drive CON TU CUOTA,
# en vez de la cuota inexistente del Service Account.
#
# PASO A PASO:
#
# 1) Ir a Google Cloud Console: https://console.cloud.google.com/apis/credentials
#    (tiene que ser el MISMO proyecto donde ya creaste el Service Account
#    "tienda-felo@tiendafelo.iam.gserviceaccount.com")
#
# 2) Click en "+ CREAR CREDENCIALES" > "ID de cliente de OAuth"
#    - Si te pide configurar la "pantalla de consentimiento" antes, elegí
#      tipo "Externo", completá los datos mínimos (nombre app, tu email) y
#      guardá. En "Usuarios de prueba" agregá tu propio Gmail.
#    - Tipo de aplicación: "Aplicación de escritorio"
#    - Nombre: el que quieras (ej: "Tienda Felo Desktop")
#    - Crear, y después descargar el JSON (ícono de descarga)
#
# 3) Renombrá ese JSON descargado a:  client_secret.json
#    y ponelo en la MISMA carpeta que este script.
#
# 4) Instalar la librería que falta (si no la tenés):
#       pip install google-auth-oauthlib
#
# 5) Correr este script:
#       python autorizar_drive.py
#
#    Se va a abrir tu navegador. Iniciá sesión con tu Gmail (el de la
#    carpeta Felo_Datos) y aceptá los permisos. Vas a ver una advertencia
#    de "app no verificada" — es normal porque es tu propia app personal;
#    click en "Avanzado" > "Ir a [nombre app] (no seguro)".
#
# 6) Al terminar, este script crea el archivo "oauth_token.json" en esta
#    carpeta. Copiá ese archivo junto a tienda_felo.py / estadisticas_tienda.py
#    (y junto al .exe si usás la versión compilada con PyInstaller — agregalo
#    como "dato adicional" al empaquetar).
#
#    Para PRODUCCIÓN (Render), en vez de copiar el archivo, el script te va
#    a imprimir 3 valores: copialos como variables de entorno en Render:
#       OAUTH_CLIENT_ID
#       OAUTH_CLIENT_SECRET
#       OAUTH_REFRESH_TOKEN
#
# IMPORTANTE: oauth_token.json y client_secret.json son credenciales
# sensibles, igual que credentials_drive.json. NO subir a GitHub público.
# ─────────────────────────────────────────────────────────────────────────────

import json
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("❌ Falta la librería google-auth-oauthlib.")
    print("   Instalala con: pip install google-auth-oauthlib")
    raise SystemExit(1)

SCOPES = ["https://www.googleapis.com/auth/drive"]
CLIENT_SECRET_FILE = "client_secret.json"
SALIDA = "oauth_token.json"


def main():
    ruta_secret = Path(CLIENT_SECRET_FILE)
    if not ruta_secret.exists():
        print(f"❌ No encontré '{CLIENT_SECRET_FILE}' en esta carpeta.")
        print("   Descargalo desde Google Cloud Console (ver instrucciones")
        print("   en los comentarios al inicio de este script) y poné ese")
        print(f"   archivo acá con el nombre '{CLIENT_SECRET_FILE}'.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(
        str(ruta_secret), SCOPES
    )

    # Abre el navegador, vos iniciás sesión, y al aceptar vuelve acá.
    creds = flow.run_local_server(port=0)

    if not creds.refresh_token:
        print("⚠️  No se recibió un refresh_token.")
        print("   Esto pasa si ya habías autorizado esta app antes.")
        print("   Solución: andá a https://myaccount.google.com/permissions")
        print("   revocá el acceso a la app, y volvé a correr este script.")
        return

    datos = {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
    }

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2)

    print(f"\n✅ Listo. Se generó '{SALIDA}' en esta carpeta.")
    print("\n── USO LOCAL (tu PC / el .exe) ──────────────────────────────")
    print(f"Copiá '{SALIDA}' junto a tienda_felo.py / estadisticas_tienda.py")
    print("(o junto al .exe compilado). drive_manager.py lo va a detectar solo.")
    print("\n── USO EN RENDER (producción) ───────────────────────────────")
    print("Creá estas 3 variables de entorno en el panel de Render:")
    print(f"  OAUTH_CLIENT_ID     = {creds.client_id}")
    print(f"  OAUTH_CLIENT_SECRET = {creds.client_secret}")
    print(f"  OAUTH_REFRESH_TOKEN = {creds.refresh_token}")
    print("\nUna vez configurado, ya podés borrar GOOGLE_CREDENTIALS de Render")
    print("(el Service Account deja de usarse).")


if __name__ == "__main__":
    main()