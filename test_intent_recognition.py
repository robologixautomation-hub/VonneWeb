#!/usr/bin/env python3
"""
Script de prueba v2.0 para verificar que el reconocimiento funciona correctamente
Ejecuta: python test_v2.py
"""

import sys
import os

# Cargar el mejorador v2.0
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loyverse_assistant_enhanced_v2 import IntentionRecognizer

def print_result(query, intent, confidence, color_code=None):
    """Imprime el resultado de forma legible"""
    conf_pct = int(confidence * 100 / 2.5) if confidence > 0 else 0  # Normalizar
    bar = "█" * (conf_pct // 10) + "░" * (10 - (conf_pct // 10))
    
    status = "✅" if confidence >= 1.5 else "⚠️" if confidence >= 0.5 else "❌"
    
    print(f"\n{status} '{query}'")
    print(f"   Intención: {intent or 'No detectada'}")
    print(f"   Confianza: {confidence:.2f} [{bar}] {conf_pct}%")

def main():
    recognizer = IntentionRecognizer()
    
    print("=" * 70)
    print("🧠 PRUEBA DE RECONOCIMIENTO v2.0 (VERSIÓN MEJORADA)")
    print("=" * 70)
    print("\n✅ = Seguro (confianza ≥ 1.5)")
    print("⚠️  = Probable (0.5 ≤ confianza < 1.5)")
    print("❌ = No detectado (confianza < 0.5)\n")
    
    # Pruebas organizadas por categoría
    test_categories = {
        "📊 VENTAS HOY": [
            "¿cuánto vendí hoy?",
            "dame el resumen de ventas",
            "¿qué se vendió al momento?",
            "ventas actuales",
            "¿cómo va la venta?",
            "total de hoy",
            "resumen al momento",
            "¿cuál es el total de ventas?",
            "¿cuánto hemos vendido?",
            "balance de ventas",
            "¿cuánto ganamos hoy?",
            "facturación del día",
            "cuanto tenemos vendido",
            "estado de ventas",
            "ingresos diarios"
        ],
        "📦 PRENDAS VENDIDAS": [
            "¿qué prendas se vendieron?",
            "artículos que sacamos",
            "ropa que salió hoy",
            "piezas vendidas",
            "¿qué modelos se vendieron?",
            "cuáles fueron las prendas",
            "qué ropa vendieron",
            "detalle de prendas",
            "prendas del día",
            "qué salió hoy"
        ],
        "💰 CAJA": [
            "¿cómo está la caja?",
            "corte de caja",
            "¿cuánto efectivo tenemos?",
            "dinero en la caja",
            "fondo de caja",
            "estado de caja",
            "dinerales en la caja",
            "cuánto hay en la caja",
            "efectivo acumulado",
            "cierre de caja"
        ],
        "📦 INVENTARIO": [
            "¿qué stock hay de blazer?",
            "inventario de vestido",
            "¿cuántas prendas tenemos?",
            "existencias totales",
            "stock bajo",
            "prendas agotadas",
            "¿cuánto inventario hay?",
            "poco stock de blazer",
            "cuántas prendas disponibles",
            "disponibilidad de prendas"
        ],
        "🏆 TOP VENDIDAS": [
            "prendas más vendidas",
            "ranking de ventas",
            "lo que más se vendió",
            "bestsellers",
            "prendas estrella",
            "top de prendas",
            "mejor venta",
            "¿cuáles son los favoritos?",
            "más populares",
            "líderes de ventas"
        ],
        "🎫 TICKETS": [
            "ticket 1234",
            "detalle del recibo",
            "folio 999",
            "#555",
            "¿quién fue la venta 123?"
        ],
        "📅 PERÍODO": [
            "ventas de la semana",
            "¿cuánto en los últimos 7 días?",
            "ventas de este mes",
            "últimos 30 días",
            "resumen mensual",
            "semanal",
            "mensual"
        ],
        "📈 MEJOR DÍA": [
            "¿cuál fue el mejor día?",
            "día que más vendimos",
            "máximo de ventas",
            "record de ventas",
            "mejor jornada",
            "día pico",
            "día récord"
        ],
        "ℹ️ AYUDA": [
            "¿qué comandos tengo?",
            "ayuda",
            "¿cómo funciona?",
            "menu",
            "opciones"
        ]
    }
    
    total_tests = 0
    success_tests = 0
    warning_tests = 0
    failed_tests = 0
    
    for category, queries in test_categories.items():
        print(f"\n{category}")
        print("-" * 70)
        
        for query in queries:
            intent, confidence, context = recognizer.detect_intent(query)
            print_result(query, intent, confidence)
            
            total_tests += 1
            if confidence >= 1.5:
                success_tests += 1
            elif confidence >= 0.5:
                warning_tests += 1
            else:
                failed_tests += 1
    
    # Resumen
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE PRUEBAS v2.0")
    print("=" * 70)
    print(f"Total de pruebas: {total_tests}")
    print(f"✅ Detectadas correctamente: {success_tests} ({int(success_tests*100/total_tests)}%)")
    print(f"⚠️  Probables: {warning_tests} ({int(warning_tests*100/total_tests)}%)")
    print(f"❌ No detectadas: {failed_tests} ({int(failed_tests*100/total_tests)}%)")
    
    success_rate = ((success_tests + warning_tests) * 100) // total_tests
    print(f"\n🎯 Tasa de éxito (con margen): {success_rate}%")
    
    if success_tests / total_tests >= 0.9:
        print("\n✅ ¡Reconocimiento EXCELENTE! Listo para producción.")
    elif success_tests / total_tests >= 0.8:
        print("\n✅ ¡Reconocimiento muy bueno!")
    elif success_tests / total_tests >= 0.6:
        print("\n⚠️  Reconocimiento funcionando, pero con margen de mejora")
    else:
        print("\n❌ Se necesita más ajuste")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
