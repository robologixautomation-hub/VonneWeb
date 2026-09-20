import urllib.request
import urllib.parse
import json
import os
import datetime

def get_ads_summary_msg():
    # 1. Load Meta credentials
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

    meta_token = os.environ.get('META_ACCESS_TOKEN') or env_vars.get('META_ACCESS_TOKEN', '')
    account_id = os.environ.get('AD_ACCOUNT_ID') or env_vars.get('AD_ACCOUNT_ID', 'act_137220572')

    if not meta_token:
        return (
            f"🎯 <b>REPORTE DE META ADS — Vonne Boutique</b>\n\n"
            f"⚠️ <i>No hay token de Meta Ads configurado actualmente.</i>\n"
            f"💡 Configura <code>META_ACCESS_TOKEN</code> y <code>AD_ACCOUNT_ID</code> para habilitar reportes de campañas en vivo.\n\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    # 2. Query Meta Insights for today
    fields = 'campaign_id,campaign_name,spend,impressions,reach,clicks,cpc,cpm,ctr,actions,cost_per_action_type'
    url = f'https://graph.facebook.com/v20.0/{account_id}/insights?level=campaign&date_preset=today&fields={fields}&access_token={meta_token}&limit=100'

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            camp_data = json.loads(resp.read().decode()).get('data', [])

        ad_fields = 'ad_id,ad_name,campaign_name,spend,impressions,reach,clicks,cpc,cpm,ctr,actions,cost_per_action_type'
        url_ads = f'https://graph.facebook.com/v20.0/{account_id}/insights?level=ad&date_preset=today&fields={ad_fields}&access_token={meta_token}&limit=100'
        req_ads = urllib.request.Request(url_ads)
        with urllib.request.urlopen(req_ads, timeout=15) as resp:
            ad_data = json.loads(resp.read().decode()).get('data', [])
    except Exception as e:
        return (
            f"🎯 <b>REPORTE DE META ADS — Vonne Boutique</b>\n\n"
            f"ℹ️ <i>No se pudieron obtener métricas de campañas de Meta Ads en este momento ({e}).</i>\n\n"
            f"📍 <i>Plaza La Fragua, Saltillo</i>"
        )

    # 3. Compute Totals & Ranking
    tot_spend = 0.0
    tot_msgs = 0
    campaign_lines = []

    for c in sorted(camp_data, key=lambda x: float(x.get('spend', 0)), reverse=True):
        sp = float(c.get('spend', 0))
        tot_spend += sp
        actions = {a['action_type']: int(a['value']) for a in c.get('actions', [])}
        msgs = actions.get('onsite_conversion.messaging_conversation_started_7d', 0)
        tot_msgs += msgs
        cpa = (sp / msgs) if msgs > 0 else 0
        c_name = c.get('campaign_name', 'Campaña')
        
        if sp > 0:
            campaign_lines.append(f"• <b>{c_name}</b>: ${sp:.2f} MXN | 💬 {msgs} msgs (CPA: ${cpa:.2f})")

    avg_cpa = (tot_spend / tot_msgs) if tot_msgs > 0 else 0

    processed_ads = []
    for a in ad_data:
        sp = float(a.get('spend', 0))
        if sp <= 0:
            continue
        actions = {item['action_type']: int(item['value']) for item in a.get('actions', [])}
        msgs = actions.get('onsite_conversion.messaging_conversation_started_7d', 0)
        cpa = (sp / msgs) if msgs > 0 else 0
        ctr = float(a.get('ctr', 0))
        processed_ads.append({
            'name': a.get('ad_name'),
            'campaign': a.get('campaign_name'),
            'spend': sp,
            'msgs': msgs,
            'cpa': cpa,
            'ctr': ctr
        })

    processed_ads.sort(key=lambda x: x['msgs'], reverse=True)

    now_str = datetime.datetime.now().strftime("%d/%m/%Y | %I:%M %p")

    msg = (
        f"📊 <b>REPORTE DE META ADS • VONNE BOUTIQUE</b>\n"
        f"📅 <i>Corte: {now_str}</i>\n\n"
        f"💰 <b>Gasto Total Hoy:</b> ${tot_spend:,.2f} MXN\n"
        f"💬 <b>Mensajes Recibidos:</b> {tot_msgs} prospectos\n"
        f"🎯 <b>CPA Promedio:</b> ${avg_cpa:.2f} MXN / mensaje\n\n"
        f"🏆 <b>Top Anuncios Ganadores Hoy:</b>\n"
    )

    medals = ["🥇", "🥈", "🥉", "🔹", "🔹"]
    for i, ad in enumerate(processed_ads[:5]):
        medal = medals[i] if i < len(medals) else "•"
        msg += f"{medal} <b>{ad['name']}</b>: <b>{ad['msgs']} msgs</b> (${ad['spend']:.2f} | CPA: ${ad['cpa']:.2f})\n"

    msg += f"\n📁 <b>Resumen por Campaña:</b>\n"
    msg += "\n".join(campaign_lines) if campaign_lines else "<i>No se registraron campañas con gasto hoy.</i>"

    # Alertas inteligentes
    msg += f"\n\n💡 <b>Diagnóstico / Alertas:</b>\n"
    if processed_ads:
        top = processed_ads[0]
        msg += f"• 🌟 Anuncio líder: <b>{top['name']}</b> con {top['msgs']} mensajes (CPA: ${top['cpa']:.2f}).\n"
    
    # Revisar si hay anuncios caros
    expensive = [a for a in processed_ads if a['cpa'] > 18 and a['spend'] > 50]
    if expensive:
        names = ", ".join(a['name'] for a in expensive)
        msg += f"• ⚠️ Alerta de CPA alto en: <i>{names}</i>. Se sugiere pausar para optimizar presupuesto.\n"
    else:
        msg += f"• ✅ El rendimiento de CPA general se mantiene saludable.\n"

    return msg

def send_summary():
    tg_cfg_path = r'C:\Users\PC3\Documents\Antigravity\Vonne boutique\sitio_web_github\telegram_config.json'
    with open(tg_cfg_path, encoding='utf-8') as f:
        tg_cfg = json.load(f)

    bot_token = tg_cfg.get('bot_token')
    chat_id = tg_cfg.get('chat_id')

    msg = get_ads_summary_msg()

    tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML"
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req_tg = urllib.request.Request(tg_url, data=data)
    with urllib.request.urlopen(req_tg, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("TELEGRAM_SEND_RESULT:", res.get("ok"))
        return res.get("ok")

if __name__ == "__main__":
    send_summary()
