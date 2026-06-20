from flask import (Flask, render_template, send_from_directory, jsonify, request, session, redirect, url_for)
import os
import random
from dbfread import DBF
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, date
from pathlib import Path
import traceback
import json
import unicodedata
from werkzeug.security import (
    generate_password_hash,
    check_password_hash)

# ─────────────────────────────────────────────
# CONFIGURACIÓN — leer de variables de entorno
# ─────────────────────────────────────────────
ARTICULO_DBF = "articulo.dbf"
OFERTAS_DBF = "ofertas.dbf"
CLIENTES_DBF = "clientes.dbf"
CARPETA_IMAGENES = "Imagenes"
CARPETA_VIDEOS = "Videos"
#ARTICULO_DBF      = os.environ.get("ARTICULO_DBF",      "/MegaMauri/AFA/ARTICULO.DBF")
#CARPETA_IMAGENES  = os.environ.get("CARPETA_IMAGENES",  "/MegaMauri/DISTRIBUIDORA/Catalogo/DIBUJOS_WEBP")
#CARPETA_VIDEOS    = os.environ.get("CARPETA_VIDEOS",    "/MegaMauri/Videos")
#OFERTAS_DBF       = os.environ.get("OFERTAS_DBF",    "/MegaMauri/AFA/OFERTAS.DBF")
EMAIL_REMITENTE   = os.environ.get("EMAIL_REMITENTE",   "acerosfelodistribuidora@gmail.com")
EMAIL_PASSWORD    = os.environ.get("EMAIL_PASSWORD")          # ← nunca hardcodeada
EMAIL_DESTINO     = os.environ.get("EMAIL_DESTINO",     "acerosfelodistribuidora@gmail.com")
FLASK_DEBUG       = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

ARCHIVO_PEDIDO    = "ultimo_pedido.txt"
ARCHIVO_COTIZACION = Path("cotizacion.txt")

# ─────────────────────────────────────────────
# CATÁLOGO GLOBAL (índice para búsqueda rápida)
# ─────────────────────────────────────────────
CATALOGO: list[dict] = []
CATALOGO_POR_CODIGO: dict[str, dict] = {}   # para validar precios en el servidor
_OFERTAS: dict[str, object] = {}

def registrar_busqueda(texto, resultados):

    with open(
        "logs_busquedas.txt",
        "a",
        encoding="utf-8"
    ) as f:

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        f.write(
            f"{fecha};{texto};{resultados}\n"
        )

def cargar_ofertas():

    global _OFERTAS

    _OFERTAS = {}

    hoy = date.today()

    for reg in DBF(OFERTAS_DBF,
                   load=True,
                   char_decode_errors="ignore"):

        codigo = str(reg.get("CODIGO","")).strip()

        if not codigo:
            continue

        feci = reg.get("FECI")
        fecv = reg.get("FECV")

        vigente = True

        if feci and hoy < feci:
            vigente = False

        if fecv and hoy > fecv:
            vigente = False

        if vigente:
            _OFERTAS[codigo] = reg



# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────
def obtener_cotizacion_dolar() -> float:
    """Lee la cotización del dólar desde archivo; devuelve 1460.0 si falla."""
    try:
        return float(ARCHIVO_COTIZACION.read_text(encoding="utf-8").strip().replace(",", "."))
    except Exception:
        return 1460.0


def obtener_numero_pedido() -> int:
    """Lee, incrementa y persiste el número de pedido."""
    archivo = Path(ARCHIVO_PEDIDO)
    if not archivo.exists():
        archivo.write_text("100")
        return 100
    nuevo = int(archivo.read_text().strip()) + 1
    archivo.write_text(str(nuevo))
    return nuevo

def datos_usuario():

    tipo = session.get("tipo", "minorista")

    if tipo == "mayorista":

        email_empresa = "acerosfelodistribuidora@gmail.com"
        whatsapp_empresa = "5492317508457"

    else:

        email_empresa = "acerosfeloonline@gmail.com"
        whatsapp_empresa = "5492317507013"  

    return {
        "logueado": "numero_cliente" in session,
        "cliente": session.get("nombre", ""),
        "numero": session.get("numero_cliente", ""),
        "tipo": session.get("tipo", "minorista"),
        "nombre_cliente": session.get("nombre", ""),
        "email": session.get("email_cliente", ""),
        "whatsapp": session.get("whatsapp_cliente", ""),
        "email_empresa": email_empresa,
        "whatsapp_empresa": whatsapp_empresa,
        "envia_email": True,
        "envia_whatsapp": True}

def normalizar_numero(valor):

    return "".join(
        c for c in str(valor)
        if c.isdigit()
    )

def normalizar_texto(texto):

    texto = str(texto or "").upper()

    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )

def buscar_cliente(documento):

    documento = normalizar_numero(documento)

    for cli in DBF(
        CLIENTES_DBF,
        encoding="cp437",
        char_decode_errors="ignore"
    ):

        cuit = normalizar_numero(
            cli["NROCUIT"]
        )

        if documento == cuit:
            return cli

        if len(cuit) == 11:

            dni = cuit[2:10]

            if documento == dni:
                return cli

    return None

USUARIOS_JSON = "usuarios.json"


def cargar_usuarios():

    try:

        with open(
            USUARIOS_JSON,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return {}


def guardar_usuarios(datos):

    with open(
        USUARIOS_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            datos,
            f,
            indent=4,
            ensure_ascii=False
        )


# ─────────────────────────────────────────────
# CARGA DEL CATÁLOGO
# ─────────────────────────────────────────────
def cargar_catalogo() -> list[dict]:
    """Lee el DBF y devuelve la lista de artículos con precios calculados."""
    catalogo = []
    dolar_web = obtener_cotizacion_dolar()

    for reg in DBF(ARTICULO_DBF, encoding="cp437", char_decode_errors="ignore"):
        precio   = float(reg["PRECIOACT"] or 0)
        precio_may = float(reg["PRECIOMAY"] or 0)
        es_dolar = str(reg["DOLAR"]).strip().upper() == "S"
        val_unid = float(reg["VAL_UNID"] or 1)
        codigo = str(reg["CODIGO"]).strip()

        if es_dolar:
            precio *= dolar_web
            precio_may *= dolar_web

        if val_unid and val_unid != 1:
            precio /= val_unid
            precio_may /= val_unid

        iva = float(reg["IVA"] or 0)
        ivaesp = str(reg["IVAESP"] or "").strip().upper()

        if ivaesp == "T":
            # todo el IVA
            precio_may *= (1 + iva / 100)

        elif ivaesp == "M":
            # mitad del IVA
            precio_may *= (1 + (iva / 2) / 100)

        elif ivaesp == "N":
            # sin IVA
            pass

        oferta = _OFERTAS.get(codigo, {})

        fijo  = float(oferta.get("FIJO") or 0)
        promo = float(oferta.get("PROMO") or 0)
        bonif = float(oferta.get("BONIF") or 0)
        bulto_oferta = float(oferta.get("BULTO") or 0)
        pago  = float(oferta.get("PAGO") or 0)

        precio_may_mostrar = precio_may

        if fijo > 0:
            precio_may_mostrar = fijo
        elif promo > 0:
            precio_may_mostrar *= (1 - promo / 100)

        articulo = {
            "codigo":    codigo,
            "nombre":    str(reg["DESCRIP"]).strip(),
            "precio":    round(precio, 2),
            "precio_mayorista": round(precio_may_mostrar, 2),
            "stock":     float(reg["STOCKACT"] or 0),
            "dolar":     es_dolar,
            "val_unid":  val_unid,
            "unid":      str(reg["UNIDAD"]).strip(),
            "bulto":     float(reg["CANTMAY"] or 0),
            "bonifcant": float(reg["BONIFCANT"] or 0),
            "fijo":      fijo,
            "promo":     promo,
            "bonif":     bonif,
            "bulto_oferta": bulto_oferta,
            "pago":      pago,
            "detalle":   str(oferta.get("DETALLE") or "").strip()}
        catalogo.append(articulo)

    return catalogo


# ─────────────────────────────────────────────
# APP FLASK
# ─────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB máximo por request
app.secret_key = "felo_2026"
CLIENTES_DBF = "clientes.dbf"

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":

        return render_template(
            "login.html",
            mensaje=""
        )

    documento = request.form["documento"]
    password = request.form["password"]

    cliente = buscar_cliente(documento)

    if not cliente:
        return render_template(
            "login.html",
            mensaje="Cliente no encontrado"
        )

    cuit = normalizar_numero(cliente["NROCUIT"])
    session["cuit_cliente"] = cuit

    usuarios = cargar_usuarios()

    if cuit not in usuarios:

        return redirect(
            url_for(
                "primer_ingreso",
                documento=documento
            )
        )

    hash_guardado = usuarios[cuit]["password"]

    if not check_password_hash(
        hash_guardado,
        password):
        return render_template(
            "login.html",
            mensaje="Contraseña incorrecta")

    session["numero_cliente"] = int(cliente["NUMERO"])
    session["nombre"] = str(cliente["NOMBRE"]).strip()
    session["email_cliente"] = usuarios[cuit].get("email", "")
    session["whatsapp_cliente"] = usuarios[cuit].get("whatsapp", "")
    session["cuit_cliente"] = cuit

    descuento = int(cliente["DESCUENTO"] or 0)

    if descuento == 5:
        session["tipo"] = "mayorista"
    else:
        session["tipo"] = "minorista"
    return redirect("/")

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

@app.route("/primer_ingreso")
def primer_ingreso():

    documento = request.args.get("documento", "")

    return render_template(
        "primer_ingreso.html",
        documento=documento,
        mensaje=""
    )

@app.route("/crear_acceso", methods=["POST"])
def crear_acceso():

    documento = request.form["documento"]
    password = request.form["password"]
    confirmar = request.form["confirmar"]
    if password != confirmar:
        return render_template(
            "primer_ingreso.html",
            mensaje="Las contraseñas no coinciden")
    
    email = request.form["email"].strip()
    whatsapp = request.form["whatsapp"].strip()

    cliente = buscar_cliente(documento)

    if not cliente:

        return render_template(
            "primer_ingreso.html",
            mensaje="Cliente no encontrado"
        )

    cuit = normalizar_numero(
        cliente["NROCUIT"]
    )

    session["cuit_cliente"] = cuit
    session["numero_cliente"] = cliente["NUMERO"]
    session["nombre"] = str(cliente["NOMBRE"]).strip()

    usuarios = cargar_usuarios()

    if cuit in usuarios:

        return render_template(
            "primer_ingreso.html",
            mensaje="El acceso ya existe"
        )

    usuarios[cuit] = {
        "numero_cliente": int(cliente["NUMERO"]),
        "password": generate_password_hash(password),
        "email": email,
        "whatsapp": whatsapp
    }

    guardar_usuarios(
        usuarios
    )

    return render_template(
        "login.html",
        mensaje="Acceso creado correctamente"
    )

# ── Archivos estáticos ──────────────────────
@app.route("/imagenes/<path:nombre>")
def servir_imagen(nombre):
    return send_from_directory(CARPETA_IMAGENES, nombre)


@app.route("/videos/<path:nombre>")
def servir_video(nombre):
    return send_from_directory(CARPETA_VIDEOS, nombre)

@app.route("/guardar_micuenta", methods=["POST"])
def guardar_micuenta():
    cuit = session.get("cuit_cliente")

    if not cuit:
        return jsonify({
            "ok": False,
            "mensaje": "Sesión inválida"
        })

    email = request.json["email"].strip()
    whatsapp = request.json["whatsapp"].strip()

    usuarios = cargar_usuarios()

    usuarios[cuit]["email"] = email
    usuarios[cuit]["whatsapp"] = whatsapp

    guardar_usuarios(usuarios)

    session["email_cliente"] = email
    session["whatsapp_cliente"] = whatsapp

    return jsonify({
        "ok": True,
        "mensaje": "Datos actualizados"
    })

# ── Búsqueda ────────────────────────────────
@app.route("/buscar")
def buscar():

    tipo = session.get("tipo", "minorista")

    texto = normalizar_texto(
        request.args.get("q", "")
    ).strip()

    if not texto:
        return jsonify([])

    palabras = texto.split()

    resultados = []

    for art in CATALOGO:

        codigo = normalizar_texto(
            art["codigo"]
        )

        nombre = normalizar_texto(
            art["nombre"]
        )

        coincide = all(
            palabra in codigo or palabra in nombre
            for palabra in palabras
        )

        if not coincide:
            continue

        prod = art.copy()

        if tipo == "mayorista":
            prod["precio"] = prod["precio_mayorista"]
        else:
            prod["fijo"] = 0
            prod["promo"] = 0
            prod["bonif"] = 0
            prod["bulto_oferta"] = 0
            prod["pago"] = 0
            prod["detalle"] = ""

        resultados.append(prod)

    registrar_busqueda( texto, len(resultados))

    return jsonify(resultados[:100])

# ── Pedido ──────────────────────────────────
@app.route("/enviar_pedido", methods=["POST"])
def enviar_pedido():

    try:
        if "numero_cliente" not in session:
            return jsonify({
                "ok": False,
                "requiere_login": True,
                "mensaje": "Debe iniciar sesión para enviar pedidos."
            })
        datos        = request.get_json(force=True)
        email        = datos.get("email", "").strip()
        observaciones = datos.get("observaciones", "").strip()
        carrito      = datos.get("carrito", {})

        # Validación básica del request
        if not email:
            return jsonify({"ok": False, "mensaje": "El email es obligatorio."})
        if not carrito:
            return jsonify({"ok": False, "mensaje": "El carrito está vacío."})

        # ── Validar precios en el servidor ──────────────────────────────────
        # Se ignoran los precios que manda el cliente; se usan los del catálogo.
        tipo = session.get("tipo", "minorista")

        items_validados = []
        for codigo, item in carrito.items():
            articulo_real = CATALOGO_POR_CODIGO.get(codigo.strip().upper())

            if not articulo_real:
                # Artículo no encontrado — se incluye con precio 0 y se avisa
                items_validados.append({
                    "codigo": codigo.strip().upper(),
                    "nombre": item.get("nombre", ""),
                    "unidad": item.get("unid", ""),
                    "cantidad": int(item.get("cantidad", 1)),
                    "precio": 0.0,
                    "bulto": 0.0,
                    "bonifcant": 0.0,
                    "bulto_oferta": 0.0,
                    "bonif": 0.0,
                    "promo_pct": 0,
                    "detalle": "",
                    "promo_marcada": bool(item.get("promo", False)),
                    "advertencia": True,
                })
                continue

            if tipo == "mayorista":
                precio_real = articulo_real["precio_mayorista"]
            else:
                precio_real = articulo_real["precio"]

            items_validados.append({
                "codigo": articulo_real["codigo"],
                "nombre": articulo_real["nombre"],
                "unidad": articulo_real["unid"],
                "cantidad": int(item.get("cantidad", 1)),
                "precio": precio_real,
                # Descuento por cantidad del catálogo base — aplica a MINORISTA
                "bulto": articulo_real.get("bulto", 0.0),
                "bonifcant": articulo_real.get("bonifcant", 0.0),
                # Descuento por cantidad de OFERTAS.DBF — aplica a MAYORISTA
                "bulto_oferta": articulo_real.get("bulto_oferta", 0.0),
                "bonif": articulo_real.get("bonif", 0.0),
                # Solo informativos, no afectan el subtotal
                "promo_pct": articulo_real.get("promo", 0),
                "detalle": articulo_real.get("detalle", ""),
                # Checkbox "Promo" tildado por el cliente en el carrito
                "promo_marcada": bool(item.get("promo", False)),
            })

        numero_pedido = obtener_numero_pedido()
        fecha_hora    = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # ── Armar cuerpo del email ──────────────────────────────────────────
        # CODIGO(10) DESCRIPCION(35) CANT(6) PRECIO(12) PROMO(8) DETALLE(20) = 91
        SEP = "-" * 91
        lineas = [
            "ACEROS FELO - PEDIDO WEB",
            "=" * 91,
            f"Pedido Nro: {numero_pedido}",
            f"Fecha:      {fecha_hora}",
            f"Cliente:    {email}", "",
            f"{'CODIGO':<10}"
            f"{'DESCRIPCION':<35}"
            f"{'CANT':>6}"
            f"{'PRECIO':>12} "
            f"{'PROMO':<8}"
            f"{'DETALLE':<20}",
            SEP
        ]

        total = 0.0
        for item in items_validados:
            cantidad = item["cantidad"]
            precio = item["precio"]
            subtotal = cantidad * precio
            # MINORISTA -> bonifcant/bulto (catálogo). MAYORISTA -> bonif/bulto_oferta (OFERTAS.DBF)
            if tipo == "mayorista":
                if (
                    item.get("bulto_oferta", 0) > 0 and
                    item.get("bonif", 0) > 0 and
                    cantidad >= item["bulto_oferta"]
                ):
                    subtotal *= item["bonif"]
            else:
                if (
                    item.get("bulto", 0) > 0 and
                    item.get("bonifcant", 0) > 0 and
                    cantidad >= item["bulto"]
                ):
                    subtotal *= item["bonifcant"]

            total += subtotal

        with open("logs_pedidos.txt","a", encoding="utf-8") as f:

            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            f.write(f"{fecha};{numero_pedido};{email};"f"{len(items_validados)};{total:.2f}\n")

            # PROMO/DETALLE: solo si el cliente tildó el checkbox "Promo" en el carrito
            promo_txt = ""
            detalle_txt = ""
            if item.get("promo_marcada"):
                promo_mult = item.get("promo_pct", 0)
                if 0 < promo_mult < 1:
                    promo_txt = f"-{round((1 - promo_mult) * 100)}%"
                detalle_txt = item.get("detalle", "")[:20]

            precio_mostrar = precio

            if tipo == "mayorista":
                if (
                    item.get("bulto_oferta", 0) > 0 and
                    cantidad >= item["bulto_oferta"] and
                    item.get("bonif", 0) > 0
                ):
                    precio_mostrar = precio * item["bonif"]
            else:
                if (
                    item.get("bulto", 0) > 0 and
                    cantidad >= item["bulto"] and
                    item.get("bonifcant", 0) > 0
                ):
                    precio_mostrar = precio * item["bonifcant"]

            lineas.append(
                f"{item['codigo']:<10}"
                f"{item['nombre'][:35]:<35}"
                f"{cantidad:>6}"
                f"{precio_mostrar:>12,.2f} "
                f"{promo_txt:<8}"
                f"{detalle_txt:<20}"
            )

        lineas += [SEP, f"{'TOTAL':>66} ${total:>12,.2f}"]

        if observaciones:
            lineas += [
                "",
                "📝 OBSERVACIONES",
                observaciones
            ]

        cuerpo = "\n".join(lineas)

        mensaje_preview = cuerpo

        # ── Envío opcional de emails ────────────────────────────

        if EMAIL_PASSWORD:

            try:

                correo_vendedor = MIMEText(
                    cuerpo,
                    "plain",
                    "utf-8")

                correo_vendedor["Subject"] = (
                    f"Pedido Web Nro {numero_pedido}")

                correo_vendedor["From"] = EMAIL_REMITENTE
                correo_vendedor["To"]   = EMAIL_DESTINO

                email_cliente = session.get("email_cliente", "")

                with smtplib.SMTP("smtp.gmail.com", 587) as servidor:

                    servidor.starttls()

                    servidor.login(
                        EMAIL_REMITENTE,
                        EMAIL_PASSWORD)

                    servidor.send_message(correo_vendedor)

                    if email_cliente:

                        correo_cliente = MIMEText(
                            cuerpo,
                            "plain",
                            "utf-8")

                        correo_cliente["Subject"] = (
                            f"Tu pedido Nro {numero_pedido} - Aceros Felo")

                        correo_cliente["From"] = EMAIL_REMITENTE
                        correo_cliente["To"]   = email_cliente

                    servidor.send_message(correo_cliente)

            except Exception as e:

                print("Error enviando email:", str(e))

        else:

            print(
                "EMAIL_PASSWORD no configurada. "
                "Pedido generado sin correo.")
            
        return jsonify({
            "ok": True,
            "numero_pedido": numero_pedido,
            "mensaje": f"Pedido Nro {numero_pedido} generado correctamente.",
            "preview": mensaje_preview
        })

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "ok": False,
            "mensaje": f"Error al enviar pedido: {str(e)}"
        })
    
# ── Página principal ────────────────────────
@app.route("/")
def inicio():

    tipo = session.get("tipo", "minorista")

    imagenes = [
        f for f in os.listdir(CARPETA_IMAGENES)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    videos = [
        f for f in os.listdir(CARPETA_VIDEOS)
        if f.lower().endswith(".mp4")
    ]

    imagenes_random = random.sample(
        imagenes,
        min(50, len(imagenes))
    )

    videos_random = random.sample(
        videos,
        len(videos)
    )

    productos = random.sample(
        CATALOGO,
        min(20, len(CATALOGO))
    )

    productos_mostrar = []

    for p in productos:

        prod = p.copy()

        if tipo == "mayorista":
            prod["precio"] = prod["precio_mayorista"]
        else:
            prod["fijo"] = 0
            prod["promo"] = 0
            prod["bonif"] = 0
            prod["bulto_oferta"] = 0
            prod["pago"] = 0
            prod["detalle"] = ""

        productos_mostrar.append(prod)

    usuario = datos_usuario()
    print("USUARIO =", usuario)

    return render_template(
        "index.html",
        imagenes=imagenes_random,
        videos=videos_random,
        productos=productos_mostrar,
        usuario=usuario
    )        
# ─────────────────────────────────────────────
# CARGA INICIAL
# ─────────────────────────────────────────────

print("Cargando ofertas...")
cargar_ofertas()

print("Cargando catálogo...")
CATALOGO = cargar_catalogo()

CATALOGO_POR_CODIGO = {
    art["codigo"].upper(): art
    for art in CATALOGO
}

print(f"Artículos cargados: {len(CATALOGO)}")

# ─────────────────────────────────────────────
# INICIO LOCAL
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG)