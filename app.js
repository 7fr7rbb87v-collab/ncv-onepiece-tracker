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

    card.innerHTML = `
      <img src="${deal.image || 'https://via.placeholder.com/300x400?text=No+Image'}" alt="${deal.title}">
      <div class="cardBody">
        <span class="badge">${deal.source} · ${deal.type}</span>
        <h3>${deal.title}</h3>
        <div class="price">$${deal.price}</div>
        <div>Buy Target: $${deal.max_buy_price}</div>
        <div>Resale Target: $${deal.target_resale_price}</div>
        <div class="profit">Est. Profit: $${deal.estimated_profit}</div>
        <button onclick="showChart('${deal.product_id}', '${deal.keyword.replace(/'/g, "\\'")}')">View Chart</button>
        <a href="${deal.url}" target="_blank">Open Deal</a>
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
      responsive: true
    }
  });
}

loadData();
