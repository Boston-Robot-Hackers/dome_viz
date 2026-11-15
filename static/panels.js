// panels.js — everything on the page that is not the map canvas.
//
// Owns the object markers over the map, the objects list and its detail
// block, the camera panel, the status line with its per-source details and
// the offline banner, and the four "this run" graphs.
//
// It reads `window.domeViz` (set up by app.js) for the world state and the
// view transform, and replaces three hooks there: `onPanels` when something
// changed, `onDraw` after every map repaint so markers follow pan and zoom,
// and `onCameraFrame` for the binary JPEG frames.
(() => {
  const viz = window.domeViz;
  const { world, state } = viz;
  const css = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const CLASS_VAR = { can: "--can", cup: "--cup" };
  const ICON = { can: "#ic-can", cup: "#ic-cup" };
  const colourOf = (label) => `var(${CLASS_VAR[label] ?? "--muted"})`;
  const iconOf = (label) =>
    `<svg aria-hidden="true"><use href="${ICON[label] ?? "#ic-obj"}"/></svg>`;

  const escaped = (text) =>
    String(text).replace(/[&<>\x22]/g, (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);

  const clock = (seconds) => {
    const whole = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(whole / 3600);
    const minutes = Math.floor(whole / 60) % 60;
    const rest = whole % 60;
    const pad = (value) => String(value).padStart(2, "0");
    return hours ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${minutes}:${pad(rest)}`;
  };

  // `ago` is for the per-source rows and the objects list, where "live" is the
  // useful word; `since` is for sentences that already say "updated".
  const ago = (seconds) =>
    seconds == null ? "never"
      : seconds <= 5 ? "live"
      : seconds < 60 ? `${Math.round(seconds)} s ago`
      : `${Math.round(seconds / 60)} min ago`;

  const since = (seconds) =>
    seconds == null ? "not yet"
      : seconds < 2 ? "just now"
      : seconds < 60 ? `${Math.round(seconds)} s ago`
      : `${Math.round(seconds / 60)} min ago`;

  const oldestAge = (ages) => {
    const known = Object.values(ages).filter((age) => age != null);
    return known.length ? Math.max(...known) : null;
  };

  // ---- object markers over the map ---------------------------------------
  // One element per target, reused between renders: rebuilding them on every
  // repaint would throw away focus and make clicking unreliable.
  const markersEl = document.getElementById("markers");
  const markerEls = new Map();

  function markerFor(target) {
    let element = markerEls.get(target.id);
    if (!element) {
      element = document.createElement("button");
      element.className = "marker";
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        viz.select(target.id);
      });
      markersEl.appendChild(element);
      markerEls.set(target.id, element);
    }
    return element;
  }

  function placeMarkers() {
    const live = new Set(world.targets.map((target) => target.id));
    for (const [id, element] of markerEls) {
      if (!live.has(id)) { element.remove(); markerEls.delete(id); }
    }
    markersEl.hidden = !world.plan;
    if (!world.plan) return;
    // Draw the important ones first so that where chips collide, the loser is
    // the less interesting object: selected, then in view, then most seen.
    const rank = (target) =>
      (target.id === state.selected ? 1e9 : 0) +
      (target.is_lost ? 0 : 1e6) + target.observations;
    const placed = [];
    for (const target of [...world.targets].sort((a, b) => rank(b) - rank(a))) {
      const element = markerFor(target);
      const [sx, sy] = viz.toScreen(target.x, target.y);
      const isSelected = target.id === state.selected;
      element.style.left = `${sx}px`;
      element.style.top = `${sy}px`;
      element.style.setProperty("--cls", colourOf(target.label));
      element.dataset.lost = target.is_lost;
      element.dataset.selected = isSelected;
      element.setAttribute(
        "aria-label", `${target.name} ${target.id}, ${ago(target.seen_ago_s)}`
      );
      const label = isSelected
        ? `${escaped(target.id)} · <span class="full">${escaped(target.name)}</span>`
        : escaped(target.id);
      element.innerHTML =
        `<span class="pin"></span><span class="chip">${iconOf(target.label)}${label}</span>`;
      const box = { x: sx, y: sy - 11, w: element.offsetWidth, h: 22 };
      const overlaps = placed.some((other) =>
        box.x < other.x + other.w && box.x + box.w > other.x &&
        box.y < other.y + other.h && box.y + box.h > other.y);
      const isCrowded = overlaps && !isSelected;
      element.dataset.crowded = isCrowded;
      if (!isCrowded) placed.push(box);   // a hidden chip blocks nothing
    }
  }

  // ---- objects list ------------------------------------------------------
  function objectRow(target) {
    return `<button class="obj" data-id="${escaped(target.id)}"
      data-lost="${target.is_lost}"
      aria-pressed="${target.id === state.selected}"
      style="--cls: ${colourOf(target.label)}">${iconOf(target.label)}<span
      class="id">${escaped(target.id)}</span><span
      class="name">${escaped(target.name)}</span><span
      class="when">${ago(target.seen_ago_s)}</span></button>`;
  }

  function detailBlock(target) {
    return `<div class="detail" style="--cls: ${colourOf(target.label)}">
      <div class="title">${escaped(target.name)}<span
        class="id">${escaped(target.id)}</span></div>
      <dl><dt>Status</dt><dd>${target.is_lost ? "out of view" : "in view"}</dd>
      <dt>Last seen</dt><dd>${ago(target.seen_ago_s)}</dd>
      <dt>Position</dt><dd>${target.x.toFixed(2)}, ${target.y.toFixed(2)} m</dd>
      <dt>Sightings</dt><dd>${target.observations}</dd></dl></div>`;
  }

  function renderObjects() {
    const inView = world.targets
      .filter((target) => !target.is_lost)
      .sort((a, b) => b.observations - a.observations);
    const earlier = world.targets
      .filter((target) => target.is_lost)
      .sort((a, b) => a.seen_ago_s - b.seen_ago_s);
    const selected = world.targets.find((target) => target.id === state.selected);
    document.getElementById("objectsHead").textContent =
      `Objects · ${world.targets.length}`;
    document.getElementById("objectsBody").innerHTML = [
      selected ? detailBlock(selected) : "",
      '<div class="group-label">In view now</div>',
      inView.map(objectRow).join("") || '<div class="group-label">None</div>',
      earlier.length ? '<div class="group-label">Seen earlier</div>' : "",
      earlier.map(objectRow).join(""),
    ].join("");
    for (const button of document.querySelectorAll(".obj")) {
      button.addEventListener("click", () => viz.select(button.dataset.id));
    }
  }

  // ---- camera ------------------------------------------------------------
  // The toggle is what makes the robot encode images at all, so "off" really
  // does cost the Pi nothing (notes.md, "Keep the Pi's load unchanged").
  const cameraToggle = document.getElementById("camToggle");
  const cameraBody = document.getElementById("cameraBody");
  let cameraUrl = null;

  const OFF_TEXT =
    `<p class="off">The camera is off. Turning it on makes the robot send its
     video, which adds load on the robot.</p>`;

  function renderCamera() {
    document.getElementById("camState").textContent =
      cameraToggle.checked ? "On" : "Off";
    if (!cameraToggle.checked) {
      cameraBody.innerHTML = OFF_TEXT;
      if (cameraUrl) { URL.revokeObjectURL(cameraUrl); cameraUrl = null; }
      return;
    }
    if (!cameraBody.querySelector("img")) {
      cameraBody.innerHTML =
        '<img id="camImage" alt="What the robot\'s camera sees">';
    }
  }

  cameraToggle.addEventListener("change", () => {
    viz.send({ type: "camera", is_on: cameraToggle.checked });
    renderCamera();
    renderStatus();
  });

  viz.onCameraFrame = (bytes) => {
    if (!cameraToggle.checked) return;
    const image = document.getElementById("camImage");
    if (!image) return;
    const next = URL.createObjectURL(new Blob([bytes], { type: "image/jpeg" }));
    image.src = next;
    if (cameraUrl) URL.revokeObjectURL(cameraUrl);   // or every frame leaks
    cameraUrl = next;
  };

  // ---- status line, details and banner -----------------------------------
  const SOURCE_ROWS = [
    ["Map", "map"], ["Robot", "pose"], ["Objects", "targets"],
    ["Laser", "laser"], ["Camera", "camera"],
  ];
  const WORDING = {
    live: "Live",
    waiting_for_map: "Waiting for the map",
    not_connected: "Robot not connected",
  };
  let isStatusOpen = false;

  function renderStatus() {
    const element = document.getElementById("state");
    const line = document.getElementById("statusLine");
    const details = document.getElementById("statusDetails");
    const status = world.status;

    if (!state.isSocketOpen) {
      element.dataset.state = "not_connected";
      line.innerHTML =
        '<span class="dot"></span><span>Not connected to the viewer</span>';
      details.hidden = true;
      document.getElementById("banner").hidden = true;
      return;
    }
    const ages = status?.ages_s ?? {};
    element.dataset.state = status?.state ?? "not_connected";
    const sub = status?.state === "live" ? `· map updated ${since(ages.map)}`
      : status?.state === "waiting_for_map" ? "· robot connected"
      : status ? `· last heard ${since(oldestAge(ages))}` : "";
    line.innerHTML = `<span class="dot"></span><span>${
      WORDING[status?.state] ?? "Connecting…"}</span><span class="sub">${sub}</span>`;
    line.setAttribute("aria-expanded", isStatusOpen);

    details.hidden = !isStatusOpen;
    details.innerHTML = `<dl>${SOURCE_ROWS.map(([title, key]) => {
      const text = key === "camera" && !cameraToggle.checked ? "off" : ago(ages[key]);
      return `<dt>${title}</dt><dd>${text}</dd>`;
    }).join("")}</dl>`;

    const banner = document.getElementById("banner");
    banner.hidden = status?.state !== "not_connected" || !world.plan;
    if (!banner.hidden) {
      document.getElementById("bannerSub").textContent =
        `Showing the last map, from ${since(ages.map)}.`;
    }
    document.getElementById("runTime").textContent =
      status?.run_s == null ? "—" : clock(status.run_s);
  }

  document.getElementById("statusLine").addEventListener("click", (event) => {
    event.stopPropagation();
    isStatusOpen = !isStatusOpen;
    renderStatus();
  });
  document.addEventListener("click", (event) => {
    if (isStatusOpen && !event.target.closest(".state")) {
      isStatusOpen = false;
      renderStatus();
    }
  });

  // ---- the four run graphs ------------------------------------------------
  const GRAPHS = [
    { key: "battery_pct", name: "Battery (%)", format: (v) => `${v.toFixed(0)} %`, min: 0, max: 100 },
    { key: "power_w", name: "Power draw (W)", format: (v) => `${v.toFixed(1)} W`, min: 0 },
    { key: "speed_mps", name: "Speed (m/s)", format: (v) => `${v.toFixed(2)} m/s`, min: 0 },
    { key: "objects", name: "Objects found", format: (v) => `${v}`, min: 0, isStep: true },
  ];
  const TIME_STEPS = [15, 30, 60, 120, 300, 600, 900, 1800, 3600];

  // A rounded step for an axis, aiming for about `count` ticks.
  function niceStep(span, count) {
    const raw = span / count || 1;
    const magnitude = 10 ** Math.floor(Math.log10(raw));
    const scaled = raw / magnitude;
    const factor = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5 : scaled <= 5 ? 5 : 10;
    return factor * magnitude;
  }

  function buildGraphs() {
    document.getElementById("graphs").innerHTML = GRAPHS.map((graph) =>
      `<div class="spark" data-key="${graph.key}"><div class="head"><span
        class="name">${graph.name}</span><span class="now">–</span></div>
        <canvas aria-label="${graph.name} over this run"></canvas></div>`
    ).join("");
    for (const element of document.querySelectorAll(".spark")) {
      const canvas = element.querySelector("canvas");
      canvas.addEventListener("pointermove", (event) =>
        drawGraph(element, event.clientX - canvas.getBoundingClientRect().left));
      canvas.addEventListener("pointerleave", () => drawGraph(element, null));
    }
  }

  function drawGraph(element, hoverX) {
    const graph = GRAPHS.find((item) => item.key === element.dataset.key);
    const points = world.series[graph.key] ?? [];
    const canvas = element.querySelector("canvas");
    const width = canvas.clientWidth, height = canvas.clientHeight;
    if (!width) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    element.querySelector(".tip")?.remove();
    const latest = points.at(-1);
    element.querySelector(".now").textContent =
      latest ? graph.format(latest[1]) : "–";
    if (!points.length) return;

    const left = 40, right = 8, top = 6, bottom = 16;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const runSeconds = Math.max(world.status?.run_s ?? 0, points.at(-1)[0], 1);
    const values = points.map(([, value]) => value);
    const low = graph.min ?? Math.min(...values);
    let high = graph.max, step;
    if (high == null) {
      const peak = Math.max(...values) || 1;
      step = Math.max(graph.isStep ? 1 : 0, niceStep(peak, 2));
      high = Math.ceil(peak / step) * step;
      if (high <= peak) high += step;
    } else {
      step = niceStep(high - low, 2);
    }
    const atX = (seconds) => left + (seconds / runSeconds) * plotWidth;
    const atY = (value) => top + plotHeight - ((value - low) / (high - low)) * plotHeight;

    const muted = css("--muted"), lineColour = css("--line"), accent = css("--robot");
    ctx.font = `10px ${css("--font-data")}`;
    ctx.fillStyle = muted;
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    for (let value = low; value <= high + 1e-9; value += step) {
      const y = Math.round(atY(value)) + .5;
      ctx.strokeStyle = lineColour; ctx.lineWidth = 1;
      ctx.globalAlpha = value === low ? 1 : .6;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width - right, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(
        graph.isStep ? `${Math.round(value)}` : `${Number(value.toFixed(2))}`, left - 5, y
      );
    }
    const timeStep = TIME_STEPS.find((span) => runSeconds / span <= 5) ?? 3600;
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (let seconds = 0; seconds <= runSeconds + 1e-9; seconds += timeStep) {
      const x = Math.round(atX(seconds)) + .5;
      ctx.strokeStyle = lineColour;
      ctx.beginPath(); ctx.moveTo(x, top + plotHeight); ctx.lineTo(x, top + plotHeight + 3); ctx.stroke();
      ctx.fillText(
        clock(seconds),
        Math.min(Math.max(x, left + 10), width - right - 12), top + plotHeight + 4
      );
    }
    ctx.strokeStyle = lineColour;
    ctx.beginPath(); ctx.moveTo(left + .5, top); ctx.lineTo(left + .5, top + plotHeight); ctx.stroke();

    const path = new Path2D();
    points.forEach(([seconds, value], index) => {
      const x = atX(seconds), y = atY(value);
      if (index === 0) path.moveTo(x, y);
      else if (graph.isStep) { path.lineTo(x, atY(points[index - 1][1])); path.lineTo(x, y); }
      else path.lineTo(x, y);
    });
    const area = new Path2D(path);
    area.lineTo(atX(points.at(-1)[0]), atY(low));
    area.lineTo(atX(points[0][0]), atY(low));
    area.closePath();
    ctx.fillStyle = accent; ctx.globalAlpha = .12; ctx.fill(area); ctx.globalAlpha = 1;
    ctx.strokeStyle = accent; ctx.lineWidth = 1.75; ctx.lineJoin = "round"; ctx.stroke(path);
    const endX = atX(points.at(-1)[0]), endY = atY(points.at(-1)[1]);
    ctx.fillStyle = css("--surface");
    ctx.beginPath(); ctx.arc(endX, endY, 3.5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = accent;
    ctx.beginPath(); ctx.arc(endX, endY, 2.5, 0, Math.PI * 2); ctx.fill();

    if (hoverX == null || hoverX < left) return;
    const wanted = ((hoverX - left) / plotWidth) * runSeconds;
    let index = 0;
    while (index < points.length - 1 && points[index + 1][0] <= wanted) index++;
    const [seconds, value] = points[index];
    const x = atX(seconds), y = atY(value);
    ctx.strokeStyle = muted; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(Math.round(x) + .5, top); ctx.lineTo(Math.round(x) + .5, top + plotHeight); ctx.stroke();
    ctx.fillStyle = accent;
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
    const tip = document.createElement("div");
    tip.className = "tip";
    tip.textContent = `${clock(seconds)} · ${graph.format(value)}`;
    tip.style.left = `${Math.min(Math.max(x, 50), width - 50)}px`;
    element.appendChild(tip);
  }

  const drawGraphs = () => {
    for (const element of document.querySelectorAll(".spark")) drawGraph(element, null);
  };

  // ---- hooks -------------------------------------------------------------
  // `what` is the message type that changed, so a 10 Hz pose push does not
  // re-render the objects list or redraw four graphs.
  viz.onPanels = (what) => {
    if (what === "status" || what === undefined) renderStatus();
    if (what === "targets" || what === undefined) renderObjects();
    if (what === "run" || what === undefined) drawGraphs();
  };
  viz.onDraw = placeMarkers;

  window.addEventListener("resize", drawGraphs);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawGraphs);

  buildGraphs();
  renderCamera();
  renderObjects();
  renderStatus();
  drawGraphs();
})();
