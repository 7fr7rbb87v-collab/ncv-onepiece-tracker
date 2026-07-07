let allDeals = [];
let allHistory = [];
let retailLeads = [];
let tiktokVideos = [];
let sourceStatus = {};
let priceChart = null;

const money = value => Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const safe = value => String(value || "").replace(/[&<>'"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
const btnSafe = value => String(value || "").replace(/'/g, "\\'");

async function fetchJson(path, fallback) {
  try {
    const response = await fetch(`${path}?v=${Date.now()}`);
    if (!response.ok) return fallback;
    return await response.json();
  } catch (error) {
    console.error(`Failed to load ${path}`, error);
    return fallback;
  }
}

async function loadData() {
  allDeals = await fetchJson("data/deals.json", []);
  allHistory = await fetchJson("data/history.json", []);
  retailLeads = await fetchJson("data/retail_leads.json", []);
  tiktokVideos = await fetchJson("data/tiktok_videos.json", []);
  sourceStatus = await fetchJson("data/source_status.json", {});

  renderStrongLeads();
  renderDeals(allDeals);
  renderRetail();
  renderTikTok();
  renderStatus();
}

function gradeClass(grade) {
  const g = String(grade || "").toLowerCase().replace("+", "-plus");
  return `grade-${g}`;
}

function listingCard(deal) {
  const productId = btnSafe(deal.product_id);
  const productName = btnSafe(deal.product_name || deal.keyword || deal.title);
  return `
    <article class="card">
      <img src="${safe(deal.image) || 'https://via.placeholder.com/400x400?text=No+Image'}" alt="${safe(deal.title)}">
      <div class="card-body">
        <div class="badges">
          <span class="badge">${safe(deal.source || 'Source')}</span>
          <span class="badge">${safe(deal.type || 'item')}</span>
          <span class="badge">${safe(deal.era || 'era')}</span>
          <span class="badge ${gradeClass(deal.deal_grade)}">${safe(deal.deal_grade || 'Grade')}</span>
        </div>
        <h3>${safe(deal.title)}</h3>
        <div class="price">$${money(deal.total_price || deal.price)}</div>
        <div class="meta">
          Listed: $${money(deal.price)}${Number(deal.shipping || 0) ? ` + ship $${money(deal.shipping)}` : ''}<br>
          Market value: $${money(deal.market_value)}<br>
          Buy target: $${money(deal.buy_target)}<br>
          Sale target: $${money(deal.sale_target)}<br>
          Discount: ${Number(deal.discount_to_market_percent || 0).toFixed(1)}%<br>
          Seller: ${safe(deal.seller_username || 'n/a')}
        </div>
        <div class="actions">
          <button onclick="showChart('${productId}', '${productName}')">View Chart</button>
          <a href="${safe(deal.url)}" target="_blank" rel="noopener">Open Listing</a>
        </div>
      </div>
    </article>`;
}

function renderStrongLeads() {
  const grid = document.getElementById("strongLeadsGrid");
  const strong = allDeals.filter(d => ["A+", "A", "B"].includes(d.deal_grade)).slice(0, 24);
  grid.innerHTML = strong.length ? strong.map(listingCard).join("") : `<div class="empty">No strong leads yet. Run the workflow after adding eBay API secrets.</div>`;
}

function renderDeals(deals) {
  const grid = document.getElementById("dealsGrid");
  grid.innerHTML = deals.length ? deals.map(listingCard).join("") : `<div class="empty">No eBay listings found yet. Check data/ebay_status.json after running the workflow.</div>`;
}

function filterDeals(type) {
  if (type === "all") return renderDeals(allDeals);
  const filtered = allDeals.filter(deal => deal.type === type || deal.era === type);
  renderDeals(filtered);
}

function renderRetail() {
  const grid = document.getElementById("retailGrid");
  if (!retailLeads.length) {
    grid.innerHTML = `<div class="empty">Retail search is off or no retail leads were found. Turn ENABLE_RETAIL_SEARCH=1 and add BRAVE_SEARCH_API_KEY to use this.</div>`;
    return;
  }
  grid.innerHTML = retailLeads.map(lead => `
    <article class="card">
      <div class="card-body">
        <div class="badges"><span class="badge">Retail Lead</span><span class="badge">${safe(lead.source)}</span></div>
        <h3>${safe(lead.title)}</h3>
        <div class="meta">${safe(lead.description)}</div>
        ${Number(lead.price_signal || 0) ? `<div class="price">$${money(lead.price_signal)}</div><div class="meta">Buy target: $${money(lead.buy_target)}<br>Sale target: $${money(lead.sale_target)}</div>` : ''}
        <div class="actions"><a href="${safe(lead.url)}" target="_blank" rel="noopener">Open Product</a></div>
      </div>
    </article>`).join("");
}

function renderTikTok() {
  const grid = document.getElementById("tiktokGrid");
  if (!tiktokVideos.length) {
    grid.innerHTML = `<div class="empty">TikTok search is off or no videos were found. Turn ENABLE_TIKTOK_SEARCH=1 and add BRAVE_SEARCH_API_KEY to use this.</div>`;
    return;
  }
  grid.innerHTML = tiktokVideos.map(video => `
    <article class="card">
      <div class="card-body">
        <div class="badges"><span class="badge">TikTok</span><span class="badge">${safe(video.author_name || '')}</span></div>
        <h3>${safe(video.title)}</h3>
        ${video.thumbnail_url ? `<img src="${safe(video.thumbnail_url)}" alt="${safe(video.title)}">` : ''}
        <div class="actions"><a href="${safe(video.url)}" target="_blank" rel="noopener">Open TikTok</a></div>
      </div>
    </article>`).join("");
}

function renderStatus() {
  const statusBox = document.getElementById("statusBox");
  const pill = document.getElementById("statusPill");
  statusBox.textContent = JSON.stringify(sourceStatus, null, 2);

  const ebay = sourceStatus.ebay || {};
  if (ebay.status === "success") {
    pill.textContent = `eBay connected · ${ebay.listings_found || 0} listings`;
  } else if (ebay.status) {
    pill.textContent = `eBay status: ${ebay.status}`;
  } else {
    pill.textContent = "Status not generated yet";
  }
}

function showChart(productId, productName) {
  const chartData = allHistory.filter(row => row.product_id === productId);
  document.getElementById("chartTitle").innerText = `${productName} Price History`;
  if (!chartData.length) {
    alert("No history data yet. Run the workflow a few times to build the chart.");
    return;
  }

  const labels = chartData.map(row => row.timestamp);
  const ctx = document.getElementById("priceChart");
  if (priceChart) priceChart.destroy();

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Lowest active price", data: chartData.map(row => row.lowest_active_price) },
        { label: "Average active price", data: chartData.map(row => row.average_active_price) },
        { label: "Market value", data: chartData.map(row => row.market_value) },
        { label: "Buy target", data: chartData.map(row => row.buy_target) },
        { label: "Sale target", data: chartData.map(row => row.sale_target) }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          callbacks: {
            label: context => `${context.dataset.label}: $${money(context.raw)}`
          }
        }
      }
    }
  });

  document.getElementById("charts").scrollIntoView({ behavior: "smooth" });
}

loadData();
