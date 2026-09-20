import urllib.request
import urllib.parse
import json
import os
import datetime
from collections import defaultdict

def generate_correlation_report():
    # 1. Credentials
    loyverse_token = 'd746792798aa4c43888f0aa01b6351b1'

    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_envs = [
        os.path.join(base_dir, ".env"),
        r"C:\Users\PC3\.gemini\antigravity\scratch\vonne-marketing-agent\.env",
        r"C:\Users\PC3\Documents\Antigravity\Vonne boutique\Facebook_AI_Comentarios\.env"
    ]
    env_vars = {}
    for ep in possible_envs:
        if os.path.exists(ep):
            try:
                with open(ep, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            k, v = line.split('=', 1)
                            if k.strip() not in env_vars:
                                env_vars[k.strip()] = v.strip()
            except Exception:
                pass

    DEFAULT_META_TOKEN = "EAANTUKGLuYgBSq7ItWHZBgSnHCAz7RIDC40XeiQZCpf6hHlieGCkEdtzcADskzmnrtg9cGdz53n7zRhGx7tmXnkpKzusCrDVAyuZAXzCq2xKm1f2iYDlhNbhPpXfq4NQiMBC4vMa2BkI0rpiU579ZAfXoMywqT5Iiu7QtIAdJARnA2jTN7o9qZBTMPjuG8T3soKZB0LW30sFu0ewZDZD"
    DEFAULT_AD_ACCOUNT = "act_137220572"

    meta_token = os.environ.get('META_ACCESS_TOKEN') or env_vars.get('META_ACCESS_TOKEN') or DEFAULT_META_TOKEN
    account_id = os.environ.get('AD_ACCOUNT_ID') or env_vars.get('AD_ACCOUNT_ID') or DEFAULT_AD_ACCOUNT

    # 2. Fechas para corte de hoy (UTC-6)
    today_dt = datetime.date.today()
    today_str = today_dt.strftime("%Y-%m-%d")
    
    # 3. Recibos de Loyverse POS de hoy
    # Para asegurar capturar desde las 00:00 UTC-6 (06:00 UTC)
    start_utc = f"{today_str}T06:00:00Z"
    url_loy = f"https://api.loyverse.com/v1.0/receipts?created_at_min={start_utc}&limit=250"
    req_loy = urllib.request.Request(url_loy, headers={"Authorization": f"Bearer {loyverse_token}"})
    try:
        with urllib.request.urlopen(req_loy, timeout=15) as resp:
            loy_data = json.loads(resp.read().decode("utf-8"))
            receipts = loy_data.get("receipts", [])
    except Exception as e:
        receipts = []
        print(f"Error consultando Loyverse: {e}")

    # 4. Métricas de Meta Ads de hoy
    fields = "campaign_name,spend,impressions,clicks,cpc,ctr,actions,cost_per_action_type"
    meta_url = f"https://graph.facebook.com/v20.0/{account_id}/insights?level=campaign&date_preset=today&fields={fields}&access_token={meta_token}&limit=100"
    try:
        req_meta = urllib.request.Request(meta_url)
        with urllib.request.urlopen(req_meta, timeout=15) as resp:
            meta_camps = json.loads(resp.read().decode("utf-8")).get("data", [])
    except Exception as e:
        meta_camps = []
        print(f"Error consultando Meta Campañas: {e}")

    # Métricas de anuncios específicos hoy
    ad_fields = "ad_name,campaign_name,spend,actions,cost_per_action_type"
    meta_ads_url = f"https://graph.facebook.com/v20.0/{account_id}/insights?level=ad&date_preset=today&fields={ad_fields}&access_token={meta_token}&limit=100"
    try:
        req_meta_ads = urllib.request.Request(meta_ads_url)
        with urllib.request.urlopen(req_meta_ads, timeout=15) as resp:
            meta_ads = json.loads(resp.read().decode("utf-8")).get("data", [])
    except Exception as e:
        meta_ads = []
        print(f"Error consultando Meta Anuncios: {e}")

    # 5. Clasificación de ventas POS
    def classify_item(name):
        n = (name or "").lower()
        if "blazer" in n:
            return "PUBLICIDAD_BLAZER", "Blazers"
        elif "faja" in n or "body" in n or "moldeador" in n:
            return "PUBLICIDAD_FAJA", "Fajas y Bodies"
        elif "vinil" in n or "vinipiel" in n:
            if "short" in n:
                return "PUBLICIDAD_SHORT_VINIL", "Shorts de Vinil"
            else:
                return "PUBLICIDAD_PANTALON_VINIL", "Pantalones de Vinil"
        elif "playera" in n and any(k in n for k in ["patria", "mex", "15", "16", "sept"]):
            return "PUBLICIDAD_PLAYERA", "Playeras Patrias"
        else:
            return "ORGANICO", "Orgánico / Tienda"

    pos_total = 0.0
    pos_qty = 0
    pos_ad = 0.0
    pos_ad_qty = 0
    pos_org = 0.0
    pos_org_qty = 0
    cat_sales = defaultdict(lambda: {"money": 0.0, "qty": 0})

    for r in receipts:
        if r.get("cancelled_at"):
            continue
        r_type = r.get("receipt_type", "SALE")
        mult = 1 if r_type == "SALE" else -1
        
        # Local date check
        created_at = r.get("created_at", "")
        if created_at:
            dt = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            local_dt = dt - datetime.timedelta(hours=6)
            if local_dt.strftime("%Y-%m-%d") != today_str:
                continue

        for li in r.get("line_items", []):
            iname = li.get("item_name") or "Prenda sin nombre"
            qty = float(li.get("quantity", 1)) * mult
            money = float(li.get("gross_total_money", 0)) * mult

            cat_type, cat_group = classify_item(iname)
            is_ad = cat_type.startswith("PUBLICIDAD")

            pos_total += money
            pos_qty += qty
            cat_sales[cat_group]["money"] += money
            cat_sales[cat_group]["qty"] += qty

            if is_ad:
                pos_ad += money
                pos_ad_qty += qty
            else:
                pos_org += money
                pos_org_qty += qty

    # 6. Métricas de Meta Ads
    tot_spend = 0.0
    tot_msgs = 0
    for c in meta_camps:
        sp = float(c.get("spend", 0))
        tot_spend += sp
        actions = {a["action_type"]: int(a["value"]) for a in c.get("actions", [])}
        msgs = actions.get("onsite_conversion.messaging_conversation_started_7d", 0)
        tot_msgs += msgs

    ad_pct = (pos_ad / pos_total * 100) if pos_total > 0 else 0
    org_pct = (pos_org / pos_total * 100) if pos_total > 0 else 0
    roas_direct = (pos_ad / tot_spend) if tot_spend > 0 else 0
    mer_global = (pos_total / tot_spend) if tot_spend > 0 else 0
    cpa_avg = (tot_spend / tot_msgs) if tot_msgs > 0 else 0

    # 7. Diagnóstico de anuncios para ajustes
    expensive_ads = []
    star_ads = []
    for a in meta_ads:
        sp = float(a.get("spend", 0))
        if sp < 10:
            continue
        actions = {item["action_type"]: int(item["value"]) for item in a.get("actions", [])}
        msgs = actions.get("onsite_conversion.messaging_conversation_started_7d", 0)
        cpa = (sp / msgs) if msgs > 0 else 0
        name = a.get("ad_name", "Anuncio")
        
        if cpa > 18 or (sp > 40 and msgs == 0):
            expensive_ads.append(f"• 🔴 <b>{name}</b>: Gastó ${sp:.2f} con CPA de ${cpa:.2f}")
        elif cpa > 0 and cpa < 7:
            star_ads.append(f"• 🟢 <b>{name}</b>: {msgs} msgs (CPA: ${cpa:.2f})")

    now_fmt = datetime.datetime.now().strftime("%d/%m/%Y | %I:%M %p")

    # 8. Construcción del mensaje HTML
    msg = (
        f"⚖️ <b>REPORTE NOCTURNO: PUBLICIDAD VS. CAJA (POS)</b>\n"
        f"📅 <i>Fecha: {now_fmt}</i>\n\n"
        f"💵 <b>Facturación en Caja Hoy:</b> ${pos_total:,.2f} MXN ({pos_qty:.0f} prendas)\n"
        f"  🎯 <b>De Publicidad:</b> ${pos_ad:,.2f} MXN ({pos_ad_qty:.0f} pzs) ➔ <b>{ad_pct:.1f}%</b>\n"
        f"  🟢 <b>Venta Orgánica:</b> ${pos_org:,.2f} MXN ({pos_org_qty:.0f} pzs) ➔ <b>{org_pct:.1f}%</b>\n\n"
        f"📊 <b>Inversión en Meta Ads Hoy:</b>\n"
        f"• Gasto Total: <b>${tot_spend:,.2f} MXN</b>\n"
        f"• Mensajes Recibidos: <b>{tot_msgs} prospectos</b>\n"
        f"• Costo Promedio (CPA): <b>${cpa_avg:.2f} MXN / lead</b>\n\n"
        f"📈 <b>Retorno de Inversión (ROAS):</b>\n"
        f"• <b>ROAS Directo Pauta:</b> <b>{roas_direct:.2f}x</b>\n"
        f"  <i>(Por cada $1 en ads entraron ${roas_direct:.2f} en prendas anunciadas)</i>\n"
        f"• <b>MER Global Tienda:</b> <b>{mer_global:.2f}x</b>\n\n"
        f"🛍️ <b>Prendas Pautadas Vendidas Hoy en POS:</b>\n"
    )

    ad_categories = ["Blazers", "Fajas y Bodies", "Shorts de Vinil", "Pantalones de Vinil", "Playeras Patrias"]
    has_pautadas = False
    for cat in ad_categories:
        if cat in cat_sales and cat_sales[cat]["money"] > 0:
            has_pautadas = True
            msg += f"• <b>{cat}:</b> ${cat_sales[cat]['money']:,.2f} MXN ({cat_sales[cat]['qty']:.0f} pzs)\n"
    if not has_pautadas:
        msg += "• <i>Sin ventas registradas de prendas pautadas en este corte.</i>\n"

    msg += "\n🛠️ <b>Ajustes Recomendados para Mañana:</b>\n"
    if star_ads:
        msg += "<b>Potenciar / Escalar Presupuesto:</b>\n" + "\n".join(star_ads[:3]) + "\n"
    if expensive_ads:
        msg += "<b>Pausar / Apagar para evitar fugas:</b>\n" + "\n".join(expensive_ads[:3]) + "\n"
    if not expensive_ads and not star_ads:
        msg += "• Mantener la distribución actual. El CPA promedio es estable.\n"

    msg += "\n📍 <i>Vonne Boutique Saltillo • Plaza La Fragua</i>"
    return msg

def send_correlation_summary():
    tg_cfg_path = r'C:\Users\PC3\Documents\Antigravity\Vonne boutique\sitio_web_github\telegram_config.json'
    with open(tg_cfg_path, encoding='utf-8') as f:
        tg_cfg = json.load(f)

    bot_token = tg_cfg.get('bot_token')
    chat_id = tg_cfg.get('chat_id')

    msg = generate_correlation_report()

    tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML"
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req_tg = urllib.request.Request(tg_url, data=data)
    with urllib.request.urlopen(req_tg, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("TELEGRAM_SEND_CORRELATION_RESULT:", res.get("ok"))
        return res.get("ok")

if __name__ == "__main__":
    send_correlation_summary()
