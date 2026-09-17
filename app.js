/**
 * VONNE BOUTIQUE - SALTILLO
 * Script de Catálogo, Carrito de Apartado e Integraciones WhatsApp & Redes
 * 
 * Sincronización Automática con Google Drive / Google Sheets:
 * - Permite cargar prendas, fotos, precios y descripciones directamente desde una hoja de cálculo.
 * - Convierte automáticamente enlaces de Google Drive en imágenes visibles.
 */

// Configuración general de la boutique
const BOUTIQUE_CONFIG = {
  name: "Vonne Boutique Saltillo",
  phone: "528444551868", // +52 844 455 1868
  phoneDisplay: "(844) 455-1868",
  facebookUrl: "https://www.facebook.com/VonneBoutique",
  mapsUrl: "https://maps.app.goo.gl/fAytGUAwGXgLNex69",
  address: "José María La Fragua #2151A, Col. Guanajuato, Saltillo, Coahuila de Zaragoza",
  plaza: "Plaza La Fragua (esq. Blvd. Jesús Valdés Sánchez)",
  postalCode: "25280",
  // Pega aquí tu enlace publicado de Google Sheets CSV o configúralo desde la ventana de ajustes en la web
  googleSheetCsvUrl: localStorage.getItem("vonne_google_sheet_csv_url") || "",
  schedule: {
    weekdays: { open: 12, close: 20, text: "Lunes a Viernes: 12:00 PM - 8:00 PM" },
    saturday: { open: 11, close: 19, text: "Sábados: 11:00 AM - 7:00 PM" },
    sunday: { open: null, close: null, text: "Domingos: Cerrado" }
  }
};

// Catálogo base: Se alimenta exclusivamente de las prendas reales con foto y existencias de Loyverse
const DEFAULT_PRODUCTS = [];

// Función auxiliar para formatear prendas del catálogo Loyverse
function mapLoyverseProduct(p, idx) {
  return {
    id: `pos-${p.codigo || idx}`,
    code: p.codigo || `VB-${idx + 1}`,
    name: p.nombre,
    category: p.categoria || "casual",
    price: p.precio,
    originalPrice: p.precio_original || null,
    badge: p.etiqueta || (p.stock > 0 ? "En Tienda" : "Agotado"),
    image: formatDriveImageUrl(p.foto_url),
    sizes: Array.isArray(p.tallas) && p.tallas.length ? p.tallas : ["UNITALLA"],
    description: p.descripcion || `Prenda disponible en Vonne Boutique (Plaza La Fragua, Saltillo).`,
    stock: p.stock !== undefined ? p.stock : 1
  };
}

// Productos en memoria (se inicializan con el inventario real de Loyverse cargado en catalogo_data.js)
let PRODUCTS = (typeof window !== "undefined" && window.VONNE_CATALOGO_DATA && Array.isArray(window.VONNE_CATALOGO_DATA) && window.VONNE_CATALOGO_DATA.length > 0)
  ? window.VONNE_CATALOGO_DATA.map(mapLoyverseProduct)
  : [...DEFAULT_PRODUCTS];

// Estado de la aplicación
let currentCategory = "todos";
let currentSearch = "";
let selectedProductForModal = null;
let shoppingBag = JSON.parse(localStorage.getItem("vonne_boutique_bag") || "[]");

// Elementos del DOM
document.addEventListener("DOMContentLoaded", async () => {
  initStoreStatus();
  setupFilterTabs();
  setupSearch();
  setupBagDrawer();
  updateBagUI();
  setupQuickViewModal();
  setupFaqAccordion();
  setupDriveSyncModal();

  // Cargar catálogo unificado con prioridad diferida para no competir con el primer renderizado (FCP/LCP)
  if ("requestIdleCallback" in window) {
    requestIdleCallback(() => loadCatalog(), { timeout: 200 });
  } else {
    setTimeout(() => loadCatalog(), 60);
  }
});

// =========================================================================
// CONVERTIDOR INTELIGENTE DE ENLACES DE GOOGLE DRIVE A IMAGEN DIRECTA
// =========================================================================
function formatDriveImageUrl(url) {
  if (!url || typeof url !== "string") {
    return "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80";
  }

  const cleanUrl = url.trim();

  // Caso 1: Enlace común de Google Drive: https://drive.google.com/file/d/FILE_ID/view...
  const matchFileD = cleanUrl.match(/drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)/);
  if (matchFileD && matchFileD[1]) {
    return `https://lh3.googleusercontent.com/d/${matchFileD[1]}=w1000`;
  }

  // Caso 2: Enlace con parámetro ?id=FILE_ID
  const matchIdParam = cleanUrl.match(/drive\.google\.com\/.*?id=([a-zA-Z0-9_-]+)/);
  if (matchIdParam && matchIdParam[1]) {
    return `https://lh3.googleusercontent.com/d/${matchIdParam[1]}=w1000`;
  }

  // Si no es Google Drive, regresa la URL tal cual
  return cleanUrl;
}

// =========================================================================
// CARGADOR UNIFICADO: LOYVERSE POS + GOOGLE DRIVE
// =========================================================================
async function loadCatalog() {
  const syncStatusEl = document.getElementById("drive-sync-status");
  const sheetUrl = localStorage.getItem("vonne_google_sheet_csv_url") || BOUTIQUE_CONFIG.googleSheetCsvUrl;

  // 1. Si hay URL configurada de Google Sheets CSV, intentamos sincronizar con ella
  if (sheetUrl) {
    if (syncStatusEl) {
      syncStatusEl.innerHTML = `
        <span class="inline-flex items-center gap-1.5 text-[11px] text-stone-600 bg-stone-100 px-2.5 py-1 rounded-full border border-stone-200 animate-pulse">
          <i class="fas fa-sync-alt fa-spin text-stone-500"></i>
          <span>Actualizando catálogo...</span>
        </span>
      `;
    }
    try {
      const response = await fetch(sheetUrl, { cache: "no-cache" });
      if (response.ok) {
        const csvText = await response.text();
        const parsedProducts = parseCSV(csvText);

        if (parsedProducts && parsedProducts.length > 0) {
          PRODUCTS = parsedProducts;
          if (syncStatusEl) {
            syncStatusEl.innerHTML = `
              <span class="inline-flex items-center gap-1 text-[11px] text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                <i class="fas fa-check-circle text-emerald-600"></i>
                <span>Catálogo en línea (${parsedProducts.length} prendas)</span>
              </span>
            `;
          }
          renderProducts();
          return;
        }
      }
    } catch (error) {
      console.warn("Fallo al conectar con Google Sheets, recurriendo a inventario Loyverse:", error);
    }
  }

  // 2. Cargar inventario real consolidado de Loyverse POS
  let rawItems = (typeof window !== "undefined" && window.VONNE_CATALOGO_DATA && Array.isArray(window.VONNE_CATALOGO_DATA) && window.VONNE_CATALOGO_DATA.length > 0)
    ? window.VONNE_CATALOGO_DATA
    : null;

  if (!rawItems) {
    try {
      const jsonResp = await fetch("./catalogo_vonne.json", { cache: "no-cache" });
      if (jsonResp.ok) {
        rawItems = await jsonResp.json();
      }
    } catch (error) {
      console.warn("Fallo lectura catalogo_vonne.json via fetch:", error);
    }
  }

  if (rawItems && Array.isArray(rawItems) && rawItems.length > 0) {
    PRODUCTS = rawItems.map(mapLoyverseProduct);

    if (syncStatusEl) {
      const inStockCount = PRODUCTS.filter(p => (p.stock || 0) > 0).length;
      syncStatusEl.innerHTML = `
        <span class="inline-flex items-center gap-1.5 text-[11px] text-emerald-800 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200 shadow-xs">
          <i class="fas fa-check-circle text-emerald-600"></i>
          <span>Inventario en vivo (${inStockCount} prendas disponibles)</span>
        </span>
      `;
    }
    renderProducts();
    return;
  }

  // 3. Fallback: Catálogo local estático
  PRODUCTS = [...DEFAULT_PRODUCTS];
  if (syncStatusEl) {
    syncStatusEl.innerHTML = `
      <span class="inline-flex items-center gap-1 text-[11px] text-stone-600 bg-stone-100 px-2.5 py-1 rounded-full border border-stone-200">
        <i class="fas fa-check-circle text-emerald-600"></i>
        <span>Prendas disponibles en boutique</span>
      </span>
    `;
  }
  renderProducts();
}

// Parser robusto de CSV que soporta comas entre comillas
function parseCSV(text) {
  const lines = [];
  let row = [];
  let inQuotes = false;
  let currentToken = '';

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const nextChar = text[i + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        currentToken += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      row.push(currentToken.trim());
      currentToken = '';
    } else if ((char === '\r' || char === '\n') && !inQuotes) {
      if (char === '\r' && nextChar === '\n') i++;
      row.push(currentToken.trim());
      if (row.some(field => field.length > 0)) {
        lines.push(row);
      }
      row = [];
      currentToken = '';
    } else {
      currentToken += char;
    }
  }

  if (currentToken.length > 0 || row.length > 0) {
    row.push(currentToken.trim());
    if (row.some(field => field.length > 0)) {
      lines.push(row);
    }
  }

  if (lines.length < 2) return [];

  // Mapear encabezados
  const headers = lines[0].map(h => h.toLowerCase().trim().replace(/[\s_-]+/g, ''));
  const getIndex = (name) => headers.findIndex(h => h.includes(name));

  const idxCodigo = getIndex("codigo") > -1 ? getIndex("codigo") : 0;
  const idxNombre = getIndex("nombre") > -1 ? getIndex("nombre") : 1;
  const idxCat = getIndex("cat") > -1 ? getIndex("cat") : 2;
  const idxPrecio = getIndex("precio") > -1 ? getIndex("precio") : 3;
  const idxPrecioOrig = getIndex("original") > -1 ? getIndex("original") : -1;
  const idxTallas = getIndex("talla") > -1 ? getIndex("talla") : 5;
  const idxEtiqueta = getIndex("etiqueta") > -1 ? getIndex("etiqueta") : (getIndex("badge") > -1 ? getIndex("badge") : 6);
  const idxFoto = getIndex("foto") > -1 ? getIndex("foto") : (getIndex("image") > -1 ? getIndex("image") : 7);
  const idxDesc = getIndex("desc") > -1 ? getIndex("desc") : 8;
  const idxActivo = getIndex("activo") > -1 ? getIndex("activo") : -1;

  const products = [];

  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i];
    if (!cols[idxNombre] || cols[idxNombre].trim() === '') continue;

    // Verificar si está activo (por defecto SI)
    if (idxActivo > -1 && cols[idxActivo]) {
      const valActivo = cols[idxActivo].trim().toUpperCase();
      if (valActivo === 'NO' || valActivo === 'FALSE' || valActivo === '0') {
        continue; // Ocultar prenda no activa
      }
    }

    const priceNum = parseFloat(cols[idxPrecio]?.replace(/[^0-9.]/g, '') || '0');
    let origPriceNum = null;
    if (idxPrecioOrig > -1 && cols[idxPrecioOrig]) {
      const parsed = parseFloat(cols[idxPrecioOrig].replace(/[^0-9.]/g, '') || '');
      if (!isNaN(parsed) && parsed > priceNum) {
        origPriceNum = parsed;
      }
    }

    const sizesArr = (cols[idxTallas] || "Unitalla")
      .split(/[,/|-]/)
      .map(s => s.trim())
      .filter(s => s.length > 0);

    const rawCategory = (cols[idxCat] || "casual").toLowerCase().trim().replace(/[\s_]+/g, '-');
    const rawImage = cols[idxFoto] || "";
    const cleanImage = formatDriveImageUrl(rawImage);

    products.push({
      id: `prod-drive-${i}`,
      code: cols[idxCodigo] || `VB-${i}`,
      name: cols[idxNombre],
      category: rawCategory,
      price: priceNum || 0,
      originalPrice: origPriceNum,
      badge: cols[idxEtiqueta] || "Disponible",
      image: cleanImage,
      sizes: sizesArr.length ? sizesArr : ["Unitalla"],
      description: cols[idxDesc] || "Prenda disponible en Vonne Boutique Saltillo (Plaza La Fragua)."
    });
  }

  return products;
}

// =========================================================================
// ESTADO EN TIEMPO REAL DE LA TIENDA
// =========================================================================
function initStoreStatus() {
  const statusContainers = document.querySelectorAll(".store-live-status");
  if (!statusContainers.length) return;

  const now = new Date();
  const day = now.getDay();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const currentTime = hour + minute / 60;

  let isOpen = false;
  let message = "";

  if (day >= 1 && day <= 5) {
    if (currentTime >= BOUTIQUE_CONFIG.schedule.weekdays.open && currentTime < BOUTIQUE_CONFIG.schedule.weekdays.close) {
      isOpen = true;
      message = "Abierto hoy hasta las 8:00 PM";
    } else if (currentTime < BOUTIQUE_CONFIG.schedule.weekdays.open) {
      message = "Cerrado • Abre hoy a las 12:00 PM";
    } else {
      message = "Cerrado por hoy • Abre mañana a las 12:00 PM";
    }
  } else if (day === 6) {
    if (currentTime >= BOUTIQUE_CONFIG.schedule.saturday.open && currentTime < BOUTIQUE_CONFIG.schedule.saturday.close) {
      isOpen = true;
      message = "Abierto hoy hasta las 7:00 PM";
    } else if (currentTime < BOUTIQUE_CONFIG.schedule.saturday.open) {
      message = "Cerrado • Abre hoy a las 11:00 AM";
    } else {
      message = "Cerrado por hoy • Reanudamos el Lunes a las 12:00 PM";
    }
  } else {
    message = "Domingo cerrado • Te esperamos el Lunes a las 12:00 PM";
  }

  statusContainers.forEach(container => {
    container.innerHTML = `
      <div class="status-indicator ${isOpen ? 'status-open' : 'status-closed'}">
        <span class="status-dot"></span>
        <span>${isOpen ? 'Tienda Abierta' : 'Tienda Cerrada'}</span>
        <span class="text-xs opacity-75 font-normal">(${message})</span>
      </div>
    `;
  });
}

// =========================================================================
// RENDERIZADO DE PRODUCTOS
// =========================================================================
function renderProducts() {
  const grid = document.getElementById("products-grid");
  const countSpan = document.getElementById("products-count");
  if (!grid) return;

  let filtered = PRODUCTS.filter(product => {
    // FILTRO ESTRICTO: Excluir prendas sin foto o sin inventario
    if (!product.image || product.image.trim() === "" || product.image.includes("unsplash")) return false;
    if (product.stock !== undefined && product.stock <= 0) return false;

    let matchesCategory = false;
    const cat = (product.category || "").toLowerCase();
    const name = (product.name || "").toLowerCase();

    if (currentCategory === "todos") {
      matchesCategory = true;
    } else if (currentCategory === "blazers") {
      matchesCategory = cat === "blazers" || name.includes("blazer");
    } else if (currentCategory === "vestidos") {
      matchesCategory = cat === "vestidos" || name.includes("vestido") || name.includes("palazo");
    } else if (currentCategory === "conjuntos") {
      matchesCategory = cat === "conjuntos" || name.includes("conjunto");
    } else if (currentCategory === "blusas") {
      matchesCategory = cat === "blusas" || name.includes("blusa") || name.includes("camisa");
    } else if (currentCategory === "pantalones-faldas") {
      matchesCategory = cat === "pantalones-faldas" || cat === "jeans" || 
                        name.includes("falda") || name.includes("pantalon") ||
                        name.includes("pantalón") || name.includes("short") ||
                        name.includes("leggin");
    } else if (currentCategory === "fajas") {
      matchesCategory = cat === "fajas" || name.includes("faja") || name.includes("cinturilla");
    } else if (currentCategory === "trajes-bano") {
      matchesCategory = cat === "trajes-bano" || name.includes("baño") || name.includes("bano") ||
                        name.includes("bikini") || name.includes("pareo") || name.includes("short de agua");
    } else if (currentCategory === "abrigos-chalecos") {
      matchesCategory = cat === "abrigos-chalecos" || name.includes("capa") || name.includes("chaleco") ||
                        name.includes("abrigo") || name.includes("sueter") || name.includes("suéter");
    } else if (currentCategory === "promociones") {
      matchesCategory = cat === "promociones" || product.originalPrice || (product.badge && (product.badge.toLowerCase().includes("oferta") || product.badge.toLowerCase().includes("liquid") || product.badge.toLowerCase().includes("promo")));
    } else {
      matchesCategory = cat === currentCategory;
    }

    const matchesSearch = product.name.toLowerCase().includes(currentSearch.toLowerCase()) ||
                          product.code.toLowerCase().includes(currentSearch.toLowerCase()) ||
                          product.description.toLowerCase().includes(currentSearch.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  if (countSpan) {
    countSpan.textContent = `${filtered.length} prenda${filtered.length === 1 ? '' : 's'}`;
  }

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full text-center py-16 px-4">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-stone-100 text-stone-400 mb-4">
          <i class="fas fa-search text-2xl"></i>
        </div>
        <h3 class="text-xl font-medium text-stone-700 font-serif-luxury">No encontramos prendas en esta sección</h3>
        <p class="text-stone-500 text-sm mt-1">Intenta con otra categoría o palabra clave.</p>
        <button onclick="resetFilters()" class="mt-4 px-5 py-2 text-sm bg-stone-800 text-white rounded-full hover:bg-stone-700 transition">
          Ver todo el catálogo
        </button>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(product => {
    const isOutOfStock = product.stock !== undefined && product.stock <= 0;
    const isSale = product.category === 'promociones' || product.originalPrice;
    let badgeClass = isSale ? 'badge-sale' : 'badge-gold';
    let badgeText = product.badge;

    if (isOutOfStock) {
      badgeClass = 'bg-stone-200 text-stone-600 border border-stone-300';
      badgeText = 'Agotado';
    }

    return `
      <div class="product-card group bg-white rounded-2xl overflow-hidden border border-stone-200/80 shadow-sm flex flex-col justify-between" data-id="${product.id}">
        <div>
          <!-- Contenedor Imagen -->
          <div class="product-img-wrapper aspect-[3/4] w-full relative">
            <img 
              src="${product.image}" 
              alt="${product.name}" 
              loading="lazy"
              onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80';"
              class="w-full h-full object-cover object-center"
            />
            <!-- Badge -->
            <div class="absolute top-3 left-3 z-10">
              <span class="px-2.5 py-1 text-xs uppercase tracking-wider rounded-full shadow-sm ${badgeClass}">
                ${badgeText}
              </span>
            </div>

            <!-- Código -->
            <div class="absolute top-3 right-3 z-10">
              <span class="px-2 py-0.5 text-[11px] bg-white/90 backdrop-blur font-mono text-stone-600 rounded">
                ${product.code}
              </span>
            </div>

            <!-- Botón flotante de Vista Rápida -->
            <button 
              onclick="openQuickView('${product.id}')"
              class="absolute inset-x-4 bottom-4 py-2.5 bg-white/95 backdrop-blur-md text-stone-800 text-xs font-semibold tracking-wider uppercase rounded-xl opacity-0 group-hover:opacity-100 transition-all duration-300 shadow-md flex items-center justify-center gap-2 hover:bg-stone-900 hover:text-white"
            >
              <i class="far fa-eye"></i> Vista Rápida
            </button>
          </div>

          <!-- Información de la prenda -->
          <div class="p-4 sm:p-5">
            <div class="flex items-center justify-between text-xs text-stone-400 mb-1">
              <span class="uppercase tracking-widest text-[10px] font-medium text-stone-500">${product.category}</span>
              <span>Tallas: ${product.sizes.join(', ')}</span>
            </div>
            
            <h3 class="font-medium text-stone-800 text-base leading-snug group-hover:text-amber-900 transition-colors line-clamp-1 font-serif-luxury text-lg">
              ${product.name}
            </h3>

            <!-- Precios -->
            <div class="mt-2.5 flex items-baseline gap-2">
              <span class="text-xl font-bold text-stone-900">
                $${product.price} <span class="text-xs font-normal text-stone-500">MXN</span>
              </span>
              ${product.originalPrice ? `
                <span class="text-sm line-through text-stone-400">
                  $${product.originalPrice}
                </span>
              ` : ''}
            </div>
          </div>
        </div>

        <!-- Acciones inferiores -->
        <div class="p-4 pt-0 sm:p-5 sm:pt-0 flex gap-2">
          <button 
            onclick="openQuickView('${product.id}')"
            class="flex-1 py-2.5 px-3 bg-stone-900 hover:bg-stone-800 text-white text-xs font-medium tracking-wider rounded-xl transition flex items-center justify-center gap-1.5"
          >
            <i class="fas fa-shopping-bag text-xs opacity-80"></i> Apartar / Ver
          </button>
          <button 
            onclick="askDirectWhatsApp('${product.id}')"
            title="Preguntar por WhatsApp"
            class="w-10 h-10 flex items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 hover:bg-emerald-600 hover:text-white transition border border-emerald-200"
          >
            <i class="fab fa-whatsapp text-lg"></i>
          </button>
        </div>
      </div>
    `;
  }).join("");
}

// =========================================================================
// PESTAÑAS DE CATEGORÍA & BÚSQUEDA
// =========================================================================
function setupFilterTabs() {
  const tabs = document.querySelectorAll(".category-tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => {
        t.classList.remove("bg-stone-900", "text-white", "shadow-sm");
        t.classList.add("bg-stone-100", "text-stone-600");
      });
      tab.classList.add("bg-stone-900", "text-white", "shadow-sm");
      tab.classList.remove("bg-stone-100", "text-stone-600");

      currentCategory = tab.dataset.category || "todos";
      renderProducts();
    });
  });
}

function resetFilters() {
  currentCategory = "todos";
  currentSearch = "";
  const searchInput = document.getElementById("catalog-search");
  if (searchInput) searchInput.value = "";

  const tabs = document.querySelectorAll(".category-tab-btn");
  tabs.forEach(t => {
    if (t.dataset.category === "todos") {
      t.classList.add("bg-stone-900", "text-white");
      t.classList.remove("bg-stone-100", "text-stone-600");
    } else {
      t.classList.remove("bg-stone-900", "text-white");
      t.classList.add("bg-stone-100", "text-stone-600");
    }
  });

  renderProducts();
}

function setupSearch() {
  const searchInput = document.getElementById("catalog-search");
  if (!searchInput) return;

  searchInput.addEventListener("input", (e) => {
    currentSearch = e.target.value.trim();
    renderProducts();
  });
}

// =========================================================================
// MODAL DE VISTA RÁPIDA
// =========================================================================
function setupQuickViewModal() {
  const modal = document.getElementById("quickview-modal");
  const closeBtn = document.getElementById("close-quickview-btn");
  const backdrop = document.getElementById("quickview-backdrop");

  if (closeBtn) closeBtn.addEventListener("click", closeQuickView);
  if (backdrop) backdrop.addEventListener("click", closeQuickView);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
      closeQuickView();
    }
  });
}

function openQuickView(productId) {
  const product = PRODUCTS.find(p => p.id === productId);
  if (!product) return;

  selectedProductForModal = product;
  const modal = document.getElementById("quickview-modal");
  if (!modal) return;

  const imgEl = document.getElementById("qv-image");
  imgEl.src = product.image;
  imgEl.alt = product.name;
  imgEl.onerror = () => { imgEl.src = "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80"; };

  document.getElementById("qv-badge").textContent = product.badge;
  document.getElementById("qv-code").textContent = `Código: ${product.code}`;
  document.getElementById("qv-name").textContent = product.name;
  document.getElementById("qv-description").textContent = product.description;
  document.getElementById("qv-price").textContent = `$${product.price} MXN`;

  const origPriceEl = document.getElementById("qv-original-price");
  if (product.originalPrice) {
    origPriceEl.textContent = `$${product.originalPrice} MXN`;
    origPriceEl.classList.remove("hidden");
  } else {
    origPriceEl.classList.add("hidden");
  }

  const sizesContainer = document.getElementById("qv-sizes-container");
  sizesContainer.innerHTML = product.sizes.map((size, index) => `
    <button 
      type="button"
      onclick="selectQuickViewSize('${size}')" 
      class="qv-size-btn px-4 py-2 border rounded-xl text-sm font-medium transition ${index === 0 ? 'bg-stone-900 text-white border-stone-900 active' : 'bg-stone-50 border-stone-200 text-stone-700 hover:border-stone-400'}"
      data-size="${size}"
    >
      ${size}
    </button>
  `).join("");

  modal.classList.remove("hidden");
  document.body.classList.add("overflow-hidden");
}

function selectQuickViewSize(size) {
  const btns = document.querySelectorAll(".qv-size-btn");
  btns.forEach(btn => {
    if (btn.dataset.size === size) {
      btn.classList.add("bg-stone-900", "text-white", "border-stone-900", "active");
      btn.classList.remove("bg-stone-50", "border-stone-200", "text-stone-700");
    } else {
      btn.classList.remove("bg-stone-900", "text-white", "border-stone-900", "active");
      btn.classList.add("bg-stone-50", "border-stone-200", "text-stone-700");
    }
  });
}

function closeQuickView() {
  const modal = document.getElementById("quickview-modal");
  if (modal) modal.classList.add("hidden");
  document.body.classList.remove("overflow-hidden");
}

function addCurrentModalToBag() {
  if (!selectedProductForModal) return;

  const activeSizeBtn = document.querySelector(".qv-size-btn.active");
  const chosenSize = activeSizeBtn ? activeSizeBtn.dataset.size : selectedProductForModal.sizes[0];

  addItemToBag(selectedProductForModal, chosenSize);
  closeQuickView();
  openBagDrawer();
  showToast(`¡${selectedProductForModal.name} agregada a tu bolsa de apartado!`);
}

function askCurrentModalWhatsApp() {
  if (!selectedProductForModal) return;

  const activeSizeBtn = document.querySelector(".qv-size-btn.active");
  const chosenSize = activeSizeBtn ? activeSizeBtn.dataset.size : selectedProductForModal.sizes[0];

  const text = `¡Hola Vonne Boutique! 👋 Me interesa la prenda *${selectedProductForModal.name}* (Código: ${selectedProductForModal.code}) en Talla *${chosenSize}* ($${selectedProductForModal.price} MXN). ¿La tienen en perchero hoy para pasar a probármela a su tienda de Plaza La Fragua?`;
  window.open(`https://wa.me/${BOUTIQUE_CONFIG.phone}?text=${encodeURIComponent(text)}`, '_blank');
}

function askDirectWhatsApp(productId) {
  const product = PRODUCTS.find(p => p.id === productId);
  if (!product) return;

  const text = `¡Hola Vonne Boutique! 👋 Vi la prenda *${product.name}* en su página web ($${product.price} MXN). ¿La tienen disponible en perchero hoy en Plaza La Fragua para pasar a verla?`;
  window.open(`https://wa.me/${BOUTIQUE_CONFIG.phone}?text=${encodeURIComponent(text)}`, '_blank');
}

// =========================================================================
// BOLSA / CARRITO DE APARTADO
// =========================================================================
function addItemToBag(product, size) {
  const existingIndex = shoppingBag.findIndex(item => item.id === product.id && item.size === size);

  if (existingIndex > -1) {
    shoppingBag[existingIndex].quantity += 1;
  } else {
    shoppingBag.push({
      id: product.id,
      name: product.name,
      code: product.code,
      price: product.price,
      size: size,
      image: product.image,
      quantity: 1
    });
  }

  updateBagBadge();
  renderBagItems();
  saveBagToLocalStorage();
}

function removeItemFromBag(index) {
  shoppingBag.splice(index, 1);
  updateBagBadge();
  renderBagItems();
  saveBagToLocalStorage();
}

function changeBagItemQuantity(index, delta) {
  if (!shoppingBag[index]) return;
  shoppingBag[index].quantity += delta;
  if (shoppingBag[index].quantity <= 0) {
    removeItemFromBag(index);
    return;
  }
  updateBagBadge();
  renderBagItems();
  saveBagToLocalStorage();
}

function saveBagToLocalStorage() {
  try {
    localStorage.setItem("vonne_boutique_bag", JSON.stringify(shoppingBag));
  } catch (e) {
    console.error("Error guardando bolsa en localStorage:", e);
  }
}

function clearBag() {
  shoppingBag = [];
  saveBagToLocalStorage();
  updateBagBadge();
  renderBagItems();
  showToast("Tu bolsa de apartado ha sido vaciada.");
}

async function loadProductsFromGoogleSheets() {
  await loadCatalog();
}

function updateBagBadge() {
  const totalCount = shoppingBag.reduce((sum, item) => sum + (item.quantity || 1), 0);
  const badges = document.querySelectorAll(".bag-count-badge, .bag-badge-count");
  badges.forEach(b => {
    b.textContent = totalCount;
    if (totalCount > 0) {
      b.classList.remove("hidden");
    } else {
      b.classList.add("hidden");
    }
  });
}

function renderBagItems() {
  const container = document.getElementById("bag-items-list");
  const emptyState = document.getElementById("bag-empty-state");
  const footer = document.getElementById("bag-footer");
  const totalDisplay = document.getElementById("bag-total-amount");

  if (!container) return;

  if (shoppingBag.length === 0) {
    container.innerHTML = "";
    if (emptyState) emptyState.classList.remove("hidden");
    if (footer) footer.classList.add("hidden");
    return;
  }

  if (emptyState) emptyState.classList.add("hidden");
  if (footer) footer.classList.remove("hidden");

  let totalMoney = 0;
  container.innerHTML = shoppingBag.map((item, index) => {
    const subtotal = item.price * item.quantity;
    totalMoney += subtotal;

    return `
      <div class="flex items-center gap-3 p-3 bg-stone-50 rounded-2xl border border-stone-100">
        <img src="${item.image}" alt="${item.name}" class="w-16 h-20 object-cover rounded-xl bg-stone-200" onerror="this.src='https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=400&q=80'" />
        <div class="flex-1 min-w-0">
          <h4 class="text-xs font-bold text-stone-900 truncate">${item.name}</h4>
          <p class="text-[11px] text-stone-500">Talla: <span class="font-semibold text-stone-800">${item.size}</span> • $${item.price} c/u</p>
          
          <div class="flex items-center gap-2 mt-2">
            <button onclick="changeBagItemQuantity(${index}, -1)" class="w-6 h-6 rounded-lg bg-white border border-stone-200 text-stone-600 flex items-center justify-center text-xs hover:bg-stone-100 font-bold">-</button>
            <span class="text-xs font-bold text-stone-800">${item.quantity}</span>
            <button onclick="changeBagItemQuantity(${index}, 1)" class="w-6 h-6 rounded-lg bg-white border border-stone-200 text-stone-600 flex items-center justify-center text-xs hover:bg-stone-100 font-bold">+</button>
          </div>
        </div>
        <div class="text-right">
          <span class="text-xs font-bold text-stone-900 block">$${subtotal}</span>
          <button onclick="removeItemFromBag(${index})" class="text-stone-400 hover:text-red-600 text-xs mt-2 transition" title="Eliminar"><i class="fas fa-trash-alt"></i></button>
        </div>
      </div>
    `;
  }).join("");

  if (totalDisplay) {
    totalDisplay.textContent = `$${totalMoney} MXN`;
  }
}

function checkoutViaWhatsApp() {
  if (shoppingBag.length === 0) return;

  let totalMoney = 0;
  let itemsText = shoppingBag.map((item, i) => {
    const subtotal = item.price * item.quantity;
    totalMoney += subtotal;
    return `${i + 1}. *${item.name}* (Cód: ${item.code})\n   - Talla: ${item.size}\n   - Cantidad: ${item.quantity}\n   - Subtotal: $${subtotal} MXN`;
  }).join("\n\n");

  const message = 
`¡Hola *Vonne Boutique*! 👋✨
Vi estas prendas en su página web y quisiera confirmar si las tienen en perchero hoy para pasar a probármelas a Plaza La Fragua:

${itemsText}

━━━━━━━━━━━━━━━━━━━━
*Total:* $${totalMoney} MXN
━━━━━━━━━━━━━━━━━━━━

¿En qué horario me pueden atender hoy en la boutique? ¡Muchas gracias!`;

  window.open(`https://wa.me/${BOUTIQUE_CONFIG.phone}?text=${encodeURIComponent(message)}`, '_blank');
}

function updateBagUI() {
  updateBagBadge();
  renderBagItems();
}

function setupBagDrawer() {
  const openButtons = document.querySelectorAll(".open-bag-btn");
  const closeButton = document.getElementById("close-bag-btn");
  const backdrop = document.getElementById("bag-drawer-backdrop");

  openButtons.forEach(btn => btn.addEventListener("click", openBagDrawer));
  if (closeButton) closeButton.addEventListener("click", closeBagDrawer);
  if (backdrop) backdrop.addEventListener("click", closeBagDrawer);
}

function openBagDrawer() {
  const drawer = document.getElementById("bag-drawer");
  const backdrop = document.getElementById("bag-drawer-backdrop");
  if (drawer) {
    drawer.classList.remove("translate-x-full");
    drawer.style.transform = "translateX(0)";
  }
  if (backdrop) backdrop.classList.remove("hidden");
  document.body.classList.add("overflow-hidden");
}

function closeBagDrawer() {
  const drawer = document.getElementById("bag-drawer");
  const backdrop = document.getElementById("bag-drawer-backdrop");
  if (drawer) {
    drawer.classList.add("translate-x-full");
    drawer.style.transform = "translateX(100%)";
  }
  if (backdrop) backdrop.classList.add("hidden");
  document.body.classList.remove("overflow-hidden");
}

// =========================================================================
// CONFIGURACIÓN DE VINCULACIÓN CON GOOGLE DRIVE / SHEETS (MODAL EN LA WEB)
// =========================================================================
function setupDriveSyncModal() {
  const modal = document.getElementById("drive-sync-modal");
  const openBtns = document.querySelectorAll(".open-drive-sync-btn");
  const closeBtn = document.getElementById("close-drive-sync-btn");
  const backdrop = document.getElementById("drive-sync-backdrop");
  const saveBtn = document.getElementById("save-drive-url-btn");
  const clearBtn = document.getElementById("clear-drive-url-btn");
  const input = document.getElementById("drive-url-input");

  openBtns.forEach(b => b.addEventListener("click", openDriveSyncModal));
  if (closeBtn) closeBtn.addEventListener("click", closeDriveSyncModal);
  if (backdrop) backdrop.addEventListener("click", closeDriveSyncModal);

  if (saveBtn && input) {
    saveBtn.addEventListener("click", async () => {
      const url = input.value.trim();
      if (!url) {
        alert("Por favor ingresa el enlace de tu Google Sheet publicado como CSV.");
        return;
      }
      localStorage.setItem("vonne_google_sheet_csv_url", url);
      closeDriveSyncModal();
      showToast("¡Enlace de Google Drive guardado! Sincronizando catálogo...");
      await loadProductsFromGoogleSheets();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      if (confirm("¿Deseas desconectar el enlace de Google Sheets y volver al catálogo base?")) {
        localStorage.removeItem("vonne_google_sheet_csv_url");
        if (input) input.value = "";
        closeDriveSyncModal();
        showToast("Enlace eliminado. Restaurando catálogo base.");
        await loadProductsFromGoogleSheets();
      }
    });
  }
}

function openDriveSyncModal() {
  const modal = document.getElementById("drive-sync-modal");
  const input = document.getElementById("drive-url-input");
  if (!modal) return;

  const currentUrl = localStorage.getItem("vonne_google_sheet_csv_url") || BOUTIQUE_CONFIG.googleSheetCsvUrl;
  if (input) input.value = currentUrl;

  modal.classList.remove("hidden");
  document.body.classList.add("overflow-hidden");
}

function closeDriveSyncModal() {
  const modal = document.getElementById("drive-sync-modal");
  if (modal) modal.classList.add("hidden");
  document.body.classList.remove("overflow-hidden");
}

// =========================================================================
// TOAST & FAQ
// =========================================================================
function showToast(message) {
  const existing = document.getElementById("vonne-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "vonne-toast";
  toast.className = "fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-stone-900 text-white px-5 py-3 rounded-2xl shadow-xl flex items-center gap-3 text-sm animate-fade-in border border-stone-700/50";
  toast.innerHTML = `
    <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
    <span>${message}</span>
  `;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = "opacity 0.4s ease";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 400);
  }, 2800);
}

function setupFaqAccordion() {
  const faqItems = document.querySelectorAll(".faq-toggle");
  faqItems.forEach(item => {
    item.addEventListener("click", () => {
      const content = item.nextElementSibling;
      const icon = item.querySelector(".faq-icon");

      const isExpanded = !content.classList.contains("hidden");

      document.querySelectorAll(".faq-content").forEach(c => c.classList.add("hidden"));
      document.querySelectorAll(".faq-icon").forEach(i => i.classList.remove("rotate-180"));

      if (!isExpanded) {
        content.classList.remove("hidden");
        if (icon) icon.classList.add("rotate-180");
      }
    });
  });
}
