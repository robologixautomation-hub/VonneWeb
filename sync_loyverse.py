#!/usr/bin/env python3
"""
Sincronizador Oficial de Loyverse POS para Vonne Boutique
- Lee Vonne_items.csv (exportacion de punto de venta)
- O se conecta a la API REST de Loyverse (https://api.loyverse.com/v1.0) usando un Token de Acceso
- Consolida variantes de tallas (CH, M, G, XL, XXL) en productos unificados
- Mapea a las categorias de la boutique
- Genera catalogo_vonne.json y actualiza catalogo_google_drive.csv
"""

import os
import sys
import csv
import json
import re
import urllib.request
import urllib.error

# Forzar codificación UTF-8 en consola de Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POS_CSV_PATH = os.path.join(BASE_DIR, "Vonne_items.csv")
CONFIG_PATH = os.path.join(BASE_DIR, "loyverse_config.json")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "catalogo_vonne.json")
OUTPUT_CSV_PATH = os.path.join(BASE_DIR, "catalogo_google_drive.csv")

# Mapeo de categorias del POS a slugs de la web
CATEGORY_MAPPING = {
    "blazer": "blazers",
    "blusas primavera": "blusas",
    "blusas y panty blusas  varias": "blusas",
    "vestidos primavera": "vestidos",
    "vestido y blusones tejidos": "vestidos",
    "traje de baño": "trajes-bano",
    "traje de bano": "trajes-bano",
    "conjuntos": "conjuntos",
    "faldas": "pantalones-faldas",
    "pantalon": "pantalones-faldas",
    "short": "pantalones-faldas",
    "fajas": "fajas",
    "camisa": "blusas",
    "chalecos": "abrigos-chalecos",
    "abrigos": "abrigos-chalecos",
    "suéter": "abrigos-chalecos",
    "sueter": "abrigos-chalecos",
    "medias": "accesorios",
    "cintos": "accesorios",
    "ofertas": "promociones",
    "liquidaciones": "promociones",
    "liquidados": "promociones",
}

def load_config():
    token = os.environ.get("LOYVERSE_TOKEN", "").strip()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if not token and cfg.get("token"):
                    token = cfg.get("token").strip()
        except Exception:
            pass
    return {"token": token}

def clean_base_name(name):
    n = name.strip()
    # Corrección de typos en el POS
    n = re.sub(r'\bbalzer\b', 'Blazer', n, flags=re.IGNORECASE)
    n = re.sub(r'\bbalser\b', 'Blazer', n, flags=re.IGNORECASE)
    # Tallas en texto completo
    n = re.sub(r'\s+(?:talla\s+)?(?:chica|mediana|grande|extra grande)\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s+(?:talla\s+)?(?:ch|m|g|xl|xxl|2xl|unitalla|exch)\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'[\s\-_]+(?:ch|m|g|xl|xxl)$', '', n, flags=re.IGNORECASE)
    n = " ".join(n.split())
    return n.title()

def extract_size(name):
    n = name.lower()
    if "unitalla" in n:
        return "UNITALLA"
    if "xxl" in n or "2xl" in n:
        return "XXL"
    if "xl" in n or "extra grande" in n:
        return "XL"
    if re.search(r'\b(ch|chica|s|exch)\b', n):
        return "CH"
    if re.search(r'\b(m|mediana)\b', n):
        return "M"
    if re.search(r'\b(g|grande|l)\b', n):
        return "G"
    return "UNITALLA"

def map_category(cat_pos_name, item_name=""):
    cleaned = (cat_pos_name or "").strip().lower()
    cleaned = cleaned.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    mapped = CATEGORY_MAPPING.get(cleaned)
    if mapped:
        return mapped

    # Inferencia inteligente a partir del nombre de la prenda si no tiene categoría
    n = (item_name or "").lower()
    if "blazer" in n:
        return "blazers"
    if "blusa" in n or "camisa" in n:
        return "blusas"
    if "vestido" in n or "palazo" in n or "jumpsuit" in n:
        return "vestidos"
    if "falda" in n or "pantalon" in n or "pantalón" in n or "leggin" in n or "short" in n:
        return "pantalones-faldas"
    if "conjunto" in n:
        return "conjuntos"
    if "faja" in n or "cinturilla" in n:
        return "fajas"
    if "traje de" in n or "baño" in n or "bano" in n or "bikini" in n or "pareo" in n or "agua" in n:
        return "trajes-bano"
    if "capa" in n or "chaleco" in n or "abrigo" in n or "sueter" in n or "suéter" in n:
        return "abrigos-chalecos"
    if "media" in n or "cinto" in n or "gorro" in n:
        return "accesorios"
    return "casual"

def fetch_loyverse_api(token):
    print("📡 Conectando a Loyverse API (https://api.loyverse.com/v1.0)...")
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "VonneBoutiqueSync/1.0"
    }

    categories_map = {}
    try:
        req = urllib.request.Request("https://api.loyverse.com/v1.0/categories", headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for cat in data.get("categories", []):
                categories_map[cat["id"]] = cat.get("name", "")
        print(f"✅ Categorias obtenidas de API: {len(categories_map)}")
    except Exception as e:
        print(f"⚠️ Aviso categorias: {e}")

    inventory_map = {}
    cursor = None
    while True:
        url = "https://api.loyverse.com/v1.0/inventory"
        if cursor:
            url += f"?cursor={cursor}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for inv in data.get("inventory_levels", []):
                    inventory_map[inv.get("variant_id")] = float(inv.get("in_stock", 0))
                cursor = data.get("cursor")
                if not cursor:
                    break
        except Exception as e:
            print(f"⚠️ Error inventario: {e}")
            break

    print(f"✅ Existencias obtenidas para {len(inventory_map)} variantes")

    items = []
    cursor = None
    while True:
        url = "https://api.loyverse.com/v1.0/items"
        if cursor:
            url += f"?cursor={cursor}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items.extend(data.get("items", []))
                cursor = data.get("cursor")
                if not cursor:
                    break
        except Exception as e:
            print(f"❌ Error items Loyverse: {e}")
            break

    print(f"✅ Total items descargados: {len(items)}")

    # Consolidación inteligente de variantes y fotos reales
    products_by_base = {}

    for item in items:
        item_id = item.get("id")
        raw_name = item.get("item_name") or ""
        if raw_name.lower() in ["anticipos", "liquidados", "prendas liquidación rack", "liquidaciones"]:
            continue

        base_name = clean_base_name(raw_name)
        cat_name = categories_map.get(item.get("category_id"), "")
        cat_slug = map_category(cat_name, base_name)
        item_image = item.get("image_url")
        size_from_name = extract_size(raw_name)

        if base_name not in products_by_base:
            products_by_base[base_name] = {
                "id": item_id,
                "codigo": "",
                "nombre": base_name,
                "categoria": cat_slug,
                "precio": 0,
                "precio_original": None,
                "tallas_con_stock": set(),
                "todas_tallas": set(),
                "stock_total": 0,
                "foto_url": item_image or "",
                "descripcion": ""
            }

        prod = products_by_base[base_name]
        if item_image and not prod["foto_url"]:
            prod["foto_url"] = item_image

        variants = item.get("variants", [])
        for var in variants:
            var_id = var.get("variant_id")
            var_name = var.get("variant_name")
            sku = var.get("sku") or ""
            if sku and not prod["codigo"]:
                prod["codigo"] = f"VB-{sku}"

            # Determinar talla
            size = size_from_name
            if var_name and var_name.lower() not in ["regular", "predeterminado", "default", "unitalla"]:
                size = extract_size(var_name)

            prod["todas_tallas"].add(size)

            price = float(var.get("default_price") or var.get("price") or 0)
            if price > 0 and (prod["precio"] == 0 or price < prod["precio"]):
                prod["precio"] = price

            stock = inventory_map.get(var_id, 0)
            if stock > 0:
                prod["tallas_con_stock"].add(size)
                prod["stock_total"] += stock

    final_catalog = []
    size_order = {"EXCH": 1, "CH": 2, "M": 3, "G": 4, "XL": 5, "XXL": 6, "2XL": 7, "UNITALLA": 8}

    for base_name, data in products_by_base.items():
        # Filtro estricto 1: Omitir si no tiene existencias (stock <= 0)
        if data["stock_total"] <= 0:
            continue

        # Filtro estricto 2: Omitir si no tiene foto real (sin fotos genéricas ni placeholders)
        photo = (data.get("foto_url") or "").strip()
        if not photo:
            continue

        avail = data["tallas_con_stock"] if data["tallas_con_stock"] else data["todas_tallas"]
        sorted_sizes = sorted(list(avail), key=lambda s: size_order.get(s, 99))
        tallas_str = ", ".join(sorted_sizes) if sorted_sizes else "UNITALLA"

        cat_slug = data["categoria"]

        etiqueta = "En Tienda"
        if "blazer" in base_name.lower():
            etiqueta = "Favorito Saltillo"
        elif data["categoria"] == "trajes-bano":
            etiqueta = "Top Búsquedas"
        elif data["categoria"] == "fajas":
            etiqueta = "Cintura de Avispa"
        elif data["precio"] >= 700:
            etiqueta = "Colección Gala"
        elif data["precio"] <= 300 and data["precio"] > 0:
            etiqueta = "Oferta"

        desc = (f"Prenda disponible en Vonne Boutique Plaza La Fragua, Saltillo. "
                f"Tallas: {tallas_str}. Consulta existencias en tiempo real por WhatsApp.")

        final_catalog.append({
            "codigo": data["codigo"] or f"VB-{data['id'][:6]}",
            "nombre": data["nombre"],
            "categoria": cat_slug,
            "precio": data["precio"],
            "precio_original": round(data["precio"] * 1.25) if data["precio"] > 0 else None,
            "tallas": sorted_sizes,
            "stock": data["stock_total"],
            "etiqueta": etiqueta,
            "foto_url": photo,
            "descripcion": desc,
            "activo": "SI"
        })

    final_catalog.sort(key=lambda x: (
        "api.loyverse.com" in x.get("foto_url", "") or "googleusercontent.com" in x.get("foto_url", "") or "drive.google.com" in x.get("foto_url", ""),
        x["stock"] > 0,
        x["precio"]
    ), reverse=True)
    return final_catalog

def process_csv_inventory(csv_path):
    if not os.path.exists(csv_path):
        print(f"❌ Error: No se encontro el archivo {csv_path}")
        return []

    print(f"📖 Leyendo archivo POS: {os.path.basename(csv_path)}...")
    with open(csv_path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"📊 Registros en el POS: {len(rows)}")

    products_by_base = {}

    for row in rows:
        name_raw = row.get("Nombre", "").strip()
        ref = row.get("REF", "").strip()
        cat_pos = row.get("Categoria", "").strip()
        price_str = row.get("Precio [VONNE BOUTIQUE]", "").strip()
        stock_str = row.get("En inventario [VONNE BOUTIQUE]", "0").strip()

        if name_raw.lower() in ["anticipos", "liquidados", "prendas liquidación rack", "liquidaciones"]:
            continue

        try:
            stock = float(stock_str)
        except Exception:
            stock = 0.0

        try:
            price = float(price_str)
        except Exception:
            price = 0.0

        base_name = clean_base_name(name_raw)
        size = extract_size(name_raw)
        cat_slug = map_category(cat_pos, base_name)

        if base_name not in products_by_base:
            products_by_base[base_name] = {
                "codigo": f"VB-{ref}" if ref else f"VB-{len(products_by_base)+1:03d}",
                "nombre": base_name,
                "categoria": cat_slug,
                "categoria_pos": cat_pos,
                "precio": price,
                "precio_original": None,
                "tallas_con_stock": set(),
                "todas_tallas": set(),
                "stock_total": 0,
                "foto_url": "",
                "descripcion": ""
            }

        prod = products_by_base[base_name]
        prod["todas_tallas"].add(size)
        if stock > 0:
            prod["tallas_con_stock"].add(size)
            prod["stock_total"] += stock
        if price > 0 and (prod["precio"] == 0 or price < prod["precio"]):
            prod["precio"] = price

    final_catalog = []
    size_order = {"EXCH": 1, "CH": 2, "M": 3, "G": 4, "XL": 5, "XXL": 6, "2XL": 7, "UNITALLA": 8}

    for base_name, data in products_by_base.items():
        # Filtro estricto 1: Omitir si no tiene existencias (stock <= 0)
        if data["stock_total"] <= 0:
            continue

        # Filtro estricto 2: Omitir si no tiene foto real (sin fotos genéricas ni placeholders)
        photo = (data.get("foto_url") or "").strip()
        if not photo:
            continue

        available_sizes = data["tallas_con_stock"] if data["tallas_con_stock"] else data["todas_tallas"]
        sorted_sizes = sorted(list(available_sizes), key=lambda s: size_order.get(s, 99))
        tallas_str = ", ".join(sorted_sizes) if sorted_sizes else "UNITALLA"

        cat_slug = data["categoria"]

        etiqueta = "En Tienda"
        if "blazer" in base_name.lower():
            etiqueta = "Favorito Saltillo"
        elif data["categoria"] == "trajes-bano":
            etiqueta = "Top Búsquedas"
        elif data["categoria"] == "fajas":
            etiqueta = "Cintura de Avispa"
        elif data["precio"] >= 700:
            etiqueta = "Colección Gala"
        elif data["precio"] <= 300 and data["precio"] > 0:
            etiqueta = "Oferta"

        desc = (f"Prenda disponible en Vonne Boutique Plaza La Fragua, Saltillo. "
                f"Tallas: {tallas_str}. Consulta existencias en tiempo real por WhatsApp.")

        final_catalog.append({
            "codigo": data["codigo"],
            "nombre": data["nombre"],
            "categoria": cat_slug,
            "precio": data["precio"],
            "precio_original": round(data["precio"] * 1.25) if data["precio"] > 0 else None,
            "tallas": sorted_sizes,
            "stock": data["stock_total"],
            "etiqueta": etiqueta,
            "foto_url": photo,
            "descripcion": desc,
            "activo": "SI"
        })

    final_catalog.sort(key=lambda x: (
        "api.loyverse.com" in x.get("foto_url", "") or "googleusercontent.com" in x.get("foto_url", "") or "drive.google.com" in x.get("foto_url", ""),
        x["stock"] > 0,
        x["precio"]
    ), reverse=True)
    return final_catalog

def save_catalogs(catalog_items):
    # 1. Guardar catalogo_vonne.json (formato API/JSON)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog_items, f, indent=2, ensure_ascii=False)
    print(f"✨ Guardado JSON: {OUTPUT_JSON_PATH}")
    print(f"   Total productos consolidados: {len(catalog_items)}")

    # 2. Guardar catalogo_data.js (inyección directa sin bloqueos de CORS en navegadores locales)
    OUTPUT_JS_PATH = os.path.join(BASE_DIR, "catalogo_data.js")
    with open(OUTPUT_JS_PATH, "w", encoding="utf-8") as f:
        f.write("// Catálogo oficial sincronizado de Vonne Boutique\n")
        f.write("window.VONNE_CATALOGO_DATA = " + json.dumps(catalog_items, indent=2, ensure_ascii=False) + ";\n")
    print(f"✨ Guardado JS directo: {OUTPUT_JS_PATH}")

    # 3. Guardar catalogo_google_drive.csv (plantilla sincronizada)
    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "codigo", "nombre", "categoria", "precio", "precio_original",
            "tallas", "etiqueta", "foto_url", "descripcion", "activo"
        ])
        for p in catalog_items:
            tallas_str = ", ".join(p["tallas"]) if isinstance(p["tallas"], list) else str(p["tallas"])
            precio_orig = p.get("precio_original") or ""
            writer.writerow([
                p["codigo"],
                p["nombre"],
                p["categoria"],
                p["precio"],
                precio_orig,
                tallas_str,
                p["etiqueta"],
                p["foto_url"],
                p["descripcion"],
                p["activo"]
            ])
    print(f"✨ Actualizada plantilla de Google Drive: {OUTPUT_CSV_PATH}")

    # Registro en historial de sincronización
    try:
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        in_stock_cnt = len([p for p in catalog_items if (p.get("stock") or 0) > 0])
        log_file = os.path.join(BASE_DIR, "historial_sincronizacion.log")
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"[{now_str}] Sincronización OK: {len(catalog_items)} modelos ({in_stock_cnt} en stock)\n")
    except Exception:
        pass

def main():
    print("=" * 60)
    print(" 🌟 Vonne Boutique - Sincronizador Loyverse POS / Inventario")
    print("=" * 60)

    cfg = load_config()
    token = cfg.get("token")

    if len(sys.argv) > 1 and sys.argv[1].startswith("--token="):
        token = sys.argv[1].split("=", 1)[1].strip()

    catalog = None
    if token:
        try:
            catalog = fetch_loyverse_api(token)
        except Exception as e:
            print(f"⚠️ Error API Loyverse: {e}")
            print("🔄 Recurriendo al archivo Vonne_items.csv...")

    if not catalog:
        catalog = process_csv_inventory(POS_CSV_PATH)

    if catalog:
        save_catalogs(catalog)
        with_stock = [p for p in catalog if p["stock"] > 0]
        print(f"\n🎉 ¡Sincronización completada con éxito!")
        print(f"   • Productos con existencias en tienda: {len(with_stock)}")
        print(f"   • Modelos totales en catálogo: {len(catalog)}")
    else:
        print("❌ No se pudo generar el catálogo.")

if __name__ == "__main__":
    main()
