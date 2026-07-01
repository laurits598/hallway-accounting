(function () {
  const routes = {
    "/": "system",
    "/system": "system",
    "/products": "products",
    "/residents": "residents",
    "/accounting": "accounting",
    "/kalender": "kalender",
    "/admin": "admin",
  };

  const navItems = [
    { route: "/system", label: "Ølsystem", icon: "🛒" },
    { route: "/products", label: "Produkter", icon: "🍸" },
    { route: "/residents", label: "Beboere", icon: "👥" },
    { route: "/accounting", label: "Regnskab", icon: "🧾" },
    { route: "/kalender", label: "Kalender", icon: "📅" },
    { route: "/admin", label: "Admin", icon: "🛠️" },
  ];

  const storageKeys = {
    products: "kollegianeren.products.v1",
    residents: "kollegianeren.residents.v1",
    purchases: "kollegianeren.purchases.v1",
    seedSignature: "kollegianeren.seed-signature.v1",
  };

  const app = document.getElementById("app");
  const nav = document.getElementById("sidebar-nav");
  const modalRoot = document.getElementById("modal-root");
  const toastRoot = document.getElementById("toast-root");

  const state = {
    products: [],
    residents: [],
    purchases: [],
    selection: {
      residentId: null,
      quantities: {},
    },
    modal: null,
    filters: {
      fromDate: "",
      toDate: "",
    },
    accounting: {
      month: new Date().getMonth() + 1,
      year: new Date().getFullYear(),
      view: "summary",
      data: null,
      status: "idle", // idle | loading | loaded | error
      statusKey: null,
      error: null,
    },
    calendar: {
      month: new Date().getMonth() + 1,
      year: new Date().getFullYear(),
      data: null,
      status: "idle", // idle | loading | loaded | error
      statusKey: null,
      error: null,
    },
    admin: {
      generating: false,
      result: null,
      error: null,
    },
  };

  const MONTH_NAMES_DA = [
    "Januar", "Februar", "Marts", "April", "Maj", "Juni",
    "Juli", "August", "September", "Oktober", "November", "December",
  ];

  const WEEKDAYS_SHORT_DA = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"];
  const WEEKDAYS_LONG_DA = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"];

  function currentView() {
    return routes[window.location.pathname] || "system";
  }

  function slugify(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function priceNumber(value) {
    const normalized = String(value ?? "")
      .trim()
      .replace(",", ".");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function formatPrice(value) {
    return `${priceNumber(value).toFixed(2).replace(/\.00$/, "")} kr`;
  }

  // Money formatter for accounting figures (handles negatives, hides .00).
  function formatKr(value) {
    const n = priceNumber(value);
    const safe = Math.abs(n) < 0.005 ? 0 : n;
    return `${safe.toFixed(2).replace(/\.00$/, "")} kr`;
  }

  function monthRange(month, year) {
    const lastDay = new Date(year, month, 0).getDate();
    const mm = String(month).padStart(2, "0");
    return {
      from: `${year}-${mm}-01`,
      to: `${year}-${mm}-${String(lastDay).padStart(2, "0")}`,
    };
  }

  // Mirror of overview.normalize_room so summary rows can be matched to
  // local residents (for avatars) by room.
  function normalizeRoomJs(room) {
    const value = String(room ?? "").trim();
    return value.length === 2 ? `5${value}` : value;
  }

  function normalizeImagePath(value) {
    if (!value) {
      return "";
    }
    return String(value)
      .replace("/assets/products/", "/assets/residents/products/")
      .replace("assets/products/", "assets/residents/products/");
  }

  function normalizeProduct(product, index) {
    const name = String(product.name || "").trim() || `Produkt ${index + 1}`;
    return {
      id: product.id || `product-${slugify(name)}-${index}`,
      name,
      retail_price: String(product.retail_price ?? "").trim(),
      price: String(product.price ?? "").trim(),
      image: normalizeImagePath(product.image || ""),
      active: product.active !== false,
      createdAt: product.createdAt || new Date().toISOString(),
    };
  }

  function normalizeResident(resident, index) {
    const name = String(resident.name || "").trim() || `Beboer ${index + 1}`;
    return {
      id: resident.id || `resident-${slugify(name)}-${index}`,
      name,
      room: String(resident.room ?? "").trim(),
      image: normalizeImagePath(resident.image || ""),
      active: resident.active !== false,
      createdAt: resident.createdAt || new Date().toISOString(),
    };
  }

  function sortByName(items) {
    return [...items].sort((left, right) => left.name.localeCompare(right.name, "da"));
  }

  async function fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) {
      throw new Error(`Kunne ikke hente ${path}`);
    }
    return response.json();
  }

  function readStorage(key) {
    try {
      const value = localStorage.getItem(key);
      return value ? JSON.parse(value) : null;
    } catch (error) {
      return null;
    }
  }

  function writeStorage(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function seedSignature(products, residents) {
    return JSON.stringify({
      products,
      residents,
    });
  }

  async function savePurchases() {
    try {
      await fetch("/api/purchases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.purchases),
      });
    } catch (error) {
      console.error("Failed to save purchases:", error);
    }
  }

  function persistAll() {
    writeStorage(storageKeys.products, state.products);
    writeStorage(storageKeys.residents, state.residents);
    savePurchases();
  }

  function initials(name) {
    return String(name || "")
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join("");
  }

  function getResidentById(id) {
    return state.residents.find((resident) => resident.id === id) || null;
  }

  function getProductById(id) {
    return state.products.find((product) => product.id === id) || null;
  }

  function activeProducts() {
    return sortByName(state.products.filter((product) => product.active));
  }

  function activeResidents() {
    return sortByName(state.residents.filter((resident) => resident.active));
  }

  function selectedProducts() {
    return Object.entries(state.selection.quantities)
      .filter(([, quantity]) => quantity > 0)
      .map(([productId, quantity]) => ({ product: getProductById(productId), quantity }))
      .filter((entry) => entry.product);
  }

  function selectedResident() {
    return getResidentById(state.selection.residentId);
  }

  function showToast(message) {
    const node = document.createElement("div");
    node.className = "toast";
    node.textContent = message;
    toastRoot.appendChild(node);
    window.setTimeout(() => {
      node.remove();
    }, 3200);
  }

  function setModal(modal) {
    state.modal = modal;
    renderModal();
  }

  function closeModal() {
    setModal(null);
  }

  function renderNav() {
    const view = currentView();
    nav.innerHTML = navItems
      .map(
        (item) => `
          <a class="nav-item${view === item.route.slice(1) ? " active" : ""}" data-route="${item.route}" href="${item.route}">
            <span class="nav-icon" aria-hidden="true">${item.icon}</span>
            <span class="nav-label">${item.label}</span>
          </a>
        `
      )
      .join("");
  }

  function productMedia(product, className) {
    if (product.image) {
      return `<img class="${className}" src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)}">`;
    }
    return `<div class="${className} placeholder">${escapeHtml(initials(product.name))}</div>`;
  }

  function residentMedia(resident, className) {
    if (resident.image) {
      return `<img class="${className}" src="${escapeHtml(resident.image)}" alt="${escapeHtml(resident.name)}">`;
    }
    return `<div class="${className} placeholder">${escapeHtml(initials(resident.name))}</div>`;
  }

  function pageHeader(title, subtitle, actions) {
    return `
      <header class="page-header">
        <div class="page-heading">
          <h1 class="page-title">${escapeHtml(title)}</h1>
          ${subtitle ? `<p class="page-subtitle">${subtitle}</p>` : ""}
        </div>
        ${actions ? `<div class="page-actions">${actions}</div>` : ""}
      </header>
    `;
  }

  function productCard(product) {
    const quantity = Number(state.selection.quantities[product.id] || 0);
    return `
      <article class="select-card${quantity > 0 ? " is-selected" : ""}" data-action="increment-product" data-product-id="${product.id}">
        <div class="card-copy">
          <h3 class="card-title">${escapeHtml(product.name)}</h3>
          <div class="card-price">${formatPrice(product.price)}</div>
        </div>
        ${productMedia(product, "card-media")}
        <div class="card-qty">
          <button class="qty-button" type="button" data-action="decrement-product" data-product-id="${product.id}" aria-label="Fjern en ${escapeHtml(product.name)}">−</button>
          <span class="qty-value">${quantity}</span>
          <button class="qty-button" type="button" data-action="increment-product" data-product-id="${product.id}" aria-label="Tilføj en ${escapeHtml(product.name)}">+</button>
        </div>
      </article>
    `;
  }

  function residentCard(resident) {
    return `
      <article class="select-card${state.selection.residentId === resident.id ? " is-selected" : ""}" data-action="select-resident" data-resident-id="${resident.id}">
        <div class="card-copy">
          <h3 class="card-title">${escapeHtml(resident.name)}</h3>
          <div class="card-subtitle">Værelse ${escapeHtml(resident.room)}</div>
        </div>
        ${residentMedia(resident, "card-media card-avatar")}
      </article>
    `;
  }

  function renderSystemPage() {
    const products = activeProducts();
    const residents = activeResidents();
    const chosenResident = selectedResident();
    const pickedProducts = selectedProducts();
    const totalItems = pickedProducts.reduce((sum, entry) => sum + entry.quantity, 0);
    const totalPrice = pickedProducts.reduce(
      (sum, entry) => sum + priceNumber(entry.product.price) * entry.quantity,
      0
    );
    const canBuy = Boolean(chosenResident) && totalItems > 0;

    return `
      ${pageHeader("Ølsystem", "Vælg varer og en beboer, og registrér købet.")}
      <section class="system-page">
        <div class="system-main">
          <div class="section-block">
            <div class="section-head">
              <h2 class="section-title">1 · Vælg varer</h2>
              <span class="section-meta">${products.length} ${products.length === 1 ? "vare" : "varer"}</span>
            </div>
            <div class="card-grid">
              ${products.length
                ? products.map(productCard).join("")
                : `<div class="empty-state">Ingen aktive varer.</div>`}
            </div>
          </div>

          <div class="section-block">
            <div class="section-head">
              <h2 class="section-title">2 · Vælg beboer</h2>
              <span class="section-meta">${residents.length} ${residents.length === 1 ? "beboer" : "beboere"}</span>
            </div>
            <div class="card-grid">
              ${residents.length
                ? residents.map(residentCard).join("")
                : `<div class="empty-state">Ingen aktive beboere.</div>`}
            </div>
          </div>
        </div>

        <aside class="selection-summary">
          <div class="summary-title">Kurv</div>
          <div class="summary-lines">
            <div class="summary-line">Beboer <strong>${chosenResident ? escapeHtml(chosenResident.name) : "—"}</strong></div>
            <div class="summary-line">Varer <strong>${totalItems}</strong></div>
            <div class="summary-line is-total">Total <strong>${formatPrice(totalPrice)}</strong></div>
          </div>
          <button class="buy-button" type="button" data-action="buy" ${canBuy ? "" : "disabled"}>Køb</button>
        </aside>
      </section>
    `;
  }

  function renderProductsPage() {
    const rows = sortByName(state.products);
    const activeCount = rows.filter((product) => product.active).length;
    return `
      ${pageHeader("Produkter", `${rows.length} ${rows.length === 1 ? "produkt" : "produkter"} · ${activeCount} aktive`)}
      <section class="management-page">
        <div class="table-shell">
          <table>
            <thead>
              <tr>
                <th>Billede</th>
                <th>Navn</th>
                <th class="th-num">Indkøbspris</th>
                <th class="th-num">Salgspris</th>
                <th>Aktiv</th>
                <th class="action-cell">Ret</th>
                <th class="action-cell">Slet</th>
              </tr>
            </thead>
            <tbody>
              ${rows.length
                ? rows
                    .map(
                      (product) => `
                    <tr>
                      <td class="image-cell">${productMedia(product, "table-image")}</td>
                      <td class="cell-strong">${escapeHtml(product.name)}</td>
                      <td class="td-num">${product.retail_price ? formatPrice(product.retail_price) : `<span class="badge muted">—</span>`}</td>
                      <td class="td-num">${formatPrice(product.price)}</td>
                      <td>
                        <button class="active-mark${product.active ? " is-active" : ""}" type="button" data-action="toggle-product-active" data-product-id="${product.id}" aria-label="Skift aktiv">✓</button>
                      </td>
                      <td class="action-cell">
                        <button class="action-button" type="button" data-action="edit-product" data-product-id="${product.id}" aria-label="Ret">
                          <span class="action-icon">✎</span>
                        </button>
                      </td>
                      <td class="action-cell">
                        <button class="action-button danger" type="button" data-action="delete-product" data-product-id="${product.id}" aria-label="Slet">
                          <span class="action-icon">🗑</span>
                        </button>
                      </td>
                    </tr>
                  `
                    )
                    .join("")
                : `<tr><td colspan="7" class="empty-state">Ingen produkter endnu. Tryk på + for at tilføje et.</td></tr>`}
            </tbody>
          </table>
        </div>
        <button class="fab fab-primary" type="button" data-action="new-product" aria-label="Tilføj produkt">
          <span class="fab-plus">+</span>
        </button>
        <span class="fab-label">Tilføj produkt</span>
      </section>
    `;
  }

  function renderResidentsPage() {
    const rows = sortByName(state.residents);
    const activeCount = rows.filter((resident) => resident.active).length;
    return `
      ${pageHeader("Beboere", `${rows.length} ${rows.length === 1 ? "beboer" : "beboere"} · ${activeCount} aktive`)}
      <section class="management-page">
        <div class="table-shell">
          <table>
            <thead>
              <tr>
                <th>Billede</th>
                <th>Navn</th>
                <th>Værelse</th>
                <th>Aktiv</th>
                <th class="action-cell">Ret</th>
                <th class="action-cell">Slet</th>
              </tr>
            </thead>
            <tbody>
              ${rows.length
                ? rows
                    .map(
                      (resident) => `
                    <tr>
                      <td class="image-cell">${residentMedia(resident, "table-avatar")}</td>
                      <td class="cell-strong">${escapeHtml(resident.name)}</td>
                      <td>${escapeHtml(resident.room)}</td>
                      <td>
                        <button class="active-mark${resident.active ? " is-active" : ""}" type="button" data-action="toggle-resident-active" data-resident-id="${resident.id}" aria-label="Skift aktiv">✓</button>
                      </td>
                      <td class="action-cell">
                        <button class="action-button" type="button" data-action="edit-resident" data-resident-id="${resident.id}" aria-label="Ret">
                          <span class="action-icon">✎</span>
                        </button>
                      </td>
                      <td class="action-cell">
                        <button class="action-button danger" type="button" data-action="delete-resident" data-resident-id="${resident.id}" aria-label="Slet">
                          <span class="action-icon">🗑</span>
                        </button>
                      </td>
                    </tr>
                  `
                    )
                    .join("")
                : `<tr><td colspan="6" class="empty-state">Ingen beboere endnu. Tryk på + for at tilføje en.</td></tr>`}
            </tbody>
          </table>
        </div>
        <button class="fab fab-primary" type="button" data-action="new-resident" aria-label="Tilføj beboer">
          <span class="fab-plus">+</span>
        </button>
        <span class="fab-label">Tilføj beboer</span>
      </section>
    `;
  }

  function defaultDateRange() {
    const timestamps = state.purchases.map((purchase) => new Date(purchase.timestamp).getTime()).filter(Number.isFinite);
    const today = new Date();
    const minTime = timestamps.length ? Math.min(...timestamps) : new Date(today.getFullYear(), today.getMonth(), 1).getTime();
    const maxTime = timestamps.length ? Math.max(...timestamps) : today.getTime();
    return {
      fromDate: formatInputDate(new Date(minTime)),
      toDate: formatInputDate(new Date(maxTime)),
    };
  }

  function formatInputDate(date) {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, "0");
    const day = `${date.getDate()}`.padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function getFilteredPurchases() {
    if (!state.filters.fromDate || !state.filters.toDate) {
      const range = defaultDateRange();
      state.filters.fromDate = range.fromDate;
      state.filters.toDate = range.toDate;
    }

    const from = new Date(`${state.filters.fromDate}T00:00:00`);
    const to = new Date(`${state.filters.toDate}T23:59:59.999`);
    return state.purchases.filter((purchase) => {
      const time = new Date(purchase.timestamp);
      return time >= from && time <= to;
    });
  }

  function accountingMatrix() {
    const purchases = getFilteredPurchases();
    const productMap = new Map();

    purchases.forEach((purchase) => {
      if (!productMap.has(purchase.productId)) {
        productMap.set(purchase.productId, {
          id: purchase.productId,
          name: purchase.productName,
        });
      }
    });

    state.products.forEach((product) => {
      if (productMap.has(product.id)) {
        productMap.get(product.id).name = product.name;
      } else if (productMap.size === 0 && product.active) {
        productMap.set(product.id, {
          id: product.id,
          name: product.name,
        });
      }
    });

    const products = Array.from(productMap.values()).sort((left, right) =>
      left.name.localeCompare(right.name, "da")
    );
    const residentMap = new Map();

    purchases.forEach((purchase) => {
      if (!residentMap.has(purchase.residentId)) {
        residentMap.set(purchase.residentId, {
          residentId: purchase.residentId,
          residentName: purchase.residentName,
          room: purchase.room,
          counts: {},
          total: 0,
        });
      }
      const row = residentMap.get(purchase.residentId);
      row.counts[purchase.productId] = (row.counts[purchase.productId] || 0) + Number(purchase.quantity || 0);
      row.total += Number(purchase.quantity || 0) * Number(purchase.unitPrice || 0);
    });

    const rows = Array.from(residentMap.values()).sort((left, right) =>
      left.residentName.localeCompare(right.residentName, "da")
    );

    return { products, rows };
  }

  function accountingYears() {
    const years = new Set([state.accounting.year, new Date().getFullYear()]);
    state.purchases.forEach((purchase) => {
      const year = new Date(purchase.timestamp).getFullYear();
      if (Number.isFinite(year)) {
        years.add(year);
      }
    });
    return Array.from(years).sort((left, right) => right - left);
  }

  function accountingControls() {
    const a = state.accounting;
    const monthOptions = MONTH_NAMES_DA.map(
      (name, index) => `<option value="${index + 1}" ${a.month === index + 1 ? "selected" : ""}>${name}</option>`
    ).join("");
    const yearOptions = accountingYears()
      .map((year) => `<option value="${year}" ${a.year === year ? "selected" : ""}>${year}</option>`)
      .join("");
    return `
      <div class="acct-controls">
        <div class="control-group">
          <select class="select-field" data-action="set-acct-month" aria-label="Vælg måned">${monthOptions}</select>
          <select class="select-field" data-action="set-acct-year" aria-label="Vælg år">${yearOptions}</select>
        </div>
        <div class="control-spacer"></div>
        <div class="segmented" role="tablist" aria-label="Visning">
          <button class="seg-btn${a.view === "summary" ? " active" : ""}" type="button" data-action="set-acct-view" data-view="summary">Oversigt</button>
          <button class="seg-btn${a.view === "details" ? " active" : ""}" type="button" data-action="set-acct-view" data-view="details">Detaljer (kiosk)</button>
        </div>
        ${a.view === "details" ? `<button class="ghost-button" type="button" data-action="export-xlsx">⬇&nbsp; Eksportér .xlsx</button>` : ""}
      </div>
    `;
  }

  function residentLookupByRoom() {
    const map = new Map();
    state.residents.forEach((resident) => {
      map.set(normalizeRoomJs(resident.room), resident);
    });
    return map;
  }

  function kpiCard(key, label, value, caption) {
    return `
      <div class="kpi-card k-${key}">
        <div class="kpi-label"><span class="kpi-dot"></span>${escapeHtml(label)}</div>
        <div class="kpi-value tnum">${formatKr(value)}</div>
        ${caption ? `<div class="kpi-caption">${escapeHtml(caption)}</div>` : ""}
      </div>
    `;
  }

  function kpiCards(totals) {
    return `
      <div class="kpi-grid">
        ${kpiCard("foodclub", "Madklub", totals.foodclub)}
        ${kpiCard("bluebook", "Blue Book", totals.bluebook)}
        ${kpiCard("kiosk", "Kiosk", totals.kiosk)}
        ${kpiCard("total", "I alt", totals.total, "Madklub + Blue Book + Kiosk")}
      </div>
    `;
  }

  function sourceBanner(data) {
    const sources = (data && data.sources) || {};
    const missing = [];
    if (!sources.foodclub) missing.push("Madklub");
    if (!sources.bluebook) missing.push("Blue Book");
    if (!missing.length) {
      return "";
    }
    return `
      <div class="source-banner">
        <span class="sb-icon">⚠️</span>
        <div>Kunne ikke hente <strong>${missing.join(" og ")}</strong> fra Google Sheets lige nu — viser de tal der er tilgængelige (typisk kiosk). Tjek forbindelsen, og opdatér siden.</div>
      </div>
    `;
  }

  function amountCell(value) {
    const number = priceNumber(value);
    const zero = Math.abs(number) < 0.005;
    return `<td class="amount td-num${zero ? " zero" : ""}">${zero ? "—" : escapeHtml(formatKr(number))}</td>`;
  }

  function totalClass(value) {
    const number = priceNumber(value);
    if (Math.abs(number) < 0.005) return "zero";
    return number > 0 ? "pos" : "neg";
  }

  function statusPill(value) {
    const number = priceNumber(value);
    if (Math.abs(number) < 0.005) {
      return `<span class="status-pill settled">Afregnet</span>`;
    }
    if (number > 0) {
      return `<span class="status-pill owes">Skylder ${escapeHtml(formatKr(number))}</span>`;
    }
    return `<span class="status-pill receives">Skal have ${escapeHtml(formatKr(Math.abs(number)))}</span>`;
  }

  function acctNameCell(row, lookup) {
    const resident = lookup.get(normalizeRoomJs(row.room));
    const avatar = resident
      ? residentMedia(resident, "name-avatar")
      : `<div class="name-avatar placeholder">${escapeHtml(initials(row.name))}</div>`;
    return `<td><span class="acct-name">${avatar}<span class="name-text">${escapeHtml(row.name)}</span></span></td>`;
  }

  function summarySkeleton() {
    const kpis = '<div class="skel skel-kpi"></div>'.repeat(4);
    const rows = '<div class="skel skel-row"></div>'.repeat(7);
    return `
      <div class="skel-kpis">${kpis}</div>
      <div class="table-shell" style="padding:16px">${rows}</div>
    `;
  }

  function errorState(message) {
    return `
      <div class="state-block">
        <div class="state-icon error">⚠️</div>
        <div class="state-title">Kunne ikke hente regnskabet</div>
        <div class="state-text">${escapeHtml(message || "Der opstod en uventet fejl.")}</div>
        <button class="primary-button" type="button" data-action="retry-summary">Prøv igen</button>
      </div>
    `;
  }

  function summaryEmpty(data) {
    const a = state.accounting;
    return `
      ${data ? sourceBanner(data) : ""}
      <div class="state-block">
        <div class="state-icon">📭</div>
        <div class="state-title">Ingen data for ${MONTH_NAMES_DA[a.month - 1]} ${a.year}</div>
        <div class="state-text">Der er ingen registrerede beløb i den valgte måned. Vælg en anden måned, eller registrér køb i Ølsystemet.</div>
      </div>
    `;
  }

  function renderAccountingSummary() {
    const a = state.accounting;
    if (a.status === "loading" || a.status === "idle") {
      return summarySkeleton();
    }
    if (a.status === "error") {
      return errorState(a.error);
    }
    const data = a.data;
    if (!data || !Array.isArray(data.rows) || !data.rows.length) {
      return summaryEmpty(data);
    }

    const lookup = residentLookupByRoom();
    const totals = data.totals || { foodclub: 0, bluebook: 0, kiosk: 0, total: 0 };
    const body = data.rows
      .map(
        (row) => `
          <tr>
            <td class="col-room">${escapeHtml(row.room)}</td>
            ${acctNameCell(row, lookup)}
            ${amountCell(row.foodclub)}
            ${amountCell(row.bluebook)}
            ${amountCell(row.kiosk)}
            <td class="total-amount td-num ${totalClass(row.total)}">${escapeHtml(formatKr(row.total))}</td>
            <td>${statusPill(row.total)}</td>
          </tr>
        `
      )
      .join("");

    return `
      ${kpiCards(totals)}
      ${sourceBanner(data)}
      <div class="table-shell acct-table">
        <table>
          <thead>
            <tr>
              <th class="col-room">Værelse</th>
              <th>Beboer</th>
              <th class="th-num">Madklub</th>
              <th class="th-num">Blue Book</th>
              <th class="th-num">Kiosk</th>
              <th class="th-num">Total</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
          <tfoot>
            <tr>
              <td class="foot-label" colspan="2">I alt · ${data.rows.length} ${data.rows.length === 1 ? "beboer" : "beboere"}</td>
              <td class="amount td-num">${escapeHtml(formatKr(totals.foodclub))}</td>
              <td class="amount td-num">${escapeHtml(formatKr(totals.bluebook))}</td>
              <td class="amount td-num">${escapeHtml(formatKr(totals.kiosk))}</td>
              <td class="total-amount td-num ${totalClass(totals.total)}">${escapeHtml(formatKr(totals.total))}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;
  }

  function renderAccountingDetails() {
    const a = state.accounting;
    const { products, rows } = accountingMatrix();
    return `
      <div class="table-shell acct-table">
        <table id="accounting-table">
          <thead>
            <tr>
              <th class="col-room">Værelse</th>
              <th>Beboer</th>
              ${products.map((product) => `<th class="th-num">${escapeHtml(product.name)}</th>`).join("")}
              <th class="th-num">Total</th>
            </tr>
          </thead>
          <tbody>
            ${
              rows.length
                ? rows
                    .map(
                      (row) => `
                        <tr>
                          <td class="col-room">${escapeHtml(row.room)}</td>
                          <td class="cell-strong">${escapeHtml(row.residentName)}</td>
                          ${products
                            .map(
                              (product) =>
                                `<td class="td-num${row.counts[product.id] ? "" : " amount zero"}">${
                                  row.counts[product.id] ? escapeHtml(String(row.counts[product.id])) : "—"
                                }</td>`
                            )
                            .join("")}
                          <td class="total-amount td-num">${escapeHtml(formatKr(row.total))}</td>
                        </tr>
                      `
                    )
                    .join("")
                : `<tr><td colspan="${products.length + 3}" class="empty-state">Ingen kioskkøb i ${MONTH_NAMES_DA[a.month - 1]} ${a.year}.</td></tr>`
            }
          </tbody>
        </table>
      </div>
    `;
  }

  function renderAccountingPage() {
    const a = state.accounting;
    return `
      ${pageHeader("Regnskab", `Månedsoversigt — ${MONTH_NAMES_DA[a.month - 1]} ${a.year}`)}
      ${accountingControls()}
      ${a.view === "details" ? renderAccountingDetails() : renderAccountingSummary()}
    `;
  }

  function personLabel(person) {
    if (!person) return "—";
    return person.name || (person.room ? `Vær. ${person.room}` : "—");
  }

  function calendarNav() {
    const c = state.calendar;
    return `
      <div class="cal-nav">
        <button class="cal-arrow" type="button" data-action="cal-prev" aria-label="Forrige måned">‹</button>
        <div class="cal-title">${MONTH_NAMES_DA[c.month - 1]} ${c.year}</div>
        <button class="cal-arrow" type="button" data-action="cal-next" aria-label="Næste måned">›</button>
        <button class="cal-today-btn" type="button" data-action="cal-today">I dag</button>
        <div class="cal-spacer"></div>
      </div>
    `;
  }

  function calendarSourceBanner(data) {
    const sources = (data && data.sources) || {};
    const missing = [];
    if (!sources.foodclub) missing.push("madklub-ansvarlig (Google Sheets)");
    if (!sources.smallTeddy) missing.push("small teddy (data/small_teddy.csv)");
    if (!missing.length) return "";
    return `
      <div class="source-banner">
        <span class="sb-icon">⚠️</span>
        <div>Kunne ikke hente ${missing.join(" og ")} lige nu. Kalenderen viser de data, der er tilgængelige.</div>
      </div>
    `;
  }

  function calendarSkeleton() {
    const cells = '<div class="skel" style="height:104px;border-radius:10px"></div>'.repeat(35);
    return `<div class="cal-card"><div class="cal-grid">${cells}</div></div>`;
  }

  function calendarError(message) {
    return `
      <div class="state-block">
        <div class="state-icon error">⚠️</div>
        <div class="state-title">Kunne ikke hente kalenderen</div>
        <div class="state-text">${escapeHtml(message || "Der opstod en uventet fejl.")}</div>
        <button class="primary-button" type="button" data-action="retry-calendar">Prøv igen</button>
      </div>
    `;
  }

  function calendarEmpty() {
    const c = state.calendar;
    return `
      <div class="state-block">
        <div class="state-icon">📅</div>
        <div class="state-title">Ingen kalenderdata for ${MONTH_NAMES_DA[c.month - 1]} ${c.year}</div>
        <div class="state-text">Vælg en anden måned med pilene ovenfor.</div>
      </div>
    `;
  }

  function calendarCell(day, todayDay) {
    const chips = [];
    if (day.foodclub) {
      const label = escapeHtml(personLabel(day.foodclub));
      chips.push(`<span class="cal-chip food" title="Madklub: ${label}"><span class="ico" aria-hidden="true">🍳</span><span class="lbl">${label}</span></span>`);
    }
    if (day.smallTeddy) {
      const label = escapeHtml(personLabel(day.smallTeddy));
      chips.push(`
        <span class="cal-chip teddy${day.smallTeddyDone ? " is-done" : ""}" title="Small teddy: ${label}${day.smallTeddyDone ? " (færdig)" : ""}">
          <span class="ico" aria-hidden="true">🧽</span>
          <span class="lbl">${label}</span>
          <span class="chip-check" aria-hidden="true">${day.smallTeddyDone ? "✓" : ""}</span>
        </span>
      `);
    }
    return `
      <button class="cal-cell${day.day === todayDay ? " today" : ""}" type="button" data-action="open-cal-day" data-day="${day.day}">
        <span class="cal-daynum">${day.day}</span>
        <span class="cal-chips">${chips.join("")}</span>
      </button>
    `;
  }

  function renderCalendarGrid(data) {
    const today = new Date();
    const isCurrentMonth = today.getFullYear() === data.year && today.getMonth() + 1 === data.month;
    const todayDay = isCurrentMonth ? today.getDate() : -1;
    const firstWeekday = data.days.length ? data.days[0].weekday : 0;
    const head = WEEKDAYS_SHORT_DA.map((label) => `<div class="cal-weekday">${label}</div>`).join("");
    const leading = Array.from({ length: firstWeekday }, () => `<div class="cal-cell empty"></div>`).join("");
    const cells = data.days.map((day) => calendarCell(day, todayDay)).join("");
    return `
      ${calendarSourceBanner(data)}
      <div class="cal-card">
        <div class="cal-weekdays">${head}</div>
        <div class="cal-grid">${leading}${cells}</div>
        <div class="cal-legend">
          <span class="leg"><span class="dot food"></span>Madklub-ansvarlig</span>
          <span class="leg"><span class="dot teddy"></span>Small teddy · køkkenrengøring</span>
        </div>
      </div>
    `;
  }

  function renderCalendarBody() {
    const c = state.calendar;
    if (c.status === "loading" || c.status === "idle") return calendarSkeleton();
    if (c.status === "error") return calendarError(c.error);
    const data = c.data;
    if (!data || !Array.isArray(data.days) || !data.days.length) return calendarEmpty();
    return renderCalendarGrid(data);
  }

  function renderCalendarPage() {
    const c = state.calendar;
    return `
      ${pageHeader("Kalender", `Madklub og small teddy — ${MONTH_NAMES_DA[c.month - 1]} ${c.year}`)}
      ${calendarNav()}
      ${renderCalendarBody()}
    `;
  }

  function renderAdminPage() {
    const a = state.admin;
    const result = a.result;
    const countRows = result
      ? Object.entries(result.counts || {})
        .sort((left, right) => left[0].localeCompare(right[0], "da"))
        .map(([room, count]) => `<div class="admin-summary-row"><span>Værelse ${escapeHtml(room)}</span><strong>${count}</strong></div>`)
        .join("")
      : "";
    return `
      <div class="page">
        ${pageHeader(
          "Admin",
          "Simple driftsværktøjer",
          `<button class="primary-button" type="button" data-action="generate-small-teddy-next-month" ${a.generating ? "disabled" : ""}>${a.generating ? "Genererer…" : "New month gen"}</button>`
        )}
        <div class="admin-card">
          <div class="admin-title">Small teddy næste måned</div>
          <div class="admin-copy">
            Genererer næste måned i <code>data/small_teddy.csv</code>. Beboere uden flueben i seneste måned får 2 ekstra small teddy næste måned, så de ender på 3 i alt.
          </div>
          ${a.error ? `<div class="admin-error">${escapeHtml(a.error)}</div>` : ""}
          ${result ? `
            <div class="admin-result">
              <div class="admin-result-head">Genereret ${escapeHtml(result.generatedMonth)} · ${result.days} dage</div>
              <div class="admin-copy">Ekstra small teddy pga. manglende afkrydsning: ${result.uncheckedFromPreviousMonth?.length ? escapeHtml(result.uncheckedFromPreviousMonth.join(", ")) : "ingen"}</div>
              <div class="admin-summary">${countRows}</div>
            </div>
          ` : ""}
        </div>
      </div>
    `;
  }

  function ensureCalendarLoaded() {
    const c = state.calendar;
    const key = `${c.year}-${c.month}`;
    if (c.statusKey === key && c.status !== "idle") return;
    loadCalendar(c.month, c.year);
  }

  async function loadCalendar(month, year) {
    const c = state.calendar;
    const key = `${year}-${month}`;
    c.status = "loading";
    c.statusKey = key;
    c.error = null;
    c.data = null;
    render();
    try {
      const response = await fetch(`/api/calendar?month=${month}&year=${year}`);
      if (!response.ok) {
        throw new Error(`Serveren svarede med fejl (${response.status}).`);
      }
      const data = await response.json();
      if (`${state.calendar.year}-${state.calendar.month}` !== key) return;
      c.data = decorateCalendarData(data);
      c.status = "loaded";
      c.error = null;
    } catch (error) {
      if (`${state.calendar.year}-${state.calendar.month}` !== key) return;
      c.status = "error";
      c.error = error.message || "Netværksfejl.";
      c.data = null;
    }
    render();
  }

  function shiftCalendar(delta) {
    const c = state.calendar;
    let month = c.month + delta;
    let year = c.year;
    if (month < 1) { month = 12; year -= 1; }
    else if (month > 12) { month = 1; year += 1; }
    c.month = month;
    c.year = year;
    render();
  }

  function calendarToday() {
    const now = new Date();
    state.calendar.month = now.getMonth() + 1;
    state.calendar.year = now.getFullYear();
    render();
  }

  function openCalendarDay(day) {
    const c = state.calendar;
    if (!c.data || !Array.isArray(c.data.days)) return;
    const dayData = c.data.days.find((entry) => entry.day === day);
    if (dayData) {
      setModal({ type: "calendar-day", item: dayData });
    }
  }

  function startOfDay(dateLike) {
    const date = new Date(`${dateLike}T00:00:00`);
    date.setHours(0, 0, 0, 0);
    return date;
  }

  function canToggleSmallTeddy(date) {
    const target = startOfDay(date);
    if (Number.isNaN(target.getTime())) {
      return false;
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const latest = new Date(target);
    latest.setDate(latest.getDate() + 1);
    return today >= target && today <= latest;
  }

  function decorateCalendarDay(day) {
    return {
      ...day,
      smallTeddyDone: Boolean(day.smallTeddy && (day.smallTeddyDone || day.smallTeddy?.done)),
    };
  }

  function decorateCalendarData(data) {
    if (!data || !Array.isArray(data.days)) {
      return data;
    }
    return {
      ...data,
      days: data.days.map(decorateCalendarDay),
    };
  }

  async function toggleSmallTeddyDone(date, checked) {
    if (!canToggleSmallTeddy(date)) {
      showToast("Small teddy kan kun markeres på dagen eller dagen efter.");
      renderModal();
      return;
    }

    try {
      const response = await fetch("/api/small-teddy-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, checked }),
      });
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        throw new Error(errorPayload?.error || `Serveren svarede med fejl (${response.status}).`);
      }
    } catch (error) {
      showToast(error.message || "Kunne ikke gemme small teddy-status.");
      render();
      return;
    }

    const calendarDays = state.calendar.data?.days;
    if (Array.isArray(calendarDays)) {
      const match = calendarDays.find((day) => day.date === date);
      if (match) {
        match.smallTeddyDone = checked;
      }
    }
    if (state.modal?.type === "calendar-day" && state.modal.item?.date === date) {
      state.modal.item.smallTeddyDone = checked;
    }

    render();
    showToast(checked ? "Small teddy markeret som færdig." : "Small teddy fjernet som færdig.");
  }

  async function generateSmallTeddyNextMonth() {
    state.admin.generating = true;
    state.admin.error = null;
    render();
    try {
      const response = await fetch("/api/admin/generate-small-teddy-next-month", {
        method: "POST",
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.error || `Serveren svarede med fejl (${response.status}).`);
      }
      state.admin.result = payload;
      showToast(`Small teddy-plan genereret for ${payload.generatedMonth}.`);
    } catch (error) {
      state.admin.error = error.message || "Kunne ikke generere næste måned.";
      state.admin.result = null;
    } finally {
      state.admin.generating = false;
      render();
    }
  }

  function render() {
    renderNav();
    const view = currentView();
    if (view === "products") {
      app.innerHTML = renderProductsPage();
    } else if (view === "residents") {
      app.innerHTML = renderResidentsPage();
    } else if (view === "accounting") {
      app.innerHTML = renderAccountingPage();
      ensureSummaryLoaded();
    } else if (view === "kalender") {
      app.innerHTML = renderCalendarPage();
      ensureCalendarLoaded();
    } else if (view === "admin") {
      app.innerHTML = renderAdminPage();
    } else {
      app.innerHTML = renderSystemPage();
    }
    renderModal();
  }

  function renderModal() {
    if (!state.modal) {
      modalRoot.innerHTML = "";
      return;
    }

    const { type, item } = state.modal;

    if (type === "product") {
      modalRoot.innerHTML = `
        <div class="modal-backdrop" data-action="close-modal">
          <div class="modal" role="dialog" aria-modal="true" aria-labelledby="product-modal-title">
            <div class="modal-header" id="product-modal-title">${item ? "Ret produkt" : "Nyt produkt"}</div>
            <form class="modal-body" id="product-form">
              <div class="field">
                <label for="product-name">Navn</label>
                <input id="product-name" name="name" class="text-field" required value="${escapeHtml(item?.name || "")}">
              </div>
              <div class="modal-row">
                <div class="field">
                  <label for="product-retail-price">Indkøbspris</label>
                  <input id="product-retail-price" name="retail_price" class="text-field" value="${escapeHtml(item?.retail_price || "")}">
                </div>
                <div class="field">
                  <label for="product-price">Salgspris</label>
                  <input id="product-price" name="price" class="text-field" required value="${escapeHtml(item?.price || "")}">
                </div>
              </div>
              <div class="field">
                <label for="product-image">Billede</label>
                <div style="display: flex; gap: 8px;">
                  <input id="product-image" name="image" class="text-field" value="${escapeHtml(item?.image || "")}" placeholder="/assets/residents/products/tonic.png" style="flex: 1;">
                  <button type="button" class="primary-button" data-action="upload-product-image" style="white-space: nowrap;">Upload</button>
                </div>
              </div>
              <div class="field">
                <label><input name="active" class="checkbox-field" type="checkbox" ${item?.active !== false ? "checked" : ""}> Aktiv</label>
              </div>
            </form>
            <div class="modal-actions">
              <button class="text-button" type="button" data-action="close-modal">Annuller</button>
              <button class="primary-button" type="button" data-action="save-product" data-product-id="${item?.id || ""}">Gem</button>
            </div>
          </div>
        </div>
      `;
      return;
    }

    if (type === "calendar-day") {
      const date = new Date(`${item.date}T00:00:00`);
      const weekday = WEEKDAYS_LONG_DA[item.weekday] || "";
      const heading = `${weekday} d. ${date.getDate()}. ${MONTH_NAMES_DA[date.getMonth()].toLowerCase()} ${date.getFullYear()}`;
      const fc = item.foodclub;
      const st = item.smallTeddy;
      const canCheckTeddy = st && canToggleSmallTeddy(item.date);
      modalRoot.innerHTML = `
        <div class="modal-backdrop" data-action="close-modal">
          <div class="modal" role="dialog" aria-modal="true" aria-labelledby="day-modal-title">
            <div class="modal-header" id="day-modal-title">${escapeHtml(heading)}</div>
            <div class="modal-body">
              <div class="day-detail">
                <div class="day-row">
                  <div class="day-ico food" aria-hidden="true">🍳</div>
                  <div>
                    <div class="day-kind">Madklub-ansvarlig</div>
                    ${fc
                      ? `<div class="day-name">${escapeHtml(fc.name || `Vær. ${fc.room}`)}</div>
                         ${fc.room ? `<div class="day-sub">Værelse ${escapeHtml(fc.room)}</div>` : ""}
                         ${fc.menu ? `<div class="day-sub">Menu: ${escapeHtml(fc.menu)}</div>` : ""}`
                      : `<div class="day-name day-none">Ingen madklub denne dag</div>`}
                  </div>
                </div>
                <div class="day-row">
                  <div class="day-ico teddy" aria-hidden="true">🧽</div>
                  <div>
                    <div class="day-kind">Small teddy · køkkenrengøring</div>
                    ${st
                      ? `<div class="day-name">${escapeHtml(st.name || `Vær. ${st.room}`)}</div>
                         ${st.room ? `<div class="day-sub">Værelse ${escapeHtml(st.room)}</div>` : ""}
                         <label class="day-check${item.smallTeddyDone ? " is-checked" : ""}">
                           <input
                             type="checkbox"
                             class="checkbox-field"
                             data-action="toggle-small-teddy"
                             data-date="${escapeHtml(item.date)}"
                             ${item.smallTeddyDone ? "checked" : ""}
                             ${canCheckTeddy ? "" : "disabled"}
                           >
                           <span>Færdiggjort</span>
                         </label>
                         <div class="day-sub">${canCheckTeddy ? "Kan markeres nu." : "Kan kun markeres på dagen eller dagen efter."}</div>`
                      : `<div class="day-name day-none">Ikke tildelt</div>`}
                  </div>
                </div>
              </div>
            </div>
            <div class="modal-actions">
              <button class="primary-button" type="button" data-action="close-modal">Luk</button>
            </div>
          </div>
        </div>
      `;
      return;
    }

    modalRoot.innerHTML = `
      <div class="modal-backdrop" data-action="close-modal">
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="resident-modal-title">
          <div class="modal-header" id="resident-modal-title">${item ? "Ret beboer" : "Ny beboer"}</div>
          <form class="modal-body" id="resident-form">
            <div class="field">
              <label for="resident-name">Navn</label>
              <input id="resident-name" name="name" class="text-field" required value="${escapeHtml(item?.name || "")}">
            </div>
            <div class="field">
              <label for="resident-room">Værelse</label>
              <input id="resident-room" name="room" class="text-field" required value="${escapeHtml(item?.room || "")}">
            </div>
            <div class="field">
              <label for="resident-image">Billede</label>
              <div style="display: flex; gap: 8px;">
                <input id="resident-image" name="image" class="text-field" value="${escapeHtml(item?.image || "")}" placeholder="/assets/residents/wilma.png" style="flex: 1;">
                <button type="button" class="primary-button" data-action="upload-resident-image" style="white-space: nowrap;">Upload</button>
              </div>
            </div>
            <div class="field">
              <label><input name="active" class="checkbox-field" type="checkbox" ${item?.active !== false ? "checked" : ""}> Aktiv</label>
            </div>
          </form>
          <div class="modal-actions">
            <button class="text-button" type="button" data-action="close-modal">Annuller</button>
            <button class="primary-button" type="button" data-action="save-resident" data-resident-id="${item?.id || ""}">Gem</button>
          </div>
        </div>
      </div>
    `;
  }

  function navigate(pathname) {
    const path = routes[pathname] ? pathname : "/system";
    window.history.pushState({}, "", path);
    render();
  }

  function updateProductQuantity(productId, delta) {
    const product = getProductById(productId);
    if (!product || !product.active) {
      return;
    }
    const nextQuantity = Math.max(0, Number(state.selection.quantities[productId] || 0) + delta);
    if (nextQuantity === 0) {
      delete state.selection.quantities[productId];
    } else {
      state.selection.quantities[productId] = nextQuantity;
    }
    render();
  }

  function performPurchase() {
    const resident = selectedResident();
    const items = selectedProducts();
    if (!resident || !items.length) {
      return;
    }

    const timestamp = new Date().toISOString();
    items.forEach((entry) => {
      state.purchases.push({
        id: `purchase-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        residentId: resident.id,
        residentName: resident.name,
        room: resident.room,
        productId: entry.product.id,
        productName: entry.product.name,
        quantity: entry.quantity,
        unitPrice: priceNumber(entry.product.price),
        timestamp,
      });
    });

    state.selection = { residentId: null, quantities: {} };
    persistAll();
    // A new purchase changes the kiosk total — force the summary to refetch.
    state.accounting.statusKey = null;
    if (!state.filters.fromDate || !state.filters.toDate) {
      const range = defaultDateRange();
      state.filters.fromDate = range.fromDate;
      state.filters.toDate = range.toDate;
    }
    render();
    showToast("Køb registreret.");
  }

  function formValues(form) {
    const data = new FormData(form);
    return Object.fromEntries(data.entries());
  }

  function handleImageUpload(inputSelector) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.addEventListener("change", (event) => {
      const file = event.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (e) => {
        const imageField = document.querySelector(inputSelector);
        if (imageField) {
          imageField.value = e.target?.result || "";
        }
      };
      reader.readAsDataURL(file);
    });
    input.click();
  }

  function saveProduct(productId) {
    const form = document.getElementById("product-form");
    if (!form || !form.reportValidity()) {
      return;
    }
    const values = formValues(form);
    const payload = {
      id: productId || `product-${slugify(values.name)}-${Date.now()}`,
      name: values.name.trim(),
      retail_price: values.retail_price.trim(),
      price: values.price.trim(),
      image: normalizeImagePath(values.image.trim()),
      active: form.elements.active.checked,
      createdAt: new Date().toISOString(),
    };

    const index = state.products.findIndex((product) => product.id === productId);
    if (index >= 0) {
      payload.createdAt = state.products[index].createdAt;
      state.products[index] = payload;
    } else {
      state.products.push(payload);
    }
    persistAll();
    closeModal();
    render();
    showToast("Produkt gemt.");
  }

  function saveResident(residentId) {
    const form = document.getElementById("resident-form");
    if (!form || !form.reportValidity()) {
      return;
    }
    const values = formValues(form);
    const payload = {
      id: residentId || `resident-${slugify(values.name)}-${Date.now()}`,
      name: values.name.trim(),
      room: values.room.trim(),
      image: normalizeImagePath(values.image.trim()),
      active: form.elements.active.checked,
      createdAt: new Date().toISOString(),
    };

    const index = state.residents.findIndex((resident) => resident.id === residentId);
    if (index >= 0) {
      payload.createdAt = state.residents[index].createdAt;
      state.residents[index] = payload;
    } else {
      state.residents.push(payload);
    }
    persistAll();
    closeModal();
    render();
    showToast("Beboer gemt.");
  }

  function removeProduct(productId) {
    const product = getProductById(productId);
    if (!product || !window.confirm(`Slet ${product.name}?`)) {
      return;
    }
    state.products = state.products.filter((item) => item.id !== productId);
    delete state.selection.quantities[productId];
    persistAll();
    render();
    showToast("Produkt slettet.");
  }

  function removeResident(residentId) {
    const resident = getResidentById(residentId);
    if (!resident || !window.confirm(`Slet ${resident.name}?`)) {
      return;
    }
    state.residents = state.residents.filter((item) => item.id !== residentId);
    if (state.selection.residentId === residentId) {
      state.selection.residentId = null;
    }
    persistAll();
    render();
    showToast("Beboer slettet.");
  }

  function setDateFilter(key, value) {
    state.filters[key] = value;
    render();
  }

  function latestPurchaseDate() {
    const times = state.purchases
      .map((purchase) => new Date(purchase.timestamp).getTime())
      .filter(Number.isFinite);
    return times.length ? new Date(Math.max(...times)) : new Date();
  }

  function setAccountingMonthYear(month, year) {
    const a = state.accounting;
    a.month = month;
    a.year = year;
    const range = monthRange(month, year);
    state.filters.fromDate = range.from;
    state.filters.toDate = range.to;
    render();
  }

  function setAccountingView(view) {
    if (view !== "summary" && view !== "details") {
      return;
    }
    state.accounting.view = view;
    render();
  }

  function ensureSummaryLoaded() {
    const a = state.accounting;
    if (a.view !== "summary") {
      return;
    }
    const key = `${a.year}-${a.month}`;
    if (a.statusKey === key && a.status !== "idle") {
      return;
    }
    loadAccountingSummary(a.month, a.year);
  }

  async function loadAccountingSummary(month, year) {
    const a = state.accounting;
    const key = `${year}-${month}`;
    a.status = "loading";
    a.statusKey = key;
    a.error = null;
    a.data = null;
    render();

    try {
      const response = await fetch(`/api/accounting?month=${month}&year=${year}`);
      if (!response.ok) {
        throw new Error(`Serveren svarede med fejl (${response.status}).`);
      }
      const data = await response.json();
      if (`${state.accounting.year}-${state.accounting.month}` !== key) {
        return; // user changed the month while this request was in flight
      }
      a.data = data;
      a.status = "loaded";
      a.error = null;
    } catch (error) {
      if (`${state.accounting.year}-${state.accounting.month}` !== key) {
        return;
      }
      a.status = "error";
      a.error = error.message || "Netværksfejl.";
      a.data = null;
    }
    render();
  }

  function xmlEscape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function columnName(index) {
    let name = "";
    let current = index + 1;
    while (current > 0) {
      const remainder = (current - 1) % 26;
      name = String.fromCharCode(65 + remainder) + name;
      current = Math.floor((current - 1) / 26);
    }
    return name;
  }

  function makeSheetXml(headers, rows) {
    const allRows = [headers, ...rows];
    const rowXml = allRows
      .map((row, rowIndex) => {
        const cells = row
          .map((value, cellIndex) => {
            const ref = `${columnName(cellIndex)}${rowIndex + 1}`;
            if (value === "" || value === null || value === undefined) {
              return `<c r="${ref}" t="inlineStr"><is><t></t></is></c>`;
            }
            if (typeof value === "number") {
              return `<c r="${ref}"><v>${value}</v></c>`;
            }
            return `<c r="${ref}" t="inlineStr"><is><t>${xmlEscape(value)}</t></is></c>`;
          })
          .join("");
        return `<row r="${rowIndex + 1}">${cells}</row>`;
      })
      .join("");

    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
      <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
        <sheetData>${rowXml}</sheetData>
      </worksheet>`;
  }

  function crc32Table() {
    const table = new Uint32Array(256);
    for (let i = 0; i < 256; i += 1) {
      let c = i;
      for (let j = 0; j < 8; j += 1) {
        c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
      }
      table[i] = c >>> 0;
    }
    return table;
  }

  const CRC_TABLE = crc32Table();

  function crc32(bytes) {
    let crc = 0xffffffff;
    for (let i = 0; i < bytes.length; i += 1) {
      crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  function writeUInt16(array, offset, value) {
    array[offset] = value & 0xff;
    array[offset + 1] = (value >>> 8) & 0xff;
  }

  function writeUInt32(array, offset, value) {
    array[offset] = value & 0xff;
    array[offset + 1] = (value >>> 8) & 0xff;
    array[offset + 2] = (value >>> 16) & 0xff;
    array[offset + 3] = (value >>> 24) & 0xff;
  }

  function buildZip(files) {
    const encoder = new TextEncoder();
    const localParts = [];
    const centralParts = [];
    let offset = 0;

    files.forEach((file) => {
      const nameBytes = encoder.encode(file.name);
      const dataBytes = encoder.encode(file.content);
      const crc = crc32(dataBytes);

      const localHeader = new Uint8Array(30 + nameBytes.length);
      writeUInt32(localHeader, 0, 0x04034b50);
      writeUInt16(localHeader, 4, 20);
      writeUInt16(localHeader, 6, 0);
      writeUInt16(localHeader, 8, 0);
      writeUInt16(localHeader, 10, 0);
      writeUInt16(localHeader, 12, 0);
      writeUInt32(localHeader, 14, crc);
      writeUInt32(localHeader, 18, dataBytes.length);
      writeUInt32(localHeader, 22, dataBytes.length);
      writeUInt16(localHeader, 26, nameBytes.length);
      writeUInt16(localHeader, 28, 0);
      localHeader.set(nameBytes, 30);

      const centralHeader = new Uint8Array(46 + nameBytes.length);
      writeUInt32(centralHeader, 0, 0x02014b50);
      writeUInt16(centralHeader, 4, 20);
      writeUInt16(centralHeader, 6, 20);
      writeUInt16(centralHeader, 8, 0);
      writeUInt16(centralHeader, 10, 0);
      writeUInt16(centralHeader, 12, 0);
      writeUInt16(centralHeader, 14, 0);
      writeUInt32(centralHeader, 16, crc);
      writeUInt32(centralHeader, 20, dataBytes.length);
      writeUInt32(centralHeader, 24, dataBytes.length);
      writeUInt16(centralHeader, 28, nameBytes.length);
      writeUInt16(centralHeader, 30, 0);
      writeUInt16(centralHeader, 32, 0);
      writeUInt16(centralHeader, 34, 0);
      writeUInt16(centralHeader, 36, 0);
      writeUInt32(centralHeader, 38, 0);
      writeUInt32(centralHeader, 42, offset);
      centralHeader.set(nameBytes, 46);

      localParts.push(localHeader, dataBytes);
      centralParts.push(centralHeader);
      offset += localHeader.length + dataBytes.length;
    });

    const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
    const endRecord = new Uint8Array(22);
    writeUInt32(endRecord, 0, 0x06054b50);
    writeUInt16(endRecord, 4, 0);
    writeUInt16(endRecord, 6, 0);
    writeUInt16(endRecord, 8, files.length);
    writeUInt16(endRecord, 10, files.length);
    writeUInt32(endRecord, 12, centralSize);
    writeUInt32(endRecord, 16, offset);
    writeUInt16(endRecord, 20, 0);

    const totalSize =
      localParts.reduce((sum, part) => sum + part.length, 0) +
      centralSize +
      endRecord.length;
    const output = new Uint8Array(totalSize);
    let pointer = 0;

    [...localParts, ...centralParts, endRecord].forEach((part) => {
      output.set(part, pointer);
      pointer += part.length;
    });

    return output;
  }

  function exportAccountingXlsx() {
    const { products, rows } = accountingMatrix();
    const headers = ["name", "room", ...products.map((product) => product.name), "total"];
    const body = rows.map((row) => [
      row.residentName,
      row.room,
      ...products.map((product) => row.counts[product.id] || ""),
      Number(row.total.toFixed(2)),
    ]);
    const sheetXml = makeSheetXml(headers, body);
    const workbookXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
      <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
        <sheets>
          <sheet name="Regnskab" sheetId="1" r:id="rId1"/>
        </sheets>
      </workbook>`;
    const relsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
      <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
        <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
      </Relationships>`;
    const workbookRelsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
      <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
        <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
      </Relationships>`;
    const contentTypesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
      <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
        <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
        <Default Extension="xml" ContentType="application/xml"/>
        <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
        <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
      </Types>`;

    const archive = buildZip([
      { name: "[Content_Types].xml", content: contentTypesXml },
      { name: "_rels/.rels", content: relsXml },
      { name: "xl/workbook.xml", content: workbookXml },
      { name: "xl/_rels/workbook.xml.rels", content: workbookRelsXml },
      { name: "xl/worksheets/sheet1.xml", content: sheetXml },
    ]);

    const blob = new Blob([archive], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `regnskab-${state.filters.fromDate}-${state.filters.toDate}.xlsx`;
    link.click();
    URL.revokeObjectURL(url);
    showToast("Regnskab eksporteret.");
  }

  document.addEventListener("click", (event) => {
    const routeLink = event.target.closest("[data-route]");
    if (routeLink) {
      event.preventDefault();
      navigate(routeLink.getAttribute("href"));
      return;
    }

    const actionNode = event.target.closest("[data-action]");
    if (!actionNode) {
      return;
    }

    const action = actionNode.getAttribute("data-action");
    if (action === "increment-product") {
      updateProductQuantity(actionNode.getAttribute("data-product-id"), 1);
    } else if (action === "decrement-product") {
      event.stopPropagation();
      updateProductQuantity(actionNode.getAttribute("data-product-id"), -1);
    } else if (action === "select-resident") {
      state.selection.residentId = actionNode.getAttribute("data-resident-id");
      render();
    } else if (action === "buy") {
      performPurchase();
    } else if (action === "new-product") {
      setModal({ type: "product", item: null });
    } else if (action === "edit-product") {
      setModal({ type: "product", item: getProductById(actionNode.getAttribute("data-product-id")) });
    } else if (action === "toggle-product-active") {
      const product = getProductById(actionNode.getAttribute("data-product-id"));
      if (product) {
        product.active = !product.active;
        if (!product.active) {
          delete state.selection.quantities[product.id];
        }
        persistAll();
        render();
      }
    } else if (action === "delete-product") {
      removeProduct(actionNode.getAttribute("data-product-id"));
    } else if (action === "new-resident") {
      setModal({ type: "resident", item: null });
    } else if (action === "edit-resident") {
      setModal({ type: "resident", item: getResidentById(actionNode.getAttribute("data-resident-id")) });
    } else if (action === "toggle-resident-active") {
      const resident = getResidentById(actionNode.getAttribute("data-resident-id"));
      if (resident) {
        resident.active = !resident.active;
        if (!resident.active && state.selection.residentId === resident.id) {
          state.selection.residentId = null;
        }
        persistAll();
        render();
      }
    } else if (action === "delete-resident") {
      removeResident(actionNode.getAttribute("data-resident-id"));
    } else if (action === "close-modal") {
      if (event.target === actionNode) {
        closeModal();
      }
    } else if (action === "save-product") {
      saveProduct(actionNode.getAttribute("data-product-id"));
    } else if (action === "save-resident") {
      saveResident(actionNode.getAttribute("data-resident-id"));
    } else if (action === "upload-product-image") {
      event.preventDefault();
      handleImageUpload("#product-image");
    } else if (action === "upload-resident-image") {
      event.preventDefault();
      handleImageUpload("#resident-image");
    } else if (action === "set-acct-view") {
      setAccountingView(actionNode.getAttribute("data-view"));
    } else if (action === "retry-summary") {
      loadAccountingSummary(state.accounting.month, state.accounting.year);
    } else if (action === "open-cal-day") {
      openCalendarDay(Number(actionNode.getAttribute("data-day")));
    } else if (action === "cal-prev") {
      shiftCalendar(-1);
    } else if (action === "cal-next") {
      shiftCalendar(1);
    } else if (action === "cal-today") {
      calendarToday();
    } else if (action === "retry-calendar") {
      loadCalendar(state.calendar.month, state.calendar.year);
    } else if (action === "generate-small-teddy-next-month") {
      generateSmallTeddyNextMonth();
    } else if (action === "export-xlsx") {
      exportAccountingXlsx();
    }
  });

  document.addEventListener("change", (event) => {
    const action = event.target.getAttribute("data-action");
    if (action === "set-acct-month") {
      setAccountingMonthYear(Number(event.target.value), state.accounting.year);
    } else if (action === "set-acct-year") {
      setAccountingMonthYear(state.accounting.month, Number(event.target.value));
    } else if (action === "toggle-small-teddy") {
      toggleSmallTeddyDone(event.target.getAttribute("data-date"), event.target.checked);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.modal) {
      closeModal();
    }
  });

  window.addEventListener("popstate", render);

  async function loadState() {
    const [defaultProducts, defaultResidents, purchases] = await Promise.all([
      fetchJson("/data/seed/products.json"),
      fetchJson("/data/seed/residents.json"),
      fetchJson("/api/purchases"),
    ]);

    const currentSeedSignature = seedSignature(defaultProducts, defaultResidents);
    const storedSeedSignature = readStorage(storageKeys.seedSignature);
    const storedProducts = readStorage(storageKeys.products);
    const storedResidents = readStorage(storageKeys.residents);
    const useStoredCatalog = storedSeedSignature === currentSeedSignature;

    state.products = ((useStoredCatalog && storedProducts) || defaultProducts).map(normalizeProduct);
    state.residents = ((useStoredCatalog && storedResidents) || defaultResidents).map(normalizeResident);
    state.purchases = Array.isArray(purchases) ? purchases : [];

    // Default the accounting view to the most recent month that has data.
    const latest = latestPurchaseDate();
    state.accounting.month = latest.getMonth() + 1;
    state.accounting.year = latest.getFullYear();
    const range = monthRange(state.accounting.month, state.accounting.year);
    state.filters.fromDate = range.from;
    state.filters.toDate = range.to;

    writeStorage(storageKeys.seedSignature, currentSeedSignature);
    persistAll();
  }

  renderNav();
  app.innerHTML = `
    <div class="state-block">
      <div class="spinner"></div>
      <div class="state-title">Indlæser Kollegianeren…</div>
    </div>
  `;

  loadState()
    .then(() => {
      if (!routes[window.location.pathname]) {
        navigate("/system");
        return;
      }
      render();
    })
    .catch((error) => {
      app.innerHTML = `
        <div class="state-block">
          <div class="state-icon error">⚠️</div>
          <div class="state-title">Kunne ikke indlæse appen</div>
          <div class="state-text">${escapeHtml(error.message)}</div>
          <button class="primary-button" type="button" onclick="location.reload()">Genindlæs</button>
        </div>
      `;
    });
})();
