#!/usr/bin/env python3
"""
Mejorador para Loyverse Assistant - Reconocimiento Inteligente de Intenciones v2.2
VERSIÓN MEJORADA: Soporte completo para rangos de fechas (del 7 al 17 de septiembre)
"""

import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone

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

def normalize_text(text):
    """Normaliza texto para comparación"""
    if not text:
        return ""
    t = text.lower()
    t = unicodedata.normalize('NFD', t)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return t.strip()

class IntentionRecognizer:
    """
    Reconoce intenciones de usuario de forma más flexible y con mejor cobertura
    VERSIÓN v2.2 - SOPORTE COMPLETO DE RANGOS DE FECHAS
    """
    
    # Diccionarios de sinónimos EXPANDIDOS
    INTENT_KEYWORDS = {
        'ventas_hoy': {
            'keywords': [
                'ventas', 'vendí', 'vendimos', 'total', 'cuanto', 'se vendió',
                'ingresos', 'recaudado', 'al momento', 'ahorita', 'ahora', 'cuantas ventas',
                'cuánto ganamos', 'balance', 'total del día', 'cantidad vendida', 'facturación',
                'cuanto hemos vendido', 'resumen de ventas', 'como va', 'como vamos',
                'estado de ventas', 'movimiento', 'transacciones', 'cifra', 'monto',
                'ganancias', 'ingresos del día', 'venta diaria', 'corte parcial'
            ],
            'exclude': ['ayer', 'mes', 'semana', 'mejor', 'más', 'histórico', 'cuando', 'cual dia', 'del', 'al']
        },
        
        'ventas_ayer': {
            'keywords': ['ayer', 'dia anterior', 'anterior', 'pasado', 'día anterior', 'ayoche'],
            'exclude': ['mejor', 'mas']
        },
        
        'prendas_vendidas': {
            'keywords': [
                'prendas', 'ropa', 'articulos', 'piezas', 'modelos', 'que se vendio',
                'que vendieron', 'que sacamos', 'que salieron', 'prendas que', 'artículos que',
                'piezas que', 'ropa que', 'detalle de prendas', 'lista de prendas',
                'qué salió', 'qué se sacó', 'cuáles fueron', 'prendas del día'
            ],
            'exclude': ['inventario', 'stock', 'precio', 'agotadas']
        },
        
        'caja': {
            'keywords': [
                'caja', 'corte', 'efectivo', 'dinero', 'fondo', 'cajon', 'dinerales',
                'cierre de caja', 'cuánto hay', 'estado de caja', 'cajon actual',
                'dinero en caja', 'efectivo acumulado', 'fondo de caja', 'caja actual',
                'cuanto tenemos', 'dinero disponible', 'balance de caja', 'resultado de caja'
            ],
            'exclude': ['prendas', 'stock', 'inventario']
        },
        
        'ticket': {
            'keywords': ['ticket', 'recibo', 'factura', 'folio', 'orden', '#', 'venta numero', 'número de venta'],
            'exclude': []
        },
        
        'top_vendidas': {
            'keywords': [
                'top', 'mas vendido', 'ranking', 'lo que mas', 'mejor venta', 'estrella',
                'más popular', 'favorita', 'bestseller', 'mas se vendio', 'lo más vendido',
                'prendas estrella', 'más solicitadas', 'favoritas', 'líderes de ventas',
                'artículos de mayor venta', 'prendas líderes', 'campeonas',
                'talla más vendida', 'talla mas vendida', 'cual talla se vende mas',
                'talla que más se vende', 'talla popular', 'talla favorita',
                'que talla vende mas', 'que se vende mas', 'talla más solicitada',
                'mejor talla', 'talla estrella', 'talla preferida', 'talla lider'
            ],
            'exclude': []
        },
        
        'agotadas': {
            'keywords': [
                'agotada', 'agotado', 'sin stock', 'poco stock', 'bajo stock', 'acabado',
                'se termino', 'resurtir', 'que falta', 'inventario bajo', 'por agotarse',
                'agotándose', 'falta de stock', 'escasez', 'casi agotado', 'casi sin stock',
                'necesita resurtir', 'falta reabastecer', 'stock crítico'
            ],
            'exclude': []
        },
        
        'stock_inventario': {
            'keywords': [
                'stock', 'inventario', 'existencia', 'talla', 'cuanto queda', 'cuantas',
                'tenemos', 'hay', 'disponible', 'cuántas prendas', 'disponibilidad',
                'cantidad en stock', 'existencias', 'cuanto hay', 'qué hay', 'qué tenemos',
                'cuánto inventario', 'cuántas hay', 'disponibles', 'en stock', 'tenemos de'
            ],
            'exclude': ['vendidas', 'vendido', 'más vendido', 'mas vendido', 'talla más vendida']
        },
        
        'rango_fechas': {
            'keywords': ['del', 'al', 'desde', 'hasta'],
            'exclude': []
        },
        
        'periodo': {
            'keywords': [
                'semana', 'mes', '7 dias', '30 dias', 'ultimos dias', 'este mes',
                'esta semana', 'últimas', 'últimos', 'semanal', 'mensual', 'período',
                '7 días', '30 días', 'quincena', 'quincenal'
            ],
            'exclude': []
        },
        
        'precio': {
            'keywords': ['precio', 'cuesta', 'valor', 'cuanto cuesta', 'cuanto vale', 'costo', 'tarifa'],
            'exclude': []
        },
        
        'mejor_dia': {
            'keywords': [
                'mejor dia', 'dia que mas', 'mas vendimos', 'record', 'maximo',
                'cual dia', 'que dia', 'mejor jornada', 'máximo de ventas', 'día pico',
                'día récord', 'mejor desempeño', 'pico de ventas'
            ],
            'exclude': []
        },
        
        'ayuda': {
            'keywords': ['ayuda', 'help', 'comandos', 'que puedo', 'como funciona', 'menu', 'opciones'],
            'exclude': []
        }
    }
    
    def __init__(self):
        self.tz = timezone(timedelta(hours=-6))  # Zona horaria México
    
    def detect_intent(self, text):
        """
        Detecta la intención del usuario con puntuación de confianza
        Retorna: (intent, confidence, context)
        """
        if not text:
            return None, 0, {}
        
        clean = text.lower().strip()
        clean = re.sub(r'^/(?:asistente|pregunta|ask|consulta)\s*', '', clean)
        clean = re.sub(r'@\w+', '', clean).strip()
        norm = normalize_text(clean)
        
        # 🆕 PRIORIDAD: Detectar PRIMERO si tiene rango de fechas (del X al Y)
        date_range_context = self._extract_date_range(text, norm)
        if date_range_context.get('type') == 'date_range':
            return 'rango_fechas', 2.0, date_range_context
        
        # Luego buscar fecha específica
        date_context = self._extract_date_context(clean, norm)
        
        # Calcular puntuaciones para cada intención
        scores = {}
        for intent, config in self.INTENT_KEYWORDS.items():
            if intent == 'rango_fechas':
                continue  # Ya se procesó arriba
            score = self._calculate_intent_score(norm, config)
            scores[intent] = score
        
        # Obtener mejor intención
        if scores:
            best_intent = max(scores, key=scores.get)
            confidence = scores[best_intent]
            
            # Solo retornar si la confianza es suficiente
            if confidence > 0:
                return best_intent, confidence, date_context
        
        return None, 0, date_context
    
    def _calculate_intent_score(self, norm_text, config):
        """Calcula puntuación para una intención"""
        keywords = config.get('keywords', [])
        exclude = config.get('exclude', [])
        
        # Contar palabras clave encontradas
        keyword_count = sum(1 for kw in keywords if normalize_text(kw) in norm_text)
        
        # Si hay palabras de exclusión, penalizar
        exclude_count = sum(1 for ex in exclude if normalize_text(ex) in norm_text)
        
        # Puntuación: palabras clave * 1.0, menos palabras de exclusión * 0.5
        score = (keyword_count * 1.0) - (exclude_count * 0.5)
        
        return max(0, score)
    
    def _extract_date_range(self, text, norm_text):
        """
        🆕 Extrae rango de fechas como "del 7 al 17 de septiembre"
        Retorna contexto con start_date y end_date
        """
        context = {
            'type': None,
            'start': None,
            'end': None
        }
        
        now_dt = datetime.now(self.tz)
        
        # Patrón: "del X al Y de [mes]" o "del X de [mes] al Y de [mes]"
        pattern = (
            r'\b(?:del|desde)\s+(?:el\s+)?(\d{1,2})(?:\s+de\s+([a-záéíóú]+))?'
            r'(?:\s+(?:de|del)?\s+(\d{4}))?\s+al\s+(?:el\s+)?(\d{1,2})?'
            r'(?:\s+de\s+([a-záéíóú]+))?(?:\s+(?:de|del)?\s+(\d{4}))?\b'
        )
        
        m = re.search(pattern, norm_text)
        if m:
            d1_str = m.group(1)
            m1_str = m.group(2)
            y1_str = m.group(3)
            
            d2_str = m.group(4)
            m2_str = m.group(5)
            y2_str = m.group(6)
            
            # Convertir strings a integers
            try:
                d1 = int(d1_str)
                d2 = int(d2_str) if d2_str else now_dt.day
                
                # Resolver meses
                month1 = MONTHS_NAME_TO_NUM.get(m1_str) if m1_str else now_dt.month
                month2 = MONTHS_NAME_TO_NUM.get(m2_str) if m2_str else (month1 if m1_str else now_dt.month)
                
                # Resolver años
                year = int(y2_str or y1_str or now_dt.year)
                
                if month1 and month2:
                    try:
                        start_dt = datetime(year, month1, d1, 0, 0, 0, tzinfo=self.tz)
                        end_dt = datetime(year, month2, d2, 23, 59, 59, tzinfo=self.tz)
                        
                        if start_dt <= end_dt:
                            context['type'] = 'date_range'
                            context['start'] = start_dt
                            context['end'] = end_dt
                            print(f"[DEBUG v2.2] Rango detectado: {start_dt.date()} -> {end_dt.date()}")
                    except ValueError:
                        pass
            except (ValueError, TypeError):
                pass
        
        return context
    
    def _extract_date_context(self, text, norm_text):
        """Extrae contexto de fecha de la pregunta"""
        context = {
            'has_date': False,
            'date': None,
            'period': None
        }
        
        today = datetime.now(self.tz)
        
        # Detectar "hoy"
        if re.search(r'\bhoy\b', norm_text):
            context['has_date'] = True
            context['date'] = today
        
        # Detectar "ayer"
        elif re.search(r'\bayer\b', norm_text):
            context['has_date'] = True
            context['date'] = today - timedelta(days=1)
        
        # Detectar periodo
        if re.search(r'\b(?:semana|7 dias|ultimos dias|esta semana)\b', norm_text):
            context['period'] = 7
        elif re.search(r'\b(?:mes|30 dias|este mes|ultimo mes|mensual)\b', norm_text):
            context['period'] = 30
        
        return context
    
    def get_specific_garment(self, text):
        """Extrae el nombre de una prenda específica si la hay"""
        garment_words = [
            "blazer", "vestido", "falda", "short", "blusa", "chaleco", "capa",
            "conjunto", "pantalon", "top", "playera", "satin", "gamuza", "mesh",
            "peluche", "faja", "cinto", "chaqueta", "abrigo", "cardigan", "polo",
            "camisa", "blusas", "faldon", "talle", "saco", "sweater", "sudadera",
            "jeans", "pants", "leggings", "bermuda", "capri", "crop", "tank"
        ]
        
        norm = normalize_text(text)
        for garment in garment_words:
            if re.search(r'\b' + garment + r'\b', norm):
                return garment
        
        return None


# Ejemplo de uso mejorado
def enhanced_answer(assistant, text, chat_id="default"):
    """
    Método mejorado de answer() que usa mejor reconocimiento de intenciones
    VERSIÓN v2.2 - SOPORTE COMPLETO DE RANGOS DE FECHAS
    """
    recognizer = IntentionRecognizer()
    intent, confidence, context = recognizer.detect_intent(text)
    
    print(f"[DEBUG v2.2] Intención detectada: {intent} (confianza: {confidence:.2f})")
    print(f"[DEBUG v2.2] Contexto: {context}")
    print(f"[DEBUG v2.2] Texto: {text}")
    
    # Si la confianza es muy baja, usar Gemini o mostrar ayuda
    if confidence < 0.5:
        if assistant.gemini_api_key:
            return assistant.ask_gemini(text, chat_id=chat_id)
        else:
            return show_help()
    
    # 🆕 PROCESAMIENTO DE RANGO DE FECHAS
    if intent == 'rango_fechas':
        start_date = context.get('start')
        end_date = context.get('end')
        
        if start_date and end_date:
            # Buscar si menciona prendas específicas
            if re.search(r'\b(?:prendas?|ropa|piezas?|articulos?|vendieron|salieron?)\b', text.lower()):
                return assistant.get_date_range_sales_summary(
                    start_date, end_date,
                    label=f"Del {start_date.day} al {end_date.day} de {MONTHS_ES.get(start_date.month)}"
                )
            else:
                return assistant.get_date_range_sales_summary(
                    start_date, end_date,
                    label=f"Del {start_date.day} al {end_date.day} de {MONTHS_ES.get(start_date.month)}"
                )
    
    # RESTO DE INTENCIONES...
    if intent == 'ventas_hoy':
        stats = assistant.get_day_sales_summary()
        if re.search(r'\b(?:prendas?|ropa|piezas?|articulos?|vendieron|salieron?)\b', text.lower()):
            return assistant.format_items_list_msg(stats, title="PRENDAS VENDIDAS HOY")
        else:
            return assistant.format_sales_summary_msg(stats, title="VENTAS DE HOY")
    
    elif intent == 'ventas_ayer':
        yesterday = datetime.now(recognizer.tz) - timedelta(days=1)
        stats = assistant.get_day_sales_summary(yesterday)
        if re.search(r'\b(?:prendas?|ropa|piezas?|articulos?|vendieron|salieron?)\b', text.lower()):
            return assistant.format_items_list_msg(stats, title="PRENDAS VENDIDAS AYER")
        else:
            return assistant.format_sales_summary_msg(stats, title="VENTAS DE AYER")
    
    elif intent == 'prendas_vendidas':
        stats = assistant.get_day_sales_summary(context.get('date') if context.get('has_date') else None)
        return assistant.format_items_list_msg(stats, title="PRENDAS VENDIDAS")
    
    elif intent == 'caja':
        return assistant.get_drawer_status_msg()
    
    elif intent == 'ticket':
        return assistant.search_ticket(text)
    
    elif intent == 'top_vendidas':
        garment = recognizer.get_specific_garment(text)
        if garment:
            return assistant.get_top_sellers_by_garment(garment, days=30)
        else:
            return assistant.get_top_sellers(30)
    
    elif intent == 'agotadas':
        return assistant.get_low_stock_report()
    
    elif intent == 'stock_inventario':
        garment = recognizer.get_specific_garment(text)
        if garment:
            return assistant.answer_stock_or_price(text)
        else:
            return assistant.get_inventory_overview_report()
    
    elif intent == 'periodo':
        if context.get('period') == 7:
            return assistant.get_period_sales_summary(7, "ÚLTIMOS 7 DÍAS")
        elif context.get('period') == 30:
            return assistant.get_period_sales_summary(30, "ÚLTIMOS 30 DÍAS")
    
    elif intent == 'mejor_dia':
        return assistant.get_best_sales_day(days=30)
    
    elif intent == 'ayuda':
        return show_help()
    
    # Fallback a Gemini
    if assistant.gemini_api_key:
        return assistant.ask_gemini(text, chat_id=chat_id)
    
    return show_help()


def show_help():
    """Menú de ayuda mejorado"""
    return (
        f"🤖 <b>Asistente Inteligente de Ventas v2.2</b>\n\n"
        f"Entiendo muchas formas de hacer preguntas. Prueba:\n\n"
        f"📊 <b>Ventas (Rangos de Fechas):</b>\n"
        f"• \"Dame las ventas del 7 al 17 de septiembre\"\n"
        f"• \"Ventas del 1 al 30 de agosto\"\n"
        f"• \"¿Cuánto vendí del 10 al 25 de octubre?\"\n\n"
        f"📊 <b>Ventas (Períodos):</b>\n"
        f"• \"¿Cuánto vendí hoy?\"\n"
        f"• \"Resumen de ventas\"\n"
        f"• \"Ventas de la semana\"\n"
        f"• \"Ventas de ayer\"\n\n"
        f"💰 <b>Caja:</b>\n"
        f"• \"¿Cómo está la caja?\"\n"
        f"• \"Corte de caja\"\n\n"
        f"📦 <b>Inventario:</b>\n"
        f"• \"¿Qué stock hay de blazer?\"\n"
        f"• \"Prendas agotadas\"\n\n"
        f"🏆 <b>Top Vendidas:</b>\n"
        f"• \"Cual es la talla más vendida de blazer\"\n"
        f"• \"Prendas estrella\"\n\n"
        f"🎫 <b>Más:</b>\n"
        f"• \"Detalle del ticket 1234\"\n"
    )


if __name__ == "__main__":
    recognizer = IntentionRecognizer()
    
    test_queries = [
        "dame las ventas del 7 al 17 de septiembre 2026",  # ← NUEVO CASO
        "ventas del 1 al 30 de agosto",  # ← NUEVO CASO
        "¿cuánto vendí del 10 al 25 de octubre?",  # ← NUEVO CASO
        "¿cuánto vendí hoy?",
        "cual es la talla más vendida de blazer",
        "prendas agotadas",
        "ticket 1234",
    ]
    
    print("=" * 60)
    print("PRUEBAS DE RECONOCIMIENTO v2.2 - RANGOS DE FECHAS")
    print("=" * 60)
    
    for query in test_queries:
        intent, confidence, context = recognizer.detect_intent(query)
        print(f"\n📝 '{query}'")
        print(f"   └─ Intención: {intent} (conf: {confidence:.2f})")
        if context.get('type') == 'date_range':
            print(f"   └─ Rango: {context.get('start').date()} -> {context.get('end').date()}")
        elif context.get('has_date'):
            print(f"   └─ Fecha: {context.get('date').strftime('%d/%m/%Y')}")
