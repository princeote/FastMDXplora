/* FastMDXplora Live Dashboard — controller
 *
 * Vanilla JS — no framework, no CDN. Responsible for:
 *   - Page navigation (Overview / Live / Viewer / Analysis / Files / Settings)
 *   - Polling telemetry & state APIs at a configurable interval
 *   - Updating top bar, hero card, metric cards, stage timeline, events
 *   - Broadcasting state changes to charts.js and molecule-viewer.js
 *   - Honouring "Pause Updates" (browser-side only)
 */

(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const state = {
    outputDir: "",
    polling: true,
    paused: false,
    pollIntervalMs: 3000,
    lastUpdateMs: 0,
    refreshTimer: null,
    pages: ["overview", "live", "viewer", "analysis", "files", "settings"],
    activePage: "overview",
    ligandResname: null,
    bindingPocketCutoff: 5,
    playbackAvailable: false,
    playbackFrames: 0,
    playbackTotalFrames: 0,
    metrics: [],
    status: {},
    health: {},
    structureInfo: null,
    runId: "",
    runTitle: "FastMDXplora Live",
  };

  /* ---------------------------------------------- *
   * Boot                                          *
   * ---------------------------------------------- */
  document.addEventListener("DOMContentLoaded", boot);

  function boot() {
    wireNavigation();
    wireTopBar();
    wireViewerToggle();
    wireInfoTabs();
    wireTrajectoryControls();
    wireSettings();
    startLoadingChecklist();
    schedulePoll(0);
  }

  function wireNavigation() {
    $$("[data-view-link]").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.preventDefault();
        const target = el.getAttribute("data-view-link");
        navigate(target);
      });
    });
  }

  function navigate(page) {
    if (!state.pages.includes(page)) return;
    state.activePage = page;
    $$(".page").forEach((el) => {
      const hidden = el.getAttribute("data-page") !== page;
      el.hidden = hidden;
    });
    $$("[data-view-link]").forEach((el) => {
      const isActive = el.getAttribute("data-view-link") === page;
      el.classList.toggle("active", isActive);
    });
    if (page === "viewer") {
      window.dispatchEvent(new CustomEvent("dashboard:viewer-page-opened"));
    }
    if (page === "analysis" || page === "files") {
      window.dispatchEvent(new CustomEvent("dashboard:results-page-opened"));
    }
  }

  function startLoadingChecklist() {
    setLoadingStep("telemetry", "active");
    fetchJSON("/api/status")
      .then(() => setLoadingStep("telemetry", "done"))
      .catch(() => setLoadingStep("telemetry", "error"));
    setLoadingStep("structure", "active");
    fetchJSON("/api/structure-info")
      .then(() => setLoadingStep("structure", "done"))
      .catch(() => setLoadingStep("structure", "error"));
    setLoadingStep("metrics", "active");
    fetchJSON("/api/metrics")
      .then(() => setLoadingStep("metrics", "done"))
      .catch(() => setLoadingStep("metrics", "error"));
    setTimeout(() => {
      document.body.classList.remove("state-loading");
      document.body.classList.add("state-ready");
    }, 1100); /* fade-out tied to successful lookup, not a fixed timeout, but with a brief post-poll settle delay */
  }

  function setLoadingStep(name, status) {
    const el = document.querySelector(`.loading-step[data-step="${name}"]`);
    if (el) el.setAttribute("data-state", status);
  }

  function wireTopBar() {
    $("#pause-toggle").addEventListener("click", () => {
      state.paused = !state.paused;
      $("#pause-toggle").setAttribute("aria-pressed", state.paused);
      $("#pause-label").textContent = state.paused ? "Resume Updates" : "Pause Updates";
    });
    $("#refresh-now").addEventListener("click", () => {
      schedulePoll(0);
    });
    $("#open-output").addEventListener("click", () => {
      /* Best-effort: the dashboard never opens the OS browser from a
         page that's already opened in a browser; show the absolute path
         and copy it. */
      const text = $("#sidebar-run-name").textContent || "";
      if (!text || text === "not available") return;
      const toast = document.createElement("div");
      toast.className = "sr-only";
      toast.textContent = `Output folder: ${text}`;
      document.body.appendChild(toast);
    });
  }

  function wireViewerToggle() {
    $("#mini-preview-frame").addEventListener("click", () => navigate("viewer"));
  }

  function wireInfoTabs() {
    $$(".info-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        const name = tab.getAttribute("data-tab");
        $$(".info-tab").forEach((t) => t.classList.toggle("active", t === tab));
        $$(".info-pane").forEach((p) => {
          p.hidden = p.getAttribute("data-tab") !== name;
          p.classList.toggle("active", p.getAttribute("data-tab") === name);
        });
      });
    });
  }

  function wireTrajectoryControls() {
    const slider = $("#traj-slider");
    if (!slider) return;
    slider.addEventListener("input", () => {
      const frame = parseInt(slider.value, 10);
      window.dispatchEvent(
        new CustomEvent("dashboard:trajectory-seek", {detail: {frame}})
      );
    });
    $$("[data-traj]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const action = btn.getAttribute("data-traj");
        window.dispatchEvent(
          new CustomEvent("dashboard:trajectory-action", {detail: {action}})
        );
      });
    });
  }

  function wireSettings() {
    /* Settings page wires its own values via onSettingsChanged */
    document.getElementById("setting-refresh-seconds")
      .addEventListener("change", onSettingsChanged);
    document.getElementById("setting-pocket-cutoff")
      .addEventListener("change", onSettingsChanged);
    document.getElementById("setting-reduced-motion")
      .addEventListener("change", onSettingsChanged);
    document.getElementById("setting-ligand-resname")
      .addEventListener("change", onSettingsChanged);
    document.getElementById("setting-chart-history")
      .addEventListener("change", onSettingsChanged);
  }

  function onSettingsChanged() {
    state.pollIntervalMs = clampInt(
      parseInt($("#setting-refresh-seconds").value, 10), 1000, 60000, 3000);
    state.bindingPocketCutoff = clampFloat(
      parseFloat($("#setting-pocket-cutoff").value), 3.0, 15.0, 5.0);
    const lig = ($("#setting-ligand-resname").value || "").trim().toUpperCase();
    state.ligandResname = lig || null;
    chartHistorySamples = clampInt(
      parseInt($("#setting-chart-history").value, 10), 60, 5000, 600);
    document.body.classList.toggle("compact-mode",
      $("#setting-compact").checked);
    document.body.classList.toggle("reduced-motion",
      $("#setting-reduced-motion").checked);
    /* Tell the viewer + chart modules to bind the new settings */
    window.dispatchEvent(new CustomEvent("dashboard:settings-updated", {
      detail: {
        ligand: state.ligandResname,
        pocketCutoff: state.bindingPocketCutoff,
        chartHistory: chartHistorySamples,
      }
    }));
    schedulePoll(0);
  }

  /* ---------------------------------------------- *
   * Polling                                       *
   * ---------------------------------------------- */
  let chartHistorySamples = 600;

  async function fetchJSON(url) {
    const res = await fetch(url, {cache: "no-store", headers: {"X-FastMDX": "live"}});
    if (!res.ok) throw new Error(`HTTP ${res.status} on ${url}`);
    return await res.json();
  }

  function schedulePoll(delayMs) {
    if (state.refreshTimer) {
      clearTimeout(state.refreshTimer);
      state.refreshTimer = null;
    }
    if (state.paused) {
      state.refreshTimer = setTimeout(() => schedulePoll(state.pollIntervalMs), state.pollIntervalMs);
      return;
    }
    state.refreshTimer = setTimeout(() => {
      pollNow().catch((err) => console.warn("dashboard poll error", err))
        .finally(() => schedulePoll(state.pollIntervalMs));
    }, Math.max(0, delayMs));
  }

  async function pollNow() {
    const [statusPayload, metricsPayload, eventsPayload, resultsPayload, structurePayload, playbackPayload] =
      await Promise.allSettled([
        fetchJSON("/api/status"),
        fetchJSON("/api/metrics"),
        fetchJSON("/api/events"),
        fetchJSON("/api/results"),
        fetchJSON("/api/structure-info"),
        fetchJSON("/api/playback-info"),
      ]);

    if (statusPayload.status === "fulfilled") {
      applyStatus(statusPayload.value);
    }
    if (metricsPayload.status === "fulfilled") {
      applyMetrics(metricsPayload.value.metrics || []);
    }
    if (eventsPayload.status === "fulfilled") {
      renderEvents(eventsPayload.value.events || []);
    }
    if (resultsPayload.status === "fulfilled") {
      applyResults(resultsPayload.value);
    }
    if (structurePayload.status === "fulfilled") {
      applyStructure(structurePayload.value);
    }
    if (playbackPayload.status === "fulfilled") {
      applyPlayback(playbackPayload.value);
    }

    state.lastUpdateMs = Date.now();
    updateRefreshedAt();
    pulseTopbarIfLive();
  }

  function pulseTopbarIfLive() {
    const age = (Date.now() - state.lastUpdateMs) / 1000;
    const dot = $("#topbar-status-dot");
    if (age > 30) {
      dot.classList.remove("status-dot-live");
      dot.classList.add("status-dot-stale");
    } else {
      dot.classList.add("status-dot-live");
      dot.classList.remove("status-dot-stale");
    }
  }

  function updateRefreshedAt() {
    const date = new Date(state.lastUpdateMs);
    const use24 = !$("#setting-time-format") || $("#setting-time-format").value !== "12h";
    const fmt = use24
      ? `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {hour12: false})}`
      : date.toLocaleTimeString();
    const el = $("#refreshed-at");
    if (el) el.textContent = fmt;
  }

  function applyStatus(payload) {
    const status = payload.status || {};
    const health = payload.health || {};
    state.status = status;
    state.health = health;
    renderTopBar(status, health);
    renderHero(status);
    renderHealth(health);
    renderStageTimeline(status);
    renderLiveProgress(status);
    window.dispatchEvent(new CustomEvent("dashboard:status-updated", {detail: {status, health}}));
  }

  function renderTopBar(status, health) {
    const stateName = (health.state || status.status || "live").toLowerCase();
    const dot = $("#topbar-status-dot");
    dot.className = "status-dot " + stateDotClass(stateName);
    $("#topbar-status-text").textContent = stateName;
    $("#topbar-stage").textContent = status.stage || "not available";
    const step = status.current_step;
    const total = status.total_planned_steps;
    $("#topbar-step").textContent = step != null ? String(step) : "—";
    $("#topbar-total").textContent = total != null ? String(total) : "—";
    $("#topbar-platform").textContent = status.platform || "—";
    const temp = status.target_temperature_K ||
      (state.metrics.length
        ? (state.metrics[state.metrics.length - 1].temperature || "")
        : "");
    $("#topbar-temperature").textContent = temp ? `${temp} K` : "—";

    $("#sidebar-status-dot").className = "status-dot " + stateDotClass(stateName);
    $("#sidebar-connection-state").textContent = stateName;
    $("#sidebar-platform").textContent = status.platform || "not available";
    $("#sidebar-run-name").textContent = state.runTitle;
    state.runId = status.system_id || state.runId;
    $("#topbar-run-id").textContent = state.runId || "system";
    $("#topbar-run-title").textContent = state.runTitle;
  }

  function stateDotClass(s) {
    if (s === "ok" || s === "live" || s === "completed") return "status-dot-live";
    if (s === "warning" || s === "waiting" || s === "stale") return "status-dot-stale";
    if (s === "failed" || s === "error") return "status-dot-error";
    return "status-dot-stale";
  }

  function renderHero(status) {
    const card = $("#hero-card");
    card.setAttribute("data-state", (status.status || "running").toLowerCase());
    $("#hero-stage").textContent = status.stage || "—";
    let pct = null;
    if (typeof status.progress_percent === "number") pct = status.progress_percent;
    else if (status.current_step && status.total_planned_steps)
      pct = (status.current_step / status.total_planned_steps) * 100;
    if (pct !== null) {
      $("#hero-progress-fill").style.width = `${Math.max(0, Math.min(100, pct))}%`;
      $("#hero-progress-pct").textContent = pct.toFixed(1);
    } else {
      $("#hero-progress-fill").style.width = "0%";
      $("#hero-progress-pct").textContent = "—";
    }
    $("#hero-sim-time").textContent = status.simulation_time_completed_ns
      ? status.simulation_time_completed_ns.toFixed(3) : "—";
    $("#hero-elapsed").textContent = status.elapsed_wall_time_s
      ? fmtDuration(status.elapsed_wall_time_s) : "—";
    $("#hero-eta").textContent = computeETA(status);
    $("#hero-step").textContent = status.current_step != null
      ? `${status.current_step} / ${status.total_planned_steps ?? "—"}` : "—";
  }

  function fmtDuration(seconds) {
    const s = Math.max(0, Math.floor(seconds));
    const hh = Math.floor(s / 3600);
    const mm = Math.floor((s % 3600) / 60);
    const ss = s % 60;
    return hh ? `${hh}h ${mm}m` : `${mm}m ${ss}s`;
  }

  function computeETA(status) {
    if (!status.current_step || !status.total_planned_steps
        || !status.elapsed_wall_time_s) return "—";
    const total = status.total_planned_steps;
    const elapsed = status.elapsed_wall_time_s;
    const ratio = total / Math.max(status.current_step, 1);
    return fmtDuration(elapsed * (ratio - 1));
  }

  function renderHealth(health) {
    const card = $("#hero-health");
    const stateName = health.state || "unknown";
    card.setAttribute("data-state", stateName);
    $("#health-headline").textContent = health.message || stateName;
    $("#health-explanation").textContent = health.explanation || "";
    $("#health-pill").textContent = stateName;
    $("#health-pill").setAttribute("data-state", stateName);
    const items = (health.items || []).slice(0, 4);
    const list = $("#health-list");
    list.innerHTML = items.map((it) =>
      `<li data-state="${escapeAttr(it.severity || "ok")}">
        <strong>${escapeHTML(it.title || it.severity || "info")}</strong>
        <span class="muted small"> — ${escapeHTML(it.detail || "")}</span>
      </li>`
    ).join("");
    const livePill = $("#live-health-pill");
    if (livePill) {
      livePill.textContent = stateName;
      livePill.setAttribute("data-state", stateName);
    }
    $("#live-health-message").textContent = health.message || "not available";
    $("#live-health-explanation").textContent = health.explanation || "";
  }

  function renderStageTimeline(status) {
    const map = {
      setup: "setup", minimization: "minimization", nvt: "nvt",
      npt: "npt", production: "production", analysis: "analysis",
      report: "report", loading: "setup"
    };
    const order = ["setup", "minimization", "nvt", "npt", "production", "analysis", "report"];
    const current = (status.stage || "").toLowerCase();
    const currentIdx = order.indexOf(map[current] || current);
    $$(".stage-step").forEach((el) => {
      const stage = el.getAttribute("data-stage");
      const idx = order.indexOf(stage);
      el.removeAttribute("data-state");
      if (idx === -1) return;
      if (idx < currentIdx) el.setAttribute("data-state", "completed");
      else if (idx === currentIdx) el.setAttribute("data-state", "current");
      else el.setAttribute("data-state", "waiting");
    });
  }

  function renderLiveProgress(status) {
    let pct = null;
    if (typeof status.progress_percent === "number") pct = status.progress_percent;
    else if (status.current_step && status.total_planned_steps)
      pct = (status.current_step / status.total_planned_steps) * 100;
    if (pct !== null) {
      $("#live-progress-fill").style.width = `${Math.max(0, Math.min(100, pct))}%`;
      $("#live-progress-pct").textContent = pct.toFixed(1);
    } else {
      $("#live-progress-fill").style.width = "0%";
      $("#live-progress-pct").textContent = "—";
    }
    $("#live-sim-time").textContent = status.simulation_time_completed_ns
      ? status.simulation_time_completed_ns.toFixed(3) : "—";
    $("#live-stage-cell").textContent = status.stage || "not available";
    $("#live-step-cell").textContent = status.current_step != null ? String(status.current_step) : "not available";
    $("#live-total-cell").textContent = status.total_planned_steps != null ? String(status.total_planned_steps) : "not available";
    $("#live-frames-cell").textContent = status.current_frame_count != null
      ? `${status.current_frame_count}${status.planned_frame_count != null ? ` / ${status.planned_frame_count}` : ""}`
      : "not available";
    $("#live-simtime-cell").textContent = status.simulation_time_completed_ns
      ? `${status.simulation_time_completed_ns} ns` : "not available";
    $("#live-elapsed-cell").textContent = status.elapsed_wall_time_s
      ? fmtDuration(status.elapsed_wall_time_s) : "not available";
    $("#live-eta-cell").textContent = computeETA(status);
    $("#live-checkpoint-cell").textContent = status.current_checkpoint_path || "not available";
    $("#live-lastupdate-cell").textContent = status.last_update_timestamp || "not available";
    $("#live-card-step").textContent = status.current_step != null ? String(status.current_step) : "—";
  }

  function applyMetrics(metrics) {
    state.metrics = metrics.slice(-chartHistorySamples);
    renderMetricCards();
    if (window.FastMDXCharts) {
      window.FastMDXCharts.update(state.metrics);
    }
  }

  function renderMetricCards() {
    const latest = state.metrics.length ? state.metrics[state.metrics.length - 1] : {};
    const map = {
      potential_energy: {unit: "kJ/mol"},
      temperature: {unit: "K"},
      density: {unit: "g/mL"},
      speed: {unit: "ns/day"},
      frames: {unit: "frames"},
      pressure: {unit: "bar"},
    };
    $$(".metric-card").forEach((card) => {
      const key = card.getAttribute("data-metric");
      const derived = deriveMetric(key, latest);
      const value = card.querySelector("[data-value]");
      const unit = card.querySelector(".metric-card-unit");
      if (value) value.textContent = derived != null ? derived : "—";
      if (unit && map[key]) unit.textContent = map[key].unit;
      if (derived !== card.getAttribute("data-last-value")) {
        if (derived != null && card.getAttribute("data-last-value") != null) {
          card.setAttribute("data-pulse", "");
          setTimeout(() => card.removeAttribute("data-pulse"), 1200);
        }
        card.setAttribute("data-last-value", derived != null ? String(derived) : "");
      }
    });
  }

  function deriveMetric(key, latest) {
    if (key === "frames") {
      return latest.current_frame_count || latest.frame || null;
    }
    if (key === "speed") {
      /* OpenMM reports ns/day via its reporter; flatten to a numeric.
         If it's missing, we cannot honestly invent it. */
      return latest.speed != null ? Number(latest.speed).toFixed(2) : null;
    }
    if (latest[key] === undefined) return null;
    const v = Number(latest[key]);
    return Number.isFinite(v) ? v.toFixed(2) : null;
  }

  function renderEvents(events) {
    const ul = $("#events-list");
    if (!ul) return;
    const items = events.slice(-50).reverse();
    ul.innerHTML = items.map((ev) => {
      const level = ev.level || "info";
      const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString([], {hour12:false}) : "";
      return `<li data-level="${escapeAttr(level)}">
        <span class="level-badge">${escapeHTML(level)}</span>
        <span class="event-message">${escapeHTML(ev.message || "")}</span>
        <span class="event-time">${escapeHTML(ts)}</span>
      </li>`;
    }).join("") || '<li data-level="info"><span class="level-badge">info</span><span class="event-message">No events yet.</span><span class="event-time"></span></li>';
  }

  function applyResults(payload) {
    state.results = payload;
    renderAnalysis(payload);
    renderFiles(payload);
    renderRunSummary(payload);
    window.dispatchEvent(new CustomEvent("dashboard:results-updated", {detail: payload}));
  }

  function renderAnalysis(payload) {
    const grid = $("#analysis-grid");
    const empty = $("#analysis-empty");
    if (!grid) return;
    const plots = payload.plots || [];
    grid.innerHTML = "";
    if (!plots.length) {
      empty.removeAttribute("hidden");
      return;
    }
    empty.setAttribute("hidden", "");
    plots.forEach((plot) => {
      const card = document.createElement("article");
      card.className = "analysis-card";
      card.setAttribute("data-state", (plot.mode || "artifact fallback").includes("dashboard") ? "complete" : "complete");
      card.innerHTML = `
        <div class="ac-header">
          <div class="ac-title">${escapeHTML(plot.title || plot.name || "Analysis")}</div>
          <div class="ac-status">${escapeHTML(plot.mode || "complete")}</div>
        </div>
        <div class="ac-frame"><img src="${escapeAttr(plot.href)}" alt="${escapeAttr(plot.title || "")}" loading="lazy"></div>
        <div class="ac-body">${escapeHTML(plot.summary || plot.category || "")}</div>
        <div class="ac-footer">
          <a class="file-action" href="${escapeAttr(plot.href)}" download="${escapeAttr(plot.path || "")}">PNG</a>
          <a class="file-action" href="${escapeAttr(plot.href)}" target="_blank" rel="noopener">Open</a>
          <a class="file-action" href="/artifacts/${escapeAttr(plot.path || "")}" target="_blank" rel="noopener">Open raw</a>
          <a class="file-action" href="/structure/topology.pdb" target="_blank" rel="noopener">Topology</a>
        </div>
      `;
      grid.appendChild(card);
    });
  }

  function renderFiles(payload) {
    const groups = {
      reports: payload.reports || [],
      simulation: (payload.artifacts || []).filter((a) =>
        a.path.startsWith("simulation/")),
      analysis: (payload.artifacts || []).filter((a) =>
        a.path.startsWith("analysis/")),
    };
    Object.keys(groups).forEach((key) => {
      const root = $(`#${key.replace(/^./, (c) => key === "reports" ? "reports" : key)}-files`);
      if (!root) return;
      const list = groups[key];
      root.innerHTML = list.length ? list.map(fileRowHtml).join("") :
        `<div class="muted small">No ${key} files yet.</div>`;
    });
    wireFileActions();
  }

  function fileRowHtml(a) {
    const title = humaniseFile(a.path, a.name);
    const size = a.size ? humanSize(parseInt(a.size, 10)) : "—";
    const mtime = a.mtime ? new Date(parseInt(a.mtime, 10) * 1000).toLocaleString() : "—";
    return `<div class="file-row" data-href="${escapeAttr(a.href)}" data-path="${escapeAttr(a.path)}">
      <div class="file-title" title="${escapeAttr(a.path)}">${escapeHTML(title)}</div>
      <div class="file-meta">
        <span>${escapeHTML(size)}</span>
        <span class="muted">${escapeHTML(mtime)}</span>
        <div class="file-actions">
          <button class="file-action" data-action="open">Open</button>
          <button class="file-action" data-action="download">Download</button>
          <button class="file-action" data-action="copy">Copy path</button>
        </div>
      </div>
    </div>`;
  }

  function humaniseFile(path, name) {
    if (!name) return path;
    return name;
  }

  function humanSize(bytes) {
    if (!Number.isFinite(bytes)) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  function wireFileActions() {
    $$(".file-row").forEach((row) => {
      row.querySelectorAll(".file-action").forEach((btn) => {
        btn.addEventListener("click", () => {
          const action = btn.getAttribute("data-action");
          const href = row.getAttribute("data-href");
          const path = row.getAttribute("data-path");
          if (action === "open") window.open(href, "_blank");
          if (action === "download") {
            const a = document.createElement("a");
            a.href = href; a.download = path;
            document.body.appendChild(a); a.click(); a.remove();
          }
          if (action === "copy" && navigator.clipboard) {
            navigator.clipboard.writeText(path || "").catch(() => {});
          }
        });
      });
    });
  }

  function renderRunSummary(payload) {
    const card = $("#summary-card");
    if (!card) return;
    if (!payload.has_report && !payload.has_analysis) {
      card.setAttribute("hidden", "");
      return;
    }
    card.removeAttribute("hidden");
    const plots = payload.plots || [];
    const reports = payload.reports || [];
    const analyses = (payload.artifacts || []).filter((a) => a.path.startsWith("analysis/"));
    const stats = [
      {label: "Analyses", value: analyses.length.toString()},
      {label: "Figures", value: plots.length.toString()},
      {label: "Report formats", value: reports.length.toString()},
      {label: "Result bundle", value: reports.some((r) => r.path.includes("bundle")) ? "ready" : "—"},
    ];
    $("#summary-grid").innerHTML = stats.map((s) => `
      <div class="summary-stat">
        <span class="summary-stat-label">${escapeHTML(s.label)}</span>
        <span class="summary-stat-value">${escapeHTML(s.value)}</span>
      </div>
    `).join("");
  }

  function applyStructure(info) {
    state.structureInfo = info;
    renderStructureTab(info);
    if (info.ligand_resnames && info.ligand_resnames.length && !state.ligandResname) {
      state.ligandResname = info.ligand_resnames[0];
    }
    renderLigandTab(info);
    renderSimulationTab(info);
    window.dispatchEvent(new CustomEvent("dashboard:structure-updated", {detail: info}));
  }

  function renderStructureTab(info) {
    const tbody = $("#structure-tab-tbody");
    if (!tbody) return;
    if (!info || !info.valid) {
      tbody.innerHTML = `<tr><td colspan="2" class="muted">Structure not available yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = `
      <tr><th>Protein chains</th><td>${info.n_chains}</td></tr>
      <tr><th>Protein residues</th><td>${info.protein_residues}</td></tr>
      <tr><th>Protein atoms</th><td>${info.protein_atoms}</td></tr>
      <tr><th>Ligands</th><td>${info.ligand_resnames.join(", ") || "none"}</td></tr>
      <tr><th>Water</th><td>${info.water_residues}</td></tr>
      <tr><th>Ions</th><td>${info.ions}</td></tr>
    `;
  }

  function renderSimulationTab(info) {
    const tbody = $("#simulation-tab-tbody");
    if (!tbody) return;
    const s = state.status || {};
    const sim = state.simManifest || {};
    tbody.innerHTML = `
      <tr><th>Force field</th><td>${s.force_field || sim.force_field || "—"}</td></tr>
      <tr><th>Water model</th><td>${s.water_model || sim.water_model || "—"}</td></tr>
      <tr><th>pH</th><td>${s.ph || sim.ph || "—"}</td></tr>
      <tr><th>Ion concentration</th><td>${sim.ion_concentration_M != null ? sim.ion_concentration_M + " M" : "—"}</td></tr>
      <tr><th>Temperature</th><td>${s.target_temperature_K != null ? s.target_temperature_K + " K" : "—"}</td></tr>
      <tr><th>Timestep</th><td>${s.timestep_fs != null ? s.timestep_fs + " fs" : "—"}</td></tr>
      <tr><th>Precision</th><td>${s.precision || "—"}</td></tr>
      <tr><th>Platform</th><td>${s.platform || "—"}</td></tr>
    `;
  }

  function renderLigandTab(info) {
    const tools = $("#ligand-tools");
    const meta = $("#ligand-meta");
    if (!tools || !meta) return;
    if (!state.ligandResname || (info && !info.valid)) {
      tools.setAttribute("hidden", "");
      meta.textContent = "not available";
      return;
    }
    tools.removeAttribute("hidden");
    const ins = (info && info.ligand_instances || []).find(
      (i) => i.resname === state.ligandResname) || (info && info.ligand_instances || [])[0];
    if (!ins) {
      meta.textContent = "—";
      return;
    }
    const atoms = (info && info.atoms_by_resname && info.atoms_by_resname[state.ligandResname]) || "—";
    meta.textContent =
      `${state.ligandResname} · chain ${ins.chain} · resi ${ins.resi} · ${atoms} atoms`;
    const tbody = $("#ligand-tab-tbody");
    if (!tbody) return;
    tbody.innerHTML = `
      <tr><th>Ligand</th><td>${escapeHTML(state.ligandResname)}</td></tr>
      <tr><th>Chain</th><td>${escapeHTML(ins.chain || "—")}</td></tr>
      <tr><th>Residue ID</th><td>${escapeHTML(ins.resi || "—")}</td></tr>
      <tr><th>Atom count</th><td>${escapeHTML(String(atoms))}</td></tr>
      <tr><th>Nearby residues</th><td>—</td></tr>
      <tr><th>Pocket distance</th><td>—</td></tr>
      <tr><th>H-bonds</th><td>—</td></tr>
      <tr><th>Hydrophobic contacts</th><td>—</td></tr>
      <tr><th>Salt bridges</th><td>—</td></tr>
    `;
  }

  function applyPlayback(payload) {
    state.playbackAvailable = !!payload.playback_available;
    state.playbackFrames = payload.n_frames_browser || 0;
    state.playbackTotalFrames = payload.n_frames_total || 0;
    const slider = $("#traj-slider");
    if (state.playbackAvailable) {
      slider.max = String(Math.max(0, state.playbackFrames - 1));
      $("#traj-total").textContent = String(state.playbackFrames);
      $("#traj-current").textContent = slider.value;
      const simNs = payload.frame_times_ns && payload.frame_times_ns[0];
      $("#traj-simtime").textContent = simNs != null ? simNs.toFixed(3) : "—";
      $("#trajectory-row").removeAttribute("hidden");
      window.dispatchEvent(new CustomEvent("dashboard:playback-ready", {detail: payload}));
    } else {
      $("#trajectory-row").setAttribute("hidden", "");
      if (payload.reason) {
        const reason = $("#analysis-empty .empty-detail");
        if (reason) reason.textContent = `Trajectory playback is unavailable (${payload.reason}).`;
      }
    }
  }

  /* ---------------------------------------------- *
   * Tiny utility helpers                          *
   * ---------------------------------------------- */
  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g,
      (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  }

  function escapeAttr(s) {
    return escapeHTML(s);
  }

  function clampInt(v, lo, hi, fallback) {
    v = parseInt(v, 10);
    if (!Number.isFinite(v)) return fallback;
    return Math.max(lo, Math.min(hi, v));
  }
  function clampFloat(v, lo, hi, fallback) {
    v = parseFloat(v);
    if (!Number.isFinite(v)) return fallback;
    return Math.max(lo, Math.min(hi, v));
  }

  /* Expose state read-only for sibling JS modules */
  window.FastMDXDashboard = {
    get state() { return JSON.parse(JSON.stringify(state)); },
    navigate,
    applyStatus,
    applyMetrics,
    applyStructure,
    applyPlayback,
    applyResults,
    on(eventName, handler) {
      window.addEventListener("dashboard:" + eventName, (ev) => handler(ev.detail));
    },
  };

})();
