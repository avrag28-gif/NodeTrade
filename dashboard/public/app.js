const API_BASE = window.NODETRADE_PUBLIC_API || "";
const endpoint = `${API_BASE}/v1/public/performance`;

const $ = id => document.getElementById(id);
const fmt = (v, suffix = "") => v === null || v === undefined ? "—" : `${v}${suffix}`;

function drawEquity(points) {
  const canvas = $("equityChart");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const w = rect.width, h = rect.height;
  ctx.clearRect(0, 0, w, h);
  if (!points || points.length < 2) {
    ctx.fillStyle = "#9aa7c2";
    ctx.font = "14px system-ui";
    ctx.fillText("No equity data available", 20, 30);
    return;
  }
  const values = points.map(Number).filter(Number.isFinite);
  if (values.length < 2) return;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  ctx.strokeStyle = "#34415f";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) { const y = 20 + (h - 40) * i / 4; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke(); }
  ctx.strokeStyle = "#8fa9ff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((v, i) => { const x = 8 + (w - 16) * i / (values.length - 1); const y = h - 20 - (h - 40) * (v - min) / span; i ? ctx.lineTo(x,y) : ctx.moveTo(x,y); });
  ctx.stroke();
}

function render(data) {
  const m = data.metrics || {};
  $("netPnl").textContent = fmt(m.net_pnl ?? data.net_pnl);
  $("returnPct").textContent = fmt(m.return_pct ?? (data.return === null ? null : data.return * 100), "%");
  $("winRate").textContent = fmt(m.win_rate ?? (data.win_rate * 100), "%");
  $("drawdown").textContent = fmt(m.max_drawdown_pct ?? data.max_drawdown, "%");
  $("profitFactor").textContent = fmt(m.profit_factor ?? data.profit_factor);
  $("trades").textContent = fmt(m.total_trades ?? data.trade_count);
  $("updatedAt").textContent = data.updated_at || new Date().toISOString();
  $("period").textContent = data.period || "All recorded events";
  const risk = { "Expectancy": m.expectancy ?? data.expectancy, "Average win": m.average_win ?? data.average_win, "Average loss": m.average_loss ?? data.average_loss, "Consecutive losses": m.max_consecutive_losses ?? data.consecutive_losses };
  $("riskList").innerHTML = Object.entries(risk).map(([k,v]) => `<dt>${k}</dt><dd>${fmt(v)}</dd>`).join("");
  const system = { "Model": data.system?.model_version ?? data.model_version, "Regime": data.system?.regime ?? "—", "Signals": data.system?.signals ?? data.signal_statistics?.closed_profit_events, "Data status": data.system?.data_status ?? data.system_status };
  $("systemList").innerHTML = Object.entries(system).map(([k,v]) => `<dt>${k}</dt><dd>${fmt(v)}</dd>`).join("");
  drawEquity(data.equity_curve || []);
  $("status").textContent = "● Public data connected";
}

async function load() {
  try {
    const res = await fetch(endpoint, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    render(await res.json());
  } catch (e) {
    $("status").textContent = "● Data unavailable";
    console.error("NodeTrade public dashboard:", e);
  }
}

window.addEventListener("resize", load);
load();
setInterval(load, 60000);
