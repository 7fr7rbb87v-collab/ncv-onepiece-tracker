let allDeals = [];
let allHistory = [];
let priceChart = null;

async function loadData() {
  try {
    const dealsResponse = await fetch("data/deals.json?v=" + Date.now());
    const historyResponse = await fetch("data/history.json?v=" + Date.now());

    allDeals = await dealsResponse.json();
    allHistory = await historyResponse.json();

    renderDeals(allDeals);
  } catch (error) {
    console.error(error);
    document.getElementById("dealsGrid").innerHTML =
      "<p>Data could not load. Check data/deals.json.</p>";
  }
}

function escapeText(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderDeals(deals) {
  const grid = document.getElementById("dealsGrid");
  grid.innerHTML = "";

  if (!deals || deals.length === 0) {
    grid.innerHTML = "<p>No deals found yet. Check manual_listings.csv and run the workflow.</p>";
    return;
  }

  deals.forEach(deal => {
    const card = document.createElement("div");
    card.className = "card";

    const safeTitle = escapeText(deal.title);
    const safeKeyword = escapeText(deal.keyword);

    card.innerHTML = `
      <img src="${deal.image || 'https://via.placeholder.com/300x400?text=No+Image'}" alt="${safeTitle}">
      <div class="cardBody">
        <span class="badge">${escapeText(deal.source)} · ${escapeText(deal.type)}</span>
        <h3>${safeTitle}</h3>
        <div class="price">$${deal.price}</div>
        <div>Buy Target: $${deal.max_buy_price}</div>
        <div>Resale Target: $${deal.target_resale_price}</div>
        <div class="profit">Est. Profit: $${deal.estimated_profit}</div>
        <button data-product-id="${escapeText(deal.product_id)}" data-keyword="${safeKeyword}" class="chartBtn">View Chart</button>
        <a href="${deal.url}" target="_blank" rel="noopener noreferrer">Open Deal</a>
      </div>
    `;

    grid.appendChild(card);
  });

  document.querySelectorAll(".chartBtn").forEach(button => {
    button.addEventListener("click", () => {
      showChart(button.dataset.productId, button.dataset.keyword);
    });
  });
}

function filterDeals(type) {
  if (type === "all") {
    renderDeals(allDeals);
    return;
  }

  const filtered = allDeals.filter(deal => deal.type === type);
  renderDeals(filtered);
}

function showChart(productId, keyword) {
  const chartData = allHistory.filter(item => item.product_id === productId);

  document.getElementById("chartTitle").innerText = `${keyword} Price History`;

  if (!chartData.length) {
    alert("No history data yet. Run the workflow to build history.");
    return;
  }

  const labels = chartData.map(item => item.timestamp);
  const lowestPrices = chartData.map(item => item.lowest_price);
  const averagePrices = chartData.map(item => item.average_price);

  const ctx = document.getElementById("priceChart");

  if (priceChart) {
    priceChart.destroy();
  }

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

loadData();
