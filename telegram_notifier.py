#!/usr/bin/env python3
"""
Vonne Boutique Saltillo - Notificador Oficial de Loyverse POS en Telegram
Funciones:
1. Notificaciones automáticas cada 30s:
   - Nuevas Ventas / Tickets generados
   - Cancelaciones / Reembolsos
   - Apertura de caja (inicio de turno y fondo inicial)
   - Cierre de caja / Corte del día (Z-Report completo)
2. Comandos interactivos en el grupo de Telegram (< 3s):
   - /ventas o /hoy: Resumen de ventas, tickets, ingresos y prendas vendidas hoy
   - /ayer: Resumen del día anterior para comparar
   - /prendas: Lista detallada de todas las prendas vendidas hoy
   - /caja: Estado actual de la caja y efectivo acumulado
   - /ayuda: Menú de comandos disponibles
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from loyverse_assistant import LoyverseAssistant

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"Vonne Boutique Telegram Bot is running 24/7!")
    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"Servidor de estado HTTP activo en puerto {port}")
    except Exception as e:
        print(f"Aviso servidor HTTP: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Soporte para ejecución en segundo plano (pythonw) y consola
LOG_PATH = os.path.join(BASE_DIR, "telegram_bot.log")
if sys.stdout is None:
    sys.stdout = open(LOG_PATH, "a", encoding="utf-8", errors="replace", buffering=1)
elif hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if sys.stderr is None:
    sys.stderr = open(LOG_PATH, "a", encoding="utf-8", errors="replace", buffering=1)
elif hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

LOYVERSE_CONFIG_PATH = os.path.join(BASE_DIR, "loyverse_config.json")
TELEGRAM_CONFIG_PATH = os.path.join(BASE_DIR, "telegram_config.json")
STATE_PATH = os.path.join(BASE_DIR, "telegram_state.json")

def load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Error leyendo {path}: {e}")
    return default or {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Error guardando {path}: {e}")

def get_loyverse_token():
    env_token = os.environ.get("LOYVERSE_TOKEN", "").strip()
    if env_token:
        return env_token
    cfg = load_json(LOYVERSE_CONFIG_PATH)
    return cfg.get("token", "").strip()

def loyverse_api_get(endpoint, token):
    url = f"https://api.loyverse.com/v1.0/{endpoint}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "VonneBoutiqueTelegramNotifier/2.0"
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def format_for_telegram(text):
    if not text:
        return ""
    # Convert markdown bold **text** to <b>text</b>
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Convert markdown bullet * to •
    t = re.sub(r'(?m)^\*\s+', '• ', t)
    # Convert markdown code `text` to <code>text</code>
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    return t

def send_telegram(bot_token, chat_id, text, parse_mode="HTML"):
    if not bot_token or not chat_id:
        print("[AVISO] Telegram no configurado (bot_token o chat_id vacíos).")
        return False

    if isinstance(chat_id, (list, tuple)):
        targets = chat_id
    elif isinstance(chat_id, str) and "," in chat_id:
        targets = [c.strip() for c in chat_id.split(",") if c.strip()]
    else:
        targets = [chat_id]

    # Convert common markdown if sending as HTML
    formatted_text = format_for_telegram(text) if parse_mode == "HTML" else text

    all_ok = True
    for target in targets:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": target,
            "text": formatted_text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if not res.get("ok", False):
                    all_ok = False
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"[ERROR Telegram ({target})] HTTP {e.code}: {err_body}")
            # Si falló por formato HTML, reintentar sin formato para garantizar entrega
            if parse_mode:
                try:
                    payload["text"] = text
                    payload["parse_mode"] = None
                    req_plain = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req_plain, timeout=15) as resp_plain:
                        res_plain = json.loads(resp_plain.read().decode("utf-8"))
                        if res_plain.get("ok", False):
                            print(f"[Telegram ({target})] Reintento como texto plano exitoso.")
                            continue
                except Exception as e_plain:
                    print(f"[Telegram ({target})] Falló reintento plano: {e_plain}")
            all_ok = False
        except Exception as e:
            print(f"[ERROR Telegram ({target})] Error de conexión: {e}")
            all_ok = False
    return all_ok

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

def format_money(val):
    try:
        v = float(val)
        return f"${v:,.2f} MXN"
    except Exception:
        return f"${val} MXN"

MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

DAYS_ES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles",
    3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"
}

def get_telegram_config():
    cfg = load_json(TELEGRAM_CONFIG_PATH)
    bot_token = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if bot_token:
        cfg["bot_token"] = bot_token.strip()
    chat_id = os.environ.get("CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    if chat_id:
        cfg["chat_id"] = chat_id.strip()
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        cfg["gemini_api_key"] = gemini_key.strip()
    return cfg

class LoyverseTelegramNotifier:
    def __init__(self):
        self.loy_token = get_loyverse_token()
        self.tg_cfg = get_telegram_config()
        self.state = load_json(STATE_PATH, {
            "processed_receipt_ids": [],
            "processed_shift_ids": [],
            "known_open_shift_id": None,
            "last_receipt_time": None,
            "last_update_id": 0,
            "notified_out_of_stock": [],
            "notified_low_stock": [],
            "last_no_sales_alert": None,
            "first_sale_today_date": None,
            "last_biweekly_report": None,
            "last_weekly_report": None,
            "last_2h_report": None
        })
        self.employees_cache = {}
        self.payment_types_cache = {}
        self.assistant = LoyverseAssistant(self.loy_token, self.tg_cfg)
        self._load_metadata()

    def _load_metadata(self):
        if not self.loy_token:
            return
        try:
            emp_data = loyverse_api_get("employees", self.loy_token)
            for emp in emp_data.get("employees", []):
                self.employees_cache[emp["id"]] = emp.get("name", "Vonne Boutique")
        except Exception as e:
            print(f"[INFO] No se pudo cargar empleados: {e}")

        try:
            pt_data = loyverse_api_get("payment_types", self.loy_token)
            for pt in pt_data.get("payment_types", []):
                self.payment_types_cache[pt["id"]] = pt.get("name", "Otro")
        except Exception as e:
            print(f"[INFO] No se pudo cargar métodos de pago: {e}")

    def check_receipts(self):
        if not self.loy_token:
            return
        bot_token = self.tg_cfg.get("bot_token")
        chat_id = self.tg_cfg.get("chat_id")
        offset = self.tg_cfg.get("timezone_offset_hours", -6)

        try:
            data = loyverse_api_get("receipts?limit=10", self.loy_token)
            receipts = data.get("receipts", [])
        except Exception as e:
            print(f"[ERROR] Error consultando recibos: {e}")
            return

        processed = set(self.state.get("processed_receipt_ids", []))
        new_processed = list(self.state.get("processed_receipt_ids", []))

        if not self.state.get("last_receipt_time") and receipts:
            for r in receipts:
                new_processed.append(r["receipt_number"])
            self.state["processed_receipt_ids"] = new_processed[-50:]
            self.state["last_receipt_time"] = receipts[0].get("created_at")
            save_json(STATE_PATH, self.state)
            print(f"ℹ️ Estado de recibos inicializado con {len(receipts)} tickets existentes.")
            return

        for r in reversed(receipts):
            r_num = r.get("receipt_number")
            r_type = r.get("receipt_type")
            cancelled_at = r.get("cancelled_at")

            event_id = f"{r_num}_{r_type}_{'cancelled' if cancelled_at else 'ok'}"
            if event_id in processed:
                continue

            # ── Filtro de antigüedad: no notificar tickets de hace >90 min ──
            created_str = r.get("created_at") or r.get("receipt_date", "")
            is_stale = False
            if created_str:
                try:
                    created_dt = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                    age_minutes = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
                    if age_minutes > 90:
                        is_stale = True
                        print(f"⏭️ Ticket #{r_num} ignorado (hace {int(age_minutes)} min, bot estaba offline)")
                except Exception:
                    pass

            emp_name = self.employees_cache.get(r.get("employee_id"), "Vonne Boutique")
            total = r.get("total_money", 0.0)
            receipt_time = format_iso_time(r.get("created_at") or r.get("receipt_date"), offset)

            if is_stale:
                new_processed.append(event_id)
                continue


            # Caso 1: Cancelación
            if cancelled_at or r_type == "REFUND":
                if self.tg_cfg.get("notify_cancellations", True):
                    cancel_time = format_iso_time(cancelled_at or r.get("updated_at"), offset)
                    msg = (
                        f"🚨 <b>TICKET CANCELADO / REEMBOLSO</b>\n\n"
                        f"📄 <b>Ticket:</b> <code>#{r_num}</code>\n"
                        f"👤 <b>Atendió:</b> {emp_name}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"💸 <b>Total Anulado:</b> {format_money(total)}\n"
                        f"🕐 <b>Hora:</b> {cancel_time}\n"
                        f"📍 <i>Plaza La Fragua, Saltillo</i>"
                    )
                    if send_telegram(bot_token, chat_id, msg):
                        print(f"🔔 Notificación de cancelación enviada: #{r_num}")

            # Caso 2: Nueva Venta
            elif r_type == "SALE":
                if self.tg_cfg.get("notify_sales", True):
                    items_lines = []
                    for it in r.get("line_items", []):
                        qty = it.get("quantity", 1)
                        name = it.get("item_name", "Prenda")
                        price = it.get("total_money", 0.0)
                        items_lines.append(f"• {qty}x <b>{name}</b> ({format_money(price)})")

                    items_block = "\n".join(items_lines) if items_lines else "• Prenda seleccionada"

                    payments = r.get("payments", [])
                    pay_names = []
                    for p in payments:
                        p_name = p.get("name") or self.payment_types_cache.get(p.get("payment_type_id"), "Efectivo")
                        pay_names.append(p_name)
                    pay_str = ", ".join(pay_names) if pay_names else "Efectivo"

                    msg = (
                        f"🛍️ <b>NUEVA VENTA - Vonne Boutique</b>\n\n"
                        f"📄 <b>Ticket:</b> <code>#{r_num}</code>\n"
                        f"👤 <b>Atendió:</b> {emp_name}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"{items_block}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 <b>TOTAL:</b> <b>{format_money(total)}</b>\n"
                        f"💳 <b>Forma de Pago:</b> {pay_str}\n"
                        f"🕐 <b>Hora:</b> {receipt_time}\n"
                        f"📍 <i>Plaza La Fragua, Saltillo</i>"
                    )
                    if send_telegram(bot_token, chat_id, msg):
                        print(f"🔔 Notificación de venta enviada: #{r_num} ({format_money(total)})")

                    # ── Primera venta del día ──────────────────────────────
                    offset = self.tg_cfg.get("timezone_offset_hours", -6)
                    tz_local = timezone(timedelta(hours=offset))
                    now_local = datetime.now(tz_local)
                    today_str = now_local.strftime("%Y-%m-%d")
                    if self.state.get("first_sale_today_date") != today_str:
                        self.state["first_sale_today_date"] = today_str
                        first_msg = (
                            f"🎀 <b>¡PRIMERA VENTA DEL DÍA! — Vonne Boutique</b>\n\n"
                            f"📄 <b>Ticket:</b> <code>#{r_num}</code>\n"
                            f"👤 <b>Atendió:</b> {emp_name}\n"
                            f"💰 <b>Total:</b> <b>{format_money(total)}</b>\n"
                            f"🕐 <b>Hora:</b> {receipt_time}\n\n"
                            f"✨ <i>¡A vender mucho hoy!</i>\n"
                            f"📍 <i>Plaza La Fragua, Saltillo</i>"
                        )
                        send_telegram(bot_token, chat_id, first_msg)
                        print("🎀 Notificación de primera venta del día enviada.")

                    # ── Descuento grande (≥30%) ────────────────────────────
                    gross = r.get("gross_total_money", 0.0) or r.get("total_money", 0.0)
                    discount_amt = r.get("discount_total_money", 0.0) or 0.0
                    discount_pct_threshold = self.tg_cfg.get("discount_alert_pct", 30)
                    if gross > 0 and discount_amt > 0:
                        pct = (discount_amt / gross) * 100
                        if pct >= discount_pct_threshold:
                            disc_msg = (
                                f"🏷️ <b>DESCUENTO GRANDE APLICADO</b>\n\n"
                                f"📄 <b>Ticket:</b> <code>#{r_num}</code>\n"
                                f"👤 <b>Atendió:</b> {emp_name}\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"💸 <b>Descuento:</b> -{format_money(discount_amt)} ({pct:.0f}%)\n"
                                f"💰 <b>Total cobrado:</b> {format_money(total)}\n"
                                f"🕐 <b>Hora:</b> {receipt_time}\n"
                                f"📍 <i>Plaza La Fragua, Saltillo</i>"
                            )
                            send_telegram(bot_token, chat_id, disc_msg)
                            print(f"🏷️ Alerta de descuento grande enviada: #{r_num} ({pct:.0f}%)")

            new_processed.append(event_id)

        self.state["processed_receipt_ids"] = new_processed[-80:]
        if receipts:
            self.state["last_receipt_time"] = receipts[0].get("created_at")
        save_json(STATE_PATH, self.state)

    def check_shifts(self):
        if not self.loy_token:
            return
        bot_token = self.tg_cfg.get("bot_token")
        chat_id = self.tg_cfg.get("chat_id")
        offset = self.tg_cfg.get("timezone_offset_hours", -6)

        try:
            data = loyverse_api_get("shifts?limit=5", self.loy_token)
            shifts = data.get("shifts", [])
        except Exception as e:
            print(f"[ERROR] Error consultando turnos: {e}")
            return

        if not shifts:
            return

        processed_shifts = set(self.state.get("processed_shift_ids", []))
        known_open = self.state.get("known_open_shift_id")

        if not processed_shifts and known_open is None:
            for s in shifts:
                if s.get("closed_at"):
                    processed_shifts.add(s["id"])
                else:
                    self.state["known_open_shift_id"] = s["id"]
            self.state["processed_shift_ids"] = list(processed_shifts)
            save_json(STATE_PATH, self.state)
            print(f"ℹ️ Estado de turnos de caja inicializado.")
            return

        for s in reversed(shifts):
            shift_id = s.get("id")
            emp_name = self.employees_cache.get(s.get("employee_id"), "Vonne Boutique")
            opened_at = s.get("opened_at")
            closed_at = s.get("closed_at")
            start_cash = s.get("starting_cash", 0.0)

            # Caso 1: Apertura
            if closed_at is None:
                if known_open != shift_id:
                    self.state["known_open_shift_id"] = shift_id
                    save_json(STATE_PATH, self.state)

                    notify_open = self.tg_cfg.get("notify_drawer_open", self.tg_cfg.get("notify_shift_open", True))
                    if notify_open:
                        open_time_str = format_iso_time(opened_at, offset)
                        msg = (
                            f"🔓 <b>APERTURA DE CAJA - Vonne Boutique</b>\n\n"
                            f"👤 <b>Abrió:</b> {emp_name}\n"
                            f"💵 <b>Fondo Inicial de Caja:</b> <b>{format_money(start_cash)}</b>\n"
                            f"🕐 <b>Hora de Apertura:</b> {open_time_str}\n"
                            f"📍 <i>Plaza La Fragua, Saltillo</i>\n\n"
                            f"✨ <i>¡Excelente jornada de ventas!</i>"
                        )
                        if send_telegram(bot_token, chat_id, msg):
                            print(f"🔔 Notificación de apertura de caja enviada: {open_time_str}")

            # Caso 2: Cierre
            else:
                if shift_id not in processed_shifts:
                    processed_shifts.add(shift_id)
                    if self.state.get("known_open_shift_id") == shift_id:
                        self.state["known_open_shift_id"] = None
                    self.state["processed_shift_ids"] = list(processed_shifts)[-30:]
                    save_json(STATE_PATH, self.state)

                    # ── Filtro de antigüedad: no notificar cortes de hace >90 min ──
                    is_stale = False
                    if closed_at:
                        try:
                            closed_dt = datetime.fromisoformat(
                                closed_at.replace("Z", "+00:00")
                            ).astimezone(timezone.utc)
                            age_minutes = (datetime.now(timezone.utc) - closed_dt).total_seconds() / 60
                            if age_minutes > 90:
                                is_stale = True
                                print(f"⏭️ Turno #{shift_id} ignorado por antigüedad ({int(age_minutes)} min)")
                        except Exception:
                            pass

                    if is_stale:
                        continue

                    notify_close = self.tg_cfg.get("notify_drawer_close", self.tg_cfg.get("notify_shift_close", True))
                    if notify_close:
                        open_time_str = format_iso_time(opened_at, offset)
                        close_time_str = format_iso_time(closed_at, offset)

                        gross_sales = s.get("gross_sales", 0.0)
                        net_sales = s.get("net_sales", 0.0)
                        discounts = s.get("discounts", 0.0)
                        refunds = s.get("refunds", 0.0)

                        cash_payments = s.get("cash_payments", 0.0)
                        cash_refunds = s.get("cash_refunds", 0.0)
                        paid_in = s.get("paid_in", 0.0)
                        paid_out = s.get("paid_out", 0.0)
                        expected_cash = s.get("expected_cash", 0.0)
                        actual_cash = s.get("actual_cash", 0.0)
                        difference = actual_cash - expected_cash

                        payments_summary = s.get("payments", [])
                        pay_lines = []
                        for pm in payments_summary:
                            pm_name = pm.get("payment_type_name") or self.payment_types_cache.get(pm.get("payment_type_id"), "Otro")
                            pm_amount = pm.get("total_money", 0.0)
                            pay_lines.append(f"• <b>{pm_name}:</b> {format_money(pm_amount)}")
                        payments_block = "\n".join(pay_lines) if pay_lines else f"• <b>Efectivo:</b> {format_money(cash_payments)}"

                        if abs(difference) < 0.01:
                            diff_badge = "✅ Cuadrado exacto (Sin diferencia)"
                        elif difference > 0:
                            diff_badge = f"🟢 Sobrante: +{format_money(difference)}"
                        else:
                            diff_badge = f"🔴 Faltante: {format_money(difference)}"

                        msg = (
                            f"🔒 <b>CORTE DE CAJA / CIERRE DEL DÍA</b>\n"
                            f"🏪 <b>Vonne Boutique Saltillo</b>\n\n"
                            f"👤 <b>Cajero/a:</b> {emp_name}\n"
                            f"📅 <b>Período:</b> {open_time_str} ➡️ {close_time_str}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"📊 <b>RESUMEN DE VENTAS</b>\n"
                            f"• Ventas Brutas: {format_money(gross_sales)}\n"
                            f"• Descuentos: -{format_money(discounts)}\n"
                            f"• Devoluciones: -{format_money(refunds)}\n"
                            f"💰 <b>VENTAS NETAS:</b> <b>{format_money(net_sales)}</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"💳 <b>DESGLOSE POR FORMA DE PAGO</b>\n"
                            f"{payments_block}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"💵 <b>CONTROL DE EFECTIVO EN CAJA</b>\n"
                            f"• Fondo Inicial: {format_money(start_cash)}\n"
                            f"• Cobros en Efectivo: {format_money(cash_payments - cash_refunds)}\n"
                            f"• Entradas de Caja: +{format_money(paid_in)}\n"
                            f"• Salidas de Caja: -{format_money(paid_out)}\n"
                            f"• Efectivo Esperado: {format_money(expected_cash)}\n"
                            f"• <b>Efectivo Real Contado:</b> <b>{format_money(actual_cash)}</b>\n"
                            f"⚖️ <b>Estado del Cuadre:</b> {diff_badge}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"📍 <i>Plaza La Fragua, Saltillo</i>"
                        )
                        # ── Reporte completo combinado al cierre ──────────
                        try:
                            stats      = self.assistant.get_day_sales_summary()
                            date_str   = stats.get("date_human", close_time_str)
                            net        = stats.get("net", 0.0)
                            t_count    = stats.get("ticket_count", 0)
                            pieces     = stats.get("total_pieces", 0)
                            pay_totals = stats.get("payments", {})
                            items_dict = stats.get("items", {})

                            # Formas de pago
                            pay_lines_sales = []
                            for pname, pamount in pay_totals.items():
                                if pamount > 0:
                                    pay_lines_sales.append(f"• {pname}: {format_money(pamount)}")
                            pay_block_sales = "\n".join(pay_lines_sales) if pay_lines_sales else f"• {payments_block}"

                            # Prendas vendidas
                            sorted_items = sorted(items_dict.items(), key=lambda x: x[1]["qty"], reverse=True)
                            item_lines = []
                            for iname, d in sorted_items[:15]:
                                item_lines.append(f"• {d['qty']}x <b>{iname}</b> ({format_money(d['money'])})")
                            if len(sorted_items) > 15:
                                extra = sum(d['qty'] for _, d in sorted_items[15:])
                                item_lines.append(f"<i>... y {extra} prendas más</i>")
                            items_block_sales = "\n".join(item_lines) if item_lines else "• Sin prendas registradas"

                            combined_msg = (
                                f"🔒 <b>CORTE DE CAJA / CIERRE DEL DÍA</b>\n"
                                f"🏪 <b>Vonne Boutique Saltillo</b>\n\n"
                                f"👤 <b>Cajero/a:</b> {emp_name}\n"
                                f"📅 <b>Período:</b> {open_time_str} ➡️ {close_time_str}\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"📊 <b>RESUMEN DE VENTAS</b>\n"
                                f"• Ventas Brutas: {format_money(gross_sales)}\n"
                                f"• Descuentos: -{format_money(discounts)}\n"
                                f"• Devoluciones: -{format_money(refunds)}\n"
                                f"💰 <b>VENTAS NETAS: {format_money(net_sales)}</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"💳 <b>DESGLOSE POR FORMA DE PAGO</b>\n"
                                f"{payments_block}\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"💵 <b>CONTROL DE EFECTIVO EN CAJA</b>\n"
                                f"• Fondo Inicial: {format_money(start_cash)}\n"
                                f"• Cobros en Efectivo: {format_money(cash_payments - cash_refunds)}\n"
                                f"• Entradas de Caja: +{format_money(paid_in)}\n"
                                f"• Salidas de Caja: -{format_money(paid_out)}\n"
                                f"• Efectivo Esperado: {format_money(expected_cash)}\n"
                                f"• <b>Efectivo Real Contado: {format_money(actual_cash)}</b>\n"
                                f"⚖️ <b>Estado del Cuadre:</b> {diff_badge}\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"🎟️ <b>Tickets Cobrados:</b> {t_count}  |  👗 <b>Prendas:</b> {pieces} piezas\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"🛍️ <b>PRENDAS VENDIDAS:</b>\n"
                                f"{items_block_sales}\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"📍 <i>Plaza La Fragua, Saltillo</i>"
                            )
                            if send_telegram(bot_token, chat_id, combined_msg):
                                print(f"🔔 Mensaje de cierre combinado enviado: {close_time_str}")
                        except Exception as e:
                            # Si falla el combinado, mandar solo el corte de caja
                            print(f"[ERROR] Reporte combinado de cierre: {e}")
                            if send_telegram(bot_token, chat_id, msg):
                                print(f"🔔 Notificación de corte de caja (fallback) enviada: {close_time_str}")

    # =========================================================================
    # LÓGICA DE REPORTES INTERACTIVOS
    # =========================================================================

    def get_day_sales_summary(self, target_dt=None):
        offset = self.tg_cfg.get("timezone_offset_hours", -6)
        tz = timezone(timedelta(hours=offset))
        if target_dt is None:
            target_dt = datetime.now(tz)

        start_local = datetime(target_dt.year, target_dt.month, target_dt.day, 0, 0, 0, tzinfo=tz)
        end_local = start_local + timedelta(days=1)

        start_utc = start_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc = end_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        day_name = DAYS_ES.get(target_dt.weekday(), "")
        month_name = MONTHS_ES.get(target_dt.month, "")
        human_date = f"{day_name} {target_dt.day} de {month_name}, {target_dt.year}"

        url = f"receipts?created_at_min={start_utc}&created_at_max={end_utc}&limit=250"
        try:
            data = loyverse_api_get(url, self.loy_token)
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

        # Top prendas vendidas
        items_lines = []
        sorted_items = sorted(stats["items"].items(), key=lambda x: x[1]["qty"], reverse=True)
        for name, d in sorted_items[:12]:
            items_lines.append(f"• {d['qty']}x <b>{name}</b> ({format_money(d['money'])})")
        if len(sorted_items) > 12:
            remaining = sum(d['qty'] for _, d in sorted_items[12:])
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

    def format_items_list_msg(self, stats):
        date_str = stats["date_human"]
        pieces = stats["total_pieces"]
        if pieces == 0:
            return (
                f"👗 <b>PRENDAS VENDIDAS HOY - Vonne Boutique</b>\n"
                f"📅 <i>{date_str}</i>\n\n"
                f"ℹ️ Aún no se registran prendas vendidas el día de hoy."
            )

        sorted_items = sorted(stats["items"].items(), key=lambda x: x[1]["qty"], reverse=True)
        lines = []
        for name, d in sorted_items:
            lines.append(f"• <b>{d['qty']}x</b> {name} — {format_money(d['money'])}")

        return (
            f"👗 <b>PRENDAS VENDIDAS HOY ({pieces} piezas)</b>\n"
            f"🏪 <b>Vonne Boutique Saltillo</b>\n"
            f"📅 <i>{date_str}</i>\n\n"
            + "\n".join(lines) + "\n\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    def get_drawer_status_msg(self):
        offset = self.tg_cfg.get("timezone_offset_hours", -6)
        try:
            data = loyverse_api_get("shifts?limit=3", self.loy_token)
            shifts = data.get("shifts", [])
        except Exception as e:
            return f"❌ Error consultando el estado de caja: {e}"

        if not shifts:
            return "ℹ️ No hay registros recientes de turnos de caja en Loyverse."

        # Buscar turno abierto
        open_shift = next((s for s in shifts if s.get("closed_at") is None), None)

        if open_shift:
            emp = self.employees_cache.get(open_shift.get("employee_id"), "Vonne Boutique")
            opened_at = format_iso_time(open_shift.get("opened_at"), offset)
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
                f"➕ <b>Entradas:</b> {format_money(paid_in)}\n"
                f"➖ <b>Salidas:</b> {format_money(paid_out)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 <b>Efectivo Esperado en Caja:</b> <b>{format_money(expected_cash)}</b>\n\n"
                f"📍 <i>Plaza La Fragua, Saltillo</i>"
            )
        else:
            last = shifts[0]
            emp = self.employees_cache.get(last.get("employee_id"), "Vonne Boutique")
            closed_at = format_iso_time(last.get("closed_at"), offset)
            return (
                f"🔒 <b>ESTADO DE CAJA: CAJA CERRADA</b>\n"
                f"🏪 <b>Vonne Boutique Saltillo</b>\n\n"
                f"El último turno fue cerrado por <b>{emp}</b> a las <b>{closed_at}</b>.\n\n"
                f"<i>En cuanto se abra turno en el punto de venta, se notificará aquí en automático.</i>"
            )

    def get_help_msg(self):
        return (
            f"✨ <b>ASISTENTE INTELIGENTE VONNE BOUTIQUE</b>\n"
            f"🏪 <i>Loyverse POS & Perchero en Vivo</i>\n\n"
            f"Puedes escribir comandos directos o preguntarme de forma natural:\n\n"
            f"📊 <b>Ventas y Rendimiento:</b>\n"
            f"• <code>/ventas</code> o <code>/hoy</code> : Corte acumulado de hoy\n"
            f"• <code>/prendas</code> : Lista de prendas vendidas hoy\n"
            f"• <code>/ayer</code> : Reporte completo de ventas de ayer\n"
            f"• <code>/semana</code> : Ventas de los últimos 7 días\n"
            f"• <code>/mes</code> : Ventas de los últimos 30 días\n"
            f"• <code>/top</code> : Ranking de prendas más vendidas\n\n"
            f"🎯 <b>Marketing & Meta Ads:</b>\n"
            f"• <code>/ads</code> : Reporte en vivo de Meta Ads (gasto, mensajes y CPA)\n"
            f"• <code>/roas</code> o <code>/roi</code> : Correlación de Publicidad vs. Ventas en Caja (POS)\n\n"
            f"📦 <b>Inventario y Stock:</b>\n"
            f"• <code>/stock blazer</code> : Existencias y tallas de una prenda\n"
            f"• <code>/agotados</code> : Prendas agotadas o por agotarse\n"
            f"• <code>/caja</code> : Estado de caja y efectivo estimado\n"
            f"• <code>ticket 3949</code> : Consulta el detalle de un ticket\n\n"
            f"💬 <b>Preguntas Libres:</b>\n"
            f"También puedes preguntarme: <i>\"¿Cuánto stock queda de blazer blanco?\"</i>, <i>\"¿Qué precio tiene el vestido?\"</i> o <i>\"¿Cuáles son las prendas más vendidas?\"</i>.\n\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    def process_telegram_commands(self):
        bot_token = self.tg_cfg.get("bot_token")
        if not bot_token:
            return

        last_id = self.state.get("last_update_id", 0)
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={last_id + 1}&limit=10&timeout=0"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                updates = data.get("result", [])
        except Exception as e:
            return

        if not updates:
            return

        allowed_chats = set(str(c) for c in self.tg_cfg.get("allowed_chat_ids", ["-5559233999", "549065780"]))
        main_chat = str(self.tg_cfg.get("chat_id", "-5559233999"))
        allowed_chats.add(main_chat)

        for u in updates:
            up_id = u.get("update_id")
            if up_id > self.state.get("last_update_id", 0):
                self.state["last_update_id"] = up_id
                save_json(STATE_PATH, self.state)

            msg = u.get("message") or u.get("channel_post")
            if not msg:
                continue

            chat = msg.get("chat", {})
            sender_chat_id = str(chat.get("id"))
            raw_text = (msg.get("text") or "").strip()
            text = raw_text.lower()

            msg_date = msg.get("date")
            if msg_date and (time.time() - msg_date) > 900:
                print(f"⏭️ Mensaje ignoro por antigüedad ({int((time.time() - msg_date)/60)} min): '{raw_text}'")
                continue

            if allowed_chats and sender_chat_id not in allowed_chats:
                continue

            if not text:
                continue

            print(f"💬 Mensaje recibido: '{raw_text}' en chat {sender_chat_id}")
            
            # Comando directo de Meta Ads / Campañas (coincidencia amplia)
            if any(k in text for k in ["/ads", "/campanas", "/campañas", "/meta", "/facebook", "campana", "campaña", "campanas", "campañas", "anuncio", "anuncios", "publicidad", "pauta", "ads"]):
                try:
                    from send_ads_summary_telegram import get_ads_summary_msg
                    ads_reply = get_ads_summary_msg()
                    if send_telegram(bot_token, sender_chat_id, ads_reply):
                        continue
                except Exception as ex:
                    print(f"Error generando reporte de Ads en Telegram: {ex}")

            # Comando directo de Correlación Ads vs Ventas POS (ROAS / ROI)
            if text in ["/roas", "/roi", "/correlacion", "/caja_ads"] or any(k in text for k in ["relacion pauta ventas", "cuanto se vendio de publicidad", "publicidad vs ventas", "retorno publicidad"]):
                try:
                    from send_ads_pos_correlation_telegram import generate_correlation_report
                    corr_reply = generate_correlation_report()
                    if send_telegram(bot_token, sender_chat_id, corr_reply):
                        continue
                except Exception as ex:
                    print(f"Error generando reporte de Correlación en Telegram: {ex}")

            reply = self.assistant.answer(raw_text, chat_id=sender_chat_id)
            if not reply:
                from loyverse_assistant_enhanced import show_help
                reply = show_help(raw_text)
            send_telegram(bot_token, sender_chat_id, reply)

    # =========================================================================
    # ALERTAS DE INVENTARIO
    # =========================================================================

    _startup_time = None  # se setea al inicio del daemon

    def check_inventory_alerts(self):
        """Detecta prendas agotadas en tiempo real cuando cambian a 0 stock."""
        if not self.loy_token:
            return

        bot_token = self.tg_cfg.get("bot_token")
        chat_id   = self.tg_cfg.get("chat_id")
        offset    = self.tg_cfg.get("timezone_offset_hours", -6)
        tz_local  = timezone(timedelta(hours=offset))
        now_local = datetime.now(tz_local)
        today_str = now_local.strftime("%Y-%m-%d")

        # ── Construir mapa variant_id → nombre desde Loyverse items API ────
        variant_names = {}
        try:
            page_cursor = None
            while True:
                endpoint = "items?limit=250"
                if page_cursor:
                    endpoint += f"&cursor={page_cursor}"
                items_data = loyverse_api_get(endpoint, self.loy_token)
                for item in items_data.get("items", []):
                    item_name = item.get("item_name", "")
                    for v in item.get("variants", []):
                        vid   = v.get("variant_id", "")
                        talla = v.get("option1_value") or v.get("option2_value") or ""
                        full  = f"{item_name} — {talla}".strip(" —") if talla else item_name
                        variant_names[vid] = full
                cursor = items_data.get("cursor")
                if not cursor:
                    break
                page_cursor = cursor
        except Exception as e:
            print(f"[AVISO] No se pudo cargar nombres de variantes: {e}")

        # ── Stock agotado: detectar transiciones a 0 ──────────────────────
        try:
            inv_data = loyverse_api_get("inventory?limit=250", self.loy_token)
            items    = inv_data.get("inventory_levels", [])
            notified_out = set(self.state.get("notified_out_of_stock", []))
            is_first_run = not self.state.get("inventory_initialized", False)
            newly_out_names = []

            for item in items:
                variant_id = item.get("variant_id", "")
                stock      = item.get("in_stock", 0) or 0
                name = (variant_names.get(variant_id)
                        or item.get("item_name")
                        or item.get("variant_name")
                        or "Prenda desconocida")

                if stock == 0:
                    if variant_id not in notified_out:
                        notified_out.add(variant_id)
                        if not is_first_run:
                            newly_out_names.append(name)
                else:
                    # Si volvió a tener stock (reabastecimiento), quitar de notificados
                    if variant_id in notified_out:
                        notified_out.remove(variant_id)

            if is_first_run:
                self.state["inventory_initialized"] = True
                print(f"ℹ️ Estado de inventario inicializado en silencio ({len(notified_out)} prendas en 0 stock).")

            if newly_out_names and not is_first_run:
                lines = "\n".join(f"• <b>{n}</b>" for n in newly_out_names)
                count_str = f"{len(newly_out_names)} PRENDAS AGOTADAS" if len(newly_out_names) > 1 else "PRENDA AGOTADA"
                msg = (
                    f"🚨 <b>¡{count_str}!</b>\n\n"
                    f"{lines}\n\n"
                    f"📦 <b>Stock:</b> 0 piezas\n"
                    f"⚠️ <i>Ya no hay existencias disponibles para venta.</i>\n"
                    f"📍 <i>Plaza La Fragua, Saltillo</i>"
                )
                send_telegram(bot_token, chat_id, msg)
                print(f"🚨 Alerta stock agotado agrupada ({len(newly_out_names)} prendas): {', '.join(newly_out_names)}")

            self.state["notified_out_of_stock"] = list(notified_out)
            save_json(STATE_PATH, self.state)

        except Exception as e:
            print(f"[ERROR] check_inventory_alerts: {e}")





    # =========================================================================
    # REPORTES PROGRAMADOS (QUINCENAL, SEMANAL, CADA 2H)
    # =========================================================================

    def check_scheduled_reports(self):
        """Envía reportes automáticos: quincenal, semanal (sábado) y acumulado cada 2h."""
        import calendar as _cal
        bot_token = self.tg_cfg.get("bot_token")
        chat_id   = self.tg_cfg.get("chat_id")
        offset    = self.tg_cfg.get("timezone_offset_hours", -6)
        tz_local  = timezone(timedelta(hours=offset))
        now_local = datetime.now(tz_local)
        today_str = now_local.strftime("%Y-%m-%d")
        hora      = now_local.hour
        dia       = now_local.day
        mes       = now_local.month
        anio      = now_local.year
        dow       = now_local.weekday()  # 0=Lun … 5=Sáb … 6=Dom

        # ── Reporte diario de stock bajo a las 12pm ────────────────────────
        if hora == 12:
            last_stock_report = self.state.get("last_stock_low_report")
            if last_stock_report != today_str:
                try:
                    inv_data = loyverse_api_get("inventory?limit=250", self.loy_token)
                    items    = inv_data.get("inventory_levels", [])
                    low_threshold = self.tg_cfg.get("low_stock_threshold", 3)

                    low_items = [
                        (item.get("item_name") or item.get("variant_name") or "Prenda",
                         int(item.get("in_stock", 0) or 0))
                        for item in items
                        if 0 < (item.get("in_stock", 0) or 0) < low_threshold
                    ]
                    low_items.sort(key=lambda x: x[1])  # menor stock primero

                    if low_items:
                        lines = "\n".join(
                            f"• <b>{name}</b> — {qty} {'pieza' if qty == 1 else 'piezas'}"
                            for name, qty in low_items
                        )
                        msg = (
                            f"⚠️ <b>REPORTE DE STOCK BAJO — Vonne Boutique</b>\n"
                            f"📅 <i>{now_local.strftime('%d/%m/%Y')}</i>\n\n"
                            f"Las siguientes prendas tienen <b>menos de {low_threshold} piezas</b>:\n\n"
                            f"{lines}\n\n"
                            f"🛒 <i>Considera reabastecer antes de que se agoten.</i>\n"
                            f"📍 <i>Plaza La Fragua, Saltillo</i>"
                        )
                        if send_telegram(bot_token, chat_id, msg):
                            self.state["last_stock_low_report"] = today_str
                            save_json(STATE_PATH, self.state)
                            print(f"⚠️ Reporte de stock bajo enviado ({len(low_items)} prendas).")
                    else:
                        self.state["last_stock_low_report"] = today_str
                        save_json(STATE_PATH, self.state)
                        print("✅ Reporte stock bajo: todas las prendas tienen stock suficiente.")
                except Exception as e:
                    print(f"[ERROR] Reporte stock bajo: {e}")

        # ── Acumulado del día: 2pm, 4pm y 6pm ─────────────────────────────
        horas_reporte = [14, 16, 18]
        if hora in horas_reporte:
            last_2h = self.state.get("last_2h_report")
            slot_key = f"{today_str} {hora:02d}"
            if last_2h != slot_key:
                try:
                    stats = self.assistant.get_day_sales_summary()
                    hora_label = now_local.strftime("%I:%M %p")
                    sales_msg  = self.assistant.format_sales_summary_msg(
                        stats,
                        title=f"⏰ ACUMULADO DEL DÍA — {hora_label}"
                    )
                    if send_telegram(bot_token, chat_id, sales_msg):
                        self.state["last_2h_report"] = slot_key
                        save_json(STATE_PATH, self.state)
                        print(f"⏰ Reporte acumulado enviado a las {hora_label}")
                except Exception as e:
                    print(f"[ERROR] Reporte cada 2h: {e}")

        # ── Resumen semanal: sábados a las 9pm ─────────────────────────────
        if dow == 5 and hora == 21:
            last_weekly = self.state.get("last_weekly_report")
            if last_weekly != today_str:
                try:
                    # Ventas de lunes a hoy (sábado)
                    start_week = now_local - timedelta(days=5)  # lunes
                    start_dt   = datetime(start_week.year, start_week.month, start_week.day,
                                          0, 0, 0, tzinfo=tz_local)
                    end_dt     = datetime(now_local.year, now_local.month, now_local.day,
                                          23, 59, 59, tzinfo=tz_local)
                    sales_msg  = self.assistant.get_date_range_sales_summary(start_dt, end_dt)
                    week_header = (
                        f"📊 <b>RESUMEN SEMANAL — Vonne Boutique</b>\n"
                        f"📅 <i>Lunes {start_dt.strftime('%d/%m')} al Sábado {now_local.strftime('%d/%m/%Y')}</i>\n\n"
                    )
                    full_msg = week_header + sales_msg
                    if send_telegram(bot_token, chat_id, full_msg):
                        self.state["last_weekly_report"] = today_str
                        save_json(STATE_PATH, self.state)
                        print("📊 Resumen semanal enviado.")
                except Exception as e:
                    print(f"[ERROR] Resumen semanal: {e}")

        # ── Reporte quincenal: día 15 y último día del mes a las 9pm ───────
        _, last_day_of_month = _cal.monthrange(anio, mes)
        is_biweekly_day = (dia == 15 or dia == last_day_of_month)
        if is_biweekly_day and hora == 21:
            last_bi = self.state.get("last_biweekly_report")
            if last_bi != today_str:
                try:
                    # Período: 1–15 o 16–último
                    if dia == 15:
                        start_day, end_day = 1, 15
                        periodo_label = f"1 al 15 de {MONTHS_ES.get(mes, '')}"
                    else:
                        start_day, end_day = 16, last_day_of_month
                        periodo_label = f"16 al {last_day_of_month} de {MONTHS_ES.get(mes, '')}"

                    start_dt = datetime(anio, mes, start_day, 0, 0, 0, tzinfo=tz_local)
                    end_dt   = datetime(anio, mes, end_day,   23, 59, 59, tzinfo=tz_local)
                    sales_msg = self.assistant.get_date_range_sales_summary(start_dt, end_dt)
                    bi_header = (
                        f"📅 <b>REPORTE QUINCENAL — Vonne Boutique</b>\n"
                        f"🗓️ <i>{periodo_label} {anio}</i>\n\n"
                    )
                    full_msg = bi_header + sales_msg
                    if send_telegram(bot_token, chat_id, full_msg):
                        self.state["last_biweekly_report"] = today_str
                        save_json(STATE_PATH, self.state)
                        print(f"📅 Reporte quincenal enviado ({periodo_label}).")
                except Exception as e:
                    print(f"[ERROR] Reporte quincenal: {e}")

    def run_cycle(self):
        self.tg_cfg = get_telegram_config()
        self.check_receipts()
        self.check_shifts()
        self.check_inventory_alerts()
        self.check_scheduled_reports()


def send_test_message():
    tg_cfg = get_telegram_config()
    bot_token = tg_cfg.get("bot_token")
    chat_id = tg_cfg.get("chat_id")

    if not bot_token or not chat_id or "TU_BOT_TOKEN" in str(bot_token):
        print("\n❌ Error: Aún no has configurado el bot_token o chat_id en telegram_config.json.")
        return False

    msg = (
        f"🤖 <b>¡Conexión Exitosa con Vonne Boutique!</b>\n\n"
        f"Este bot de Telegram está activo y configurado.\n\n"
        f"💡 <b>Prueba escribir en el chat:</b>\n"
        f"• <code>/ventas</code> para ver el corte al momento\n"
        f"• <code>/prendas</code> para ver prendas vendidas\n"
        f"• <code>/caja</code> para revisar la caja\n"
        f"• <code>/ayuda</code> para ver todos los comandos\n\n"
        f"📍 <i>Plaza La Fragua, Saltillo, Coahuila</i>"
    )
    print("Enviando mensaje de prueba a Telegram...")
    ok = send_telegram(bot_token, chat_id, msg)
    if ok:
        print("✅ ¡Mensaje de prueba enviado exitosamente a tu Telegram!")
    else:
        print("❌ No se pudo enviar el mensaje. Verifica el token y el chat_id.")
    return ok

def run_daemon():
    print("==================================================")
    print("  Vonne Boutique - Notificador y Bot Interactivo  ")
    print("==================================================")
    print("1. Notificaciones automáticas cada 30 segundos.")
    print("2. Respuestas interactivas a comandos cada 3 segundos (/ventas, /caja, etc).")
    print("Presiona Ctrl + C para detener.\n")

    start_health_server()

    notifier = LoyverseTelegramNotifier()
    loy_interval = notifier.tg_cfg.get("check_interval_seconds", 30)
    cmd_interval = notifier.tg_cfg.get("command_check_interval_seconds", 3)

    # ── Notificación de reinicio ───────────────────────────────────────────
    try:
        offset    = notifier.tg_cfg.get("timezone_offset_hours", -6)
        tz_local  = timezone(timedelta(hours=offset))
        now_local = datetime.now(tz_local)
        hora_str  = now_local.strftime("%I:%M %p")
        fecha_str = now_local.strftime("%d/%m/%Y")
        restart_msg = (
            f"🔄 <b>BOT REINICIADO — Vonne Boutique</b>\n\n"
            f"✅ El notificador de Telegram volvió a estar activo.\n"
            f"🕐 <b>Hora de reinicio:</b> {hora_str}\n"
            f"📅 <b>Fecha:</b> {fecha_str}\n\n"
            f"<i>Las notificaciones de ventas, caja y alertas continúan funcionando con normalidad.</i>\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )
        bot_token = notifier.tg_cfg.get("bot_token")
        chat_id   = notifier.tg_cfg.get("chat_id")
        send_telegram(bot_token, chat_id, restart_msg)
        print(f"🔄 Notificación de reinicio enviada a las {hora_str}")
    except Exception as e:
        print(f"[AVISO] No se pudo enviar notificación de reinicio: {e}")

    last_loy_check = 0


    while True:
        try:
            now = time.time()
            # 1. Comandos de chat interactivos (rápido)
            notifier.process_telegram_commands()

            # 2. Monitoreo de Loyverse (cada 30s)
            if now - last_loy_check >= loy_interval:
                notifier.run_cycle()
                last_loy_check = now

        except KeyboardInterrupt:
            print("\nDeteniendo monitor de Telegram. ¡Hasta pronto!")
            break
        except Exception as e:
            print(f"[ERROR] Error inesperado en ciclo: {e}")

        time.sleep(cmd_interval)

def run_once():
    notifier = LoyverseTelegramNotifier()
    notifier.run_cycle()
    print("Ciclo único completado.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "--test":
            send_test_message()
        elif cmd == "--once":
            run_once()
        elif cmd == "--daemon":
            run_daemon()
        else:
            print("Uso: python telegram_notifier.py [--test | --once | --daemon]")
    else:
        run_daemon()
