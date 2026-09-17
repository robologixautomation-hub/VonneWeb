# 🛒 Guía de Integración: Loyverse POS & Vonne Boutique

¡Tu página web ahora está conectada directamente con tu sistema de inventario y caja **Loyverse POS**!

---

## ⚡ ¿Cómo funciona la sincronización?

1. **Tu inventario real ya está cargado en la web:**
   - Se importaron y consolidaron las **315 variantes** del punto de venta en **194 modelos de prendas**.
   - Se agruparon las tallas (`CH, M, G, XL, XXL`) automáticamente para que la clienta seleccione su talla en una sola tarjeta elegante.
   - Precios exactos de tienda: **Blazers a $550**, vestidos, conjuntos, fajas colombianas, trajes de baño, blusas, etc.
   - Existencias activas en tiempo real: Las prendas con stock `0` se marcan como *Agotadas* o se ocultan automáticamente.

---

## 🔄 Opción 1: Actualizar inventario con 1 Clic (Archivo Local)

Cada vez que agregues prendas nuevas en tu punto de venta o quieras actualizar existencias:

1. En tu **Loyverse Back Office**, exporta tu inventario a CSV (**Artículos > Lista de artículos > Exportar**).
2. Guarda o reemplaza el archivo **`Vonne_items.csv`** en la carpeta de tu página web.
3. Da **doble clic** al archivo:
   👉 **`sincronizar_loyverse.bat`**
4. ¡Listo! En segundos, el script actualizará automáticamente `catalogo_vonne.json` y tu plantilla de Google Drive con las nuevas prendas, existencias y precios.

---

## 🌐 Opción 2: Sincronización en Vivo por API de Loyverse

Si prefieres que se conecte directamente a la nube de Loyverse sin tener que exportar archivos:

1. Inicia sesión en tu **[Loyverse Back Office](https://loyverse.com/)**.
2. Ve a **Ajustes** (o Configuración) > **Tokens de Acceso** (*Access Tokens*).
3. Haz clic en **+ Añadir token de acceso**.
4. Escribe de nombre: `Web Vonne Boutique` y guarda.
5. Copia el token generado y pégalo dentro del archivo **`loyverse_config.json`**:
   ```json
   {
     "token": "PEGA_AQUÍ_TU_TOKEN_DE_LOYVERSE"
   }
   ```
6. Da doble clic a **`sincronizar_loyverse.bat`** y se descargará automáticamente todo tu catálogo, categorías y existencias en vivo.

---

## 📸 ¿Cómo poner tus fotos de Google Drive a las prendas de Loyverse?

El sincronizador generó también el archivo [**`catalogo_google_drive.csv`**](file:///c:/Users/PC3/Documents/Antigravity/Vonne%20boutique/catalogo_google_drive.csv) que ya tiene todos tus productos reales de Loyverse:

1. Súbelo a tu **Google Drive** y ábrelo como **Google Sheets**.
2. En la columna **`foto_url`**, pega los enlaces de las fotos tomadas en la boutique (desde Google Drive con permiso de lector).
3. Publica la hoja como CSV (**Archivo > Compartir > Publicar en la web > CSV**) y pega el enlace en el botón de ajustes de tu página web.
4. ¡Tus clientas verán las prendas reales de tu punto de venta con las fotos reales de tu boutique!

---

## ⏰ Sincronización Automática Diaria a las 12:00 PM (Hora de México)

¡Ya quedó configurada la tarea programada en tu sistema de Windows!

- **Nombre de la tarea en Windows:** `VonneBoutique_Sync_12PM`
- **Frecuencia:** Todos los días a las **12:00:00 PM**.
- **Modo silencioso:** Se ejecuta 100% en segundo plano sin interrumpir lo que estés haciendo en la computadora ni abrir ventanas negras.
- **Historial de auditoría:** Cada vez que se ejecuta, guarda un registro con la fecha, hora y prendas actualizadas en el archivo [**`historial_sincronizacion.log`**](file:///c:/Users/PC3/Documents/Antigravity/Vonne%20boutique/historial_sincronizacion.log).
- **Reinstalador en 1 clic:** Si en el futuro cambias de computadora o deseas reactivarla, solo da doble clic a [**`instalar_sincronizacion_12pm.bat`**](file:///c:/Users/PC3/Documents/Antigravity/Vonne%20boutique/instalar_sincronizacion_12pm.bat).

---

## ☁️ Despliegue en GitHub + Netlify (100% en la Nube)

Para que tu sitio web se actualice a las 12:00 PM **incluso con tu computadora apagada**:

1. Sube los archivos de la carpeta `Vonne boutique` a tu repositorio de **GitHub**.
2. Conecta tu repositorio en **Netlify** (creará tu página web con dominio seguro `https://...netlify.app`).
3. Creamos el archivo de automatización [**`.github/workflows/actualizar_inventario_12pm.yml`**](file:///c:/Users/PC3/Documents/Antigravity/Vonne%20boutique/.github/workflows/actualizar_inventario_12pm.yml).
   - Todos los días a las **12:00 PM México (18:00 UTC)**, los servidores de GitHub consultarán tu API de Loyverse.
   - Si detecta cambios de inventario o precios, GitHub guardará los cambios y **Netlify reconstruirá y publicará la web actualizada en automático**.
4. En tu repositorio de GitHub, ve a **Settings > Secrets and variables > Actions** y crea un secreto llamado `LOYVERSE_TOKEN` con tu token `d746792798aa4c43888f0aa01b6351b1`.
