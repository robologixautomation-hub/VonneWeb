#!/usr/bin/env python3
"""
Vonne Boutique Saltillo - Asistente Inteligente de Loyverse POS
Permite responder preguntas en lenguaje natural en Telegram sobre:
- Stock y existencias de prendas específicas
- Precios y tallas disponibles
- Ventas del día, ayer, semana o mes
- Prendas más vendidas (Top Sellers)
- Prendas agotadas o con poco inventario
- Desempeño y ventas por cajera/colaboradora
- Búsqueda de tickets específicos
- Síntesis inteligente con IA (Google Gemini) si está configurada la API Key
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE_DIR, "catalogo_vonne.json")
LOYVERSE_CONFIG_PATH = os.path.join(BASE_DIR, "loyverse_config.json")
TELEGRAM_CONFIG_PATH = os.path.join(BASE_DIR, "telegram_config.json")

MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

DAYS_ES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles",
    3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"
}

def format_money(val):
    try:
        v = float(val)
        return f"${v:,.2f} MXN"
    except Exception:
        return f"${val} MXN"

def format_iso_time(iso_str, offset_hours=-6):
    if not iso_str:
        return "N/A"
    try:
        clean_str = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        local_dt = dt.astimezone(timezone(timedelta(hours=offset_hours)))
        return local_dt.strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        return iso_str[:16].replace("T", " ")

class LoyverseAssistant:
    def __init__(self, loy_token, tg_cfg=None):
        self.loy_token = loy_token
        self.tg_cfg = tg_cfg or {}
        self.offset_hours = self.tg_cfg.get("timezone_offset_hours", -6)
        self.tz = timezone(timedelta(hours=self.offset_hours))
        self.employees_cache = {}
        self.payment_types_cache = {}
        self._load_metadata()

    def _api_get(self, endpoint):
        url = f"https://api.loyverse.com/v1.0/{endpoint}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.loy_token}",
            "User-Agent": "VonneAssistant/2.0"
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _load_metadata(self):
        if not self.loy_token:
            return
        try:
            data = self._api_get("employees")
            for emp in data.get("employees", []):
                self.employees_cache[emp["id"]] = emp.get("name", "Vonne Boutique")
        except Exception:
            pass
        try:
            pt_data = self._api_get("payment_types")
            for pt in pt_data.get("payment_types", []):
                self.payment_types_cache[pt["id"]] = pt.get("name", "Otro")
        except Exception:
            pass

    def load_catalog(self):
        if os.path.exists(CATALOG_PATH):
            try:
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    # -------------------------------------------------------------------------
    # 1. Búsqueda de Stock y Precios de Prendas
    # -------------------------------------------------------------------------
    def search_products(self, query):
        catalog = self.load_catalog()
        stop_words = {
            "tienes", "cuanto", "cuánto", "queda", "quedan", "hay", "stock",
            "precio", "cuesta", "cuestan", "talla", "tallas", "tienen", "de", "la",
            "el", "los", "las", "un", "una", "en", "por", "favor", "me", "dices",
            "existencia", "existencias", "disponible", "disponibles"
        }
        tokens = [t.lower().strip("?,.!") for t in query.split() if len(t) > 1]
        search_terms = [t for t in tokens if t not in stop_words]
        if not search_terms:
            search_terms = tokens

        scored = []
        for p in catalog:
            text = f"{p.get('nombre', '')} {p.get('codigo', '')} {p.get('categoria', '')}".lower()
            score = 0
            for term in search_terms:
                if term in text:
                    score += 2 if term in p.get("nombre", "").lower() else 1
            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:5]]

    def answer_stock_or_price(self, query):
        matches = self.search_products(query)
        if not matches:
            return (
                "🔍 <b>No encontré esa prenda en el catálogo.</b>\n\n"
                "Intenta con palabras clave como <i>blazer, faja, vestido, chaleco, blusa, short</i> o el código de prenda (ej. <code>VB-10101</code>)."
            )

        lines = [f"👗 <b>RESULTADOS EN CATÁLOGO ({len(matches)})</b>\n"]
        for p in matches:
            nombre = p.get("nombre", "Prenda")
            codigo = p.get("codigo", "")
            precio = format_money(p.get("precio", 0))
            tallas = ", ".join(p.get("tallas", ["UNITALLA"]))
            stock = int(p.get("stock", 0))
            badge = "🟢 Disponible" if stock > 3 else ("🟡 Pocas piezas" if stock > 0 else "🔴 Agotado")

            lines.append(
                f"• <b>{nombre}</b> (<code>{codigo}</code>)\n"
                f"  💰 <b>Precio:</b> {precio}\n"
                f"  📏 <b>Tallas:</b> {tallas}\n"
                f"  📦 <b>Stock:</b> <b>{stock} pzas</b> ({badge})\n"
            )

        lines.append("📍 <i>Plaza La Fragua, Saltillo</i>")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # 2. Resumen Semanal o Mensual
    # -------------------------------------------------------------------------
    def get_period_sales_summary(self, days=7, label="ÚLTIMOS 7 DÍAS"):
        now_utc = datetime.now(timezone.utc)
        start_utc = now_utc - timedelta(days=days)
        s_iso = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        e_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            data = self._api_get(f"receipts?created_at_min={s_iso}&created_at_max={e_iso}&limit=250")
            receipts = data.get("receipts", [])
        except Exception as e:
            return f"❌ Error consultando ventas del período: {e}"

        sales_receipts = [r for r in receipts if r.get("receipt_type") == "SALE" and not r.get("cancelled_at")]
        total_money = sum(r.get("total_money", 0.0) for r in sales_receipts)
        total_tickets = len(sales_receipts)

        items_agg = defaultdict(int)
        payments_agg = defaultdict(float)
        employees_agg = defaultdict(float)

        for r in sales_receipts:
            for it in r.get("line_items", []):
                items_agg[it.get("item_name", "Prenda")] += it.get("quantity", 1)
            for p in r.get("payments", []):
                p_name = p.get("name") or self.payment_types_cache.get(p.get("payment_type_id"), "Efectivo")
                payments_agg[p_name] += p.get("money_amount", 0.0)
            emp_name = self.employees_cache.get(r.get("employee_id"), "Vonne Boutique")
            employees_agg[emp_name] += r.get("total_money", 0.0)

        total_pieces = sum(items_agg.values())
        avg_ticket = (total_money / total_tickets) if total_tickets > 0 else 0.0

        pay_lines = [f"• <b>{k}:</b> {format_money(v)}" for k, v in sorted(payments_agg.items(), key=lambda x: x[1], reverse=True)]
        pay_str = "\n".join(pay_lines) if pay_lines else "• Sin cobros registrados"

        emp_lines = [f"• <b>{k}:</b> {format_money(v)}" for k, v in sorted(employees_agg.items(), key=lambda x: x[1], reverse=True)]
        emp_str = "\n".join(emp_lines) if emp_lines else "• General"

        top_items = sorted(items_agg.items(), key=lambda x: x[1], reverse=True)[:5]
        top_lines = [f"• {qty}x <b>{name}</b>" for name, qty in top_items]
        top_str = "\n".join(top_lines) if top_lines else "• Sin prendas"

        return (
            f"📊 <b>REPORTE DE VENTAS ({label})</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n\n"
            f"💰 <b>Ventas Totales:</b> <b>{format_money(total_money)}</b>\n"
            f"🎟️ <b>Tickets Cobrados:</b> {total_tickets}\n"
            f"👗 <b>Prendas Vendidas:</b> {total_pieces} piezas\n"
            f"🎯 <b>Ticket Promedio:</b> {format_money(avg_ticket)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 <b>FORMAS DE PAGO:</b>\n"
            f"{pay_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>VENTAS POR COLABORADORA:</b>\n"
            f"{emp_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛍️ <b>PRENDAS MÁS VENDIDAS:</b>\n"
            f"{top_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    # -------------------------------------------------------------------------
    # 3. Prendas Más Vendidas (Top Sellers)
    # -------------------------------------------------------------------------
    def get_top_sellers(self, days=30):
        now_utc = datetime.now(timezone.utc)
        start_utc = now_utc - timedelta(days=days)
        s_iso = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            data = self._api_get(f"receipts?created_at_min={s_iso}&limit=250")
            receipts = data.get("receipts", [])
        except Exception as e:
            return f"❌ Error consultando prendas más vendidas: {e}"

        sales = [r for r in receipts if r.get("receipt_type") == "SALE" and not r.get("cancelled_at")]
        items_agg = defaultdict(lambda: {"qty": 0, "money": 0.0})

        for r in sales:
            for it in r.get("line_items", []):
                name = it.get("item_name", "Prenda")
                items_agg[name]["qty"] += it.get("quantity", 1)
                items_agg[name]["money"] += it.get("total_money", 0.0)

        if not items_agg:
            return "ℹ️ No hay suficientes ventas registradas para generar el ranking."

        sorted_items = sorted(items_agg.items(), key=lambda x: x[1]["qty"], reverse=True)[:10]

        lines = [
            f"🏆 <b>TOP 10 PRENDAS MÁS VENDIDAS (Últimos {days} días)</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n"
        ]

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for idx, (name, d) in enumerate(sorted_items):
            m = medals[idx] if idx < len(medals) else "•"
            lines.append(f"{m} <b>{d['qty']} pzas</b> — {name} ({format_money(d['money'])})")

        lines.append("\n📍 <i>Plaza La Fragua, Saltillo</i>")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # 4. Alertas de Poco Stock y Agotados
    # -------------------------------------------------------------------------
    def get_low_stock_report(self):
        catalog = self.load_catalog()
        out_of_stock = [p for p in catalog if p.get("stock", 0) <= 0]
        low_stock = [p for p in catalog if 0 < p.get("stock", 0) <= 3]

        lines = [
            f"⚠️ <b>CONTROL DE INVENTARIO Y RESURTIDO</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n"
        ]

        if low_stock:
            lines.append("🟡 <b>PRENDAS POR AGOTARSE (<= 3 pzas):</b>")
            for p in low_stock:
                lines.append(f"• <b>{p['nombre']}</b>: {int(p['stock'])} pzas restantes ({format_money(p['precio'])})")
            lines.append("")

        if out_of_stock:
            lines.append("🔴 <b>PRENDAS AGOTADAS (0 pzas):</b>")
            for p in out_of_stock[:8]:
                lines.append(f"• <b>{p['nombre']}</b> (<code>{p['codigo']}</code>)")
            if len(out_of_stock) > 8:
                lines.append(f"<i>... y {len(out_of_stock) - 8} prendas más agotadas</i>")
            lines.append("")

        if not low_stock and not out_of_stock:
            lines.append("✅ <b>¡Excelente!</b> Todas las prendas del perchero tienen buen stock disponible.")

        lines.append("📍 <i>Plaza La Fragua, Saltillo</i>")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # 5. Búsqueda de Ticket Específico
    # -------------------------------------------------------------------------
    def search_ticket(self, query):
        clean_num = re.sub(r'[^0-9\-]', '', query).strip("-")
        if not clean_num:
            return "🔍 Por favor indica el número de ticket (ejemplo: <code>ticket 3949</code> o <code>#2-3949</code>)."

        try:
            data = self._api_get(f"receipts?limit=50")
            receipts = data.get("receipts", [])
        except Exception as e:
            return f"❌ Error buscando ticket: {e}"

        found = None
        for r in receipts:
            num = str(r.get("receipt_number", ""))
            if clean_num == num or clean_num in num:
                found = r
                break

        if not found:
            return f"🔍 No encontré el ticket <code>#{clean_num}</code> entre los últimos 50 recibos de Loyverse."

        r_num = found.get("receipt_number")
        emp = self.employees_cache.get(found.get("employee_id"), "Vonne Boutique")
        date_str = format_iso_time(found.get("created_at"), self.offset_hours)
        total = format_money(found.get("total_money", 0.0))
        r_type = found.get("receipt_type", "SALE")
        is_canc = bool(found.get("cancelled_at"))

        status = "🔴 CANCELADO / REEMBOLSADO" if (is_canc or r_type == "REFUND") else "🟢 COBRADO EXITOSO"

        items = []
        for it in found.get("line_items", []):
            items.append(f"• {it.get('quantity', 1)}x <b>{it.get('item_name')}</b> ({format_money(it.get('total_money', 0))})")
        items_str = "\n".join(items) if items else "• Sin desglose"

        payments = []
        for p in found.get("payments", []):
            p_name = p.get("name") or self.payment_types_cache.get(p.get("payment_type_id"), "Efectivo")
            payments.append(f"{p_name}: {format_money(p.get('money_amount', 0))}")
        pay_str = ", ".join(payments) if payments else "Efectivo"

        return (
            f"📄 <b>DETALLE DE TICKET #{r_num}</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n\n"
            f"📌 <b>Estado:</b> {status}\n"
            f"👤 <b>Atendió:</b> {emp}\n"
            f"🕐 <b>Fecha y Hora:</b> {date_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{items_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>TOTAL:</b> <b>{total}</b>\n"
            f"💳 <b>Pago:</b> {pay_str}\n\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    # -------------------------------------------------------------------------
    # 6. Motor Inteligente de Respuestas
    # -------------------------------------------------------------------------
    def answer(self, text):
        clean = text.lower().strip()

        # Quitar prefijo de comando o mención
        clean = re.sub(r'^/(?:asistente|pregunta|ask|consulta)\s*', '', clean)
        clean = re.sub(r'@\w+', '', clean).strip()

        # A) Búsqueda de ticket
        if re.search(r'\b(?:ticket|recibo|folio)\b', clean):
            return self.search_ticket(clean)

        # B) Alertas de stock bajo / agotados
        if any(w in clean for w in ["agotado", "agotados", "poco stock", "resurtir", "resurtido", "por agotarse", "inventario bajo"]):
            return self.get_low_stock_report()

        # C) Top prendas más vendidas
        if any(w in clean for w in ["top", "mas vendida", "más vendida", "mas vendidas", "más vendidas", "mejores prendas", "ranking"]):
            return self.get_top_sellers(30)

        # D) Ventas de la semana
        if any(w in clean for w in ["esta semana", "semana", "ultimos 7 dias", "últimos 7 días", "7 dias", "7 días"]):
            return self.get_period_sales_summary(7, "ÚLTIMOS 7 DÍAS")

        # E) Ventas del mes
        if any(w in clean for w in ["este mes", "mes", "mensual", "ultimos 30 dias", "30 dias", "30 días"]):
            return self.get_period_sales_summary(30, "ÚLTIMOS 30 DÍAS")

        # F) Consulta de Stock o Precios de prendas
        if any(w in clean for w in [
            "stock", "precio", "cuanto", "cuánto", "queda", "quedan", "hay",
            "tienes", "tienen", "talla", "tallas", "blazer", "faja", "vestido",
            "chaleco", "blusa", "short", "conjunto", "capa", "pantalon", "pantalón", "falda"
        ]):
            return self.answer_stock_or_price(clean)

        # G) Mensaje de ayuda / guía
        return (
            f"🤖 <b>Asistente Vonne Boutique - Loyverse POS</b>\n\n"
            f"¡Hola! Puedes preguntarme sobre cualquier tema de la tienda. Por ejemplo:\n\n"
            f"📦 <b>Stock y Precios:</b>\n"
            f"• <i>¿Cuánto stock queda de blazer blanco?</i>\n"
            f"• <i>¿Qué precio tiene la faja moldeadora?</i>\n"
            f"• <i>¿Qué prendas están agotadas o con poco stock?</i>\n\n"
            f"📊 <b>Ventas y Reportes:</b>\n"
            f"• <i>¿Cómo van las ventas de la semana?</i>\n"
            f"• <i>¿Cuáles son las prendas más vendidas del mes?</i>\n"
            f"• <i>Detalle del ticket 3949</i>\n\n"
            f"📍 <i>Plaza La Fragua, Saltillo, Coahuila</i>"
        )
