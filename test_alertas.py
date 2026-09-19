#!/usr/bin/env python3
"""
Test de notificaciones nuevas — Vonne Boutique
Envía un ejemplo de cada alerta con 30s de diferencia.
"""
import sys, time, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_notifier import send_telegram, load_json, format_money, TELEGRAM_CONFIG_PATH
from loyverse_assistant import LoyverseAssistant
from datetime import datetime, timezone, timedelta

tg  = load_json(TELEGRAM_CONFIG_PATH)
bot = tg["bot_token"]
cid = tg["chat_id"]
offset = tg.get("timezone_offset_hours", -6)
tz = timezone(timedelta(hours=offset))
now = datetime.now(tz)
today_str = now.strftime("%d/%m/%Y")

loy_cfg = load_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), "loyverse_config.json"))
asst = LoyverseAssistant(loy_cfg["token"], tg)

alerts = []

# ── 1. Prenda agotada ──────────────────────────────────────────────────────
alerts.append((
    "🚨 PRENDA AGOTADA",
    (
        f"🚨 <b>¡PRENDA AGOTADA!</b>\n\n"
        f"👗 <b>Blazer Negro Talla M</b>\n"
        f"📦 <b>Stock:</b> 0 piezas\n"
        f"⚠️ <i>Ya no hay existencias disponibles para venta.</i>\n"
        f"📍 <i>Plaza La Fragua, Saltillo</i>"
    )
))

# ── 2. Stock bajo (reporte diario 12pm) ────────────────────────────────────
def get_low_stock_msg():
    try:
        from telegram_notifier import loyverse_api_get
        inv_data = loyverse_api_get("inventory?limit=250", loy_cfg["token"])
        items = inv_data.get("inventory_levels", [])
        low_items = [
            (item.get("item_name") or item.get("variant_name") or "Prenda",
             int(item.get("in_stock", 0) or 0))
            for item in items
            if 0 < (item.get("in_stock", 0) or 0) < 3
        ]
        low_items.sort(key=lambda x: x[1])
        if not low_items:
            return None, "✅ Todas las prendas tienen stock >= 3 (no hay stock bajo real aún)."
        lines = "\n".join(
            f"• <b>{name}</b> — {qty} {'pieza' if qty == 1 else 'piezas'}"
            for name, qty in low_items[:20]
        )
        return (
            f"⚠️ <b>REPORTE DE STOCK BAJO — Vonne Boutique</b>\n"
            f"📅 <i>{today_str}</i>\n\n"
            f"Las siguientes prendas tienen <b>menos de 3 piezas</b>:\n\n"
            f"{lines}\n\n"
            f"🛒 <i>Considera reabastecer antes de que se agoten.</i>\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        ), None
    except Exception as e:
        return None, f"Error: {e}"

low_msg, low_info = get_low_stock_msg()
if low_msg:
    alerts.append(("⚠️ STOCK BAJO (12pm)", low_msg))
else:
    print(f"ℹ️ Stock bajo: {low_info}")
    alerts.append((
        "⚠️ STOCK BAJO (12pm) — EJEMPLO",
        (
            f"⚠️ <b>REPORTE DE STOCK BAJO — Vonne Boutique</b>\n"
            f"📅 <i>{today_str}</i>\n\n"
            f"Las siguientes prendas tienen <b>menos de 3 piezas</b>:\n\n"
            f"• <b>Blazer Café Talla S</b> — 1 pieza\n"
            f"• <b>Vestido Verde Botella</b> — 2 piezas\n"
            f"• <b>Pantalón Beige Talla M</b> — 2 piezas\n\n"
            f"🛒 <i>Considera reabastecer antes de que se agoten.</i>\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )
    ))

# ── 3. Primera venta del día ───────────────────────────────────────────────
alerts.append((
    "🎀 PRIMERA VENTA DEL DÍA",
    (
        f"🎀 <b>¡PRIMERA VENTA DEL DÍA! — Vonne Boutique</b>\n\n"
        f"📄 <b>Ticket:</b> <code>#4021</code>\n"
        f"👤 <b>Atendió:</b> Karla\n"
        f"💰 <b>Total:</b> <b>$750.00 MXN</b>\n"
        f"🕐 <b>Hora:</b> 12:15 PM\n\n"
        f"✨ <i>¡A vender mucho hoy!</i>\n"
        f"📍 <i>Plaza La Fragua, Saltillo</i>"
    )
))

# ── 4. Descuento grande ────────────────────────────────────────────────────
alerts.append((
    "🏷️ DESCUENTO GRANDE",
    (
        f"🏷️ <b>DESCUENTO GRANDE APLICADO</b>\n\n"
        f"📄 <b>Ticket:</b> <code>#4022</code>\n"
        f"👤 <b>Atendió:</b> Karla\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 <b>Descuento:</b> -$300.00 MXN (40%)\n"
        f"💰 <b>Total cobrado:</b> $450.00 MXN\n"
        f"🕐 <b>Hora:</b> 01:30 PM\n"
        f"📍 <i>Plaza La Fragua, Saltillo</i>"
    )
))

# ── 5. Acumulado del día (2pm/4pm/6pm) ────────────────────────────────────
try:
    stats = asst.get_day_sales_summary()
    acc_msg = asst.format_sales_summary_msg(stats, title="⏰ ACUMULADO DEL DÍA — 02:00 PM")
    alerts.append(("⏰ ACUMULADO DEL DÍA (ej. 2pm)", acc_msg))
except Exception as e:
    alerts.append(("⏰ ACUMULADO DEL DÍA", f"Error generando acumulado: {e}"))

# ── 6. Resumen semanal (sábado 9pm) ───────────────────────────────────────
try:
    from datetime import date
    start_week = now - timedelta(days=5)
    start_dt = datetime(start_week.year, start_week.month, start_week.day, 0, 0, 0, tzinfo=tz)
    end_dt   = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=tz)
    weekly_body = asst.get_date_range_sales_summary(start_dt, end_dt)
    weekly_msg = (
        f"📊 <b>RESUMEN SEMANAL — Vonne Boutique</b>\n"
        f"📅 <i>Lunes {start_dt.strftime('%d/%m')} al Sábado {now.strftime('%d/%m/%Y')}</i>\n\n"
    ) + weekly_body
    alerts.append(("📊 RESUMEN SEMANAL (sábados 9pm)", weekly_msg))
except Exception as e:
    alerts.append(("📊 RESUMEN SEMANAL", f"Error: {e}"))

# ── 7. Reporte quincenal ───────────────────────────────────────────────────
try:
    import calendar as _cal
    _, last_day = _cal.monthrange(now.year, now.month)
    start_dt = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=tz)
    end_dt   = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=tz)
    bi_body  = asst.get_date_range_sales_summary(start_dt, end_dt)
    MONTHS_ES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                 7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
    periodo = f"1 al {now.day} de {MONTHS_ES.get(now.month,'')} (previa al quincenal)"
    bi_msg  = (
        f"📅 <b>REPORTE QUINCENAL — Vonne Boutique</b>\n"
        f"🗓️ <i>{periodo} {now.year}</i>\n\n"
    ) + bi_body
    alerts.append(("📅 REPORTE QUINCENAL (día 15 y último del mes)", bi_msg))
except Exception as e:
    alerts.append(("📅 REPORTE QUINCENAL", f"Error: {e}"))

# ── Enviar con 30s de diferencia ──────────────────────────────────────────
total = len(alerts)
print(f"\n🚀 Enviando {total} notificaciones de prueba (30s entre cada una)...\n")

for i, (label, msg) in enumerate(alerts, 1):
    print(f"[{i}/{total}] Enviando: {label}...", end=" ", flush=True)
    ok = send_telegram(bot, cid, msg)
    print("✅ OK" if ok else "❌ FALLÓ")
    if i < total:
        print(f"   ⏳ Esperando 30 segundos...\n")
        time.sleep(30)

print(f"\n✅ ¡Listo! Se enviaron {total} notificaciones de prueba a Telegram.")
