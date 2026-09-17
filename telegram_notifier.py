#!/usr/bin/env python3
"""
Vonne Boutique Saltillo - Notificador Oficial de Loyverse POS en Telegram
Monitorea eventos de caja y ventas en tiempo real:
1. Nuevas Ventas / Tickets generados (prendas, precios, total, forma de pago)
2. Cancelaciones / Reembolsos de tickets
3. Apertura de caja (inicio de turno con fondo de caja)
4. Cierre de caja (corte del día / Z-report con ventas brutas, netas, desglose de pagos y diferencia de efectivo)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Soporte completo para pythonw (segundo plano sin consola) y consola Windows
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
        "User-Agent": "VonneBoutiqueTelegramNotifier/1.0"
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

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

    all_ok = True
    for target in targets:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": target,
            "text": text,
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

class LoyverseTelegramNotifier:
    def __init__(self):
        self.loy_token = get_loyverse_token()
        self.tg_cfg = load_json(TELEGRAM_CONFIG_PATH)
        self.state = load_json(STATE_PATH, {
            "processed_receipt_ids": [],
            "processed_shift_ids": [],
            "known_open_shift_id": None,
            "last_receipt_time": None
        })
        self.employees_cache = {}
        self.payment_types_cache = {}
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

        # Si es la primera vez que se ejecuta y no hay historial guardado, sincronizamos sin disparar notificaciones masivas
        if not self.state.get("last_receipt_time") and receipts:
            for r in receipts:
                new_processed.append(r["receipt_number"])
            self.state["processed_receipt_ids"] = new_processed[-50:]
            self.state["last_receipt_time"] = receipts[0].get("created_at")
            save_json(STATE_PATH, self.state)
            print(f"ℹ️ Estado de recibos inicializado con {len(receipts)} tickets existentes.")
            return

        # Procesar del más antiguo al más reciente
        for r in reversed(receipts):
            r_num = r.get("receipt_number")
            r_type = r.get("receipt_type")  # SALE o REFUND
            cancelled_at = r.get("cancelled_at")

            event_id = f"{r_num}_{r_type}_{'cancelled' if cancelled_at else 'ok'}"
            if event_id in processed:
                continue

            emp_name = self.employees_cache.get(r.get("employee_id"), "Vonne Boutique")
            total = r.get("total_money", 0.0)
            receipt_time = format_iso_time(r.get("created_at") or r.get("receipt_date"), offset)

            # Caso 1: Cancelación / Devolución
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

        # Inicialización de primer arranque
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

            # Caso 1: Apertura de caja nueva
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

            # Caso 2: Cierre de caja (Corte del día)
            else:
                if shift_id not in processed_shifts:
                    processed_shifts.add(shift_id)
                    if self.state.get("known_open_shift_id") == shift_id:
                        self.state["known_open_shift_id"] = None
                    self.state["processed_shift_ids"] = list(processed_shifts)[-30:]
                    save_json(STATE_PATH, self.state)

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

                        # Desglose de pagos por método
                        payments_summary = s.get("payments", [])
                        pay_lines = []
                        for pm in payments_summary:
                            pm_name = pm.get("payment_type_name") or self.payment_types_cache.get(pm.get("payment_type_id"), "Otro")
                            pm_amount = pm.get("total_money", 0.0)
                            pay_lines.append(f"• <b>{pm_name}:</b> {format_money(pm_amount)}")
                        payments_block = "\n".join(pay_lines) if pay_lines else f"• <b>Efectivo:</b> {format_money(cash_payments)}"

                        # Indicador de diferencia
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
                        if send_telegram(bot_token, chat_id, msg):
                            print(f"🔔 Notificación de corte de caja enviada: {close_time_str}")

    def run_cycle(self):
        # Recargar configuración por si el usuario actualizó tokens
        self.tg_cfg = load_json(TELEGRAM_CONFIG_PATH)
        self.check_receipts()
        self.check_shifts()

def send_test_message():
    tg_cfg = load_json(TELEGRAM_CONFIG_PATH)
    bot_token = tg_cfg.get("bot_token")
    chat_id = tg_cfg.get("chat_id")

    if not bot_token or not chat_id or "TU_BOT_TOKEN" in str(bot_token):
        print("\n❌ Error: Aún no has configurado el bot_token o chat_id en telegram_config.json.")
        print("Edita el archivo telegram_config.json con tus credenciales de Telegram.")
        return False

    msg = (
        f"🤖 <b>¡Conexión Exitosa con Vonne Boutique!</b>\n\n"
        f"Este bot de Telegram está configurado para avisarte al instante cuando:\n"
        f"• 🛍️ Se registre una nueva venta\n"
        f"• 🚨 Se cancele o devuelva un ticket\n"
        f"• 🔓 Se abra la caja con su fondo inicial\n"
        f"• 🔒 Se cierre la caja con el corte del día (Z-Report)\n\n"
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
    print("  Vonne Boutique - Notificador de Loyverse POS   ")
    print("==================================================")
    print("Monitoreando ventas y movimientos de caja cada 60s...")
    print("Presiona Ctrl + C para detener en cualquier momento.\n")

    notifier = LoyverseTelegramNotifier()
    interval = notifier.tg_cfg.get("check_interval_seconds", notifier.tg_cfg.get("poll_interval_seconds", 30))

    while True:
        try:
            notifier.run_cycle()
        except KeyboardInterrupt:
            print("\nDeteniendo monitor de Telegram. ¡Hasta pronto!")
            break
        except Exception as e:
            print(f"[ERROR] Error inesperado en ciclo: {e}")
        time.sleep(interval)

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
