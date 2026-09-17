#!/usr/bin/env python3
"""
Mejorador para Loyverse Assistant - Reconocimiento Inteligente de Intenciones v2.3
VERSIÓN COMPLETA: Soporte para fechas individuales, rangos y períodos predefinidos
Replica todas las opciones de filtro de fecha de Loyverse POS nativo
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
    VERSIÓN v2.3 - SOPORTE COMPLETO: Fechas individuales, rangos Y períodos predefinidos
    """
    
    INTENT_KEYWORDS = {
        'ventas_hoy': {
            'keywords': ['ventas', 'vendí', 'vendimos', 'total', 'cuanto', 'se vendió',
                         'ingresos', 'recaudado', 'al momento', 'ahorita', 'ahora'],
            'exclude': ['ayer', 'mes', 'semana', 'mejor', 'más', 'del', 'al', 'rango']
        },
        
        'ventas_ayer': {
            'keywords': ['ayer', 'dia anterior', 'anterior', 'pasado', 'día anterior'],
            'exclude': ['mejor', 'mas']
        },
        
        'top_vendidas': {
            'keywords': ['top', 'mas vendido', 'ranking', 'mejor venta', 'estrella',
                         'más popular', 'bestseller', 'talla más vendida', 'cual talla'],
            'exclude': []
        },
        
        'caja': {
            'keywords': ['caja', 'corte', 'efectivo', 'dinero', 'fondo', 'cajon'],
            'exclude': ['prendas', 'stock']
        },
        
        'agotadas': {
            'keywords': ['agotada', 'sin stock', 'bajo stock', 'acabado', 'resurtir'],
            'exclude': []
        },
        
        'ayuda': {
            'keywords': ['ayuda', 'help', 'comandos', 'que puedo', 'menu'],
            'exclude': []
        }
    }
    
    def __init__(self):
        self.tz = timezone(timedelta(hours=-6))  # Zona horaria México
    
    def detect_intent(self, text):
        """Detecta la intención del usuario"""
        if not text:
            return None, 0, {}
        
        clean = text.lower().strip()
        clean = re.sub(r'^/(?:asistente|pregunta|ask|consulta)\s*', '', clean)
        clean = re.sub(r'@\w+', '', clean).strip()
        norm = normalize_text(clean)
        
        # PRIORIDAD 1: Detectar período predefinido
        period_context = self._extract_period(clean, norm)
        if period_context.get('type'):
            return 'periodo_predefinido', 2.0, period_context
        
        # PRIORIDAD 2: Detectar rango de fechas (del X al Y)
        range_context = self._extract_date_range(text, norm)
        if range_context.get('type') == 'date_range':
            return 'rango_fechas', 2.0, range_context
        
        # PRIORIDAD 3: Detectar fecha individual (del X de mes)
        single_date_context = self._extract_single_date(text, norm)
        if single_date_context.get('type') == 'single_date':
            return 'fecha_individual', 2.0, single_date_context
        
        # PRIORIDAD 4: Detectar otras intenciones
        scores = {}
        for intent, config in self.INTENT_KEYWORDS.items():
            score = self._calculate_intent_score(norm, config)
            scores[intent] = score
        
        if scores:
            best_intent = max(scores, key=scores.get)
            confidence = scores[best_intent]
            if confidence > 0:
                return best_intent, confidence, {}
        
        return None, 0, {}
    
    def _extract_period(self, text, norm_text):
        """
        Detecta períodos predefinidos como en Loyverse:
        - hoy
        - ayer
        - esta semana
        - última semana
        - este mes
        - último mes
        - últimos 7 días
        - últimos 30 días
        """
        context = {'type': None, 'period': None, 'label': None}
        now = datetime.now(self.tz)
        
        # HOY
        if re.search(r'\bhoy\b', norm_text):
            context['type'] = 'single_period'
            context['period'] = 'today'
            context['label'] = 'HOY'
            return context
        
        # AYER
        if re.search(r'\bayer\b', norm_text):
            context['type'] = 'single_period'
            context['period'] = 'yesterday'
            context['label'] = 'AYER'
            return context
        
        # ESTA SEMANA
        if re.search(r'\b(?:esta|ésta)\s+semana\b', norm_text):
            context['type'] = 'period_range'
            context['period'] = 'this_week'
            # Calcular lunes de esta semana
            days_since_monday = now.weekday()
            week_start = now - timedelta(days=days_since_monday)
            context['start'] = week_start.replace(hour=0, minute=0, second=0)
            context['end'] = now
            context['label'] = 'ESTA SEMANA'
            return context
        
        # ÚLTIMA SEMANA
        if re.search(r'\b(?:ultima|última|pasada)\s+semana\b', norm_text):
            context['type'] = 'period_range'
            context['period'] = 'last_week'
            days_since_monday = now.weekday()
            last_week_start = now - timedelta(days=days_since_monday + 7)
            last_week_end = last_week_start + timedelta(days=6)
            context['start'] = last_week_start.replace(hour=0, minute=0, second=0)
            context['end'] = last_week_end.replace(hour=23, minute=59, second=59)
            context['label'] = 'ÚLTIMA SEMANA'
            return context
        
        # ESTE MES
        if re.search(r'\b(?:este|éste)\s+(?:mes|mes)\b', norm_text):
            context['type'] = 'period_range'
            context['period'] = 'this_month'
            month_start = now.replace(day=1, hour=0, minute=0, second=0)
            context['start'] = month_start
            context['end'] = now
            context['label'] = f'ESTE MES ({MONTHS_ES.get(now.month).upper()})'
            return context
        
        # ÚLTIMO MES
        if re.search(r'\b(?:ultimo|último|pasado)\s+(?:mes|mes)\b', norm_text):
            context['type'] = 'period_range'
            context['period'] = 'last_month'
            first_day_this_month = now.replace(day=1)
            last_day_last_month = first_day_this_month - timedelta(days=1)
            first_day_last_month = last_day_last_month.replace(day=1)
            context['start'] = first_day_last_month.replace(hour=0, minute=0, second=0)
            context['end'] = last_day_last_month.replace(hour=23, minute=59, second=59)
            prev_month = MONTHS_ES.get(first_day_last_month.month, 'Mes')
            context['label'] = f'ÚLTIMO MES ({prev_month.upper()})'
            return context
        
        # ÚLTIMOS 7 DÍAS
        if re.search(r'\b(?:ultimos|últimos)\s+7\s+(?:dias|días)\b', norm_text):
            context['type'] = 'period_range'
            context['period'] = 'last_7_days'
            start = now - timedelta(days=7)
            context['start'] = start.replace(hour=0, minute=0, second=0)
            context['end'] = now
            context['label'] = 'ÚLTIMOS 7 DÍAS'
            return context
        
        # ÚLTIMOS 30 DÍAS
        if re.search(r'\b(?:ultimos|últimos)\s+30\s+(?:dias|días)\b', norm_text):
            context['type'] = 'period_range'
            context['period'] = 'last_30_days'
            start = now - timedelta(days=30)
            context['start'] = start.replace(hour=0, minute=0, second=0)
            context['end'] = now
            context['label'] = 'ÚLTIMOS 30 DÍAS'
            return context
        
        # ÚLTIMA SEMANA (genérico "últimos días")
        if re.search(r'\b(?:ultimos|últimos)\s+(?:dias|días)\b', norm_text):
            context['type'] = 'period_range'
            context['period'] = 'last_7_days'
            start = now - timedelta(days=7)
            context['start'] = start.replace(hour=0, minute=0, second=0)
            context['end'] = now
            context['label'] = 'ÚLTIMOS DÍAS'
            return context
        
        return context
    
    def _extract_date_range(self, text, norm_text):
        """
        Extrae rango de fechas: "del 7 al 17 de septiembre"
        """
        context = {'type': None, 'start': None, 'end': None}
        now_dt = datetime.now(self.tz)
        
        # Patrón mejorado para rangos
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
            
            try:
                d1 = int(d1_str)
                d2 = int(d2_str) if d2_str else now_dt.day
                
                month1 = MONTHS_NAME_TO_NUM.get(m1_str) if m1_str else now_dt.month
                month2 = MONTHS_NAME_TO_NUM.get(m2_str) if m2_str else (month1 if m1_str else now_dt.month)
                
                year = int(y2_str or y1_str or now_dt.year)
                
                if month1 and month2:
                    try:
                        start_dt = datetime(year, month1, d1, 0, 0, 0, tzinfo=self.tz)
                        end_dt = datetime(year, month2, d2, 23, 59, 59, tzinfo=self.tz)
                        
                        if start_dt <= end_dt:
                            context['type'] = 'date_range'
                            context['start'] = start_dt
                            context['end'] = end_dt
                    except ValueError:
                        pass
            except (ValueError, TypeError):
                pass
        
        return context
    
    def _extract_single_date(self, text, norm_text):
        """
        Extrae fecha individual: "del 15 de septiembre"
        """
        context = {'type': None, 'date': None}
        now_dt = datetime.now(self.tz)
        
        # Patrón para fecha individual (sin "al")
        pattern = r'\b(?:del|el)\s+(\d{1,2})(?:\s+de\s+([a-záéíóú]+))?(?:\s+(?:de|del)?\s+(\d{4}))?\b'
        
        # Buscar SOLO si NO hay "al" después (para no confundir con rangos)
        if not re.search(r'\bal\b', norm_text):
            m = re.search(pattern, norm_text)
            if m:
                d_str = m.group(1)
                m_str = m.group(2)
                y_str = m.group(3)
                
                try:
                    day = int(d_str)
                    month = MONTHS_NAME_TO_NUM.get(m_str) if m_str else now_dt.month
                    year = int(y_str) if y_str else now_dt.year
                    
                    if month:
                        try:
                            date_dt = datetime(year, month, day, 0, 0, 0, tzinfo=self.tz)
                            context['type'] = 'single_date'
                            context['date'] = date_dt
                        except ValueError:
                            pass
                except (ValueError, TypeError):
                    pass
        
        return context
    
    def _calculate_intent_score(self, norm_text, config):
        """Calcula puntuación para una intención"""
        keywords = config.get('keywords', [])
        exclude = config.get('exclude', [])
        
        keyword_count = sum(1 for kw in keywords if normalize_text(kw) in norm_text)
        exclude_count = sum(1 for ex in exclude if normalize_text(ex) in norm_text)
        
        score = (keyword_count * 1.0) - (exclude_count * 0.5)
        return max(0, score)


def enhanced_answer(assistant, text, chat_id="default"):
    """
    Método mejorado de answer() que usa reconocimiento v2.3
    VERSIÓN v2.3 - SOPORTE COMPLETO DE FECHAS
    """
    recognizer = IntentionRecognizer()
    intent, confidence, context = recognizer.detect_intent(text)
    
    print(f"[DEBUG v2.3] Intención: {intent} (conf: {confidence:.2f})")
    print(f"[DEBUG v2.3] Contexto: {context}")
    
    if confidence < 0.5:
        if assistant.gemini_api_key:
            return assistant.ask_gemini(text, chat_id=chat_id)
        else:
            return show_help()
    
    # PROCESAMIENTO DE INTENCIONES
    if intent == 'periodo_predefinido':
        period = context.get('period')
        label = context.get('label', 'PERÍODO')
        
        if period == 'today':
            return assistant.format_sales_summary_msg(
                assistant.get_day_sales_summary(),
                title=f"VENTAS {label}"
            )
        
        elif period == 'yesterday':
            yesterday = datetime.now(recognizer.tz) - timedelta(days=1)
            return assistant.format_sales_summary_msg(
                assistant.get_day_sales_summary(yesterday),
                title=f"VENTAS {label}"
            )
        
        elif context.get('type') == 'period_range':
            start = context.get('start')
            end = context.get('end')
            if start and end:
                return assistant.get_date_range_sales_summary(start, end, label=label)
    
    elif intent == 'fecha_individual':
        date = context.get('date')
        if date:
            # Buscar ventas de ese día específico
            return assistant.format_sales_summary_msg(
                assistant.get_day_sales_summary(date),
                title=f"VENTAS DEL {date.strftime('%d de %B de %Y').replace('January', 'Enero').replace('February', 'Febrero').replace('March', 'Marzo').replace('April', 'Abril').replace('May', 'Mayo').replace('June', 'Junio').replace('July', 'Julio').replace('August', 'Agosto').replace('September', 'Septiembre').replace('October', 'Octubre').replace('November', 'Noviembre').replace('December', 'Diciembre')}"
            )
    
    elif intent == 'rango_fechas':
        start = context.get('start')
        end = context.get('end')
        if start and end:
            label = f"Del {start.day} al {end.day} de {MONTHS_ES.get(start.month, 'Mes')}"
            return assistant.get_date_range_sales_summary(start, end, label=label)
    
    elif intent == 'ventas_hoy':
        return assistant.format_sales_summary_msg(
            assistant.get_day_sales_summary(),
            title="VENTAS DE HOY"
        )
    
    elif intent == 'ventas_ayer':
        yesterday = datetime.now(recognizer.tz) - timedelta(days=1)
        return assistant.format_sales_summary_msg(
            assistant.get_day_sales_summary(yesterday),
            title="VENTAS DE AYER"
        )
    
    elif intent == 'top_vendidas':
        return assistant.get_top_sellers(30)
    
    elif intent == 'caja':
        return assistant.get_drawer_status_msg()
    
    elif intent == 'agotadas':
        return assistant.get_low_stock_report()
    
    elif intent == 'ayuda':
        return show_help()
    
    if assistant.gemini_api_key:
        return assistant.ask_gemini(text, chat_id=chat_id)
    
    return show_help()


def show_help():
    """Menú de ayuda mejorado"""
    return (
        f"🤖 <b>Asistente Inteligente de Ventas v2.3</b>\n\n"
        f"Entiendo muchas formas de hacer preguntas. Prueba:\n\n"
        f"📅 <b>Períodos Predefinidos:</b>\n"
        f"• \"Ventas de hoy\"\n"
        f"• \"¿Cuánto vendí ayer?\"\n"
        f"• \"Ventas de esta semana\"\n"
        f"• \"Ventas de último mes\"\n"
        f"• \"Últimos 7 días\"\n"
        f"• \"Últimos 30 días\"\n\n"
        f"📆 <b>Fechas Específicas:</b>\n"
        f"• \"Dame las ventas del 15 de septiembre\"\n"
        f"• \"Ventas del 20 de agosto\"\n\n"
        f"📊 <b>Rangos de Fechas:</b>\n"
        f"• \"Ventas del 7 al 17 de septiembre\"\n"
        f"• \"¿Cuánto vendí del 1 al 30 de octubre?\"\n\n"
        f"💰 <b>Otros:</b>\n"
        f"• \"¿Cómo está la caja?\"\n"
        f"• \"Prendas agotadas\"\n"
        f"• \"Top de vendidas\"\n"
    )


if __name__ == "__main__":
    recognizer = IntentionRecognizer()
    
    test_queries = [
        "ventas de hoy",
        "ventas de ayer",
        "ventas de esta semana",
        "ventas de última semana",
        "ventas de este mes",
        "ventas del último mes",
        "últimos 7 días",
        "últimos 30 días",
        "dame las ventas del 15 de septiembre",
        "ventas del 20 de agosto",
        "ventas del 7 al 17 de septiembre",
        "¿cuánto vendí del 1 al 30 de octubre?",
        "¿cómo está la caja?",
        "prendas agotadas",
    ]
    
    print("=" * 70)
    print("PRUEBAS v2.3 - SOPORTE COMPLETO DE FECHAS")
    print("=" * 70)
    
    for query in test_queries:
        intent, confidence, context = recognizer.detect_intent(query)
        print(f"\n📝 '{query}'")
        print(f"   └─ Intención: {intent} (conf: {confidence:.2f})")
        if context.get('date'):
            print(f"   └─ Fecha: {context.get('date').strftime('%d/%m/%Y')}")
        if context.get('start') and context.get('end'):
            print(f"   └─ Rango: {context.get('start').date()} → {context.get('end').date()}")
        if context.get('label'):
            print(f"   └─ Label: {context.get('label')}")
