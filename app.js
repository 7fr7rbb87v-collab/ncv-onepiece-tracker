let allDeals = [];
let allHistory = [];
let priceChart = null;

function money(value) {
  const number = Number(value || 0);
  return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function escapeForButton(value) {
  return String(value || "").replace(/'/g, "\\'");
}

async function loadData() {
  try {
    const cacheBust = Date.now();
    const dealsResponse = await fetch("data/deals.json?v=" + cacheBust);
    const historyResponse = await fetch("data/history.json?v=" + cacheBust);

    allDeals = await dealsResponse.json();
    allHistory = await historyResponse.json();

    renderDeals(allDeals);
  } catch (error) {
    console.error(error);
    document.getElementById("dealsGrid").innerHTML =
      "<p>Data could not load. Check data/deals.json and run the GitHub Action.</p>";
  }
}

function renderDeals(deals) {
  const grid = document.getElementById("dealsGrid");
  grid.innerHTML = "";

  if (!deals || deals.length === 0) {
    grid.innerHTML = "<p>No listings found yet. Add listings to manual_listings.csv and run the workflow.</p>";
    return;
  }

  deals.forEach(deal => {
    const card = document.createElement("div");
    card.className = "card";

    const safeKeyword = escapeForButton(deal.keyword);
    const safeProductId = escapeForButton(deal.product_id);

    card.innerHTML = `
      <img src="${deal.image || 'https://via.placeholder.com/300x400?text=No+Image'}" alt="${deal.title}">
      <div class="cardBody">
        <span class="badge">${deal.source || 'Manual'} · ${deal.type || 'item'}</span>
        <h3>${deal.title}</h3>
        <div class="price">Listed: $${money(deal.price)}</div>
        <div class="target">Buy Target -20%: $${money(deal.buy_target)}</div>
        <div class="target">Sale Target +35%: $${money(deal.sale_target)}</div>
        <div class="profit">Target Spread: $${money(deal.estimated_spread)}</div>
        <button onclick="showChart('${safeProductId}', '${safeKeyword}')">View Chart</button>
        <a href="${deal.url}" target="_blank">Open Listing</a>
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
  const listedPrices = chartData.map(item => item.lowest_price);
  const buyTargets = chartData.map(item => item.buy_target);
  const saleTargets = chartData.map(item => item.sale_target);

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
