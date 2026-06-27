# ─────────────────────────────────────────────────────────────────────────────
# SUBIR ARCHIVOS LOCALES A DRIVE — ejecutar UNA SOLA VEZ
# Este script sube tus archivos locales a la carpeta Felo_Datos de Drive.
# Después de ejecutarlo podés borrarlo.
# ─────────────────────────────────────────────────────────────────────────────

from pathlib import Path
import drive_manager as drive

# Archivos a subir — ajustá la ruta si están en otra carpeta
CARPETA_LOCAL = Path(".")

ARCHIVOS = [
    "usuarios.json",
    "logs_busquedas.txt",
    "logs_carrito.txt",
    "logs_pedidos.txt",
    "logs_productos.txt",
    "logs_sesiones.txt",
]

print("=== Subiendo archivos a Google Drive (Felo_Datos) ===\n")

for nombre in ARCHIVOS:
    ruta = CARPETA_LOCAL / nombre
    if ruta.exists():
        contenido = ruta.read_text(encoding="utf-8")
        drive.escribir_archivo(nombre, contenido)
        print(f"  ✓ Subido: {nombre} ({len(contenido)} chars)")
    else:
        # Si no existe localmente, crear vacío en Drive para que exista
        drive.escribir_archivo(nombre, "")
        print(f"  ~ Creado vacío: {nombre} (no existía localmente)")

print("\n=== Listo. Podés borrar este script. ===")