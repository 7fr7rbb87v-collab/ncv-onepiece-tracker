let allDeals = [];
let allHistory = [];
let priceChart = null;

function money(value) {
  const number = Number(value || 0);
  return number.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function escapeText(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeForButton(value) {
  return String(value || "").replace(/'/g, "\\'");
}

async function loadData() {
  try {
    const cacheBust = Date.now();
    const dealsResponse = await fetch(`data/deals.json?v=${cacheBust}`);
    const historyResponse = await fetch(`data/history.json?v=${cacheBust}`);

    allDeals = await dealsResponse.json();
    allHistory = await historyResponse.json();

    renderDeals(allDeals);
  } catch (error) {
    console.error(error);
    document.getElementById("dealsGrid").innerHTML =
      "<p class='empty'>Data could not load. Check data/deals.json and run the GitHub Action.</p>";
  }
}

function renderDeals(deals) {
  const grid = document.getElementById("dealsGrid");
  grid.innerHTML = "";

  if (!deals || deals.length === 0) {
    grid.innerHTML = "<p class='empty'>No listings found yet. Add listings to manual_listings.csv and run the workflow.</p>";
    return;
  }

  deals.forEach((deal) => {
    const card = document.createElement("article");
    card.className = "card";

    const safeKeyword = escapeForButton(deal.keyword);
    const safeProductId = escapeForButton(deal.product_id);
    const image = deal.image || "https://via.placeholder.com/300x400?text=No+Image";

    card.innerHTML = `
      <img class="card-img" src="${escapeText(image)}" alt="${escapeText(deal.title)}" loading="lazy" />
      <div class="card-body">
        <div class="badge">${escapeText(deal.source || "Manual")} · ${escapeText(deal.type || "item")}</div>
        <h3>${escapeText(deal.title)}</h3>
        <div class="metric listed">Listed: $${money(deal.price)}</div>
        <div class="metric">Buy Target -20%: $${money(deal.buy_target)}</div>
        <div class="metric">Sale Target +35%: $${money(deal.sale_target)}</div>
        <div class="metric spread">Target Spread: $${money(deal.estimated_spread)}</div>
        <button class="chart-btn" onclick="showChart('${safeProductId}', '${safeKeyword}')">View Chart</button>
        <a class="open-btn" href="${escapeText(deal.url)}" target="_blank" rel="noopener noreferrer">Open Listing</a>
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

  const filtered = allDeals.filter((deal) => deal.type === type);
  renderDeals(filtered);
}

function showChart(productId, keyword) {
  const chartData = allHistory.filter((item) => item.product_id === productId);
  document.getElementById("chartTitle").innerText = `${keyword} Price History`;

  if (!chartData.length) {
    alert("No history data yet. Run the workflow a few times to build history.");
    return;
  }

  const labels = chartData.map((item) => item.timestamp);
  const listedPrices = chartData.map((item) => item.lowest_price);
  const buyTargets = chartData.map((item) => item.buy_target);
  const saleTargets = chartData.map((item) => item.sale_target);

  const ctx = document.getElementById("priceChart");

  if (priceChart) {
    priceChart.destroy();
  }

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        { label: "Listed Price", data: listedPrices },
        { label: "Buy Target -20%", data: buyTargets },
        { label: "Sale Target +35%", data: saleTargets }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: $${money(context.raw)}`;
            }
          }
        }
      }
    }
  });
}

loadData();
