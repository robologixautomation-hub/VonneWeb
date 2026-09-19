#!/usr/bin/env python3
"""
==============================================================================
Vonne Boutique Saltillo - Auto-Respondedor de Comentarios con IA (Facebook)
==============================================================================
Monitorea publicaciones de la FanPage de Vonne Boutique, analiza las preguntas
de las clientas (precios, tallas, ubicación, envíos, stock) y responde de forma
personalizada, cálida y natural utilizando el catálogo real de la tienda.
"""

import os
import sys
import json
import time
import random
import unicodedata
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# Asegurar codificación UTF-8 en consola de Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ==============================================================================
# CONFIGURACIÓN Y RUTAS
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRATCH_ENV = r"C:\Users\PC3\.gemini\antigravity\scratch\vonne-marketing-agent\.env"
CATALOG_PATH = os.path.join(BASE_DIR, "catalogo_vonne.json")
TELEGRAM_CONFIG_PATH = os.path.join(BASE_DIR, "telegram_config.json")
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_comments.json")
LOG_FILE = os.path.join(BASE_DIR, "facebook_ai_responder.log")

STORE_LOCATION = "Blvd. Dr. Jesús Valdez Sánchez 1365, Plaza La Fragua, Saltillo, Coahuila"
STORE_HOURS = "Lunes a Sábado de 11:00 am a 8:00 pm"
STORE_WHATSAPP = "https://wa.me/528441234567"

# ==============================================================================
# UTILIDADES
# ==============================================================================
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except Exception:
        print(line.encode('ascii', errors='replace').decode('ascii'))
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def normalize(text):
    if not text:
        return ""
    t = text.lower()
    t = unicodedata.normalize('NFD', t)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return t.strip()

def load_env():
    env = {}
    if os.path.exists(SCRATCH_ENV):
        with open(SCRATCH_ENV, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env

def load_catalog():
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error cargando catálogo: {e}")
    return []

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_processed(data):
    try:
        with open(PROCESSED_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error guardando processed_comments: {e}")

def send_telegram_alert(comment_author, comment_text, reply_text, post_snippet, product_match=None):
    if not os.path.exists(TELEGRAM_CONFIG_PATH):
        return
    try:
        with open(TELEGRAM_CONFIG_PATH, encoding='utf-8') as f:
            tcfg = json.load(f)
        bot_token = tcfg.get("bot_token")
        chat_id = tcfg.get("chat_id")
        if not bot_token or not chat_id:
            return

        prod_line = f"\n👗 *Prenda identificada:* {product_match}" if product_match else ""
        msg = (
            f"🌸 *Respuesta Automática de IA en Facebook* 🌸\n\n"
            f"👤 *Clienta:* {comment_author}\n"
            f"💬 *Comentario:* \"{comment_text}\"\n"
            f"📌 *Post:* _{post_snippet[:60]}..._\n"
            f"{prod_line}\n"
            f"✨ *Respuesta enviada:*\n\"{reply_text}\""
        )
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown"
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=8)
    except Exception as e:
        log(f"Error enviando alerta a Telegram: {e}")

# ==============================================================================
# MOTOR INTELIGENTE DE RESPUESTAS (Vonne Boutique Style)
# ==============================================================================
class VonneBoutiqueAI:
    def __init__(self, catalog):
        self.catalog = catalog

    def match_product(self, text, post_context=""):
        combined = normalize(text + " " + post_context)
        best_match = None
        highest_score = 0

        for item in self.catalog:
            name_norm = normalize(item.get("nombre", ""))
            words = [w for w in name_norm.split() if len(w) > 3]
            score = 0
            for w in words:
                if w in combined:
                    score += 1
            if name_norm in combined:
                score += 3
            if score > highest_score:
                highest_score = score
                best_match = item

        return best_match if highest_score >= 1 else None

    def generate_reply(self, author_name, comment_text, post_context=""):
        norm = normalize(comment_text)
        prod = self.match_product(comment_text, post_context)
        first_name = author_name.split()[0] if author_name else "hermosa"

        greetings = [
            f"¡Hola {first_name}! ✨",
            f"¡Hola hermosa! 💕",
            f"¡Hola linda! ✨ Qué gusto saludarte.",
            f"¡Hola {first_name}! Con muchísimo gusto te apoyamos 💕",
            f"¡Hola linda! Gracias por escribirnos ✨"
        ]
        greet = random.choice(greetings)

        # 1. PRECIO
        if any(w in norm for w in ["precio", "cuanto", "$", "costo", "valor", "informes", "info"]):
            if prod:
                price = int(prod.get("precio", 0))
                tallas = ", ".join(prod.get("tallas", [])) or "Unitalla"
                options = [
                    f"{greet} Nuestro modelo *{prod['nombre']}* tiene un costo de ${price} MXN. Disponible en tallas: {tallas}. ¿Te gustaría que te apartemos el tuyo o visitarnos en Plaza La Fragua? 💕",
                    f"{greet} Con gusto: el modelo *{prod['nombre']}* está en ${price} MXN ✨ Tallas disponibles: {tallas}. Puedes apartarlo con solo el 20% enviándonos mensajito directo. ¿Te apartamos una talla?",
                    f"{greet} Esta prenda divina (*{prod['nombre']}*) cuesta ${price} MXN ✨ La tenemos en tallas {tallas}. ¡Quedan pocas piezas! ¿Te enviamos fotos o detalles por mensaje privado? 💕"
                ]
                return random.choice(options), prod['nombre']
            else:
                options = [
                    f"{greet} Con muchísimo gusto te compartimos el precio exacto y las tallas disponibles por mensaje directo para darte atención personalizada ✨ ¡Revisa tu buzón!",
                    f"{greet} Claro que sí hermosa ✨ Te enviamos el costo y detalles completos por mensajito privado para atenderte súper bien 💕",
                    f"{greet} ¡Hola! Con gusto te damos el precio. ¿De qué modelo o foto te gustaría recibir la información completa? Te mandamos mensajito directo ✨"
                ]
                return random.choice(options), None

        # 2. UBICACIÓN / DIRECCIÓN / HORARIO
        if any(w in norm for w in ["donde", "ubicacion", "direccion", "plaza", "saltillo", "horario", "abren", "visitar", "tienda"]):
            options = [
                f"{greet} ¡Nos encantará recibirte! 💕 Estamos ubicadas en {STORE_LOCATION}. Nuestro horario es {STORE_HOURS}. ¿Buscas alguna prenda en especial para tenerla lista? ✨",
                f"{greet} ¡Te esperamos con mucho gusto! 🛍️ Nuestra boutique física está en {STORE_LOCATION}. Abrimos {STORE_HOURS}. ¡Ven a probarte tus prendas favoritas! 💕",
                f"{greet} Estamos ubicadas en Plaza La Fragua sobre Valdez Sánchez (#1365), en Saltillo Coahuila ✨ Abrimos {STORE_HOURS}. Con gusto te esperamos hermosura."
            ]
            return random.choice(options), None

        # 3. ENVÍOS / ENTREGAS
        if any(w in norm for w in ["envio", "envios", "hacen envio", "entrega", "mandan", "paqueteria", "foraneo", "ramos", "arteaga"]):
            options = [
                f"{greet} ¡Sí hacemos envíos! 📦✨ Realizamos envíos locales en todo Saltillo y envíos nacionales seguros a toda la República Mexicana. ¿A qué ciudad o colonia te gustaría recibir tu pedido? 💕",
                f"{greet} ¡Claro que sí hermosa! Contamos con envíos express en Saltillo y paquetería a todo México 📦✈️. Puedes apartar tu prenda y te la enviamos hasta la puerta de tu casa. ¿Te gustaría cotizar tu envío? ✨",
                f"{greet} Sí manejamos servicio de envío local y nacional 🛍️📦 Escríbenos por inbox o mensaje privado con tu código postal para cotizártelo con gusto 💕"
            ]
            return random.choice(options), None

        # 4. TALLAS / MEDIDAS
        if any(w in norm for w in ["talla", "tallas", "ch", "mediana", "grande", "extra", "unitalla", "medida"]):
            if prod:
                tallas = ", ".join(prod.get("tallas", [])) or "Unitalla"
                return f"{greet} El modelo *{prod['nombre']}* lo tenemos disponible en tallas: {tallas} ✨ También te podemos compartir medidas exactas por mensaje privado si gustas 💕", prod['nombre']
            options = [
                f"{greet} Manejamos variedad de tallas desde Chica hasta Grande, además de hermosos modelos Unitalla que amoldan precioso ✨ ¿Qué talla buscas tú en específico?",
                f"{greet} Con gusto te apoyamos con la tabla de medidas y disponibilidad de tallas por mensaje directo 💕 ¿Para qué prenda te gustaría consultar?"
            ]
            return random.choice(options), None

        # 5. APARTADOS / FORMAS DE PAGO
        if any(w in norm for w in ["apartar", "apartado", "tarjeta", "transferencia", "pago", "pagar", "efectivo"]):
            options = [
                f"{greet} ¡Sí aceptamos sistema de apartado! ✨ Puedes asegurar tu prenda favorita con solo el 20% de anticipo. Aceptamos efectivo, transferencias y tarjetas de débito/crédito en tienda 💕 ¿Te gustaría apartar algún modelo?",
                f"{greet} Claro que sí hermosa, puedes apartar tus prendas con el 20% y liquidar después ✨ Aceptamos tarjeta, transferencia y pago en tienda. Mándanos mensaje directo para apartártelo de inmediato 💕"
            ]
            return random.choice(options), None

        # 6. CUMPLIDOS / INTERÉS
        if any(w in norm for w in ["hermoso", "hermosa", "bello", "bello", "encanta", "lindo", "precioso", "quiero", "me gusta"]):
            options = [
                f"{greet} ¡Muchísimas gracias! 💕 La verdad es que se ve espectacular y la calidad de la tela te va a encantar. ¿Te gustaría que te reservemos tu talla antes de que se agote? ✨",
                f"{greet} ¡Está divino verdad! 😍 Luce espectacular puesto. Te enviamos los detalles por mensaje privado para que no te quedes sin el tuyo ✨ ¡Quedan poquitas piezas!",
                f"{greet} ¡Gracias por tu lindo comentario! ✨ Es de nuestras piezas favoritas de temporada. Con mucho gusto te podemos dar atención personalizada por mensajito directo 💕"
            ]
            return random.choice(options), prod['nombre'] if prod else None

        # 7. GENERAL
        options = [
            f"{greet} Con muchísimo gusto te atendemos 💕 Te mandamos un mensajito privado para darte atención personalizada y resolver todas tus dudas sobre disponibilidad y tallas ✨",
            f"{greet} ¡Qué gusto saludarte! Con mucho gusto te compartimos todos los detalles por mensaje directo para atenderte como te mereces 💕 ¡Revisa tu buzón!",
            f"{greet} ¡Gracias por escribirnos! ✨ Te enviamos mensajito privado con toda la información de nuestras prendas y promociones activas. ¡Bonito día! 💕"
        ]
        return random.choice(options), None

# ==============================================================================
# PROCESAMIENTO PRINCIPAL
# ==============================================================================
def process_facebook_comments(simulate=False):
    log("=" * 65)
    log(f"Iniciando escaneo de comentarios Facebook (Modo Simulación: {simulate})")
    log("=" * 65)

    env = load_env()
    page_token = env.get("PAGE_ACCESS_TOKEN")
    page_id = env.get("PAGE_ID", "1717174328538010")

    if not page_token:
        log("ERROR: No se encontró PAGE_ACCESS_TOKEN en el archivo de configuración.")
        return

    catalog = load_catalog()
    ai = VonneBoutiqueAI(catalog)
    processed = load_processed()

    if simulate:
        log("--- EJECUTANDO SIMULACIÓN CON CASOS REALES ---")
        mock_comments = [
            {"from": {"name": "Mariana López", "id": "u1"}, "message": "Hola buenas tardes, que precio tiene la capa?", "post": "Nueva Capa de Gala disponible en tienda"},
            {"from": {"name": "Sofia Garza", "id": "u2"}, "message": "Donde se encuentran ubicadas?? Tienen tienda física?", "post": "Colección Otoño en Vonne Boutique"},
            {"from": {"name": "Karla Mendoza", "id": "u3"}, "message": "Hacen envios a Ramos Arizpe??", "post": "Chaleco Peluche Con Gorro"},
            {"from": {"name": "Ana Lucía R.", "id": "u4"}, "message": "Esta bellisimo me encanta 😍 se puede apartar?", "post": "Conjunto Tejidos Varios de Gala"},
            {"from": {"name": "Valeria H.", "id": "u5"}, "message": "Tienen en talla mediana disponible?", "post": "Blazer Ejecutivo Negro"},
        ]

        for mc in mock_comments:
            reply, prod = ai.generate_reply(mc["from"]["name"], mc["message"], mc["post"])
            log(f"\n[CLIENTA]: {mc['from']['name']}")
            log(f"[PREGUNTA]: \"{mc['message']}\"")
            log(f"[PRODUCTO DETECTADO]: {prod or 'General'}")
            log(f"[RESPUESTA IA]:\n{reply}")
            log("-" * 50)
        return

    url_posts = f"https://graph.facebook.com/v20.0/{page_id}/published_posts?fields=id,message,created_time,permalink_url&limit=10&access_token={page_token}"

    try:
        req = urllib.request.Request(url_posts)
        with urllib.request.urlopen(req, timeout=12) as resp:
            posts_data = json.loads(resp.read().decode())
            posts = posts_data.get("data", [])
            log(f"Se encontraron {len(posts)} publicaciones recientes.")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        log(f"AVISO GRAPH API: Código {e.code} - {err}")
        return
    except Exception as e:
        log(f"Error de conexión a Facebook: {e}")
        return

    nuevas_respuestas = 0
    for post in posts:
        post_id = post.get("id")
        post_msg = post.get("message", "")
        url_comments = f"https://graph.facebook.com/v20.0/{post_id}/comments?fields=id,message,from,created_time&limit=25&access_token={page_token}"

        try:
            req_c = urllib.request.Request(url_comments)
            with urllib.request.urlopen(req_c, timeout=10) as resp_c:
                c_data = json.loads(resp_c.read().decode())
                comments = c_data.get("data", [])
        except Exception:
            continue

        for c in comments:
            cid = c.get("id")
            c_author = c.get("from", {}).get("name", "Clienta")
            c_author_id = c.get("from", {}).get("id")
            c_text = c.get("message", "").strip()

            if c_author_id == page_id or cid in processed or not c_text:
                continue

            log(f"\n[NUEVO COMENTARIO]: De {c_author} ({cid}): \"{c_text}\"")
            reply_text, prod_match = ai.generate_reply(c_author, c_text, post_msg)
            log(f"Respuesta generada:\n{reply_text}")

            url_reply = f"https://graph.facebook.com/v20.0/{cid}/comments"
            reply_data = urllib.parse.urlencode({
                "message": reply_text,
                "access_token": page_token
            }).encode('utf-8')

            try:
                req_post = urllib.request.Request(url_reply, data=reply_data, method='POST')
                with urllib.request.urlopen(req_post, timeout=10) as r_post:
                    res = json.loads(r_post.read().decode())
                    log(f"✅ RESPUESTA PUBLICADA EN FACEBOOK! ID: {res.get('id')}")
                    processed[cid] = {
                        "author": c_author,
                        "comment": c_text,
                        "reply": reply_text,
                        "reply_id": res.get("id"),
                        "timestamp": datetime.now().isoformat()
                    }
                    save_processed(processed)
                    nuevas_respuestas += 1
                    send_telegram_alert(c_author, c_text, reply_text, post_msg, prod_match)
                    time.sleep(random.uniform(5, 12))
            except Exception as ex:
                log(f"❌ Error publicando en Facebook: {ex}")
                processed[cid] = {"error": str(ex), "timestamp": datetime.now().isoformat()}
                save_processed(processed)

    log(f"\nFin de ciclo. Respuestas enviadas: {nuevas_respuestas}")

if __name__ == "__main__":
    simulate = "--simulate" in sys.argv or "--test" in sys.argv
    is_daemon = "--daemon" in sys.argv
    test_query = None
    interval_seconds = 300  # 5 minutos por defecto

    for i, arg in enumerate(sys.argv):
        if arg == "--test-comment" and i + 1 < len(sys.argv):
            test_query = sys.argv[i + 1]
        elif arg == "--interval" and i + 1 < len(sys.argv):
            try:
                interval_seconds = int(sys.argv[i + 1])
            except ValueError:
                pass

    if test_query:
        catalog = load_catalog()
        ai = VonneBoutiqueAI(catalog)
        reply, prod = ai.generate_reply("Carolina", test_query, "Colección de Invierno Vonne Boutique")
        print("\n" + "=" * 50)
        print(f"PREGUNTA PRUEBA: \"{test_query}\"")
        print(f"PRODUCTO RECONOCIDO: {prod}")
        print(f"RESPUESTA GENERADA:\n{reply}")
        print("=" * 50 + "\n")
    elif is_daemon:
        log(f"Iniciando servicio continuo en segundo plano (Intervalo: {interval_seconds} seg)...")
        while True:
            try:
                process_facebook_comments(simulate=simulate)
            except Exception as e:
                log(f"Error en ciclo de monitoreo: {e}")
            time.sleep(interval_seconds)
    else:
        process_facebook_comments(simulate=simulate)

