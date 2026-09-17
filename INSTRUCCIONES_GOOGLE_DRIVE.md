# 🚀 Guía: Conectar Google Drive / Google Sheets con tu Catálogo Web

Con este método podrás agregar prendas, cambiar precios, actualizar tallas y subir tus propias fotos desde tu celular o computadora usando **Google Drive y Google Sheets**. Cada cambio que hagas en tu archivo se reflejará **en automático en la página web**.

---

## 📌 Paso 1: Subir la Plantilla a tu Google Drive

1. Entra a tu [Google Drive](https://drive.google.com/).
2. Haz clic en **+ Nuevo** > **Subir archivo**.
3. Selecciona el archivo `catalogo_google_drive.csv` que está en la carpeta de tu página web.
4. Una vez subido, dale clic derecho y selecciona: **Abrir con** > **Hojas de cálculo de Google**.

*(También puedes crear una Hoja de Cálculo en blanco y copiar los encabezados de la tabla).*

---

## 📋 Paso 2: Columnas del Archivo

| Columna | ¿Qué poner? | Ejemplo |
| :--- | :--- | :--- |
| **codigo** | Código único de la prenda | `VB-101` |
| **nombre** | Nombre de la prenda | `Vestido Gala Satín Esmeralda` |
| **categoria** | Categoría para los filtros | `vestidos`, `trajes-bano`, `conjuntos`, `casual`, `blusas`, `jeans`, `accesorios`, `promociones` |
| **precio** | Precio numérico en MXN | `899` |
| **precio_original** | Precio anterior (si está en oferta, dejar en blanco si no) | `1199` |
| **tallas** | Tallas disponibles separadas por coma | `CH, M, G, XL` |
| **etiqueta** | Distintivo visual en la tarjeta | `Nuevo`, `Tendencia`, `Oferta`, `Top Ventas` |
| **foto_url** | Enlace de la foto (Google Drive, Facebook, Imgur, etc.) | *Ver Paso 3* |
| **descripcion** | Descripción de la tela, corte, ocasión | `Vestido elegante para bodas en Saltillo.` |
| **activo** | `SI` para mostrar en la web, `NO` para ocultar si se agota | `SI` |

---

## 📸 Paso 3: Cómo poner fotos desde Google Drive

1. Sube las fotos de tus prendas a una carpeta en tu **Google Drive**.
2. Dale clic derecho a la foto > **Compartir** > **Compartir**.
3. En **Acceso general**, cámbialo a: **"Cualquier persona con el enlace"** (como *Lector*).
4. Haz clic en **Copiar enlace**.
5. Pega ese enlace directamente en la columna **`foto_url`** de tu hoja de cálculo.

> [!TIP]
> **El sistema es inteligente:** El sitio web detecta automáticamente si pegas un enlace de Google Drive (ej. `https://drive.google.com/file/d/1A2B3C.../view?usp=sharing`) y lo convierte en automático para que la foto se muestre directo y rápido en la página web.

---

## 🌐 Paso 4: Publicar la Hoja en la Web (Solo se hace 1 vez)

Para que la página web pueda leer tus prendas en tiempo real:

1. En tu Hoja de Cálculo de Google, ve al menú superior:
   👉 **Archivo** > **Compartir** > **Publicar en la web**.
2. En la ventana que se abre:
   - En el primer menú desplegable, selecciona tu hoja (o *Todo el documento*).
   - En el segundo menú que dice *"Página web"*, cámbialo a: **Valores separados por comas (.csv)**.
3. Haz clic en el botón verde **Publicar** y confirma.
4. **Copia el enlace que te genera** (empieza con `https://docs.google.com/spreadsheets/d/e/.../pub?output=csv`).

---

## 🔗 Paso 5: Vincular el Enlace a tu Página Web

Tienes **dos opciones muy fáciles**:

### Opción A (Desde la misma página web, sin tocar código):
1. Abre tu página web `index.html` en tu navegador.
2. En la esquina inferior izquierda o en la barra superior verás el botón: **⚙️ Conectar Google Sheets**.
3. Pega el enlace que copiaste en el Paso 4 y presiona **Guardar**.
4. ¡Listo! El catálogo se actualizará inmediatamente con tus datos de Google Drive.

### Opción B (Guardarlo permanente en `app.js`):
Abre `app.js` y en la parte superior pega tu enlace en la variable:
```javascript
const BOUTIQUE_CONFIG = {
  ...
  googleSheetCsvUrl: "PEGA_AQUÍ_TU_ENLACE_CSV_PUBLICADO",
  ...
};
```

---

## ⚡ ¿Cómo funciona la actualización automática?

- Cada vez que una clienta entre a tu página web o recargue la página, el sitio consultará tu Google Sheet.
- Si agregas una prenda nueva, cambias un precio de $899 a $799, o pones `activo = NO` a una prenda agotada, **se actualizará en automático** sin tener que volver a editar la página web.
