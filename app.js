let deals = [];
let ebayListings = [];
let activeHistory = [];
let soldHistory = [];
let retailInventory = [];
let tiktokVideos = [];
let sourceStatus = {};
let priceChart = null;

const cacheBust = `?v=${Date.now()}`;

function money(value) {
  const n = Number(value || 0);
  if (!n) return "$0.00";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function pct(value) {
  const n = Number(value || 0);
  return `${n.toFixed(1)}%`;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function getJson(path, fallback) {
  try {
    const res = await fetch(path + cacheBust);
    if (!res.ok) return fallback;
    return await res.json();
  } catch (e) {
    console.error(`Failed loading ${path}`, e);
    return fallback;
  }
}

async function loadData() {
  [deals, ebayListings, activeHistory, soldHistory, retailInventory, tiktokVideos, sourceStatus] = await Promise.all([
    getJson("data/deals.json", []),
    getJson("data/ebay_listings.json", []),
    getJson("data/active_price_history.json", []),
    getJson("data/sold_price_history.json", []),
    getJson("data/retail_inventory.json", []),
    getJson("data/tiktok_videos.json", []),
    getJson("data/source_status.json", {})
  ]);

  document.getElementById("lastRun").textContent = sourceStatus.last_run || "Not run yet";
  renderDeals();
  renderEbay();
  renderSold();
  renderRetail();
  renderTikTok();
  renderStatus();
  populateProductSelect();
}

function showSection(id) {
  document.querySelectorAll(".section").forEach(section => section.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  if (id === "charts") renderChart();
}

function card(listing, mode = "deal") {
  const grade = listing.deal_grade || "";
  const gradeClass = `grade-${String(grade).replace("+", "\\+")}`;
  const image = listing.image || "https://via.placeholder.com/400x500?text=No+Image";
  const total = listing.total_price || listing.price || 0;
  const title = listing.title || listing.product_name || "Untitled result";
  const url = listing.url || "#";

  return `
    <article class="card">
      <img src="${esc(image)}" alt="${esc(title)}" loading="lazy">
      <div class="card-body">
        <div class="badges">
          <span class="badge">${esc(listing.source || "Source")}</span>
          <span class="badge">${esc(listing.type || "")}</span>
          <span class="badge">${esc(listing.era || "")}</span>
          ${grade ? `<span class="badge ${gradeClass}">Grade ${esc(grade)}</span>` : ""}
        </div>
        <h3>${esc(title)}</h3>
        <div class="price">${money(total)}</div>
        ${listing.shipping ? `<div class="metric">Shipping: <strong>${money(listing.shipping)}</strong></div>` : ""}
        ${listing.market_value ? `<div class="metric">Market value: <strong>${money(listing.market_value)}</strong> <small>(${esc(listing.market_value_source)})</small></div>` : ""}
        ${listing.buy_target ? `<div class="metric">Buy target -20%: <strong>${money(listing.buy_target)}</strong></div>` : ""}
        ${listing.sale_target ? `<div class="metric">Sale target +35%: <strong>${money(listing.sale_target)}</strong></div>` : ""}
        ${listing.expected_profit_at_sale_target ? `<div class="metric profit">Expected spread: ${money(listing.expected_profit_at_sale_target)}</div>` : ""}
        ${listing.discount_to_market_pct ? `<div class="metric">Discount to market: <strong>${pct(listing.discount_to_market_pct)}</strong></div>` : ""}
        ${listing.condition ? `<div class="metric">Condition: <strong>${esc(listing.condition)}</strong></div>` : ""}
        ${listing.seller_username ? `<div class="metric">Seller: <strong>${esc(listing.seller_username)}</strong> ${listing.seller_feedback_percentage ? `· ${esc(listing.seller_feedback_percentage)}%` : ""}</div>` : ""}
        <a href="${esc(url)}" target="_blank" rel="noopener">Open Listing</a>
      </div>
    </article>`;
}

function renderDeals() {
  const el = document.getElementById("dealGrid");
  const strong = deals.filter(d => ["A+", "A", "B", "Watch"].includes(d.deal_grade)).slice(0, 80);
  el.innerHTML = strong.length ? strong.map(d => card(d, "deal")).join("") : `<div class="empty">No strong leads yet. Confirm EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, ENABLE_EBAY=1, then run the workflow.</div>`;
}

function renderEbay() {
  const el = document.getElementById("ebayGrid");
  el.innerHTML = ebayListings.length ? ebayListings.slice(0, 120).map(d => card(d, "ebay")).join("") : `<div class="empty">No eBay listings pulled yet.</div>`;
}

function renderSold() {
  const el = document.getElementById("soldGrid");
  if (!soldHistory.length) {
    el.innerHTML = `<div class="empty">No sold comps available yet. eBay Marketplace Insights is limited access. Enable it with ENABLE_EBAY_SOLD=1 after approval.</div>`;
    return;
  }
  el.innerHTML = soldHistory.slice().reverse().slice(0, 120).map(s => `
    <article class="card">
      <img src="${esc(s.image || 'https://via.placeholder.com/400x500?text=Sold+Comp')}" alt="${esc(s.title)}" loading="lazy">
      <div class="card-body">
        <div class="badges"><span class="badge">${esc(s.source)}</span><span class="badge">${esc(s.type)}</span></div>
        <h3>${esc(s.title)}</h3>
        <div class="price">${money(s.total_sold_price || s.sold_price)}</div>
        <div class="metric">Sold date: <strong>${esc(s.sold_date || 'n/a')}</strong></div>
        <a href="${esc(s.url || '#')}" target="_blank" rel="noopener">Open Sold Comp</a>
      </div>
    </article>`).join("");
}

function renderRetail() {
  const el = document.getElementById("retailGrid");
  if (!retailInventory.length) {
    el.innerHTML = `<div class="empty">No retail source leads yet. Add BRAVE_SEARCH_API_KEY and set ENABLE_RETAIL_SEARCH=1.</div>`;
    return;
  }
  el.innerHTML = retailInventory.map(r => `
    <article class="card">
      <div class="card-body">
        <div class="badges"><span class="badge">${esc(r.retailer)}</span><span class="badge">${esc(r.stock_status)}</span></div>
        <h3>${esc(r.title)}</h3>
        ${r.price ? `<div class="price">${money(r.price)}</div><div class="metric">Buy target: <strong>${money(r.buy_target)}</strong></div><div class="metric">Sale target: <strong>${money(r.sale_target)}</strong></div>` : `<div class="metric">Price: <strong>Check source</strong></div>`}
        <p class="metric">${esc(r.description || '')}</p>
        <a href="${esc(r.url)}" target="_blank" rel="noopener">Open Retail Source</a>
      </div>
    </article>`).join("");
}

function renderTikTok() {
  const el = document.getElementById("tiktokGrid");
  if (!tiktokVideos.length) {
    el.innerHTML = `<div class="empty">No TikTok rip videos discovered yet. Add BRAVE_SEARCH_API_KEY and set ENABLE_TIKTOK_SEARCH=1.</div>`;
    return;
  }
  el.innerHTML = tiktokVideos.map(v => `
    <article class="card">
      <div class="card-body">
        <div class="badges"><span class="badge">${esc(v.source)}</span><span class="badge">${esc(v.product_id)}</span></div>
        <h3>${esc(v.title || 'TikTok video')}</h3>
        ${v.embed_html || (v.thumbnail_url ? `<img src="${esc(v.thumbnail_url)}" alt="${esc(v.title)}">` : '')}
        <a href="${esc(v.url)}" target="_blank" rel="noopener">Open TikTok</a>
      </div>
    </article>`).join("");
  if (window.tiktokEmbedLoad) window.tiktokEmbedLoad();
}

function renderStatus() {
  document.getElementById("statusBox").textContent = JSON.stringify(sourceStatus, null, 2);
}

function populateProductSelect() {
  const select = document.getElementById("productSelect");
  const products = [...new Map(activeHistory.map(h => [h.product_id, h])).values()];
  select.innerHTML = products.map(p => `<option value="${esc(p.product_id)}">${esc(p.product_name || p.product_id)}</option>`).join("");
  renderChart();
}

function renderChart() {
  const select = document.getElementById("productSelect");
  if (!select.value) return;
  const rows = activeHistory.filter(h => h.product_id === select.value);
  const ctx = document.getElementById("priceChart");
  if (priceChart) priceChart.destroy();
  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: rows.map(r => r.timestamp),
      datasets: [
        { label: "Lowest active", data: rows.map(r => r.lowest_active_price) },
        { label: "Average active", data: rows.map(r => r.average_active_price) },
        { label: "Market value", data: rows.map(r => r.market_value) }
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#f4f6fb" } } },
      scales: {
        x: { ticks: { color: "#aab3c2" }, grid: { color: "#293143" } },
        y: { ticks: { color: "#aab3c2" }, grid: { color: "#293143" } }
      }
    }
  });
}

loadData();
