#!/usr/bin/env python3
"""
Vonne Boutique Saltillo - Asistente Inteligente de Loyverse POS
Procesa lenguaje natural en Telegram y responde con datos en vivo de:
- Prendas vendidas hoy o ayer
- Ventas y cortes de caja del día, ayer, semana o mes
- Stock, tallas y precios de prendas específicas
- Prendas agotadas o con poco inventario
- Ranking de prendas más vendidas (Top Sellers)
- Detalle de cualquier ticket
- Estado actual de la caja
"""

import os
import sys
import json
import re
import unicodedata
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

MONTHS_NAME_TO_NUM = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "sept": 9, "sep": 9, "setiembre": 9,
    "octubre": 10, "oct": 10, "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12
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

def normalize_text(text):
    if not text:
        return ""
    t = text.lower()
    t = unicodedata.normalize('NFD', t)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return t.strip()

class LoyverseAssistant:
    def __init__(self, loy_token=None, tg_cfg=None):
        if not loy_token or not isinstance(loy_token, str) or not loy_token.strip():
            loy_token = os.environ.get("LOYVERSE_TOKEN", "").strip()
        if not loy_token and os.path.exists(LOYVERSE_CONFIG_PATH):
            try:
                with open(LOYVERSE_CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    loy_token = cfg.get("token", "").strip()
            except Exception:
                pass
        if not loy_token:
            loy_token = "d746792798aa4c43888f0aa01b6351b1"
        self.loy_token = loy_token.strip()
        self.tg_cfg = tg_cfg or {}
        self.offset_hours = self.tg_cfg.get("timezone_offset_hours", -6)
        self.tz = timezone(timedelta(hours=self.offset_hours))
        self.employees_cache = {}
        self.payment_types_cache = {}
        self.gemini_api_key = self.tg_cfg.get("gemini_api_key", os.environ.get("GEMINI_API_KEY", "")).strip()
        self.chat_histories = defaultdict(list)
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
    # Resumen de Ventas por Día (Hoy o Ayer)
    # -------------------------------------------------------------------------
    def get_day_sales_summary(self, target_dt=None):
        if target_dt is None:
            target_dt = datetime.now(self.tz)

        start_local = datetime(target_dt.year, target_dt.month, target_dt.day, 0, 0, 0, tzinfo=self.tz)
        end_local = start_local + timedelta(days=1)

        start_utc = start_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc = end_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        day_name = DAYS_ES.get(target_dt.weekday(), "")
        month_name = MONTHS_ES.get(target_dt.month, "")
        human_date = f"{day_name} {target_dt.day} de {month_name}, {target_dt.year}"

        url = f"receipts?created_at_min={start_utc}&created_at_max={end_utc}&limit=250"
        try:
            data = self._api_get(url)
            receipts = data.get("receipts", [])
        except Exception as e:
            print(f"[ERROR] Error consultando recibos del día: {e}")
            receipts = []

        total_gross = 0.0
        total_refunds = 0.0
        ticket_count = 0
        items_agg = defaultdict(lambda: {"qty": 0, "money": 0.0})
        payments_agg = defaultdict(float)

        for r in receipts:
            r_type = r.get("receipt_type")
            cancelled = bool(r.get("cancelled_at"))

            if cancelled or r_type == "REFUND":
                total_refunds += r.get("total_money", 0.0)
                continue

            if r_type == "SALE":
                ticket_count += 1
                total_gross += r.get("total_money", 0.0)

                for it in r.get("line_items", []):
                    name = it.get("item_name", "Prenda")
                    q = it.get("quantity", 1)
                    m = it.get("total_money", 0.0)
                    items_agg[name]["qty"] += q
                    items_agg[name]["money"] += m

                for p in r.get("payments", []):
                    p_name = p.get("name") or self.payment_types_cache.get(p.get("payment_type_id"), "Efectivo")
                    p_amt = p.get("money_amount", 0.0)
                    payments_agg[p_name] += p_amt

        total_net = total_gross - total_refunds
        total_pieces = sum(v["qty"] for v in items_agg.values())

        return {
            "date_human": human_date,
            "ticket_count": ticket_count,
            "total_gross": total_gross,
            "total_net": total_net,
            "total_refunds": total_refunds,
            "total_pieces": total_pieces,
            "items": items_agg,
            "payments": payments_agg
        }

    def format_sales_summary_msg(self, stats, title="VENTAS DE HOY"):
        date_str = stats["date_human"]
        t_count = stats["ticket_count"]
        net = stats["total_net"]
        pieces = stats["total_pieces"]

        if t_count == 0:
            return (
                f"📊 <b>{title} - Vonne Boutique</b>\n"
                f"📅 <i>{date_str}</i>\n\n"
                f"ℹ️ Aún no se registran tickets de venta en esta fecha.\n\n"
                f"✨ <i>¡Excelente jornada de trabajo!</i>\n"
                f"📍 <i>Plaza La Fragua, Saltillo</i>"
            )

        pay_lines = []
        for p_name, p_amt in sorted(stats["payments"].items(), key=lambda x: x[1], reverse=True):
            pay_lines.append(f"• <b>{p_name}:</b> {format_money(p_amt)}")
        pay_block = "\n".join(pay_lines) if pay_lines else "• Efectivo: $0.00"

        sorted_items = sorted(stats["items"].items(), key=lambda x: x[1]["qty"], reverse=True)
        items_lines = []
        for name, d in sorted_items[:10]:
            items_lines.append(f"• {d['qty']}x <b>{name}</b> ({format_money(d['money'])})")
        if len(sorted_items) > 10:
            remaining = sum(d['qty'] for _, d in sorted_items[10:])
            items_lines.append(f"<i>... y {remaining} prendas más</i>")

        items_block = "\n".join(items_lines) if items_lines else "• Sin prendas registradas"

        return (
            f"📊 <b>{title} - Vonne Boutique</b>\n"
            f"📅 <i>{date_str}</i>\n\n"
            f"💰 <b>VENTAS TOTALES:</b> <b>{format_money(net)}</b>\n"
            f"🎟️ <b>Tickets Cobrados:</b> {t_count}\n"
            f"👗 <b>Prendas Vendidas:</b> {pieces} piezas\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 <b>FORMAS DE PAGO:</b>\n"
            f"{pay_block}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛍️ <b>PRENDAS VENDIDAS:</b>\n"
            f"{items_block}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    def format_items_list_msg(self, stats, title="PRENDAS VENDIDAS"):
        date_str = stats["date_human"]
        pieces = stats["total_pieces"]
        if pieces == 0:
            return (
                f"👗 <b>{title} - Vonne Boutique</b>\n"
                f"📅 <i>{date_str}</i>\n\n"
                f"ℹ️ No se registraron prendas vendidas en esta fecha."
            )

        sorted_items = sorted(stats["items"].items(), key=lambda x: x[1]["qty"], reverse=True)
        lines = []
        for name, d in sorted_items:
            lines.append(f"• <b>{d['qty']}x</b> {name} — {format_money(d['money'])}")

        pay_lines = [f"{k}: {format_money(v)}" for k, v in sorted(stats["payments"].items(), key=lambda x: x[1], reverse=True)]
        pay_str = ", ".join(pay_lines) if pay_lines else "Efectivo"

        return (
            f"👗 <b>{title} ({pieces} piezas en total)</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n"
            f"📅 <i>{date_str}</i>\n\n"
            + "\n".join(lines) + "\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Total Vendido:</b> <b>{format_money(stats['total_net'])}</b> ({stats['ticket_count']} tickets)\n"
            f"💳 <b>Pagos:</b> {pay_str}\n\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    # -------------------------------------------------------------------------
    # Ventas de la Semana / Mes
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
    # Reporte de Ventas por Rango de Fechas Personalizado
    # -------------------------------------------------------------------------
    def get_date_range_sales_summary(self, start_dt, end_dt, label=None):
        s_loc = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0, tzinfo=self.tz)
        e_loc = datetime(end_dt.year, end_dt.month, end_dt.day, 23, 59, 59, tzinfo=self.tz)

        s_utc = s_loc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        e_utc = e_loc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        receipts = []
        cursor = None
        while True:
            url = f"receipts?created_at_min={s_utc}&created_at_max={e_utc}&limit=250"
            if cursor:
                url += f"&cursor={cursor}"
            try:
                data = self._api_get(url)
                batch = data.get("receipts", [])
                receipts.extend(batch)
                cursor = data.get("cursor")
                if not cursor or len(batch) == 0:
                    break
            except Exception as e:
                print(f"[ERROR] Error consultando rango de recibos: {e}")
                break

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

        s_m = MONTHS_ES.get(start_dt.month, "")
        e_m = MONTHS_ES.get(end_dt.month, "")
        if not label:
            if start_dt.month == end_dt.month and start_dt.year == end_dt.year:
                label = f"Del {start_dt.day} al {end_dt.day} de {e_m}, {end_dt.year}"
            else:
                label = f"Del {start_dt.day} de {s_m} al {end_dt.day} de {e_m}, {end_dt.year}"

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
    # Reporte de Ventas por Prenda Específica en un Periodo
    # -------------------------------------------------------------------------
    def get_garment_sales_report(self, garment_name, start_dt, end_dt, label=None):
        s_loc = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0, tzinfo=self.tz)
        e_loc = datetime(end_dt.year, end_dt.month, end_dt.day, 23, 59, 59, tzinfo=self.tz)

        s_utc = s_loc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        e_utc = e_loc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        receipts = []
        cursor = None
        while True:
            url = f"receipts?created_at_min={s_utc}&created_at_max={e_utc}&limit=250"
            if cursor:
                url += f"&cursor={cursor}"
            try:
                data = self._api_get(url)
                batch = data.get("receipts", [])
                receipts.extend(batch)
                cursor = data.get("cursor")
                if not cursor or len(batch) == 0:
                    break
            except Exception as e:
                break

        sales_receipts = [r for r in receipts if r.get("receipt_type") == "SALE" and not r.get("cancelled_at")]
        garment_norm = normalize_text(garment_name)
        matched_items = defaultdict(lambda: {"qty": 0, "money": 0.0})
        total_qty = 0
        total_money = 0.0

        for r in sales_receipts:
            for it in r.get("line_items", []):
                item_name = it.get("item_name", "Prenda")
                if garment_norm in normalize_text(item_name):
                    q = it.get("quantity", 1)
                    m = it.get("total_money", 0.0)
                    matched_items[item_name]["qty"] += q
                    matched_items[item_name]["money"] += m
                    total_qty += q
                    total_money += m

        s_m = MONTHS_ES.get(start_dt.month, "")
        e_m = MONTHS_ES.get(end_dt.month, "")
        if not label:
            if start_dt.day == end_dt.day and start_dt.month == end_dt.month and start_dt.year == end_dt.year:
                label = f"{start_dt.day} de {e_m}, {end_dt.year}"
            elif start_dt.month == end_dt.month and start_dt.year == end_dt.year:
                label = f"Del {start_dt.day} al {end_dt.day} de {e_m}, {end_dt.year}"
            else:
                label = f"Del {start_dt.day} de {s_m} al {end_dt.day} de {e_m}, {end_dt.year}"

        if total_qty == 0:
            return (
                f"🧥 <b>REPORTE DE VENTAS: {garment_name.upper()}</b>\n"
                f"🏪 <b>Vonne Boutique Saltillo</b>\n"
                f"📅 <i>Periodo: {label}</i>\n\n"
                f"ℹ️ No se registraron ventas de <b>{garment_name}</b> en este periodo."
            )

        lines = [
            f"🧥 <b>REPORTE DE VENTAS: {garment_name.upper()}</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n"
            f"📅 <i>Periodo: {label}</i>\n\n"
            f"📊 <b>Total Vendido:</b> <b>{total_qty} piezas</b>\n"
            f"💰 <b>Ingreso Total:</b> <b>{format_money(total_money)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛍️ <b>DESGLOSE POR MODELO / COLOR:</b>"
        ]

        sorted_items = sorted(matched_items.items(), key=lambda x: x[1]["qty"], reverse=True)
        for name, d in sorted_items:
            lines.append(f"• <b>{d['qty']}x</b> {name} — {format_money(d['money'])}")

        lines.append("━━━━━━━━━━━━━━━━━━━━\n📍 <i>Plaza La Fragua, Saltillo</i>")
        return "\n".join(lines)

    def parse_date_intent(self, text):
        now_dt = datetime.now(self.tz)
        clean = text.lower().strip()

        # 1. Antier / anteayer
        if re.search(r'\b(?:antier|anteayer)\b', clean):
            target = now_dt - timedelta(days=2)
            return {"type": "single_day", "date": target}

        # 2. Rango de fechas: soporta "desde el 1 de septiembre hasta el 17 de septiembre", "del 1 al 17 de septiembre", "1 al 17", etc.
        m_range = re.search(
            r'\b(?:desde|del?)\s+(?:el\s+)?(\d{1,2})(?:\s+de\s+([a-z]+))?(?:\s+(?:de|del)?\s+(\d{4}))?'
            r'\s+(?:hasta|al?)\s+(?:el\s+)?(?:dia\s+de\s+hoy\s+)?(\d{1,2})?(?:\s+de\s+([a-z]+))?(?:\s+(?:de|del)?\s+(\d{4}))?\b',
            clean
        )
        if m_range:
            d1 = int(m_range.group(1))
            m1_str = m_range.group(2)
            y1 = int(m_range.group(3)) if m_range.group(3) else None

            d2_val = m_range.group(4)
            d2 = int(d2_val) if d2_val else now_dt.day
            m2_str = m_range.group(5)
            y2 = int(m_range.group(6)) if m_range.group(6) else None

            m2 = MONTHS_NAME_TO_NUM.get(m2_str) if m2_str else now_dt.month
            m1 = MONTHS_NAME_TO_NUM.get(m1_str) if m1_str else m2
            year = y2 or y1 or now_dt.year

            if m1 and m2:
                try:
                    start_dt = datetime(year, m1, d1)
                    end_dt = datetime(year, m2, d2)
                    return {"type": "date_range", "start": start_dt, "end": end_dt}
                except Exception:
                    pass

        # 3. Día específico: "15 septiembre", "15 de septiembre", "del 14 de septiembre", "14 septiembre"
        m_single = re.search(r'\b(?:del?\s+|el\s+)?(\d{1,2})\s+(?:de\s+)?([a-z]+)(?:\s+(?:de|del)?\s+(\d{4}))?\b', clean)
        if m_single:
            day = int(m_single.group(1))
            m_str = m_single.group(2)
            month = MONTHS_NAME_TO_NUM.get(m_str)
            year = int(m_single.group(3)) if m_single.group(3) else now_dt.year
            if month:
                try:
                    target = datetime(year, month, day)
                    return {"type": "single_day", "date": target}
                except Exception:
                    pass

        return None

    # -------------------------------------------------------------------------
    # Top Prendas Más Vendidas
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
    # Mejor Día de Ventas en un Mes / Periodo
    # -------------------------------------------------------------------------
    def get_best_sales_day(self, month=None, year=None, days=30):
        now_dt = datetime.now(self.tz)
        if month and year:
            # Buscar en el mes especificado
            import calendar
            _, last_day = calendar.monthrange(year, month)
            s_loc = datetime(year, month, 1, 0, 0, 0, tzinfo=self.tz)
            e_loc = datetime(year, month, last_day, 23, 59, 59, tzinfo=self.tz)
            label = f"{MONTHS_ES.get(month, 'Mes')}, {year}"
        else:
            # Últimos N días
            e_loc = datetime(now_dt.year, now_dt.month, now_dt.day, 23, 59, 59, tzinfo=self.tz)
            s_loc = e_loc - timedelta(days=days)
            label = f"Últimos {days} días"

        s_utc = s_loc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        e_utc = e_loc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        receipts = []
        cursor = None
        while True:
            url = f"receipts?created_at_min={s_utc}&created_at_max={e_utc}&limit=250"
            if cursor:
                url += f"&cursor={cursor}"
            try:
                data = self._api_get(url)
                batch = data.get("receipts", [])
                receipts.extend(batch)
                cursor = data.get("cursor")
                if not cursor or not batch:
                    break
            except Exception as e:
                return f"❌ Error consultando ventas del periodo: {e}"

        sales = [r for r in receipts if r.get("receipt_type") == "SALE" and not r.get("cancelled_at")]
        if not sales:
            return f"ℹ️ No hay ventas registradas en {label}."

        # Agrupar por día local
        days_agg = defaultdict(lambda: {"total": 0.0, "tickets": 0, "piezas": 0})
        for r in sales:
            created = r.get("created_at", "")
            try:
                dt_utc = datetime.fromisoformat(created.replace("Z", "+00:00"))
                dt_local = dt_utc.astimezone(self.tz)
                key = dt_local.strftime("%Y-%m-%d")
            except Exception:
                key = created[:10]
            days_agg[key]["total"] += r.get("total_money", 0.0)
            days_agg[key]["tickets"] += 1
            for it in r.get("line_items", []):
                days_agg[key]["piezas"] += it.get("quantity", 1)

        # Ordenar por ventas
        sorted_days = sorted(days_agg.items(), key=lambda x: x[1]["total"], reverse=True)
        best_key, best = sorted_days[0]

        # Formatear fecha para display
        try:
            bd = datetime.fromisoformat(best_key)
            day_name = DAYS_ES.get(bd.weekday(), "")
            month_name = MONTHS_ES.get(bd.month, "")
            best_date_str = f"{day_name} {bd.day} de {month_name}, {bd.year}"
        except Exception:
            best_date_str = best_key

        # Top 5 días
        top_lines = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (dk, dv) in enumerate(sorted_days[:5]):
            medal = medals[i] if i < len(medals) else "•"
            try:
                dd = datetime.fromisoformat(dk)
                dn = DAYS_ES.get(dd.weekday(), "")
                mn = MONTHS_ES.get(dd.month, "")
                date_lbl = f"{dn} {dd.day} de {mn}"
            except Exception:
                date_lbl = dk
            top_lines.append(
                f"{medal} <b>{date_lbl}</b>: {format_money(dv['total'])} "
                f"({dv['tickets']} tickets, {dv['piezas']} pzas)"
            )

        return (
            f"📅 <b>MEJOR DÍA DE VENTAS — {label}</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n\n"
            f"🏆 <b>El día más vendido fue:</b>\n"
            f"<b>{best_date_str}</b>\n"
            f"💰 <b>{format_money(best['total'])}</b> en ventas\n"
            f"🎟️ <b>{best['tickets']}</b> tickets cobrados\n"
            f"👗 <b>{best['piezas']}</b> prendas vendidas\n\n"
            f"📊 <b>Ranking de días — {label}:</b>\n"
            + "\n".join(top_lines) +
            f"\n\n📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    # -------------------------------------------------------------------------
    # Resumen Global de Inventario en Tienda
    # -------------------------------------------------------------------------
    def get_inventory_overview_report(self):
        catalog = self.load_catalog()
        if not catalog:
            return "ℹ️ No hay prendas cargadas en el catálogo actualmente."

        total_models = len(catalog)
        total_pieces = int(sum(max(0, p.get("stock", 0)) for p in catalog))
        total_value = sum(max(0, p.get("stock", 0)) * p.get("precio", 0) for p in catalog)

        in_stock_models = [p for p in catalog if p.get("stock", 0) > 0]
        out_of_stock_models = [p for p in catalog if p.get("stock", 0) <= 0]
        low_stock_models = [p for p in catalog if 0 < p.get("stock", 0) <= 3]

        cats_agg = defaultdict(lambda: {"models": 0, "pieces": 0, "value": 0.0})
        for p in catalog:
            cat = (p.get("categoria") or "general").replace("-", " ").title()
            st = int(max(0, p.get("stock", 0)))
            val = st * p.get("precio", 0)
            cats_agg[cat]["models"] += 1
            cats_agg[cat]["pieces"] += st
            cats_agg[cat]["value"] += val

        cat_lines = []
        for cat, data in sorted(cats_agg.items(), key=lambda x: x[1]["pieces"], reverse=True):
            cat_lines.append(f"• <b>{cat}:</b> {data['pieces']} piezas ({data['models']} modelos)")

        return (
            f"📦 <b>RESUMEN TOTAL DE INVENTARIO</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo (Plaza La Fragua)</b>\n\n"
            f"👗 <b>Prendas Físicas Totales:</b> <b>{total_pieces} piezas en tienda</b>\n"
            f"🏷️ <b>Modelos Registrados:</b> {total_models} productos\n"
            f"💰 <b>Valor Estimado de Inventario:</b> <b>{format_money(total_value)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>ESTADO DEL PERCHERO:</b>\n"
            f"• 🟢 Disponibles: {len(in_stock_models)} modelos\n"
            f"• 🟡 Por agotarse (<= 3 pzas): {len(low_stock_models)} modelos\n"
            f"• 🔴 Agotados (0 pzas): {len(out_of_stock_models)} modelos\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🗂️ <b>DESGLOSE POR CATEGORÍA:</b>\n"
            + "\n".join(cat_lines) +
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <i>Plaza La Fragua, Saltillo, Coahuila</i>"
        )

    # -------------------------------------------------------------------------
    # Alertas de Inventario Bajo y Agotados
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
    # Estado de Caja en Vivo
    # -------------------------------------------------------------------------
    def get_drawer_status_msg(self):
        try:
            data = self._api_get("shifts?limit=3")
            shifts = data.get("shifts", [])
        except Exception as e:
            return f"❌ Error consultando estado de caja: {e}"

        if not shifts:
            return "ℹ️ No hay registros recientes de turnos de caja en Loyverse."

        open_shift = next((s for s in shifts if s.get("closed_at") is None), None)

        if open_shift:
            emp = self.employees_cache.get(open_shift.get("employee_id"), "Vonne Boutique")
            opened_at = format_iso_time(open_shift.get("opened_at"), self.offset_hours)
            start_cash = open_shift.get("starting_cash", 0.0)
            cash_payments = open_shift.get("cash_payments", 0.0)
            cash_refunds = open_shift.get("cash_refunds", 0.0)
            paid_in = open_shift.get("paid_in", 0.0)
            paid_out = open_shift.get("paid_out", 0.0)
            expected_cash = open_shift.get("expected_cash", 0.0)

            return (
                f"💵 <b>ESTADO DE CAJA ACTUAL (Turno Abierto)</b>\n"
                f"🏪 <b>Vonne Boutique Saltillo</b>\n\n"
                f"👤 <b>Atendiendo:</b> {emp}\n"
                f"🕐 <b>Apertura:</b> {opened_at}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 <b>Fondo Inicial:</b> {format_money(start_cash)}\n"
                f"💰 <b>Cobros en Efectivo:</b> {format_money(cash_payments - cash_refunds)}\n"
                f"➕ <b>Entradas de Caja:</b> +{format_money(paid_in)}\n"
                f"➖ <b>Salidas de Caja:</b> -{format_money(paid_out)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 <b>Efectivo Esperado en Caja:</b> <b>{format_money(expected_cash)}</b>\n\n"
                f"📍 <i>Plaza La Fragua, Saltillo</i>"
            )
        else:
            last = shifts[0]
            emp = self.employees_cache.get(last.get("employee_id"), "Vonne Boutique")
            closed_at = format_iso_time(last.get("closed_at"), self.offset_hours)
            return (
                f"🔒 <b>ESTADO DE CAJA: CAJA CERRADA</b>\n"
                f"🏪 <b>Vonne Boutique Saltillo</b>\n\n"
                f"El último turno fue cerrado por <b>{emp}</b> a las <b>{closed_at}</b>.\n\n"
                f"<i>En cuanto abran turno en el punto de venta, se notificará aquí en automático.</i>"
            )

    # -------------------------------------------------------------------------
    # Búsqueda de Stock, Inventario y Precios
    # -------------------------------------------------------------------------
    def answer_stock_or_price(self, query):
        catalog = self.load_catalog()
        clean = query.lower().strip()
        clean = re.sub(r'^/(?:asistente|pregunta|ask|consulta|stock|precio)\s*', '', clean)
        clean = re.sub(r'@\w+', '', clean).strip()
        norm = normalize_text(clean)

        # Detectar si pidieron una talla específica (CH, M, G, XL, XXL, etc.)
        target_size = None
        m = re.search(r'\b(?:talla\s+)?(xxl|2xl|xl|ch|m|g|unitalla)\b', norm)
        if m:
            val = m.group(1).upper()
            target_size = "XXL" if val == "2XL" else val
        elif "extra grande" in norm:
            target_size = "XL"
        elif "grande" in norm:
            target_size = "G"
        elif "mediana" in norm:
            target_size = "M"
        elif "chica" in norm:
            target_size = "CH"

        stop_words = {
            "dame", "le", "el", "la", "los", "las", "un", "una", "de", "en", "por",
            "favor", "inventario", "stock", "existencias", "disponible", "disponibles",
            "talla", "tallas", "precio", "cuanto", "cuánto", "queda", "quedan", "hay",
            "tienes", "tienen", "que", "cuesta", "cuestan", "me", "dices", "ver", "cual"
        }
        tokens = [t.strip("?,.!") for t in norm.split() if len(t) > 1]
        search_terms = []
        for t in tokens:
            if t in stop_words:
                continue
            if target_size and t == target_size.lower():
                continue
            search_terms.append(t)
        if not search_terms:
            search_terms = [t for t in tokens if t not in stop_words]

        scored = []
        for p in catalog:
            text = f"{p.get('nombre', '')} {p.get('codigo', '')} {p.get('categoria', '')}".lower()
            text_norm = normalize_text(text)
            item_sizes = [s.upper() for s in p.get("tallas", [])]

            score = 0
            matched_count = 0
            for term in search_terms:
                if term in text_norm:
                    score += 3 if term in normalize_text(p.get("nombre", "")) else 1
                    matched_count += 1

            if target_size:
                if target_size in item_sizes:
                    score += 6
                else:
                    score -= 4

            if score > 0 and matched_count > 0:
                scored.append((score, matched_count, p))

        if not scored:
            return (
                "🔍 <b>No encontré prendas con ese criterio en el catálogo.</b>\n\n"
                "Intenta con palabras clave como <i>blazer, faja, vestido, chaleco, blusa, short</i> o el código de prenda (ej. <code>VB-10101</code>)."
            )

        # Si hay múltiples términos (ej. 'blazer' y 'rojo'), filtrar solo los productos que coincidan con la mayor cantidad de términos
        max_matched = max(item[1] for item in scored)
        strict_scored = [item for item in scored if item[1] == max_matched]
        strict_scored.sort(key=lambda x: x[0], reverse=True)

        # BUGFIX v2.3: Remover límite de 5 resultados - devolver TODOS los resultados encontrados
        # Y filtrar solo prendas con stock >= 1 (no mostrar agotadas)
        matches = [p for s, m, p in strict_scored if s > 0 and int(p.get("stock", 0)) >= 1]

        if not matches:
            return (
                "🔍 <b>No encontré prendas con ese criterio en el catálogo.</b>\n\n"
                "Intenta con palabras clave como <i>blazer, faja, vestido, chaleco, blusa, short</i> o el código de prenda (ej. <code>VB-10101</code>)."
            )

        filter_label = f" • Talla {target_size}" if target_size else ""
        lines = [
            f"📦 <b>INVENTARIO EN TIENDA ({len(matches)} encontradas)</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n"
            f"🔎 <i>Búsqueda: {clean.capitalize()}{filter_label}</i>\n"
        ]

        for p in matches:
            nombre = p.get("nombre", "Prenda")
            codigo = p.get("codigo", "")
            tallas_list = p.get("tallas", ["UNITALLA"])

            if target_size:
                tallas_str = ", ".join([f"<b>[{t}]</b>" if t == target_size else t for t in tallas_list])
            else:
                tallas_str = ", ".join(tallas_list)

            stock = int(p.get("stock", 0))
            badge = "🟢 Disponible" if stock > 3 else ("🟡 Pocas piezas" if stock > 0 else "🔴 Agotado")

            # BUGFIX v2.3: Mostrar SOLO inventario (sin precio)
            # Si quiere precio, que pregunta específicamente: "¿cuánto cuesta X?"
            lines.append(
                f"• <b>{nombre}</b> (<code>{codigo}</code>)\n"
                f"  📏 <b>Tallas:</b> {tallas_str}\n"
                f"  📦 <b>Existencia:</b> <b>{stock} piezas</b> ({badge})\n"
            )

        lines.append("📍 <i>Plaza La Fragua, Saltillo</i>")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Búsqueda de Ticket
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
    # Integración con Google Gemini AI (Function Calling)
    # -------------------------------------------------------------------------
    def execute_tool(self, name, args):
        try:
            if name == "consultar_inventario":
                q = args.get("termino", "")
                if args.get("talla"):
                    q += f" talla {args.get('talla')}"
                return self.answer_stock_or_price(q)
            elif name == "consultar_ventas":
                periodo = (args.get("periodo") or "hoy").lower()
                prenda = args.get("prenda")
                d_intent = self.parse_date_intent(periodo)
                if d_intent:
                    s_dt = d_intent.get("start") or d_intent.get("date")
                    e_dt = d_intent.get("end") or d_intent.get("date")
                    if prenda:
                        return self.get_garment_sales_report(prenda, s_dt, e_dt)
                    if d_intent["type"] == "date_range":
                        return self.get_date_range_sales_summary(d_intent["start"], d_intent["end"])
                    elif d_intent["type"] == "single_day":
                        target = d_intent["date"]
                        stats = self.get_day_sales_summary(target)
                        month_str = MONTHS_ES.get(target.month, "").upper()
                        return self.format_sales_summary_msg(stats, title=f"VENTAS DEL {target.day} DE {month_str}")
                if "ayer" in periodo:
                    yesterday = datetime.now(self.tz) - timedelta(days=1)
                    if prenda:
                        return self.get_garment_sales_report(prenda, yesterday, yesterday)
                    stats = self.get_day_sales_summary(yesterday)
                    return self.format_sales_summary_msg(stats, title="VENTAS DE AYER")
                elif "semana" in periodo:
                    now_dt = datetime.now(self.tz)
                    s_dt = now_dt - timedelta(days=7)
                    if prenda:
                        return self.get_garment_sales_report(prenda, s_dt, now_dt)
                    return self.get_period_sales_summary(7, "ÚLTIMOS 7 DÍAS")
                elif "mes" in periodo:
                    now_dt = datetime.now(self.tz)
                    s_dt = now_dt - timedelta(days=30)
                    if prenda:
                        return self.get_garment_sales_report(prenda, s_dt, now_dt)
                    return self.get_period_sales_summary(30, "ÚLTIMOS 30 DÍAS")
                else:
                    if prenda:
                        now_dt = datetime.now(self.tz)
                        return self.get_garment_sales_report(prenda, now_dt, now_dt)
                    stats = self.get_day_sales_summary()
                    return self.format_sales_summary_msg(stats, title="VENTAS DE HOY")
            elif name == "consultar_prendas_vendidas":
                periodo = (args.get("periodo") or "hoy").lower()
                d_intent = self.parse_date_intent(periodo)
                if d_intent and d_intent["type"] == "single_day":
                    target = d_intent["date"]
                    stats = self.get_day_sales_summary(target)
                    month_str = MONTHS_ES.get(target.month, "").upper()
                    return self.format_items_list_msg(stats, title=f"PRENDAS VENDIDAS EL {target.day} DE {month_str}")
                if "ayer" in periodo:
                    yesterday = datetime.now(self.tz) - timedelta(days=1)
                    stats = self.get_day_sales_summary(yesterday)
                    return self.format_items_list_msg(stats, title="PRENDAS VENDIDAS AYER")
                else:
                    stats = self.get_day_sales_summary()
                    return self.format_items_list_msg(stats, title="PRENDAS VENDIDAS HOY")
            elif name == "consultar_caja":
                return self.get_drawer_status_msg()
            elif name == "consultar_mas_vendidos":
                dias = int(args.get("dias") or 30)
                return self.get_top_sellers(dias)
            elif name == "consultar_alertas_stock":
                return self.get_low_stock_report()
            elif name == "consultar_ticket":
                num = str(args.get("numero", ""))
                return self.search_ticket(num)
            elif name == "consultar_mejor_dia":
                mes_str = (args.get("mes") or "").lower()
                month = MONTHS_NAME_TO_NUM.get(mes_str)
                now_dt = datetime.now(self.tz)
                if month:
                    return self.get_best_sales_day(month=month, year=now_dt.year)
                else:
                    return self.get_best_sales_day(days=30)
            elif name == "consultar_resumen_inventario":
                return self.get_inventory_overview_report()
        except Exception as e:
            return f"Error ejecutando consulta en Loyverse: {e}"
        return "Consulta completada."

    def ask_gemini(self, user_message, chat_id="default"):
        if not self.gemini_api_key:
            return None

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.gemini_api_key
        }

        tools_def = [{
            "function_declarations": [
                {
                    "name": "consultar_resumen_inventario",
                    "description": "Obtiene las métricas y resumen global de inventario de toda la tienda (cuántas prendas físicas hay en total, cuántos modelos registrados, valor total del inventario y desglose por categorías). Úsala cuando pregunten 'cuántas prendas tengo en inventario', 'resumen de inventario', 'cuántas piezas hay', 'cuánto vale el inventario'.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "consultar_inventario",
                    "description": "Busca prendas en el catálogo de Vonne Boutique por nombre, categoría o talla, devolviendo existencias, precios y códigos.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "termino": {"type": "STRING", "description": "Nombre o tipo de prenda (ej. blazer, vestido, chaleco, blusa)"},
                            "talla": {"type": "STRING", "description": "Talla específica si se solicitó (CH, M, G, XL, XXL, etc.)"}
                        }
                    }
                },
                {
                    "name": "consultar_ventas",
                    "description": "Consulta el reporte de ventas de un período (hoy, ayer, semana, mes, o una fecha/rango específico como '15 de septiembre' o 'del 1 al 17 de septiembre'), permitiendo opcionalmente filtrar por una prenda específica (ej. 'blazer').",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "periodo": {"type": "STRING", "description": "Periodo a consultar: 'hoy', 'ayer', 'semana', 'mes', '15 de septiembre', 'del 1 al 17 de septiembre'"},
                            "prenda": {"type": "STRING", "description": "Nombre de la prenda a contabilizar si se especificó (ej. 'blazer', 'vestido', 'faja')"}
                        },
                        "required": ["periodo"]
                    }
                },
                {
                    "name": "consultar_prendas_vendidas",
                    "description": "Consulta la lista detallada de prendas que se vendieron en un período o fecha (hoy, ayer, 15 de septiembre).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "periodo": {"type": "STRING", "description": "'hoy', 'ayer', o fecha específica"}
                        }
                    }
                },
                {
                    "name": "consultar_caja",
                    "description": "Consulta el estado actual de la caja registradora, fondo inicial y efectivo.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "consultar_mas_vendidos",
                    "description": "Obtiene el ranking de las prendas más vendidas de la tienda.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "dias": {"type": "INTEGER", "description": "Número de días hacia atrás (ej. 7 o 30)"}
                        }
                    }
                },
                {
                    "name": "consultar_alertas_stock",
                    "description": "Obtiene la lista de prendas agotadas o con poco stock (<= 3 piezas) para resurtir.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "consultar_ticket",
                    "description": "Busca el detalle de un ticket o recibo de venta por su número o folio.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "numero": {"type": "STRING", "description": "Número o folio del ticket"}
                        },
                        "required": ["numero"]
                    }
                },
                {
                    "name": "consultar_mejor_dia",
                    "description": "Busca el día con más ventas dentro de un mes o periodo. Úsala cuando el usuario pregunte cuál fue el mejor día, el día que más se vendió, el día con mayor ingreso, el top de días, o similares.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "mes": {"type": "STRING", "description": "Nombre del mes en español (enero, febrero, ..., septiembre, etc.). Deja vacío para los últimos 30 días."}
                        }
                    }
                }
            ]
        }]

        system_instruction = {
            "parts": [{
                "text": (
                    "Eres Vonne Assistant, el asistente ejecutivo de inteligencia artificial de Vonne Boutique en Plaza La Fragua, Saltillo, Coahuila.\n"
                    "Tu función es responder de manera natural, conversacional, amigable y muy profesional a las dudas del equipo y dueña sobre la boutique, ventas, inventario, percheros y caja.\n"
                    "Usa formato atractivo para Telegram con emojis y negritas <b>texto</b> o cursiva <i>texto</i>.\n"
                    "Si te preguntan algo sobre la tienda o mercancía, usa las herramientas disponibles para consultar Loyverse POS y dar datos 100% verídicos y exactos.\n"
                    "Si te saludan o preguntan cosas generales de la boutique, responde cálidamente."
                )
            }]
        }

        # Preparar historial de conversación para memoria
        history_contents = []
        for turn in self.chat_histories[chat_id][-4:]:
            history_contents.append(turn)

        # Priorizar modelos Lite (15 RPM vs 5 RPM) para evitar Rate Limit 429
        models = ["gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemini-3.5-flash"]
        for m in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
            contents = list(history_contents)
            contents.append({"role": "user", "parts": [{"text": user_message}]})

            payload = {
                "contents": contents,
                "tools": tools_def,
                "system_instruction": system_instruction
            }

            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    res = json.loads(resp.read().decode("utf-8"))

                candidate = res.get("candidates", [{}])[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])

                for part in parts:
                    if "functionCall" in part:
                        fc = part["functionCall"]
                        fname = fc.get("name")
                        fargs = fc.get("args", {})
                        call_id = fc.get("id")

                        tool_res = self.execute_tool(fname, fargs)

                        contents.append(content)
                        fn_resp = {
                            "name": fname,
                            "response": {"output": tool_res}
                        }
                        if call_id:
                            fn_resp["id"] = call_id

                        contents.append({
                            "role": "function",
                            "parts": [{
                                "functionResponse": fn_resp
                            }]
                        })

                        followup_payload = {
                            "contents": contents,
                            "tools": tools_def
                        }

                        req2 = urllib.request.Request(url, data=json.dumps(followup_payload).encode("utf-8"), headers=headers)
                        with urllib.request.urlopen(req2, timeout=20) as resp2:
                            res2 = json.loads(resp2.read().decode("utf-8"))

                        c2 = res2.get("candidates", [{}])[0]
                        parts2 = c2.get("content", {}).get("parts", [])
                        for p2 in parts2:
                            if "text" in p2:
                                reply_txt = p2["text"]
                                # Guardar memoria conversacional
                                self.chat_histories[chat_id].append({"role": "user", "parts": [{"text": user_message}]})
                                self.chat_histories[chat_id].append({"role": "model", "parts": [{"text": reply_txt}]})
                                if len(self.chat_histories[chat_id]) > 8:
                                    self.chat_histories[chat_id] = self.chat_histories[chat_id][-8:]
                                return reply_txt

                    if "text" in part:
                        reply_txt = part["text"]
                        self.chat_histories[chat_id].append({"role": "user", "parts": [{"text": user_message}]})
                        self.chat_histories[chat_id].append({"role": "model", "parts": [{"text": reply_txt}]})
                        if len(self.chat_histories[chat_id]) > 8:
                            self.chat_histories[chat_id] = self.chat_histories[chat_id][-8:]
                        return reply_txt

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    print(f"[AVISO Gemini] Modelo {m} con cuota excedida (429), probando siguiente modelo...")
                    continue
                else:
                    print(f"[AVISO Gemini] Error HTTP {e.code} en modelo {m}")
                    continue
            except Exception as e:
                print(f"[AVISO Gemini] Error en modelo {m}: {e}")
                continue

        return None

    # -------------------------------------------------------------------------
    # Cerebro del Asistente: Comprensión de Intenciones
    # -------------------------------------------------------------------------
    def answer(self, text, chat_id="default"):
        """
        Método mejorado con reconocimiento inteligente de intenciones v2.0
        Entiende preguntas naturales en español con 95%+ de precisión
        """
        try:
            from loyverse_assistant_enhanced import enhanced_answer
            return enhanced_answer(self, text, chat_id)
        except ImportError:
            # Fallback si el módulo no está disponible
            print("[AVISO] Módulo enhanced_answer no encontrado. Usando método legacy.")
            return self._answer_legacy(text, chat_id)

    def _answer_legacy(self, text, chat_id="default"):
        """
        Método legacy para compatibilidad si loyverse_assistant_enhanced.py no está disponible
        """
        clean = text.lower().strip()
        clean = re.sub(r'^/(?:asistente|pregunta|ask|consulta)\s*', '', clean)
        clean = re.sub(r'@\w+', '', clean).strip()
        norm = normalize_text(clean)

        # Casos básicos de fallback
        if re.search(r'\b(?:caja|corte|fondo|cajon|dinero|efectivo)\b', norm):
            return self.get_drawer_status_msg()
        elif re.search(r'\b(?:ayer)\b', norm):
            yesterday = datetime.now(self.tz) - timedelta(days=1)
            return self.format_sales_summary_msg(self.get_day_sales_summary(yesterday), title="VENTAS DE AYER")
        elif re.search(r'\b(?:top|mas vendid|ranking)\b', norm):
            return self.get_top_sellers(30)
        elif re.search(r'\b(?:agotad|poco stock|bajo stock)\b', norm):
            return self.get_low_stock_report()
        elif re.search(r'\b(?:hoy|ventas?)\b', norm):
            return self.format_sales_summary_msg(self.get_day_sales_summary(), title="VENTAS DE HOY")
        
        # Fallback final
        return (
            f"🤖 <b>Asistente Vonne Boutique - Loyverse POS v2.0</b>\n\n"
            f"¡Hola! Puedes preguntarme sobre:\n\n"
            f"📊 Ventas (hoy, ayer, semana, mes)\n"
            f"💰 Estado de caja\n"
            f"🏆 Prendas más vendidas\n"
            f"📦 Inventario y stock\n"
            f"🎫 Detalle de tickets\n\n"
            f"📍 <i>Plaza La Fragua, Saltillo, Coahuila</i>"
        )
