let allDeals = [];
let allHistory = [];
let retailLeads = [];
let tiktokVideos = [];
let sourceStatus = {};
let priceChart = null;

function money(value) {
  const number = Number(value || 0);
  return `$${number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function safeText(value) {
  return String(value || "").replace(/[&<>'"]/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;"
  }[c]));
}

function scrollToSection(id) {
  document.getElementById(id).scrollIntoView({ behavior: "smooth" });
}

async function fetchJson(path, fallback) {
  try {
    const response = await fetch(`${path}?v=${Date.now()}`);
    if (!response.ok) return fallback;
    return await response.json();
  } catch (error) {
    console.error(`Could not load ${path}`, error);
    return fallback;
  }
}

async function loadData() {
  allDeals = await fetchJson("data/deals.json", []);
  allHistory = await fetchJson("data/history.json", []);
  retailLeads = await fetchJson("data/retail_leads.json", []);
  tiktokVideos = await fetchJson("data/tiktok_videos.json", []);
  sourceStatus = await fetchJson("data/source_status.json", {});

  renderStatus();
  renderStrongLeads();
  renderDeals(allDeals);
  renderRetail();
  renderTikTok();
}

function renderStatus() {
  const statusBox = document.getElementById("statusBox");
  statusBox.textContent = JSON.stringify(sourceStatus, null, 2);

  const ebay = sourceStatus.ebay || {};
  const topStatus = document.getElementById("topStatus");
  if (ebay.status === "success") {
    topStatus.textContent = `eBay connected · ${ebay.listings_found || 0} listings`;
  } else if (ebay.status) {
    topStatus.textContent = `eBay status: ${ebay.status}`;
  } else {
    topStatus.textContent = "No source status yet";
  }
}

function dealCard(deal) {
  const image = deal.image || "https://via.placeholder.com/400x500?text=No+Image";
  const title = safeText(deal.title || deal.product_name);
  const grade = safeText(deal.deal_grade || "Watch");
  const gradeClass = ["A+", "A", "B"].includes(grade) ? "good" : "warn";

  return `
    <article class="card">
      <img src="${image}" alt="${title}" loading="lazy" />
      <div class="card-body">
        <span class="badge">${safeText(deal.source)} · ${safeText(deal.type)} · ${safeText(deal.era)}</span>
        <h3>${title}</h3>
        <div class="price">${money(deal.total_price || deal.price)}</div>
        <div class="metric">Market listing value: ${money(deal.market_value)}</div>
        <div class="metric">Buy under-market target: ${money(deal.buy_target)}</div>
        <div class="metric">Sale target +35%: ${money(deal.sale_target)}</div>
        <div class="metric">Gap to buy target: ${money(deal.gap_to_buy_target)}</div>
        <div class="metric">Estimated profit from listing: ${money(deal.estimated_profit)}</div>
        <div class="metric">Discount to market: ${Number(deal.discount_to_market_percent || 0).toFixed(2)}%</div>
        <div class="${gradeClass}">Grade: ${grade}${deal.is_buy_lead ? " · BUY LEAD" : ""}</div>
        <div class="metric">Seller: ${safeText(deal.seller_username || "N/A")}</div>
        <div class="card-actions">
          <button onclick="showChart('${safeText(deal.product_id)}', '${safeText(deal.product_name)}')">View chart</button>
          <a class="button-link" href="${deal.url}" target="_blank" rel="noopener">Open listing</a>
        </div>
      </div>
    </article>
  `;
}

function renderStrongLeads() {
  const grid = document.getElementById("strongLeadsGrid");
  const strong = allDeals.filter(deal => deal.is_buy_lead || ["A+", "A"].includes(deal.deal_grade)).slice(0, 24);
  grid.innerHTML = strong.length ? strong.map(dealCard).join("") : "<p class='muted'>No listings are at or under the buy target yet.</p>";
}

function renderDeals(deals) {
  const grid = document.getElementById("dealsGrid");
  grid.innerHTML = deals.length ? deals.map(dealCard).join("") : "<p class='muted'>No eBay listings found yet. Check Source Status for API errors.</p>";
}

function filterDeals(filter) {
  if (filter === "all") return renderDeals(allDeals);
  const filtered = allDeals.filter(deal => deal.type === filter || deal.era === filter);
  renderDeals(filtered);
}

function showChart(productId, productName) {
  const rows = allHistory.filter(row => row.product_id === productId);
  document.getElementById("chartTitle").textContent = `${productName} Price History`;

  if (!rows.length) {
    alert("No history yet. Run the workflow a few times to build history.");
    return;
  }

  const ctx = document.getElementById("priceChart");
  if (priceChart) priceChart.destroy();

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: rows.map(row => row.timestamp),
      datasets: [
        { label: "Lowest active", data: rows.map(row => row.lowest_active_price) },
        { label: "Average active", data: rows.map(row => row.average_active_price) },
        { label: "Market value", data: rows.map(row => row.market_value) },
        { label: "Buy under-market target", data: rows.map(row => row.buy_target) },
        { label: "Sale target", data: rows.map(row => row.sale_target) }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false }
  });
}

function renderRetail() {
  const grid = document.getElementById("retailGrid");
  grid.innerHTML = retailLeads.length ? retailLeads.map(lead => `
    <article class="card">
      <div class="card-body">
        <span class="badge">${safeText(lead.source)}</span>
        <h3>${safeText(lead.title)}</h3>
        <div class="metric">Price signal: ${lead.price_signal ? money(lead.price_signal) : "Not found"}</div>
        <div class="metric">Buy target: ${lead.buy_target ? money(lead.buy_target) : "N/A"}</div>
        <p class="muted">${safeText(lead.description)}</p>
        <a class="button-link" href="${lead.url}" target="_blank" rel="noopener">Open retail lead</a>
      </div>
    </article>
  `).join("") : "<p class='muted'>Retail search is disabled or no leads were found.</p>";
}

function renderTikTok() {
  const grid = document.getElementById("tiktokGrid");
  grid.innerHTML = tiktokVideos.length ? tiktokVideos.map(video => `
    <article class="card">
      ${video.thumbnail_url ? `<img src="${video.thumbnail_url}" alt="${safeText(video.title)}" loading="lazy" />` : ""}
      <div class="card-body">
        <span class="badge">${safeText(video.source)}</span>
        <h3>${safeText(video.title)}</h3>
        <div class="metric">${safeText(video.author_name)}</div>
        <a class="button-link" href="${video.url}" target="_blank" rel="noopener">Open TikTok</a>
      </div>
    </article>
  `).join("") : "<p class='muted'>TikTok search is disabled or no videos were found.</p>";
}

loadData();
