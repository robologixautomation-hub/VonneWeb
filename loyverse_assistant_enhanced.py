#!/usr/bin/env python3
"""
Vonne Boutique - Asistente Inteligente POS v2.4
ARQUITECTURA NUEVA: Clasificación Semántica de Intenciones con Gemini
(Abandona palabras clave literales → interpreta variaciones, sinónimos, modismos)

REGLAS DE INTERPRETACIÓN:
1. NO usar listas de palabras clave exactas
2. Usar Gemini para clasificar intención del usuario semánticamente
3. Interpretar variaciones sin importar orden o modismo
4. Devolver intención + confianza + extracción de atributos (prenda, talla, color, período)
"""

import re
import unicodedata
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict

MONTHS_NAME_TO_NUM = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "sept": 9, "sep": 9, "setiembre": 9,
    "octubre": 10, "oct": 10, "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12
}

MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

SIZES = ["CH", "M", "G", "XL", "XXL"]
COLORS = ["rojo", "azul", "negro", "blanco", "rosa", "verde", "amarillo", "gris", "beige", "lila", "morado"]

def normalize_text(text):
    """Normaliza texto para comparación"""
    if not text:
        return ""
    t = text.lower()
    t = unicodedata.normalize('NFD', t)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return t.strip()


class SemanticIntentClassifier:
    """
    Clasificador semántico de intenciones usando Gemini.
    NO depende de palabras clave exactas → interpreta variaciones.
    """
    
    def __init__(self, gemini_api_key=None):
        self.gemini_api_key = gemini_api_key
        self.tz = timezone(timedelta(hours=-6))
    
    def classify_with_gemini(self, user_text):
        """
        Llama a Gemini para clasificar la intención de forma semántica.
        
        Retorna: {
            "intent": str,  # consultar_stock_critico, consultar_ventas, etc.
            "confidence": float,  # 0.0 - 1.0
            "extracted": {  # atributos extraídos
                "prenda": str,
                "talla": str,
                "color": str,
                "periodo": str,
                "fecha_inicio": datetime,
                "fecha_fin": datetime
            }
        }
        """
        
        if not self.gemini_api_key:
            return self._classify_fallback(user_text)
        
        import urllib.request
        
        prompt = f"""
ERES UN CLASIFICADOR SEMÁNTICO DE INTENCIONES PARA UN POS DE BOUTIQUE.

Tu trabajo: Interpretar la INTENCIÓN del usuario SIN depender de palabras clave literales.
Interpreta variaciones, sinónimos, modismos y parafraseos.

CATEGORÍAS DE INTENCIÓN:
1. "consultar_stock_critico" - Prendas con poco stock (< 3 pzas) o por agotarse
   Variaciones: "stock bajo", "bajo stock", "qué se está acabando", "qué falta resurtir", "prendas por agotarse"

2. "consultar_agotados" - Prendas con 0 stock
   Variaciones: "agotado", "no hay", "en ceros", "se terminó", "qué ya no tengo"

3. "consultar_ventas" - Resumen de ventas (hoy, período, fecha específica)
   Variaciones: "cuánto vendimos hoy", "corte parcial", "cómo va el día", "ingresos", "total vendido", "ventas del..."

4. "consultar_inventario" - Stock disponible de prenda específica
   Variaciones: "cuánto hay de...", "qué tallas hay", "stock de...", "inventario de..."

5. "consultar_costo_margen" - Costo, precio y margen de ganancia
   Variaciones: "cuánto costó", "precio de compra", "cuál es el margen", "ganancia de", "cuánto sacamos"

6. "consultar_top_vendidas" - Ranking de prendas más vendidas
   Variaciones: "top vendidas", "más vendido", "bestseller", "cuáles se venden más", "prendas estrella"

7. "consultar_caja" - Estado de la caja registradora
   Variaciones: "cómo está la caja", "estado de caja", "corte de caja", "efectivo", "fondo"

8. "consultar_ticket" - Detalle de un ticket específico
   Variaciones: "detalle del ticket", "recibo", "factura", "folio"

9. "otra" - Cualquier otra cosa

TAMBIÉN EXTRAE:
- prenda (nombre: "blazer", "vestido", "pantalón", etc.)
- talla (CH, M, G, XL, XXL)
- color (rojo, azul, negro, etc.)
- período (hoy, ayer, semana, mes, o fecha específica)

RESPONDE SOLO EN JSON:
{{
  "intent": "nombre_intención",
  "confidence": 0.95,
  "extracted": {{
    "prenda": "nombre o null",
    "talla": "CH/M/G/XL/XXL o null",
    "color": "color o null",
    "periodo": "hoy/ayer/semana/mes/fecha o null"
  }}
}}

USUARIO DICE: "{user_text}"

RESPUESTA (SOLO JSON, SIN TEXTO EXTRA):
"""
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.gemini_api_key
        }
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2-flash-lite:generateContent"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 200
            }
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                response = json.loads(resp.read().decode("utf-8"))
                
                # Extraer texto de respuesta
                text_response = ""
                for candidate in response.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        if "text" in part:
                            text_response = part["text"].strip()
                
                # Parsear JSON
                try:
                    result = json.loads(text_response)
                    return result
                except json.JSONDecodeError:
                    print(f"[DEBUG] No se pudo parsear respuesta Gemini: {text_response}")
                    return self._classify_fallback(user_text)
        
        except Exception as e:
            print(f"[DEBUG] Error llamando a Gemini: {e}")
            return self._classify_fallback(user_text)
    
    def _classify_fallback(self, user_text):
        """
        Fallback ultra-básico si Gemini no está disponible.
        Usa solo heurísticas mínimas.
        """
        norm = normalize_text(user_text)
        
        if any(w in norm for w in ["agotad", "no hay", "ceros", "termino"]):
            return {"intent": "consultar_agotados", "confidence": 0.7, "extracted": {}}
        elif any(w in norm for w in ["stock", "bajo", "falta resurtir", "acaband"]):
            return {"intent": "consultar_stock_critico", "confidence": 0.7, "extracted": {}}
        elif any(w in norm for w in ["caja", "efectivo", "dinero", "fondo"]):
            return {"intent": "consultar_caja", "confidence": 0.8, "extracted": {}}
        elif any(w in norm for w in ["top", "vendido", "ranking", "bestseller"]):
            return {"intent": "consultar_top_vendidas", "confidence": 0.8, "extracted": {}}
        elif any(w in norm for w in ["campana", "campanas", "anuncio", "anuncios", "publicidad", "pauta", "ads", "meta", "facebook"]):
            return {"intent": "consultar_ads", "confidence": 0.85, "extracted": {}}
        elif any(w in norm for w in ["venta", "vendim", "corte", "ingreso", "total"]):
            return {"intent": "consultar_ventas", "confidence": 0.7, "extracted": {}}
        elif any(w in norm for w in ["costo", "precio", "margen", "ganancia"]):
            return {"intent": "consultar_costo_margen", "confidence": 0.7, "extracted": {}}
        
        return {"intent": "otra", "confidence": 0.3, "extracted": {}}
    
    def extract_date_context(self, user_text):
        """
        Extrae contexto de fecha de la pregunta.
        """
        norm = normalize_text(user_text)
        
        # Períodos predefinidos
        if "hoy" in norm:
            return {"period": "hoy", "type": "predefined"}
        elif "ayer" in norm:
            return {"period": "ayer", "type": "predefined"}
        elif "semana" in norm:
            return {"period": "semana", "type": "predefined"}
        elif "mes" in norm:
            return {"period": "mes", "type": "predefined"}
        
        # Rango de fechas: "del X al Y de mes"
        m_range = re.search(
            r'(?:del|desde)\s+(?:el\s+)?(\d{1,2})(?:\s+de\s+([a-záéíóúñ]+))?.*?(?:al|hasta)\s+(?:el\s+)?(\d{1,2})(?:\s+de\s+([a-záéíóúñ]+))?',
            user_text, re.IGNORECASE
        )
        if m_range:
            d1 = int(m_range.group(1))
            m1_str = m_range.group(2)
            d2 = int(m_range.group(3))
            m2_str = m_range.group(4) or m1_str
            
            m1 = MONTHS_NAME_TO_NUM.get(normalize_text(m1_str))
            m2 = MONTHS_NAME_TO_NUM.get(normalize_text(m2_str))
            
            if m1 and m2:
                now = datetime.now(self.tz)
                try:
                    start = datetime(now.year, m1, d1, tzinfo=self.tz)
                    end = datetime(now.year, m2, d2, 23, 59, 59, tzinfo=self.tz)
                    return {
                        "type": "date_range",
                        "start": start,
                        "end": end,
                        "label": f"Del {d1} al {d2} de {MONTHS_ES.get(m2)}"
                    }
                except ValueError:
                    pass
        
        # Fecha individual: "del 15 de septiembre"
        m_single = re.search(
            r'(?:del|^|del\s+)\s*(\d{1,2})\s+de\s+([a-záéíóúñ]+)',
            user_text, re.IGNORECASE
        )
        if m_single:
            day = int(m_single.group(1))
            month_str = normalize_text(m_single.group(2))
            month = MONTHS_NAME_TO_NUM.get(month_str)
            
            if month:
                now = datetime.now(self.tz)
                try:
                    target = datetime(now.year, month, day, tzinfo=self.tz)
                    return {"type": "single_date", "date": target}
                except ValueError:
                    pass
        
        return {}


def enhanced_answer(assistant, text, chat_id="default"):
    """
    Responde usando clasificación semántica de intenciones v2.4.
    
    Flujo:
    1. Usar Gemini para clasificar intención
    2. Extraer atributos (prenda, talla, color, período)
    3. Ejecutar función correspondiente
    4. Retornar respuesta formateada
    """
    
    classifier = SemanticIntentClassifier(assistant.gemini_api_key)
    
    # Clasificar intención semánticamente
    classification = classifier.classify_with_gemini(text)
    intent = classification.get("intent")
    confidence = classification.get("confidence", 0)
    extracted = classification.get("extracted", {})
    
    print(f"[v2.4] Intención: {intent} (confianza: {confidence:.2f})")
    print(f"[v2.4] Extracción: {extracted}")
    
    # Si confianza muy baja, fallback a Gemini general
    if confidence < 0.5:
        if assistant.gemini_api_key:
            return assistant.ask_gemini(text, chat_id=chat_id)
        return show_help()
    
    # PROCESAMIENTO DE INTENCIONES
    if intent == "consultar_stock_critico":
        return assistant.get_low_stock_report()
    
    elif intent == "consultar_agotados":
        return assistant.get_low_stock_report()
    
    elif intent == "consultar_ventas":
        # Determinar período
        date_context = classifier.extract_date_context(text)
        
        if date_context.get("type") == "date_range":
            return assistant.get_date_range_sales_summary(
                date_context["start"],
                date_context["end"],
                label=date_context.get("label")
            )
        elif date_context.get("type") == "single_date":
            return assistant.format_sales_summary_msg(
                assistant.get_day_sales_summary(date_context["date"]),
                title="RESUMEN DE VENTAS"
            )
        elif date_context.get("period") == "ayer":
            yesterday = datetime.now(classifier.tz) - timedelta(days=1)
            return assistant.format_sales_summary_msg(
                assistant.get_day_sales_summary(yesterday),
                title="VENTAS DE AYER"
            )
        elif date_context.get("period") == "semana":
            return assistant.get_period_sales_summary(7, "ÚLTIMOS 7 DÍAS")
        elif date_context.get("period") == "mes":
            return assistant.get_period_sales_summary(30, "ÚLTIMOS 30 DÍAS")
        else:
            # Por defecto: hoy
            return assistant.format_sales_summary_msg(
                assistant.get_day_sales_summary(),
                title="VENTAS DE HOY"
            )
    
    elif intent == "consultar_inventario":
        prenda = extracted.get("prenda", "")
        talla = extracted.get("talla", "")
        
        query = prenda
        if talla:
            query += f" talla {talla}"
        
        if query:
            return assistant.answer_stock_or_price(query)
        return assistant.get_inventory_overview_report()
    
    elif intent == "consultar_costo_margen":
        prenda = extracted.get("prenda", "")
        if prenda:
            # Buscar prenda y devolver costo + margen
            catalog = assistant.load_catalog()
            matches = [p for p in catalog if prenda.lower() in p.get("nombre", "").lower()]
            
            if matches:
                response_lines = [f"💰 <b>ANÁLISIS DE COSTO Y MARGEN</b>\n"]
                for p in matches[:3]:
                    nombre = p.get("nombre", "")
                    precio_venta = p.get("precio", 0)
                    costo = p.get("coste", 0)
                    margen = precio_venta - costo
                    margen_pct = (margen / precio_venta * 100) if precio_venta > 0 else 0
                    
                    response_lines.append(
                        f"• <b>{nombre}</b>\n"
                        f"  💵 Precio venta: ${precio_venta:,.2f} MXN\n"
                        f"  📦 Costo: ${costo:,.2f} MXN\n"
                        f"  📈 Margen: ${margen:,.2f} ({margen_pct:.1f}%)\n"
                    )
                return "\n".join(response_lines)
        return "❌ No encontré la prenda. Intenta con el nombre específico."
    
    elif intent == "consultar_top_vendidas":
        return assistant.get_top_sellers(30)
    
    elif intent == "consultar_caja":
        return assistant.get_drawer_status_msg()
    
    elif intent == "consultar_ticket":
        # Buscar número de ticket en el texto
        m = re.search(r'(?:ticket|recibo|folio|#)\s*(\d+)', text, re.IGNORECASE)
        if m:
            return assistant.search_ticket(m.group(1))
    elif intent == "consultar_ads":
        try:
            from send_ads_summary_telegram import get_ads_summary_msg
            return get_ads_summary_msg()
        except Exception as ex:
            return f"❌ Error generando reporte de Meta Ads: {ex}"
    
    else:
        # Fallback: Gemini general
        if assistant.gemini_api_key:
            reply = assistant.ask_gemini(text, chat_id=chat_id)
            if reply:
                return reply
        return show_help(text)


def show_help(user_text=None):
    """Menú de ayuda / no entendido"""
    prefix = ""
    if user_text:
        prefix = f"🤔 <b>No logré interpretar la consulta:</b> <i>\"{user_text}\"</i>\n\n"
    return (
        f"{prefix}"
        f"🤖 <b>Asistente Vonne Boutique v2.4</b>\n\n"
        f"Prueba con estas frases o comandos:\n\n"
        f"📊 <b>Ventas:</b> 'Cuánto vendimos hoy', 'Ventas de ayer'\n"
        f"🎯 <b>Marketing:</b> 'Campañas de hoy', 'Revisa los anuncios', 'Reporte ads'\n"
        f"📦 <b>Inventario:</b> 'Stock bajo', 'Qué falta resurtir', 'Agotados'\n"
        f"💵 <b>Caja:</b> 'Cómo está la caja', 'Estado de caja'\n"
        f"🏆 <b>Top:</b> 'Prendas más vendidas', 'Bestsellers'\n"
        f"🎫 <b>Tickets:</b> 'Detalle del ticket 1234'\n\n"
        f"📍 <i>Plaza La Fragua, Saltillo</i>"
    )


if __name__ == "__main__":
    # Test básico
    classifier = SemanticIntentClassifier()
    
    test_queries = [
        "que tenemos en stock bajo?",
        "qué prendas se están acabando?",
        "agotados",
        "cuánto vendimos hoy?",
        "ventas del 15 de septiembre",
        "cuánto costó el blazer?",
        "cuál es el margen del vestido?",
        "cómo está la caja?",
        "top de prendas más vendidas",
    ]
    
    print("=" * 70)
    print("PRUEBAS DE CLASIFICACIÓN SEMÁNTICA v2.4")
    print("=" * 70)
    
    for query in test_queries:
        result = classifier.classify_with_gemini(query)
        print(f"\n📝 '{query}'")
        print(f"   └─ Intención: {result.get('intent')} (conf: {result.get('confidence', 0):.2f})")
