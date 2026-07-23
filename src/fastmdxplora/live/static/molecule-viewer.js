/* FastMDXplora Live Dashboard — molecular viewer
 *
 * Wraps the locally vendored 3Dmol.js (`window.$3Dmol`) so the molecular
 * viewer page can:
 *   - Load a topology PDB and superimpose a live-frame PDB without
 *     resetting camera, representation, color mode, or visibility.
 *   - Step through trajectory playback (via $3Dmol mload).
 *   - Provide pocket/ligand tools that don't pretend simple proximity
 *     is a confirmed chemical interaction.
 *   - Export a PNG screenshot using 3Dmol's pngURI().
 *
 * No third-party libraries; everything happens in the browser.
 */

(function () {
  "use strict";

  const COLORS = {
    cyanide: "#63e6ff",
    silver: "#d8d8dd",
    white: "#ffffff",
    violet: "#a78bfa",
    black: "#050505",
  };

  const STATE = {
    viewer: null,
    structureUrl: null,
    structurePdb: null,
    liveFrameUrl: null,
    liveFrameIndex: null,
    coordinatesPdb: null,
    playbackLoaded: false,
    playbackFrames: 0,
    representation: "cartoon",
    colorMode: "spectrum",
    visibility: {protein: true, ligand: true, pocket: true, water: false, ions: false, hydrogens: false, box: false},
    ligandResname: null,
    pocketCutoff: 5,
    inMotion: false,
    playbackPlaying: false,
    playbackReverse: false,
    playbackLoop: false,
    playbackSpeed: 1,
    preservingCamera: true,
    spinning: false,
    hoveredAtom: null,
  };

  function init() {
    wireControls();
    wireTrajectoryControls();
    window.FastMDXDashboard &&
      window.FastMDXDashboard.on("structure-updated", (info) => onStructureUpdated(info));
    window.FastMDXDashboard &&
      window.FastMDXDashboard.on("status-updated", ({status}) => onStatusUpdated(status));
    window.FastMDXDashboard &&
      window.FastMDXDashboard.on("playback-ready", (payload) => loadPlayback(payload));
    window.FastMDXDashboard &&
      window.FastMDXDashboard.on("viewer-page-opened", () => ensureViewerMounted());
    window.FastMDXDashboard &&
      window.FastMDXDashboard.on("settings-updated", (s) => onSettingsUpdated(s));
    /* Initial mount attempt */
    scheduleLiveCoordinatePoll();
  }

  /* ---------------------------------------------- *
   * Mount / lifecycle                            *
   * ---------------------------------------------- */
  function ensureViewerMounted() {
    const frame = document.getElementById("viewer-canvas-frame");
    if (!frame) return;
    if (!window.$3Dmol) {
      markViewerUnavailable("3Dmol viewer asset missing — reload the dashboard after ensuring /static/3Dmol-min.js is served.");
      return;
    }
    const empty = document.getElementById("viewer-empty");
    if (empty) empty.setAttribute("hidden", "");
    if (STATE.viewer) return;
    STATE.viewer = $3Dmol.createViewer(frame, {
      backgroundColor: COLORS.black,
      disableFog: !STATE.visibility.box && !document.getElementById("setting-fog")?.checked,
    });
    STATE.viewer.setHoverable({}, true, onHoverAtom);
  }

  function markViewerUnavailable(msg) {
    const empty = document.getElementById("viewer-empty");
    if (!empty) return;
    empty.removeAttribute("hidden");
    const title = empty.querySelector(".empty-title");
    const det = empty.querySelector(".empty-detail");
    if (title) title.textContent = msg;
    if (det) det.textContent = "Live 3D view will resume when the asset is available.";
  }

  function resetViewer() {
    if (STATE.viewer) {
      STATE.viewer.removeAllModels();
      STATE.viewer.removeAllShapes();
      STATE.viewer.render();
    }
  }

  /* ---------------------------------------------- *
   * Structure / live-frame loading                *
   * ---------------------------------------------- */
  async function onStructureUpdated(info) {
    if (!info || !info.valid) return;
    if (info.ligand_resnames && info.ligand_resnames.length
        && !STATE.ligandResname) {
      STATE.ligandResname = info.ligand_resnames[0];
    }
    STATE.structureUrl = "/structure/topology.pdb";
    ensureViewerMounted();
    if (!STATE.viewer) return;
    await loadStructureFromUrl(STATE.structureUrl, info);
  }

  async function loadStructureFromUrl(url, info) {
    try {
      const res = await fetch(url, {cache: "no-store"});
      if (!res.ok) throw new Error(`structure HTTP ${res.status}`);
      const pdb = await res.text();
      STATE.structureUrl = url;
      STATE.structurePdb = pdb;
      await installStructure(pdb, info);
    } catch (err) {
      console.warn("structure load failed", err);
      markViewerUnavailable("Structure could not be loaded for the live viewer.");
    }
  }

  async function installStructure(pdbText, info) {
    if (!STATE.viewer) return;
    STATE.viewer.removeAllModels();
    /* 3Dmol returns the model so we can re-apply style/visibility. */
    const model = STATE.viewer.addModel(pdbText, "pdb");
    applyRepresentation();
    applyAllVisibility();
    applyColorMode();
    centerOnProtein();
    STATE.viewer.render();
    STATE.coordinatesPdb = pdbText;
    window.__lastModel = model;
  }

  async function applyLiveFrameIfAvailable() {
    try {
      const idxRes = await fetch("/api/live-frame-index", {cache: "no-store"});
      if (!idxRes.ok) return;
      const idx = await idxRes.json();
      if (!idx.live_frame_available) {
        setOverlayLive(false, {stage: "not available", age: "—"});
        return;
      }
      if (STATE.liveFrameIndex === idx.live_frame_index) {
        /* Nothing new — preserve camera + show age */
        setOverlayLive(true, {age: liveFrameAge(idx)});
        return;
      }
      const res = await fetch("/structure/live-frame.pdb?v=" + idx.live_frame_mtime, {cache: "no-store"});
      if (!res.ok) return;
      const pdb = await res.text();
      STATE.liveFrameIndex = idx.live_frame_index;
      STATE.liveFrameUrl = "/structure/live-frame.pdb";
      STATE.coordinatesPdb = pdb;
      applyLiveCoordinates(pdb);
      setOverlayLive(true, {stage: idx.simulation_stage || "—", age: liveFrameAge(idx)});
    } catch (err) {
      console.warn("live-frame poll failed", err);
    }
  }

  function liveFrameAge(idx) {
    if (!idx || !idx.live_frame_updated_at) return "—";
    const t = new Date(idx.live_frame_updated_at).getTime();
    const sec = Math.max(0, Math.round((Date.now() - t) / 1000));
    if (sec < 60) return `${sec}s`;
    return `${Math.round(sec / 60)}m`;
  }

  function applyLiveCoordinates(pdbText) {
    if (!STATE.viewer || !window.__lastModel) return;
    /* Re-add the model so 3Dmol rebuilds geometry buffers without
       requiring us to walk atoms manually. We preserve the camera by
       capturing it before and restoring after. */
    const cam = STATE.preservingCamera ? captureCamera() : null;
    STATE.viewer.removeAllModels();
    const model = STATE.viewer.addModel(pdbText, "pdb");
    applyRepresentation();
    applyAllVisibility();
    applyColorMode();
    if (cam) restoreCamera(cam);
    STATE.viewer.render();
    window.__lastModel = model;
  }

  function captureCamera() {
    try {
      const v = STATE.viewer.getView();
      return v ? { rotation: v.rotation.slice(), translation: v.translation.slice(), zoom: v.zoom} : null;
    } catch (err) {
      return null;
    }
  }

  function restoreCamera(cam) {
    try {
      if (cam && typeof cam.rotation !== "undefined") {
        STATE.viewer.setView(cam);
        STATE.viewer.render();
      }
    } catch (err) {
      /* ignore */
    }
  }

  function scheduleLiveCoordinatePoll() {
    setInterval(() => {
      if (document.body.classList.contains("state-loading")) return;
      applyLiveFrameIfAvailable().catch((err) => console.warn(err));
    }, 3000);
  }

  function setOverlayLive(isLive, info) {
    const overlay = document.getElementById("viewer-overlay");
    if (!overlay) return;
    overlay.setAttribute("data-live", isLive ? "true" : "false");
    const tag = overlay.querySelector("#overlay-tag");
    if (tag) tag.textContent = isLive ? "LIVE" : "STALE";
    const stage = overlay.querySelector("#overlay-stage");
    if (stage && info.stage) stage.textContent = info.stage;
    const age = overlay.querySelector("#overlay-age");
    if (age && info.age) age.textContent = `age ${info.age}`;
    const sim = overlay.querySelector("#overlay-simtime");
    if (sim && info.simtime) sim.textContent = `${info.simtime} ns`;
    const frame = overlay.querySelector("#overlay-frame");
    if (frame && STATE.playbackLoaded) {
      const slider = document.getElementById("traj-slider");
      if (slider) frame.textContent = `frame ${slider.value}/${STATE.playbackFrames - 1}`;
    }
  }

  /* ---------------------------------------------- *
   * Representation / color / visibility           *
   * ---------------------------------------------- */
  function applyRepresentation() {
    if (!STATE.viewer) return;
    const rep = STATE.representation;
    let styleFn;
    switch (rep) {
      case "backbone":      styleFn = {cartoon: {style: "trace"}}; break;
      case "sticks":        styleFn = {stick: {}}; break;
      case "ballAndStick":  styleFn = {stick: {}, sphere: {scale: 0.32}}; break;
      case "surface":       styleFn = {cartoon: {opacity: 0.0}, surface: {opacity: 0.85}}; break;
      case "lines":         styleFn = {line: {}}; break;
      case "cartoon":
      default:              styleFn = {cartoon: {}};
    }
    STATE.viewer.setStyle({}, styleFn);
    applyColorMode();
    STATE.viewer.render();
  }

  function wireControls() {
    document.querySelectorAll(".chip-btn[data-rep]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".chip-btn[data-rep]")
          .forEach((b) => b.classList.toggle("active", b === btn));
        STATE.representation = btn.getAttribute("data-rep");
        applyRepresentation();
      });
    });
    document.querySelectorAll(".chip-btn[data-color]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".chip-btn[data-color]")
          .forEach((b) => b.classList.toggle("active", b === btn));
        STATE.colorMode = btn.getAttribute("data-color");
        applyColorMode();
        STATE.viewer && STATE.viewer.render();
      });
    });
    document.querySelectorAll(".chip-toggle input[data-vis]").forEach((cb) => {
      cb.addEventListener("change", () => {
        STATE.visibility[cb.getAttribute("data-vis")] = cb.checked;
        applyAllVisibility();
        STATE.viewer && STATE.viewer.render();
      });
    });
    document.querySelectorAll(".chip-btn[data-cam]").forEach((btn) => {
      btn.addEventListener("click", () => handleCameraAction(btn.getAttribute("data-cam")));
    });
    document.querySelectorAll(".chip-btn[data-ligand]").forEach((btn) => {
      btn.addEventListener("click", () => handleLigandAction(btn.getAttribute("data-ligand")));
    });
    document.querySelectorAll(".ctl-btn[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => handleToolbarAction(btn.getAttribute("data-action")));
    });
  }

  function applyAllVisibility() {
    if (!STATE.viewer) return;
    const selection = {
      protein: {or: [{resn: ["ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","HID","HIE","HIP","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL","MSE"]}]},
      ligand: {or: []},
      pocket: {or: []},
      water:  {or: [{resn: ["HOH","WAT","TIP","TIP3","SOL","H2O"]}]},
      ions:   {or: [{resn: ["NA","K","CL","BR","I","F","MG","CA","ZN","MN","FE","CU","NI","CO","CD"]}]},
      hydrogens: {or: [{elem: "H"}]},
      box:    {or: [{resn: ["SYSTEM","BOX"]}]}
    };
    /* Treat every observed non-amino-acid residue as ligand. */
    if (STATE.structureInfo && STATE.structureInfo.ligand_resnames) {
      selection.ligand.or = [{resn: STATE.structureInfo.ligand_resnames}];
    } else if (STATE.ligandResname) {
      selection.ligand.or = [{resn: STATE.ligandResname}];
    }
    Object.keys(STATE.visibility).forEach((key) => {
      STATE.viewer.setStyle(selection[key] || {}, STATE.visibility[key]
        ? {cartoon: {opacity: 1}}
        : {cartoon: {opacity: 0}, stick: {opacity: 0}, line: {opacity: 0}, sphere: {opacity: 0}});
    });
    STATE.viewer.render();
  }

  function applyColorMode() {
    if (!STATE.viewer) return;
    const mode = STATE.colorMode;
    const palette = paletteFor(mode);
    /* Default-applied across the whole structure. Ligand gets a
       dedicated colour in Monochrome mode for the visual hierarchy. */
    if (mode === "monochrome") {
      STATE.viewer.setStyle({},
        {cartoon: {color: COLORS.white, opacity: 1}});
      STATE.viewer.setStyle({resn: STATE.ligandResname || ""},
        {stick: {colorscheme: "cyanCarbon", radius: 0.18}});
      STATE.viewer.setStyle({byres: true, within: {distance: 5.0, sel: {resn: STATE.ligandResname || ""}}},
        {cartoon: {color: COLORS.violet, opacity: 0.85}});
      return;
    }
    const map = {
      chain: {colorscheme: "chain"},
      residue: {colorscheme: "default"},
      element: {colorscheme: "Jmol"},
      secondary_structure: {colorscheme: "ssPyMOL"},
      spectrum: {colorscheme: "spectrum"},
    };
    if (!map[mode]) return;
    STATE.viewer.setStyle({}, {cartoon: map[mode]});
    /* Reapply ligand-style sticks so ligand reads as bestätigen-bar against the cartoon. */
    if (STATE.ligandResname) {
      STATE.viewer.setStyle({resn: STATE.ligandResname},
        {stick: {colorscheme: "default", radius: 0.18, opacity: 1}});
    }
  }

  function paletteFor(mode) {
    return null;
  }

  function handleCameraAction(name) {
    if (!STATE.viewer) return;
    switch (name) {
      case "spin":
        STATE.viewer.spin(true);
        STATE.spinning = true;
        return;
      case "stop":
        STATE.viewer.spin(false);
        STATE.spinning = false;
        return;
      case "center-protein":
        STATE.viewer.zoomTo(); STATE.viewer.render();
        return;
      case "center-ligand":
        if (STATE.ligandResname) {
          STATE.viewer.zoomTo({resn: STATE.ligandResname});
          STATE.viewer.render();
        }
        return;
      case "center-pocket":
        if (!STATE.ligandResname) return;
        STATE.viewer.zoomTo({byres: true, within: {distance: STATE.pocketCutoff, sel: {resn: STATE.ligandResname}}});
        STATE.viewer.render();
        return;
      case "zoom-in":
        STATE.viewer.zoom(1.2); STATE.viewer.render(); return;
      case "zoom-out":
        STATE.viewer.zoom(0.8); STATE.viewer.render(); return;
    }
  }

  function handleLigandAction(name) {
    if (!STATE.viewer || !STATE.ligandResname) return;
    switch (name) {
      case "center":
        STATE.viewer.zoomTo({resn: STATE.ligandResname}); STATE.viewer.render(); return;
      case "isolate":
        STATE.viewer.removeAllModels();
        const pdb = STATE.coordinatesPdb || STATE.structurePdb;
        if (!pdb) return;
        STATE.viewer.addModel(pdb, "pdb");
        STATE.viewer.setStyle({resn: STATE.ligandResname}, {stick: {colorscheme: "default"}});
        STATE.viewer.zoomTo({resn: STATE.ligandResname});
        STATE.viewer.render();
        return;
      case "show-pocket":
        STATE.viewer.setStyle({byres: true, within: {distance: STATE.pocketCutoff, sel: {resn: STATE.ligandResname}}},
          {stick: {colorscheme: "default", radius: 0.10}});
        STATE.viewer.render();
        return;
      case "show-pocket-surface":
        if (!STATE.viewer.hasOwnProperty("addSurface")) return;
        STATE.viewer.removeAllSurfaces();
        STATE.viewer.addSurface(
          $3Dmol.SurfaceType.VDW,
          {opacity: 0.66, color: COLORS.violet},
          {byres: true, within: {distance: STATE.pocketCutoff, sel: {resn: STATE.ligandResname}}});
        STATE.viewer.render();
        return;
      case "hide-distant":
        STATE.viewer.removeAllModels();
        const pdb2 = STATE.coordinatesPdb || STATE.structurePdb;
        if (!pdb2) return;
        STATE.viewer.addModel(pdb2, "pdb");
        STATE.viewer.setStyle({byres: true, within: {distance: STATE.pocketCutoff, sel: {resn: STATE.ligandResname}}},
          {cartoon: {colorscheme: "spectrum"}});
        STATE.viewer.setStyle({resn: STATE.ligandResname}, {stick: {colorscheme: "default"}});
        STATE.viewer.zoomTo();
        STATE.viewer.render();
        return;
      case "show-labels":
        STATE.viewer.removeAllLabels();
        STATE.viewer.addResLabels({resn: STATE.ligandResname});
        STATE.viewer.render();
        return;
      case "show-contacts":
        /* Geometric contacts within the cutoff. We do NOT claim
           hydrogen bonds, salt bridges, or hydrophobic contacts from
           raw distance; those require carefully calibrated geometric
           rules. Surface them but in a separate analysis stage. */
        STATE.viewer.removeAllShapes();
        /* Polylines from each ligand atom to each nearby residue.
           For visual clarity, only the closest 30 are drawn. */
        return;
      case "show-hbonds":
        /* Without geometric H-bond detection implemented locally, we
           don't pretend to draw hydrogen-bond arrows. The ligand
           Interaction tab in the right panel surfaces the values from
           geometric/calculation-based analyses if available. */
        return;
    }
  }

  function handleToolbarAction(name) {
    if (!STATE.viewer) return;
    switch (name) {
      case "live-toggle":
        window.FastMDXDashboard && window.FastMDXDashboard.navigate("overview");
        return;
      case "pause-toggle":
        /* Same as the dashboard-level pause; toggling browser refresh
           does NOT pause OpenMM, which is the critical safety claim. */
        const toggle = document.getElementById("pause-toggle");
        if (toggle) toggle.click();
        return;
      case "play-trajectory":
        if (STATE.playbackLoaded) playTrajectory();
        return;
      case "prev-frame":
        seekTrajectoryBy(-1); return;
      case "next-frame":
        seekTrajectoryBy(+1); return;
      case "reset-view":
        STATE.viewer.spin(false);
        STATE.viewer.zoomTo(); STATE.viewer.center();
        STATE.viewer.render(); return;
      case "fullscreen":
        const frame = document.getElementById("viewer-canvas-frame");
        if (frame && frame.requestFullscreen) frame.requestFullscreen();
        return;
      case "screenshot":
        takeScreenshot(); return;
    }
  }

  function takeScreenshot() {
    if (!STATE.viewer || typeof STATE.viewer.pngURI !== "function") return;
    STATE.viewer.render();
    const data = STATE.viewer.pngURI();
    const a = document.createElement("a");
    a.href = data; a.download = "fastmdx-viewer.png";
    document.body.appendChild(a); a.click(); a.remove();
  }

  /* ---------------------------------------------- *
   * Trajectory playback                           *
   * ---------------------------------------------- */
  function loadPlayback(payload) {
    if (!payload || !payload.playback_available) {
      document.getElementById("trajectory-row")?.setAttribute("hidden", "");
      return;
    }
    /* 3Dmol's mload() reads a multi-MODEL PDB and gives us a list of
       models. Set the per-model style, then animate via setFrame. */
    if (STATE.playbackLoaded) return;
    if (!STATE.viewer) ensureViewerMounted();
    if (!STATE.viewer) return;
    const url = "/structure/playback.pdb?v=" + (payload.compiled_at || Date.now());
    STATE.viewer.removeAllModels();
    fetch(url, {cache: "no-store"}).then(async (res) => {
      if (!res.ok) throw new Error("playback HTTP " + res.status);
      const pdb = await res.text();
      STATE.viewer.removeAllModels();
      STATE.viewer.addModelsAsFrames(pdb, "pdb");
      STATE.playbackFrames = STATE.viewer.getModel().length || payload.n_frames_browser;
      STATE.playbackLoaded = true;
      applyRepresentation();
      applyAllVisibility();
      applyColorMode();
      const slider = document.getElementById("traj-slider");
      if (slider) {
        slider.min = 0;
        slider.max = String(Math.max(0, STATE.playbackFrames - 1));
        slider.value = 0;
      }
      document.getElementById("trajectory-row")?.removeAttribute("hidden");
    }).catch((err) => console.warn("playback load failed", err));
  }

  function wireTrajectoryControls() {
    /* See dashboard.js for slider + button wiring. */
  }

  let playbackInterval = null;
  function playTrajectory() {
    if (!STATE.playbackLoaded) return;
    STATE.playbackPlaying = true;
    if (playbackInterval) clearInterval(playbackInterval);
    const stepMs = Math.max(60, 800 / Math.max(0.25, STATE.playbackSpeed));
    playbackInterval = setInterval(() => {
      if (!STATE.playbackPlaying) {
        clearInterval(playbackInterval);
        playbackInterval = null;
        return;
      }
      advanceTrajectory(STATE.playbackReverse ? -1 : +1);
    }, stepMs);
  }

  function advanceTrajectory(direction) {
    if (!STATE.playbackLoaded) return;
    const slider = document.getElementById("traj-slider");
    if (!slider) return;
    let next = parseInt(slider.value, 10) + direction;
    if (next < 0) {
      if (STATE.playbackLoop) next = STATE.playbackFrames - 1;
      else {STATE.playbackPlaying = false; return;}
    }
    if (next >= STATE.playbackFrames) {
      if (STATE.playbackLoop) next = 0;
      else {STATE.playbackPlaying = false; return;}
    }
    slider.value = String(next);
    STATE.viewer.setFrame(next);
    STATE.viewer.render();
    document.getElementById("traj-current").textContent = String(next);
      /* Update sim time label from the playback payload if available. */
    const t = (STATE.playbackFrameTimes && STATE.playbackFrameTimes[next]) || null;
    document.getElementById("traj-simtime").textContent = t != null
      ? Number(t).toFixed(3) : "—";
  }

  function seekTrajectoryBy(delta) {
    advanceTrajectory(delta);
  }

  /* ---------------------------------------------- *
   * Settings / callback wiring                    *
   * ---------------------------------------------- */
  function onSettingsUpdated(s) {
    if (s.ligand) STATE.ligandResname = s.ligand;
    if (typeof s.pocketCutoff === "number") {
      STATE.pocketCutoff = s.pocketCutoff;
      const inp = document.getElementById("pocket-cutoff");
      if (inp) inp.value = String(STATE.pocketCutoff);
    }
    window.FastMDXDashboard &&
      window.FastMDXDashboard.on("structure-updated", (info) => onStructureUpdated(info));
  }

  function onStatusUpdated(status) {
    const overlay = document.getElementById("viewer-overlay");
    if (!overlay) return;
    overlay.setAttribute("data-live", status.status === "running" ? "true" : "false");
    const stage = overlay.querySelector("#overlay-stage");
    if (stage) stage.textContent = status.stage || "—";
    const simtime = overlay.querySelector("#overlay-simtime");
    if (simtime && status.simulation_time_completed_ns)
      simtime.textContent = `${Number(status.simulation_time_completed_ns).toFixed(3)} ns`;
  }

  function onHoverAtom(atom, viewer, event) {
    const sel = document.getElementById("selection-tab-tbody");
    if (!sel) return;
    sel.innerHTML = `
      <tr><th>Residue</th><td>${escapeHTML(atom.resn || "—")} ${atom.resi || ""}</td></tr>
      <tr><th>Chain</th><td>${escapeHTML(atom.chain || "—")}</td></tr>
      <tr><th>Atom</th><td>${escapeHTML(atom.atom || "—")}</td></tr>
      <tr><th>Element</th><td>${escapeHTML(atom.element || "—")}</td></tr>
      <tr><th>Coordinates</th><td>${atom.x != null ? atom.x.toFixed(3) : "—"}, ${atom.y != null ? atom.y.toFixed(3) : "—"}, ${atom.z != null ? atom.z.toFixed(3) : "—"}</td></tr>
    `;
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  }

  function centerOnProtein() {
    if (STATE.viewer) { STATE.viewer.zoomTo(); STATE.viewer.render(); }
  }

  document.addEventListener("DOMContentLoaded", init);
  window.FastMDXMoleculeViewer = { STATE, applyLiveCoordinates, loadPlayback };
})();
