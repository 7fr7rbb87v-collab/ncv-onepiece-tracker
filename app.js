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
    const grid = document.getElementById("dealsGrid");
    grid.innerHTML = "<p>Data could not load. Check data/deals.json.</p>";
  }
}

function escapeForOnClick(text) {
  return String(text || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
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

    const image = deal.image || "https://via.placeholder.com/300x400?text=No+Image";
    const safeKeyword = escapeForOnClick(deal.keyword);

    card.innerHTML = `
      <img src="${image}" alt="${deal.title || "Product image"}">
      <div class="cardBody">
        <span class="badge">${deal.source || "Manual"} · ${deal.type || "item"}</span>
        <h3>${deal.title || deal.keyword || "Untitled"}</h3>
        <div class="price">$${Number(deal.price || 0).toFixed(2)}</div>
        <div>Buy Target: $${Number(deal.max_buy_price || 0).toFixed(2)}</div>
        <div>Resale Target: $${Number(deal.target_resale_price || 0).toFixed(2)}</div>
        <div class="profit">Est. Profit: $${Number(deal.estimated_profit || 0).toFixed(2)}</div>
        <button onclick="showChart('${deal.product_id}', '${safeKeyword}')">View Chart</button>
        <a href="${deal.url || '#'}" target="_blank" rel="noopener">Open Deal</a>
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

  const filtered = allDeals.filter(deal => deal.type === type);
  renderDeals(filtered);
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

  if (priceChart) {
    priceChart.destroy();
  }

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Lowest Price",
          data: lowestPrices
        },
        {
          label: "Average Price",
          data: averagePrices
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false
    }
  });
}

loadData();
