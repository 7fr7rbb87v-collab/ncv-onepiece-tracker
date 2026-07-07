let allDeals = [];
let allHistory = [];
let allRetail = [];
let allTikTok = [];
let ebayStatus = {};
let priceChart = null;

function currency(value) {
  const number = Number(value || 0);
  return "$" + number.toFixed(2);
}

async function loadJson(path, fallback) {
  const response = await fetch(path + "?v=" + Date.now());
  if (!response.ok) return fallback;
  return await response.json();
}

async function loadData() {
  try {
    allDeals = await loadJson("data/deals.json", []);
    allHistory = await loadJson("data/history.json", []);
    allRetail = await loadJson("data/retail_inventory.json", []);
    allTikTok = await loadJson("data/tiktok_videos.json", []);
    ebayStatus = await loadJson("data/ebay_status.json", {});

    renderStatus();
    renderDeals(allDeals);
    renderRetail(allRetail);
    renderTikTok(allTikTok);
  } catch (error) {
    console.error(error);
    document.getElementById("dealsGrid").innerHTML =
      "<p>Data could not load. Check the JSON files in the data folder.</p>";
  }
}

function renderStatus() {
  const box = document.getElementById("ebayStatus");
  const errors = ebayStatus.errors || [];
  if (errors.length) {
    box.innerHTML = `eBay API connected with ${errors.length} error(s). Check data/ebay_status.json.`;
    box.className = "status warning";
  } else if (ebayStatus.enabled) {
    box.innerHTML = `eBay API active · ${ebayStatus.marketplace || "EBAY_US"} · Last checked: ${ebayStatus.last_checked || ""}`;
    box.className = "status good";
  } else {
    box.innerHTML = "eBay API disabled";
    box.className = "status warning";
  }
}

function renderDeals(deals) {
  const grid = document.getElementById("dealsGrid");
  grid.innerHTML = "";

  if (!deals || deals.length === 0) {
    grid.innerHTML = "<p>No deals found yet. Run the workflow and check data/ebay_status.json.</p>";
    return;
  }

  deals.forEach(deal => {
    const card = document.createElement("div");
    card.className = "card";

    const image = deal.image || "https://via.placeholder.com/300x400?text=No+Image";
    const source = deal.source || "Unknown";
    const type = deal.type || "unknown";
    const seller = deal.seller ? `<div>Seller: ${deal.seller}</div>` : "";
    const condition = deal.condition ? `<div>Condition: ${deal.condition}</div>` : "";

    card.innerHTML = `
      <img src="${image}" alt="${deal.title || "Product image"}" loading="lazy">
      <div class="cardBody">
        <span class="badge">${source} · ${type}</span>
        <h3>${deal.title || "Untitled"}</h3>
        <div class="price">${currency(deal.price)}</div>
        <div>Offer Target -20%: ${currency(deal.buy_target)}</div>
        <div>Sale Target +35%: ${currency(deal.sale_target)}</div>
        <div class="profit">Target Spread: ${currency(deal.estimated_spread)}</div>
        ${condition}
        ${seller}
        <button onclick="showChart('${deal.product_id}', '${String(deal.keyword || deal.title || "Product").replace(/'/g, "\\'")}')">View Chart</button>
        <a href="${deal.url || "#"}" target="_blank">Open Listing</a>
      </div>
    `;

    grid.appendChild(card);
  });
}

function filterDeals(type) {
  if (type === "all") {
    renderDeals(allDeals);
    return;
  }
  renderDeals(allDeals.filter(deal => deal.type === type));
}

function filterBySource(source) {
  if (source === "Manual") {
    renderDeals(allDeals.filter(deal => String(deal.source || "").includes("Manual")));
    return;
  }
  renderDeals(allDeals.filter(deal => deal.source === source));
}

function showChart(productId, keyword) {
  const chartData = allHistory.filter(item => item.product_id === productId);
  document.getElementById("chartTitle").innerText = `${keyword} Price History`;

  if (!chartData.length) {
    alert("No history data yet. Run the workflow a few times to build history.");
    return;
  }

  const labels = chartData.map(item => item.timestamp);
  const lowestPrices = chartData.map(item => item.lowest_price);
  const averagePrices = chartData.map(item => item.average_price);

  const ctx = document.getElementById("priceChart");
  if (priceChart) priceChart.destroy();

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        { label: "Lowest Price", data: lowestPrices },
        { label: "Average Price", data: averagePrices }
      ]
    },
    options: { responsive: true }
  });
}

function renderRetail(items) {
  const grid = document.getElementById("retailGrid");
  grid.innerHTML = "";
  if (!items || !items.length) {
    grid.innerHTML = "<p>No retail inventory rows yet.</p>";
    return;
  }

  items.forEach(item => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <img src="${item.image || "https://via.placeholder.com/300x400?text=Retail"}" alt="${item.title}" loading="lazy">
      <div class="cardBody">
        <span class="badge">${item.retailer} · ${item.stock_status}</span>
        <h3>${item.title}</h3>
        <div class="price">${Number(item.price || 0) > 0 ? currency(item.price) : "Price unknown"}</div>
        <div>Offer Target -20%: ${Number(item.price || 0) > 0 ? currency(item.buy_target) : "—"}</div>
        <div>Sale Target +35%: ${Number(item.price || 0) > 0 ? currency(item.sale_target) : "—"}</div>
        <div>${item.store || "Online"} ${item.zip_code || ""}</div>
        <p>${item.notes || ""}</p>
        <a href="${item.url || "#"}" target="_blank">Open Product</a>
      </div>
    `;
    grid.appendChild(card);
  });
}

function renderTikTok(videos) {
  const grid = document.getElementById("tiktokGrid");
  grid.innerHTML = "";
  if (!videos || !videos.length) {
    grid.innerHTML = "<p>No TikTok videos yet. Add links to tiktok_videos.csv.</p>";
    return;
  }

  videos.forEach(video => {
    const card = document.createElement("div");
    card.className = "videoCard";
    card.innerHTML = `
      <h3>${video.label || "TikTok Video"}</h3>
      <a href="${video.url}" target="_blank">Open TikTok</a>
    `;
    grid.appendChild(card);
  });
}

loadData();
