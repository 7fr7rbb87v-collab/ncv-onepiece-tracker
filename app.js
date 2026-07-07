let allDeals = [];
let allHistory = [];
let sourceStatus = {};
let priceChart = null;

async function loadData() {
  try {
    const dealsRes = await fetch("data/deals.json?v=" + Date.now());
    const historyRes = await fetch("data/price_history.json?v=" + Date.now());
    const statusRes = await fetch("data/source_status.json?v=" + Date.now());

    allDeals = await dealsRes.json();
    allHistory = await historyRes.json();
    sourceStatus = await statusRes.json();

    renderDeals(allDeals);
    renderStats(allDeals);
    renderSourceStatus(sourceStatus);
  } catch (err) {
    console.error(err);
    document.getElementById("dealsGrid").innerHTML =
      `<div class="empty-state">Failed to load dashboard data.</div>`;
  }
}

function renderStats(deals) {
  const totalDeals = deals.length;
  const buyLeads = deals.filter(d => d.is_buy_lead).length;
  const avgMargin = totalDeals
    ? Math.round(deals.reduce((sum, d) => sum + Number(d.estimated_profit || 0), 0) / totalDeals)
    : 0;
  const uniqueSources = new Set(deals.map(d => d.source || "Unknown")).size;

  document.getElementById("statDeals").textContent = totalDeals;
  document.getElementById("statBuyLeads").textContent = buyLeads;
  document.getElementById("statMargin").textContent = `$${avgMargin}`;
  document.getElementById("statSources").textContent = uniqueSources;

  const ebayStatus = sourceStatus?.ebay?.status || "unknown";
  document.getElementById("sourceStatusPill").textContent = `eBay: ${ebayStatus}`;
}

function renderDeals(deals) {
  const grid = document.getElementById("dealsGrid");
  grid.innerHTML = "";

  if (!deals || !deals.length) {
    grid.innerHTML = `<div class="empty-state">No live deals found yet. Run the source pull workflow.</div>`;
    return;
  }

  deals.forEach(deal => {
    const card = document.createElement("div");
    card.className = "deal-card";

    const buyBadge = deal.is_buy_lead
      ? `<span class="badge badge-buy">Buy Lead</span>`
      : "";

    const productTitle = deal.title || deal.product_name || "Untitled listing";
    const productId = deal.product_id || "";

    card.innerHTML = `
      <img class="deal-image" src="${deal.image || 'https://via.placeholder.com/400x400?text=No+Image'}" alt="${escapeHtml(productTitle)}">
      <div class="deal-body">
        <div class="deal-badges">
          <span class="badge badge-source">${escapeHtml(deal.source || 'Source')}</span>
          <span class="badge badge-grade">${escapeHtml(deal.deal_grade || 'Watch')}</span>
          ${buyBadge}
        </div>

        <h3 class="deal-title">${escapeHtml(productTitle)}</h3>

        <div class="price-line"><span>Listing Total</span><strong>$${formatNum(deal.listing_total || deal.price)}</strong></div>
        <div class="price-line"><span>Market Value</span><strong class="market-value">$${formatNum(deal.market_value)}</strong></div>
        <div class="price-line"><span>Offer Target -20%</span><strong>$${formatNum(deal.offer_target || deal.buy_target)}</strong></div>
        <div class="price-line"><span>Max Buy vs Market</span><strong>$${formatNum(deal.market_buy_target)}</strong></div>
        <div class="price-line"><span>Sale Target</span><strong>$${formatNum(deal.sale_target)}</strong></div>
        <div class="price-line"><span>Est. Spread to Sale</span><strong class="${deal.is_buy_lead ? 'buy-lead' : ''}">$${formatNum(deal.estimated_profit)}</strong></div>

        <div class="deal-actions">
          <button class="btn btn-secondary" onclick="showChart('${escapeAttr(productId)}', '${escapeAttr(productTitle)}')">View Chart</button>
          <a class="btn btn-primary" href="${deal.url || '#'}" target="_blank" rel="noopener noreferrer">Open Listing</a>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });
}

function filterDeals(type, btn) {
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");

  if (type === "all") {
    renderDeals(allDeals);
    return;
  }

  if (type === "buy_leads") {
    renderDeals(allDeals.filter(d => d.is_buy_lead));
    return;
  }

  renderDeals(allDeals.filter(d => d.type === type));
}

function showChart(productId, title) {
  const rows = allHistory.filter(row => row.product_id === productId);

  document.getElementById("chartTitle").textContent = title || "Price History";

  if (!rows.length) {
    if (priceChart) priceChart.destroy();
    return;
  }

  const labels = rows.map(r => r.timestamp || "");
  const activeLow = rows.map(r => Number(r.lowest_active_price || 0));
  const activeAvg = rows.map(r => Number(r.average_active_price || 0));
  const marketLine = rows.map(r => Number(r.market_value || 0));

  const ctx = document.getElementById("priceChart");

  if (priceChart) priceChart.destroy();

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Lowest Active", data: activeLow },
        { label: "Average Active", data: activeAvg },
        { label: "Market Value", data: marketLine }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          labels: { color: "#f5f7fb" }
        }
      },
      scales: {
        x: {
          ticks: { color: "#8ea0ba" },
          grid: { color: "rgba(255,255,255,0.05)" }
        },
        y: {
          ticks: { color: "#8ea0ba" },
          grid: { color: "rgba(255,255,255,0.05)" }
        }
      }
    }
  });
}

function renderSourceStatus(status) {
  const box = document.getElementById("sourceHealth");
  box.innerHTML = "";

  const sources = [
    { name: "eBay", key: "ebay" },
    { name: "eBay Sold", key: "ebay_sold" },
    { name: "Retail Search", key: "retail" },
    { name: "TikTok", key: "tiktok" }
  ];

  sources.forEach(src => {
    const val = status?.[src.key]?.status || "inactive";
    const row = document.createElement("div");
    row.className = "source-row";
    row.innerHTML = `
      <span>${src.name}</span>
      <span class="${val === 'success' ? 'source-ok' : 'source-bad'}">${val}</span>
    `;
    box.appendChild(row);
  });
}

function formatNum(value) {
  return Number(value || 0).toFixed(2);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(str) {
  return String(str)
    .replaceAll("\\", "\\\\")
    .replaceAll("'", "\\'")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

loadData();
