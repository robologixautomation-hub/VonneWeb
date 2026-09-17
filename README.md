# Vonne Boutique Saltillo - Sitio Web & Catálogo en Vivo

Sitio web oficial de **Vonne Boutique** (Plaza La Fragua, Saltillo, Coahuila).

## Características
- **Catálogo Interactivo:** Filtros por categoría (Blazers, Vestidos, Conjuntos, Fajas Colombianas).
- **Inventario Sincronizado:** Conexión con Loyverse POS para reflejar existencias reales.
- **Apartados vía WhatsApp:** Enlace directo con mensaje preformateado con las prendas seleccionadas.
- **Optimización SEO y GEO:** Schema.org estructurado (`ClothingStore`, `WebSite`, `FAQPage`) y optimización para Google AI Overviews.
- **Despliegue Continuo:** Compatible al 100% con Netlify y GitHub Pages.

## Actualización Automática (GitHub Actions)
El flujo en `.github/workflows/actualizar_inventario_12pm.yml` ejecuta diariamente a las 12:00 PM (hora de México) el script `sync_loyverse.py` para consultar la API de Loyverse y actualizar el catálogo sin necesidad de intervención manual.
