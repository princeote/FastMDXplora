/* FastMDXplora Live Dashboard — charts
 *
 * Lightweight canvas charts for the Live Simulation page. We rebuild
 * each chart's data buffer in place (no full canvas redraw) so updates
 * feel smooth even at high polling cadence. The set of canvases is
 * declared in dashboard.html as <canvas class="chart-canvas"
 * data-chart="...">; we discover them on load.

 * No chart library is used — keeping the offline mandate simple and
 * the footprint small.
 */

(function () {
  "use strict";

  const COLORS = {
    cyan: "#63e6ff",
    orange: "#ffb86b",
    violet: "#a78bfa",
    silver: "#d8d8dd",
    green: "#67e8a3",
    red: "#ff7272",
  };

  const GRID = "rgba(255, 255, 255, 0.06)";
  const AXIS = "#777780";

  /* chart configurations */
  const CHARTS = [
    {key: "potential_energy", color: COLORS.cyan,   label: "Potential energy",      unit: "kJ/mol"},
    {key: "temperature",      color: COLORS.orange, label: "Temperature",          unit: "K"},
    {key: "density",          color: COLORS.violet, label: "Density",              unit: "g/mL"},
    {key: "speed",            color: COLORS.silver, label: "Simulation speed",     unit: "ns/day"},
  ];

  /** chart key -> {canvas, ctx, lastSeries, lastBounds} */
  const chartState = new Map();

  function init() {
    document.querySelectorAll(".chart-canvas").forEach((canvas) => {
      const key = canvas.getAttribute("data-chart");
      const colorName = canvas.getAttribute("data-color") || "cyan";
      chartState.set(key, {
        canvas,
        ctx: canvas.getContext("2d"),
        lastSeries: null,
        lastBounds: null,
        color: COLORS[colorName] || COLORS.cyan,
      });
    });
    window.addEventListener("resize", () => draw());
    window.FastMDXDashboard &&
      window.FastMDXDashboard.on("playback-ready", () => draw());
  }

  /** @param {Array<{step:number, [key]:string}>} metrics */
  function update(metrics) {
    for (const chart of CHARTS) {
      const state = chartState.get(chart.key);
      if (!state) continue;
      const values = metrics
        .map((row) => parseFloat(row[chart.key]))
        .filter((v) => Number.isFinite(v));
      state.lastSeries = values;
      drawChart(state, chart, values);
    }
    const empty = document.getElementById("chart-empty");
    if (empty) {
      const any = Array.from(chartState.values()).some((s) => s.lastSeries && s.lastSeries.length);
      empty.style.display = any ? "none" : "block";
    }
  }

  function draw() {
    for (const chart of CHARTS) {
      const state = chartState.get(chart.key);
      if (!state || !state.lastSeries) continue;
      drawChart(state, chart, state.lastSeries);
    }
  }

  function drawChart(state, chart, values) {
    const canvas = state.canvas;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    const ctx = state.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    /* Background gradient */
    const grad = ctx.createLinearGradient(0, 0, 0, rect.height);
    grad.addColorStop(0, "rgba(99,230,255,0.04)");
    grad.addColorStop(1, "rgba(99,230,255,0)");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, rect.width, rect.height);

    /* Threshold markers */
    drawThresholds(ctx, chart, rect);

    /* Grid */
    ctx.strokeStyle = GRID;
    ctx.lineWidth = 1;
    for (let y = 20; y < rect.height - 18; y += 36) {
      ctx.beginPath(); ctx.moveTo(40, y); ctx.lineTo(rect.width - 12, y); ctx.stroke();
    }

    if (!values || !values.length) {
      ctx.fillStyle = AXIS;
      ctx.font = "12px " + monoFont();
      ctx.fillText("no data yet", rect.width / 2 - 36, rect.height / 2);
      return;
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max === min ? 1 : max - min;
    const padding = 18;
    const plotWidth = rect.width - 52;
    const plotHeight = rect.height - 30;

    /* Series line */
    ctx.strokeStyle = chart.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = 40 + plotWidth * (i / Math.max(1, values.length - 1));
      const y = padding + plotHeight * (1 - ((v - min) / span));
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    /* Soft area under the curve */
    ctx.lineTo(40 + plotWidth, padding + plotHeight);
    ctx.lineTo(40, padding + plotHeight);
    ctx.closePath();
    ctx.fillStyle = hexToRgba(chart.color, 0.08);
    ctx.fill();

    /* Min / max labels */
    ctx.fillStyle = AXIS;
    ctx.font = "10px " + monoFont();
    ctx.textAlign = "left";
    ctx.fillText(min.toFixed(2), 6, padding + 4);
    ctx.fillText(max.toFixed(2), 6, padding + plotHeight - 4);
    ctx.textAlign = "right";
    ctx.fillText(`${values.length} samples`, rect.width - 14, padding + 4);
    ctx.fillText(chart.unit, rect.width - 14, padding + plotHeight - 4);
  }

  function drawThresholds(ctx, chart, rect) {
    if (chart.key === "temperature") {
      /* Standard MD operating band: 270K..330K (broad OK). */
      drawBand(ctx, 270, 330, COLORS.green, rect, 0.06);
    }
    if (chart.key === "density") {
      drawBand(ctx, 0.98, 1.04, COLORS.green, rect, 0.06);
    }
    if (chart.key === "potential_energy") {
      /* "Healthy" range is trajectory-specific; we draw nothing by
         default. NaN / Inf values are screened out upstream. */
    }
  }

  function drawBand(ctx, lo, hi, color, rect, alpha) {
    const padding = 18;
    const plotHeight = rect.height - 30;
    const range = ctx.canvas.__lastRange;
    if (!range) return;
    const yLo = padding + plotHeight * (1 - (lo - range.min) / (range.max - range.min || 1));
    const yHi = padding + plotHeight * (1 - (hi - range.min) / (range.max - range.min || 1));
    ctx.fillStyle = hexToRgba(color, alpha);
    ctx.fillRect(40, Math.min(yLo, yHi), rect.width - 52, Math.abs(yHi - yLo));
  }

  function hexToRgba(hex, a) {
    const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
    if (!m) return hex;
    return `rgba(${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)}, ${a})`;
  }

  function monoFont() {
    return "JetBrains Mono, SFMono-Regular, IBM Plex Mono, Consolas, Menlo, monospace";
  }

  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("dashboard:metrics-updated", () => {
    /* No-op; dashboard.js calls update() directly after polling. */
  });
  window.FastMDXCharts = { update, draw };
})();
