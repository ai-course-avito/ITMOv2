// VkusMart Web Client, MCP Live Runner & Favorites Subsystem (Practice 5 SDD)

let state = {
  products: [],
  themes: [],
  cart: {}, // { "prod-1": 2, ... }
  favorites: new Set(), // Set of product_id
  cartCalculation: null
};

// Пресеты для быстрой демонстрации ревьюверу
const MCP_PRESETS = {
  vv_search_grechka: {
    tool: "vkusvill_products_search",
    args: { "q": "гречка", "limit": 5 }
  },
  vv_recipes_syrniki: {
    tool: "vkusvill_recipes",
    args: { "q": "сырники" }
  },
  vv_discount_search: {
    tool: "vkusvill_products_discount",
    args: { "q": "молоко", "limit": 5 }
  },
  vv_error_empty: {
    tool: "vkusvill_products_search",
    args: { "q": "" }
  },
  success_theme: {
    tool: "get_theme_bundles",
    args: { "theme_id": "theme-student", "max_budget": 500 }
  }
};

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initMCPConsole();
  initFavoritesModal();
  loadCatalogData();
  setupEventListeners();
});

function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      tabs.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  const cartBtn = document.getElementById("cartBtn");
  if (cartBtn) {
    cartBtn.addEventListener("click", () => {
      document.querySelector('[data-tab="cartTab"]')?.click();
    });
  }
}

async function loadCatalogData() {
  try {
    const res = await fetch("/api/catalog");
    const data = await res.json();
    state.products = data.products || [];
    state.themes = data.themes || [];
    await syncFavorites();
    renderThemes();
    renderProducts(state.products);
  } catch (err) {
    console.error("Ошибка загрузки каталога:", err);
  }
}

function renderThemes() {
  const container = document.getElementById("themesGrid");
  if (!container) return;

  const allergenFilter = document.getElementById("themeAllergenFilter")?.value || "";

  let filteredThemes = state.themes;
  container.innerHTML = "";

  state.themes.forEach(theme => {
    let themeProds = theme.product_ids
      .map(id => state.products.find(p => p.id === id))
      .filter(Boolean);

    if (allergenFilter) {
      themeProds = themeProds.filter(p => !p.allergens.includes(allergenFilter));
    }

    const price = themeProds.reduce((sum, p) => sum + p.price, 0);
    const calories = themeProds.reduce((sum, p) => sum + p.calories, 0);

    const card = document.createElement("div");
    card.className = "theme-card";
    card.innerHTML = `
      <div>
        <div class="theme-card-top">
          <span class="theme-icon">${theme.icon}</span>
          <div>
            <h3 class="theme-title">${theme.title}</h3>
            <p class="theme-desc">${theme.description}</p>
          </div>
        </div>
        <div class="theme-products-preview">
          ${themeProds.map(p => `
            <div class="preview-item">
              <span>${p.name}</span>
              <strong>${p.price} ₽</strong>
            </div>
          `).join("")}
        </div>
      </div>
      <div>
        <div class="theme-card-bottom">
          <div class="theme-price-info">
            <span class="theme-price">${price.toFixed(0)} ₽</span>
            <span class="theme-cals">${calories} ккал • ${themeProds.length} поз.</span>
          </div>
          <button class="btn btn-primary add-bundle-btn" data-theme-id="${theme.id}">+ В корзину</button>
        </div>
      </div>
    `;

    card.querySelector(".add-bundle-btn")?.addEventListener("click", () => {
      themeProds.forEach(p => addToCart(p.id, 1));
      showToast(`Набор «${theme.title}» добавлен в корзину!`);
    });

    container.appendChild(card);
  });
}

function renderProducts(products) {
  const container = document.getElementById("productsGrid");
  const countText = document.getElementById("productsCountText");
  if (!container) return;

  if (countText) countText.textContent = `Найдено: ${products.length} товаров`;
  container.innerHTML = "";

  if (products.length === 0) {
    container.innerHTML = `<div class="empty-state" style="grid-column: 1/-1;">Ничего не найдено. Попробуйте ослабить фильтры.</div>`;
    return;
  }

  products.forEach(p => {
    const isFav = state.favorites.has(p.id);
    const card = document.createElement("div");
    card.className = "product-card";
    card.innerHTML = `
      <button class="btn-fav ${isFav ? 'active' : ''}" data-id="${p.id}" title="${isFav ? 'Удалить из избранного' : 'Добавить в избранное'}">
        ${isFav ? '❤️' : '♡'}
      </button>
      <div>
        <div class="product-header">
          <h4 class="product-name">${p.name}</h4>
          <div class="product-meta">${p.weight} • ${p.calories} ккал</div>
        </div>
        <p style="font-size: 13px; color: var(--text-muted);">${p.description}</p>
        <div class="product-tags">
          ${p.tags.map(t => `<span class="tag">#${t}</span>`).join("")}
          ${p.allergens.map(a => `<span class="tag tag-allergen">⚠️ ${a}</span>`).join("")}
        </div>
      </div>
      <div class="product-bottom">
        <span class="product-price">${p.price} ₽</span>
        <button class="btn btn-secondary add-prod-btn" data-id="${p.id}">+ Купить</button>
      </div>
    `;

    // Кнопка избранного
    const favBtn = card.querySelector(".btn-fav");
    favBtn?.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleFavorite(p.id, favBtn);
    });

    // Кнопка добавления в корзину
    card.querySelector(".add-prod-btn")?.addEventListener("click", () => {
      addToCart(p.id, 1);
      showToast(`«${p.name}» добавлен в корзину`);
    });

    container.appendChild(card);
  });
}

function setupEventListeners() {
  document.getElementById("themeAllergenFilter")?.addEventListener("change", () => {
    renderThemes();
  });

  document.getElementById("applyFiltersBtn")?.addEventListener("click", async () => {
    const q = document.getElementById("searchInput")?.value.trim() || undefined;
    const cat = document.getElementById("categoryFilter")?.value || undefined;
    const maxP = parseFloat(document.getElementById("maxPriceInput")?.value) || undefined;
    const checkedAllergens = Array.from(document.querySelectorAll('input[name="catalogAllergen"]:checked')).map(cb => cb.value);
    const source = document.querySelector('input[name="searchSource"]:checked')?.value || "vkusvill_mcp";

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonClean({
          query: q,
          category: cat,
          max_price: maxP,
          exclude_allergens: checkedAllergens.length > 0 ? checkedAllergens : undefined,
          source: source
        })
      });
      const data = await res.json();
      if (res.ok) {
        renderProducts(data.products || []);
        showToast(source === "vkusvill_mcp" ? "Найдено через официальный ВкусВилл MCP!" : "Найдено в каталоге!");
      } else {
        alert("Ошибка поиска: " + (data.message || "Неверные параметры"));
      }
    } catch (e) {
      console.error(e);
    }
  });

  document.getElementById("resetFiltersBtn")?.addEventListener("click", () => {
    document.getElementById("searchInput").value = "";
    document.getElementById("categoryFilter").value = "";
    document.getElementById("maxPriceInput").value = "";
    document.querySelectorAll('input[name="catalogAllergen"]').forEach(cb => cb.checked = false);
    renderProducts(state.products);
  });

  document.getElementById("clearCartBtn")?.addEventListener("click", () => {
    state.cart = {};
    updateCartUI();
    showToast("Корзина очищена");
  });

  document.getElementById("openFavFromCartBtn")?.addEventListener("click", () => {
    openFavoritesModal();
  });
}

function addToCart(productId, qty = 1) {
  state.cart[productId] = (state.cart[productId] || 0) + qty;
  updateCartUI();
}

function removeFromCart(productId, qty = 1) {
  if (state.cart[productId]) {
    state.cart[productId] -= qty;
    if (state.cart[productId] <= 0) {
      delete state.cart[productId];
    }
  }
  updateCartUI();
}

async function updateCartUI() {
  const items = Object.entries(state.cart).map(([pid, qty]) => ({ product_id: pid, quantity: qty }));
  const totalCount = items.reduce((s, i) => s + i.quantity, 0);

  const badge = document.getElementById("cartCountBadge");
  if (badge) badge.textContent = totalCount;

  const itemsList = document.getElementById("cartItemsList");

  if (totalCount === 0) {
    if (itemsList) {
      itemsList.innerHTML = `<div class="empty-state">Ваша корзина пуста. Добавьте товары из каталога или подборок!</div>`;
    }
    updateSummaryUI(null);
    return;
  }

  try {
    const res = await fetch("/api/cart/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items })
    });
    const data = await res.json();
    if (res.ok && data.cart) {
      state.cartCalculation = data.cart;
      renderCartList(data.cart.items_detail);
      updateSummaryUI(data.cart);
    }
  } catch (e) {
    console.error("Cart calculate error:", e);
  }
}

function renderCartList(details) {
  const container = document.getElementById("cartItemsList");
  if (!container) return;
  container.innerHTML = "";

  details.forEach(item => {
    const row = document.createElement("div");
    row.className = "cart-item-row";
    row.innerHTML = `
      <div class="cart-item-info">
        <h4>${item.name}</h4>
        <span>${item.price} ₽/шт • ${item.calories} ккал</span>
      </div>
      <div class="cart-item-actions">
        <strong style="color: var(--primary); font-size: 15px;">${item.line_price} ₽</strong>
        <div class="qty-control">
          <button class="qty-btn dec-btn" data-id="${item.product_id}">-</button>
          <span class="qty-val">${item.quantity}</span>
          <button class="qty-btn inc-btn" data-id="${item.product_id}">+</button>
        </div>
      </div>
    `;

    row.querySelector(".dec-btn")?.addEventListener("click", () => removeFromCart(item.product_id, 1));
    row.querySelector(".inc-btn")?.addEventListener("click", () => addToCart(item.product_id, 1));

    container.appendChild(row);
  });
}

function updateSummaryUI(cart) {
  const subtotalEl = document.getElementById("summarySubtotal");
  const totalEl = document.getElementById("summaryTotal");
  const discountRow = document.getElementById("discountRow");
  const discountLabel = document.getElementById("discountLabel");
  const discountVal = document.getElementById("discountValue");
  const progressFill = document.getElementById("discountProgressBar");
  const progressText = document.getElementById("discountTargetText");

  if (!cart) {
    if (subtotalEl) subtotalEl.textContent = "0.0 ₽";
    if (totalEl) totalEl.textContent = "0.0 ₽";
    if (discountRow) discountRow.style.display = "none";
    if (progressFill) progressFill.style.width = "0%";
    if (progressText) progressText.textContent = "0 / 2500 ₽ (12%)";
    return;
  }

  if (subtotalEl) subtotalEl.textContent = `${cart.subtotal.toFixed(1)} ₽`;
  if (totalEl) totalEl.textContent = `${cart.final_price.toFixed(1)} ₽`;

  if (cart.discount_rub > 0) {
    if (discountRow) discountRow.style.display = "flex";
    if (discountLabel) discountLabel.textContent = `Скидка (${cart.discount_percent}%):`;
    if (discountVal) discountVal.textContent = `-${cart.discount_rub.toFixed(1)} ₽`;
  } else {
    if (discountRow) discountRow.style.display = "none";
  }

  // Прогресс скидки
  const pct = Math.min(100, Math.round((cart.subtotal / 2500.0) * 100));
  if (progressFill) progressFill.style.width = `${pct}%`;
  if (progressText) progressText.textContent = `${cart.subtotal.toFixed(0)} / 2500 ₽ (${cart.discount_percent}%)`;

  // КБЖУ
  const pVal = document.getElementById("macroProteinVal");
  const fVal = document.getElementById("macroFatVal");
  const cVal = document.getElementById("macroCarbsVal");
  const calVal = document.getElementById("macroCaloriesVal");

  if (pVal) pVal.textContent = `${cart.protein}г (${cart.macro_percentages.protein}%)`;
  if (fVal) fVal.textContent = `${cart.fat}г (${cart.macro_percentages.fat}%)`;
  if (cVal) cVal.textContent = `${cart.carbs}г (${cart.macro_percentages.carbs}%)`;
  if (calVal) calVal.textContent = `${cart.total_calories} ккал`;

  const alertsContainer = document.getElementById("nutritionAlerts");
  if (alertsContainer) {
    alertsContainer.innerHTML = (cart.nutrition_alerts || [])
      .map(a => `<div class="alert-box">⚠️ ${a}</div>`)
      .join("");
  }
}

// =========================================================================
// FAVORITES & WISHLIST MODULE (Practice 5 SDD / Spec-Kit)
// =========================================================================

function initFavoritesModal() {
  const modal = document.getElementById("favoritesModal");
  const openBtn = document.getElementById("favoritesBtn");
  const closeBtn = document.getElementById("closeFavModalBtn");
  const clearBtn = document.getElementById("clearFavoritesBtn");
  const moveBtn = document.getElementById("moveFavoritesToCartBtn");

  openBtn?.addEventListener("click", () => openFavoritesModal());
  closeBtn?.addEventListener("click", () => closeFavoritesModal());
  
  // Закрытие по клику вне модалки
  modal?.addEventListener("click", (e) => {
    if (e.target === modal) closeFavoritesModal();
  });

  clearBtn?.addEventListener("click", () => clearAllFavorites());
  moveBtn?.addEventListener("click", () => moveAllFavoritesToCart());
}

function openFavoritesModal() {
  const modal = document.getElementById("favoritesModal");
  if (modal) {
    modal.style.display = "flex";
    loadFavoritesModal();
  }
}

function closeFavoritesModal() {
  const modal = document.getElementById("favoritesModal");
  if (modal) modal.style.display = "none";
}

async function syncFavorites() {
  try {
    const res = await fetch("/api/favorites");
    if (res.ok) {
      const data = await res.json();
      state.favorites = new Set(data.items.map(i => i.id));
      updateFavBadge(data.total_count);
      updateAllFavButtons();
    }
  } catch (err) {
    console.error("Ошибка синхронизации избранного:", err);
  }
}

function updateFavBadge(count) {
  const badge = document.getElementById("favCountBadge");
  if (badge) {
    badge.textContent = count;
    badge.classList.remove("pulse");
    void badge.offsetWidth; // force reflow
    badge.classList.add("pulse");
  }
}

function updateAllFavButtons() {
  document.querySelectorAll(".btn-fav").forEach(btn => {
    const id = btn.getAttribute("data-id");
    const isFav = state.favorites.has(id);
    if (isFav) {
      btn.classList.add("active");
      btn.textContent = "❤️";
      btn.title = "Удалить из избранного";
    } else {
      btn.classList.remove("active");
      btn.textContent = "♡";
      btn.title = "Добавить в избранное";
    }
  });
}

async function toggleFavorite(productId, buttonElem) {
  const isFav = state.favorites.has(productId);
  const url = isFav ? "/api/favorites/remove" : "/api/favorites";

  if (buttonElem) buttonElem.classList.add("is-loading");

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId })
    });
    const data = await res.json();

    if (res.ok) {
      if (isFav) {
        state.favorites.delete(productId);
        showToast("Товар удалён из избранного");
      } else {
        state.favorites.add(productId);
        showToast(data.already_exists ? "Товар уже в избранном" : "Товар добавлен в избранное ❤️");
      }
      updateFavBadge(data.total_count);
      updateAllFavButtons();

      const modal = document.getElementById("favoritesModal");
      if (modal && modal.style.display !== "none") {
        loadFavoritesModal();
      }
    } else {
      showToast("Ошибка: " + (data.message || "Не удалось обновить избранное"));
    }
  } catch (err) {
    showToast("Сетевая ошибка при обновлении избранного");
  } finally {
    if (buttonElem) buttonElem.classList.remove("is-loading");
  }
}

async function loadFavoritesModal() {
  const listContainer = document.getElementById("favoritesList");
  const emptyState = document.getElementById("favoritesEmpty");
  const summaryText = document.getElementById("favSummaryText");
  const calBadge = document.getElementById("favCaloriesText");
  const moveBtn = document.getElementById("moveFavoritesToCartBtn");
  const clearBtn = document.getElementById("clearFavoritesBtn");

  if (!listContainer) return;
  listContainer.innerHTML = '<div class="loading-spinner">Загрузка избранного...</div>';

  try {
    const res = await fetch("/api/favorites");
    const data = await res.json();

    if (!res.ok) throw new Error(data.message || "Ошибка загрузки");

    state.favorites = new Set(data.items.map(i => i.id));
    updateFavBadge(data.total_count);
    updateAllFavButtons();

    if (data.total_count === 0) {
      listContainer.style.display = "none";
      if (emptyState) emptyState.style.display = "block";
      if (summaryText) summaryText.textContent = "0 товаров на сумму 0.0 ₽";
      if (calBadge) calBadge.textContent = "0 ккал";
      if (moveBtn) moveBtn.disabled = true;
      if (clearBtn) clearBtn.disabled = true;
      return;
    }

    listContainer.style.display = "flex";
    if (emptyState) emptyState.style.display = "none";
    if (moveBtn) moveBtn.disabled = false;
    if (clearBtn) clearBtn.disabled = false;

    if (summaryText) {
      summaryText.textContent = `${data.total_count} ${pluralizeGoods(data.total_count)} на сумму ${data.total_price.toFixed(1)} ₽`;
    }
    if (calBadge) calBadge.textContent = `${data.total_calories} ккал`;

    listContainer.innerHTML = data.items.map(p => `
      <div class="fav-item-row" data-id="${p.id}">
        <div class="fav-item-info">
          <div class="fav-item-title">${p.name}</div>
          <div class="fav-item-meta">${p.weight} • ${p.calories} ккал • ${p.price} ₽</div>
        </div>
        <div class="fav-item-right">
          <span class="fav-item-price">${p.price} ₽</span>
          <button class="btn btn-sm btn-primary add-fav-to-cart-btn" data-id="${p.id}">+ В корзину</button>
          <button class="btn btn-sm btn-outline remove-fav-btn" data-id="${p.id}" title="Удалить" style="color:var(--danger); border-color:#fca5a5;">✕</button>
        </div>
      </div>
    `).join("");

    listContainer.querySelectorAll(".add-fav-to-cart-btn").forEach(b => {
      b.addEventListener("click", () => {
        addToCart(b.dataset.id, 1);
        showToast("Товар добавлен в корзину");
      });
    });

    listContainer.querySelectorAll(".remove-fav-btn").forEach(b => {
      b.addEventListener("click", () => {
        toggleFavorite(b.dataset.id);
      });
    });

  } catch (e) {
    listContainer.innerHTML = `<div class="error-msg" style="color:var(--danger);padding:10px;">Ошибка загрузки: ${e.message}</div>`;
  }
}

async function moveAllFavoritesToCart() {
  try {
    const res = await fetch("/api/favorites/move-to-cart", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clear_favorites: true })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`Перенесено в корзину: ${data.moved_items_count} товаров!`);
      // Обновляем локальную корзину
      data.cart.items_detail.forEach(item => {
        state.cart[item.product_id] = (state.cart[item.product_id] || 0) + item.quantity;
      });
      state.favorites.clear();
      updateFavBadge(0);
      updateAllFavButtons();
      updateCartUI();
      loadFavoritesModal();
    } else {
      showToast("Ошибка переноса: " + (data.message || "Не удалось перенести"));
    }
  } catch (err) {
    showToast("Сетевая ошибка при переносе товаров");
  }
}

async function clearAllFavorites() {
  try {
    const res = await fetch("/api/favorites/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}"
    });
    if (res.ok) {
      state.favorites.clear();
      updateFavBadge(0);
      updateAllFavButtons();
      loadFavoritesModal();
      showToast("Список избранного очищен");
    } else {
      showToast("Ошибка при очистке избранного");
    }
  } catch (err) {
    showToast("Сетевая ошибка при очистке избранного");
  }
}

function pluralizeGoods(count) {
  const rem10 = count % 10;
  const rem100 = count % 100;
  if (rem10 === 1 && rem100 !== 11) return "товар";
  if (rem10 >= 2 && rem10 <= 4 && (rem100 < 10 || rem100 >= 20)) return "товара";
  return "товаров";
}

// =========================================================================
// MCP LIVE CONSOLE LOGIC
// =========================================================================

function initMCPConsole() {
  const toolSelect = document.getElementById("mcpToolSelect");
  const argsInput = document.getElementById("mcpArgsInput");
  const execBtn = document.getElementById("mcpExecuteBtn");
  const outputPre = document.getElementById("mcpOutputPre");
  const statusBadge = document.getElementById("mcpStatusBadge");

  document.querySelectorAll(".preset-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const pKey = btn.getAttribute("data-preset");
      const preset = MCP_PRESETS[pKey];
      if (preset) {
        toolSelect.value = preset.tool;
        argsInput.value = JSON.stringify(preset.args, null, 2);
        execBtn.click();
      }
    });
  });

  execBtn?.addEventListener("click", async () => {
    const toolName = toolSelect.value;
    let args = {};
    try {
      args = JSON.parse(argsInput.value);
    } catch (e) {
      alert("Некорректный JSON в аргументах: " + e.message);
      return;
    }

    statusBadge.className = "status-badge badge-idle";
    statusBadge.textContent = "Выполняется...";
    outputPre.textContent = `[JSON-RPC Request]\nMethod: tools/call\nTool: ${toolName}\nParams: ${JSON.stringify(args, null, 2)}\n\nОтправка запроса на MCP сервер...`;

    try {
      const res = await fetch("/api/mcp/call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: toolName, arguments: args })
      });
      const data = await res.json();
      const isErr = data.isError;

      statusBadge.className = isErr ? "status-badge badge-error" : "status-badge badge-success";
      statusBadge.textContent = isErr ? "Ошибка (Handled Error)" : "Успех (200 OK)";

      outputPre.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      statusBadge.className = "status-badge badge-error";
      statusBadge.textContent = "Сбой сети";
      outputPre.textContent = "Network Error: " + err.message;
    }
  });
}

function jsonClean(obj) {
  return JSON.stringify(obj, (k, v) => v === undefined ? null : v);
}

function showToast(msg) {
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => {
    t.style.opacity = "0";
    t.style.transition = "opacity 0.3s";
    setTimeout(() => t.remove(), 300);
  }, 2500);
}
