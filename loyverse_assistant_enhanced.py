#!/usr/bin/env python3
"""
Mejorador para Loyverse Assistant - Reconocimiento Inteligente de Intenciones v2.0
VERSIÓN CORREGIDA con palabras clave expandidas
Reemplaza el método 'answer()' del asistente original con uno mucho más robusto
"""

import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone

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
    VERSIÓN v2.0 - PALABRAS CLAVE EXPANDIDAS
    """
    
    # Diccionarios de sinónimos EXPANDIDOS
    INTENT_KEYWORDS = {
        'ventas_hoy': {
            'keywords': [
                'ventas', 'vendí', 'vendimos', 'total', 'cuanto', 'se vendió', 'mañana',
                'ingresos', 'recaudado', 'al momento', 'ahorita', 'ahora', 'cuantas ventas',
                'cuánto ganamos', 'balance', 'total del día', 'cantidad vendida', 'facturación',
                'cuanto hemos vendido', 'resumen de ventas', 'como va', 'como vamos',
                'estado de ventas', 'movimiento', 'transacciones', 'cifra', 'monto',
                'ganancias', 'ingresos del día', 'venta diaria', 'corte parcial'
            ],
            'exclude': ['ayer', 'mes', 'semana', 'mejor', 'más', 'histórico', 'cuando', 'cual dia']
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
                'artículos de mayor venta', 'prendas líderes', 'campeonas'
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
            'exclude': ['vendidas', 'vendido']
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
        
        # Buscar fecha específica
        date_context = self._extract_date_context(clean, norm)
        
        # Calcular puntuaciones para cada intención
        scores = {}
        for intent, config in self.INTENT_KEYWORDS.items():
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
    VERSIÓN v2.0 - OPTIMIZADA
    """
    recognizer = IntentionRecognizer()
    intent, confidence, date_context = recognizer.detect_intent(text)
    
    print(f"[DEBUG] Intención detectada: {intent} (confianza: {confidence:.2f})")
    print(f"[DEBUG] Contexto de fecha: {date_context}")
    
    # Si la confianza es muy baja, usar Gemini o mostrar ayuda
    if confidence < 0.5:
        if assistant.gemini_api_key:
            return assistant.ask_gemini(text, chat_id=chat_id)
        else:
            return show_help()
    
    # Procesar según intención detectada
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
        stats = assistant.get_day_sales_summary(date_context.get('date') if date_context.get('has_date') else None)
        return assistant.format_items_list_msg(stats, title="PRENDAS VENDIDAS")
    
    elif intent == 'caja':
        return assistant.get_drawer_status_msg()
    
    elif intent == 'ticket':
        return assistant.search_ticket(text)
    
    elif intent == 'top_vendidas':
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
        if date_context.get('period') == 7:
            return assistant.get_period_sales_summary(7, "ÚLTIMOS 7 DÍAS")
        elif date_context.get('period') == 30:
            return assistant.get_period_sales_summary(30, "ÚLTIMOS 30 DÍAS")
    
    elif intent == 'mejor_dia':
        return assistant.get_best_sales_day(days=30)
    
    elif intent == 'ayuda':
        return show_help()
    
    # Fallback a Gemini si está disponible
    if assistant.gemini_api_key:
        return assistant.ask_gemini(text, chat_id=chat_id)
    
    return show_help()


def show_help():
    """Menú de ayuda mejorado"""
    return (
        f"🤖 <b>Asistente Inteligente de Ventas v2.0</b>\n\n"
        f"Entiendo muchas formas de hacer preguntas. Prueba:\n\n"
        f"📊 <b>Ventas:</b>\n"
        f"• \"¿Cuánto vendí hoy?\"\n"
        f"• \"Resumen de ventas\"\n"
        f"• \"¿Cuáles fueron las prendas que vendieron?\"\n"
        f"• \"¿Qué venta tuve ayer?\"\n"
        f"• \"Ventas de la semana\"\n"
        f"• \"Mejor día de ventas\"\n"
        f"• \"Balance del día\"\n"
        f"• \"Estado de ventas\"\n\n"
        f"💰 <b>Caja:</b>\n"
        f"• \"¿Cómo está la caja?\"\n"
        f"• \"Corte de caja\"\n"
        f"• \"¿Cuánto efectivo hay?\"\n"
        f"• \"Dinero acumulado\"\n\n"
        f"📦 <b>Inventario:</b>\n"
        f"• \"¿Qué stock hay de blazer?\"\n"
        f"• \"¿Cuántas prendas tenemos?\"\n"
        f"• \"Qué está agotado\"\n"
        f"• \"Inventario bajo\"\n\n"
        f"🏆 <b>Más:</b>\n"
        f"• \"Top de prendas más vendidas\"\n"
        f"• \"Detalle del ticket 1234\"\n"
        f"• \"¿Cuánto cuesta el vestido?\"\n"
    )


if __name__ == "__main__":
    # Pruebas de reconocimiento
    recognizer = IntentionRecognizer()
    
    test_queries = [
        "¿cuánto vendí hoy?",
        "dame el resumen de ventas",
        "¿qué prendas se vendieron?",
        "stock de blazer",
        "¿cómo está la caja?",
        "corte de caja",
        "top de prendas",
        "prendas agotadas",
        "ticket 1234",
        "ventas de ayer",
        "¿qué se vendio la semana pasada?",
        "mejor día de ventas",
        "inventario total",
        "cuantas prendas tenemos",
        "¿cuánto cuesta el vestido?",
        "prendas con poco stock",
        "¿cuánto ganamos?",
        "balance del día",
        "estado de caja",
        "prendas más populares"
    ]
    
    print("=" * 60)
    print("PRUEBAS DE RECONOCIMIENTO DE INTENCIONES v2.0")
    print("=" * 60)
    
    for query in test_queries:
        intent, confidence, context = recognizer.detect_intent(query)
        print(f"\n📝 '{query}'")
        print(f"   └─ Intención: {intent} (conf: {confidence:.2f})")
        if context.get('has_date'):
            print(f"   └─ Fecha: {context.get('date').strftime('%d/%m/%Y')}")
        if context.get('period'):
            print(f"   └─ Período: {context.get('period')} días")
