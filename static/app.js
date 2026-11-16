// app.js — the live map: websocket in, canvas out.
//
// The expensive part of drawing is the floor raster, so it is built once per
// map into an offscreen canvas and only rebuilt when a new `floor_plan`
// arrives or the theme changes. Everything else is cheap vector work, and
// repaints are coalesced into one animation frame, so a burst of messages
// costs a single redraw.
//
// This file owns the map canvas, the view transform, the websocket and the map
// controls. The DOM panels — objects list, camera, status line, run graphs —
// and the object markers belong to panels.js, which reaches them through the
// `window.domeViz` seam defined below.
(() => {
  const stage = document.getElementById("stage");
  const canvas = document.getElementById("map");
  const ctx = canvas.getContext("2d");
  const css = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const state = {
    scale: 80, cx: 0, cy: 0,       // px per metre, view centre in map metres
    follow: false, showLaser: true, selected: null,
    isSocketOpen: false, robotState: "not_connected",
  };
  const world = {
    plan: null, robot: null, trail: [], trailMax: 2000, laser: null,
    targets: [], series: {}, runMax: 1800, status: null,
  };

  // The seam to panels.js, which owns the DOM panels and the map markers.
  // It replaces `onPanels` (something changed, re-render) and `onCameraFrame`;
  // `onDraw` runs after every map repaint, so markers follow pan and zoom.
  const api = {
    world, state,
    onPanels: () => {},
    onDraw: () => {},
    onCameraFrame: () => {},
    send: (message) => socket?.readyState === WebSocket.OPEN
      && socket.send(JSON.stringify(message)),
  };
  window.domeViz = api;

  // ---- floor raster -------------------------------------------------------
  // Blur the known-space mask, resample it at `px` pixels per cell with bilinear
  // interpolation and a soft threshold: edges come out rounded and
  // anti-aliased, and single-cell holes close up.
  // `px` is chosen per map so a big room can't turn this into a long stall:
  // the raster never exceeds RASTER_SIDE_MAX on its longer side.
  const PX_MAX = 8, PX_MIN = 2, RASTER_SIDE_MAX = 2048;
  const SMOOTH = { passes: 3, threshold: 0.42, edge: 0.05 };
  let px = PX_MAX, raster = null, rasterTheme = "";
  const themeKey = () => css("--floor") + css("--wall");

  function boxBlur(src, w, h, passes) {
    let a = Float32Array.from(src), b = new Float32Array(w * h);
    for (let p = 0; p < passes; p++) {
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const i = y * w + x;
        b[i] = (a[i] + (x > 0 ? a[i - 1] : 0) + (x < w - 1 ? a[i + 1] : 0)) / 3;
      }
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const i = y * w + x;
        a[i] = (b[i] + (y > 0 ? b[i - w] : 0) + (y < h - 1 ? b[i + w] : 0)) / 3;
      }
    }
    return a;
  }

  function maskLayer(field, w, h, color) {
    const W = w * px, H = h * px;
    const layer = document.createElement("canvas");
    layer.width = W; layer.height = H;
    const lc = layer.getContext("2d");
    const img = lc.createImageData(W, H), pixels = img.data;
    const lo = SMOOTH.threshold - SMOOTH.edge, span = 2 * SMOOTH.edge;
    for (let oy = 0; oy < H; oy++) {
      const fy = Math.min(h - 1, Math.max(0, (oy + .5) / px - .5));
      const y0 = Math.floor(fy), y1 = Math.min(h - 1, y0 + 1), ty = fy - y0;
      for (let ox = 0; ox < W; ox++) {
        const fx = Math.min(w - 1, Math.max(0, (ox + .5) / px - .5));
        const x0 = Math.floor(fx), x1 = Math.min(w - 1, x0 + 1), tx = fx - x0;
        const top = field[y0 * w + x0] * (1 - tx) + field[y0 * w + x1] * tx;
        const bot = field[y1 * w + x0] * (1 - tx) + field[y1 * w + x1] * tx;
        let t = ((top * (1 - ty) + bot * ty) - lo) / span;
        t = t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t);
        pixels[(oy * W + ox) * 4 + 3] = 255 * t;
      }
    }
    lc.putImageData(img, 0, 0);
    lc.globalCompositeOperation = "source-in";
    lc.fillStyle = color; lc.fillRect(0, 0, W, H);
    return layer;
  }

  // The message is in OccupancyGrid order, row 0 at the LOWEST y. Canvas rows
  // run downwards, so the rows are flipped here once and every drawing routine
  // below can then treat field row 0 as the top of the picture.
  function decodeFloor(plan) {
    const bytes = Uint8Array.from(atob(plan.floor), (ch) => ch.charCodeAt(0));
    const { width: w, height: h } = plan;
    const field = new Float32Array(w * h);
    for (let row = 0; row < h; row++) {
      for (let col = 0; col < w; col++) {
        field[(h - 1 - row) * w + col] = bytes[row * w + col] ? 1 : 0;
      }
    }
    return field;
  }

  function buildRaster() {
    const plan = world.plan;
    const { width: w, height: h } = plan;
    px = Math.max(PX_MIN, Math.min(PX_MAX, Math.floor(RASTER_SIDE_MAX / Math.max(w, h))));
    const off = document.createElement("canvas");
    off.width = w * px; off.height = h * px;
    const blurred = boxBlur(plan.field, w, h, SMOOTH.passes);
    off.getContext("2d").drawImage(maskLayer(blurred, w, h, css("--floor")), 0, 0);
    raster = off;
    rasterTheme = themeKey();
  }

  // ---- view transform -----------------------------------------------------
  const toScreen = (x, y) => [
    stage.clientWidth / 2 + (x - state.cx) * state.scale,
    stage.clientHeight / 2 - (y - state.cy) * state.scale,
  ];
  const toWorld = (sx, sy) => [
    state.cx + (sx - stage.clientWidth / 2) / state.scale,
    state.cy - (sy - stage.clientHeight / 2) / state.scale,
  ];
  const clampScale = (s) => Math.min(600, Math.max(15, s));

  function fit() {
    const plan = world.plan;
    if (!plan) return;
    const { width: w, height: h, resolution_m: res, origin } = plan;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (let row = 0; row < h; row++) for (let col = 0; col < w; col++) {
      if (!plan.field[row * w + col]) continue;
      const x = origin[0] + col * res, y = origin[1] + (h - 1 - row) * res;
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }
    if (minX > maxX) return;                  // a map with no known cells yet
    const sw = stage.clientWidth, sh = stage.clientHeight;
    state.scale = clampScale(Math.min(
      (sw - 80) / Math.max(maxX - minX, res),
      (sh - 120) / Math.max(maxY - minY, res),
    ));
    state.cx = (minX + maxX) / 2;
    state.cy = (minY + maxY) / 2;
    setFollow(false);
  }

  // ---- drawing ------------------------------------------------------------
  function draw() {
    const dpr = window.devicePixelRatio || 1;
    const w = stage.clientWidth, h = stage.clientHeight;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    if (world.plan && (!raster || rasterTheme !== themeKey())) buildRaster();
    if (state.follow && world.robot) { state.cx = world.robot.x; state.cy = world.robot.y; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    document.getElementById("empty").hidden = Boolean(world.plan);
    if (world.plan) {
      const plan = world.plan;
      const [left, top] = toScreen(plan.origin[0], plan.origin[1] + plan.height * plan.resolution_m);
      const size = plan.resolution_m * state.scale;
      ctx.imageSmoothingEnabled = true;
      ctx.globalAlpha = isOffline() ? .55 : 1;
      ctx.drawImage(raster, left, top, plan.width * size, plan.height * size);
      ctx.globalAlpha = 1;
      drawGrid(); drawWalls(); drawOrigin(); drawLaser(); drawTrail(); drawRobot();
    }
    drawScale();
    api.onDraw();
  }

  let isDrawPending = false;
  function requestDraw() {
    if (isDrawPending) return;
    isDrawPending = true;
    requestAnimationFrame(() => { isDrawPending = false; draw(); });
  }

  const isOffline = () => state.robotState === "not_connected";

  function gridStep() {
    return [0.5, 1, 2, 5, 10].find((s) => s * state.scale >= 46) ?? 10;
  }

  function drawGrid() {
    const w = stage.clientWidth, h = stage.clientHeight, step = gridStep();
    const [x0, y1] = toWorld(0, 0), [x1, y0] = toWorld(w, h);
    ctx.lineWidth = 1; ctx.strokeStyle = css("--grid");
    ctx.beginPath();
    for (let x = Math.ceil(x0 / step) * step; x <= x1; x += step) {
      const sx = Math.round(toScreen(x, 0)[0]) + .5;
      ctx.moveTo(sx, 0); ctx.lineTo(sx, h);
    }
    for (let y = Math.ceil(y0 / step) * step; y <= y1; y += step) {
      const sy = Math.round(toScreen(0, y)[1]) + .5;
      ctx.moveTo(0, sy); ctx.lineTo(w, sy);
    }
    ctx.stroke();
    ctx.fillStyle = css("--muted");
    ctx.font = `500 10px ${css("--font-data")}`;
    const label = (v) => `${Number(v.toFixed(1))}`;
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (let x = Math.ceil(x0 / step) * step; x <= x1; x += step) {
      if (Math.abs(x) > 1e-9) ctx.fillText(label(x), toScreen(x, 0)[0], 4);
    }
    ctx.textAlign = "left"; ctx.textBaseline = "middle";
    for (let y = Math.ceil(y0 / step) * step; y <= y1; y += step) {
      if (Math.abs(y) > 1e-9) ctx.fillText(label(y), 4, toScreen(0, y)[1]);
    }
    const [ox, oy] = toScreen(0, 0);
    ctx.lineWidth = 1.5; ctx.strokeStyle = css("--axis"); ctx.globalAlpha = .55;
    ctx.beginPath(); ctx.moveTo(0, oy); ctx.lineTo(w, oy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(ox, 0); ctx.lineTo(ox, h); ctx.stroke();
    ctx.globalAlpha = 1;
  }

  function drawOrigin() {
    const [ox, oy] = toScreen(0, 0), len = 34;
    const arrow = (dx, dy, text) => {
      ctx.strokeStyle = css("--axis"); ctx.fillStyle = css("--axis"); ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox + dx * len, oy + dy * len); ctx.stroke();
      const tx = ox + dx * (len + 2), ty = oy + dy * (len + 2);
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(tx - dx * 8 - dy * 4.5, ty - dy * 8 + dx * 4.5);
      ctx.lineTo(tx - dx * 8 + dy * 4.5, ty - dy * 8 - dx * 4.5);
      ctx.closePath(); ctx.fill();
      ctx.font = `600 11px ${css("--font-data")}`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(text, ox + dx * (len + 14), oy + dy * (len + 14));
    };
    arrow(1, 0, "x");
    arrow(0, -1, "y");
    ctx.fillStyle = css("--surface"); ctx.strokeStyle = css("--fg"); ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(ox, oy, 5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.font = `600 11px ${css("--font-data")}`; ctx.fillStyle = css("--fg");
    ctx.textAlign = "right"; ctx.textBaseline = "top";
    ctx.fillText("0, 0", ox - 8, oy + 7);
  }

  function drawWalls() {
    const plan = world.plan;
    ctx.globalAlpha = isOffline() ? .55 : 1;
    ctx.fillStyle = css("--clutter");
    const dot = Math.max(1.5, plan.resolution_m * state.scale * .5);
    for (const [x, y] of plan.clutter) {
      const [sx, sy] = toScreen(x, y);
      ctx.fillRect(sx - dot / 2, sy - dot / 2, dot, dot);
    }
    ctx.strokeStyle = css("--wall"); ctx.lineCap = "round";
    ctx.lineWidth = Math.max(2.5, .07 * state.scale);
    ctx.beginPath();
    for (const [x1, y1, x2, y2] of plan.walls) {
      const [a, b] = toScreen(x1, y1), [c, d] = toScreen(x2, y2);
      ctx.moveTo(a, b); ctx.lineTo(c, d);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  function drawLaser() {
    const laser = world.laser;
    if (!state.showLaser || isOffline() || !laser?.hits.length) return;
    const color = css("--robot");
    const [lx, ly] = toScreen(laser.origin[0], laser.origin[1]);
    ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.globalAlpha = .22;
    ctx.beginPath();
    for (const [x, y] of laser.hits) {
      const [sx, sy] = toScreen(x, y);
      ctx.moveTo(lx, ly); ctx.lineTo(sx, sy);
    }
    ctx.stroke();
    ctx.fillStyle = color; ctx.globalAlpha = .6;
    const r = Math.max(1.6, .02 * state.scale);
    ctx.beginPath();
    for (const [x, y] of laser.hits) {
      const [sx, sy] = toScreen(x, y);
      ctx.moveTo(sx + r, sy); ctx.arc(sx, sy, r, 0, Math.PI * 2);
    }
    ctx.fill(); ctx.globalAlpha = 1;
  }

  function drawTrail() {
    const points = world.trail;
    ctx.lineWidth = Math.max(2, .05 * state.scale);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.strokeStyle = css("--robot");
    for (let i = 1; i < points.length; i++) {
      ctx.globalAlpha = .12 + .45 * (i / points.length);
      const [x0, y0] = toScreen(points[i - 1][0], points[i - 1][1]);
      const [x1, y1] = toScreen(points[i][0], points[i][1]);
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  // Top view of DOME from dome2's URDF, in metres in base_footprint (x
  // forward, y left): 0.30 m round plate, drive wheels at x 0.10 y +-0.125,
  // caster at x -0.12, lidar at x -0.08, camera bar at the front. To scale,
  // but never smaller than ~30 px across.
  function drawRobot() {
    const robot = world.robot;
    if (!robot) return;
    const [sx, sy] = toScreen(robot.x, robot.y);
    const s = Math.max(state.scale, 30 / 0.30);
    const offline = isOffline();
    const accent = offline ? css("--muted") : css("--robot");
    const ink = css("--wall"), surface = css("--surface");
    const rrect = (cx, cy, len, wid, rad) => {
      ctx.beginPath();
      ctx.roundRect((cx - len / 2) * s, (-cy - wid / 2) * s, len * s, wid * s, rad * s);
    };
    ctx.save(); ctx.translate(sx, sy); ctx.rotate(-robot.yaw);
    if (!offline) {
      ctx.fillStyle = accent; ctx.globalAlpha = .14;
      ctx.beginPath(); ctx.arc(0, 0, .25 * s, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;
    }
    ctx.fillStyle = ink;                       // wheels, under the plate edge
    for (const side of [1, -1]) { rrect(.10, side * .128, .075, .028, .008); ctx.fill(); }
    ctx.fillStyle = surface; ctx.strokeStyle = accent;
    ctx.lineWidth = Math.max(2, .012 * s);
    ctx.beginPath(); ctx.arc(0, 0, .15 * s, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = ink; ctx.lineWidth = Math.max(1, .006 * s);
    ctx.beginPath(); ctx.arc(-.12 * s, 0, .014 * s, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = ink;
    ctx.beginPath(); ctx.arc(-.08 * s, 0, .036 * s, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = accent;
    ctx.beginPath(); ctx.arc(-.08 * s, 0, .013 * s, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = ink; rrect(.125, 0, .022, .09, .004); ctx.fill();
    ctx.fillStyle = accent;
    ctx.beginPath(); ctx.arc(.137 * s, 0, .008 * s, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = accent; ctx.lineWidth = Math.max(2, .014 * s);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(0, -.035 * s); ctx.lineTo(.065 * s, 0); ctx.lineTo(0, .035 * s);
    ctx.stroke();
    ctx.restore();
  }

  function drawScale() {
    const metres = [0.25, 0.5, 1, 2, 5, 10].find((m) => m * state.scale >= 66) ?? 10;
    document.getElementById("scalebarBar").style.width = `${metres * state.scale}px`;
    document.getElementById("scalebarLabel").textContent =
      metres < 1 ? `${metres * 100} cm` : `${metres} m`;
  }

  // ---- messages -----------------------------------------------------------
  const handlers = {
    floor_plan(message) {
      const isFirst = world.plan === null;
      world.plan = { ...message, field: decodeFloor(message) };
      raster = null;
      if (isFirst) fit();
    },
    robot(message) { world.robot = message; },
    trail(message) {
      world.trailMax = message.max_points;
      world.trail = message.is_full ? message.points : world.trail.concat(message.points);
      if (world.trail.length > world.trailMax) {
        world.trail = world.trail.slice(world.trail.length - world.trailMax);
      }
    },
    laser(message) { world.laser = message; },
    targets(message) { world.targets = message.targets; },
    run(message) {
      world.runMax = message.max_points;
      for (const [name, points] of Object.entries(message.series)) {
        const kept = message.is_full ? [] : world.series[name] ?? [];
        const joined = kept.concat(points);
        world.series[name] = joined.length > world.runMax
          ? joined.slice(joined.length - world.runMax)
          : joined;
      }
    },
    status(message) {
      world.status = message;
      state.robotState = message.state;
    },
  };

  let socket = null;

  function connect() {
    socket = new WebSocket(`ws://${location.host}/ws`);
    socket.binaryType = "arraybuffer";
    socket.addEventListener("open", () => {
      state.isSocketOpen = true;
      api.onPanels();
    });
    socket.addEventListener("message", (event) => {
      if (typeof event.data !== "string") {
        api.onCameraFrame(event.data);
        return;
      }
      const message = JSON.parse(event.data);
      const handler = handlers[message.type];
      if (!handler) return;
      handler(message);
      api.onPanels(message.type);
      requestDraw();
    });
    socket.addEventListener("close", () => {
      state.isSocketOpen = false;
      api.onPanels();
      setTimeout(connect, 1000);
    });
  }

  // ---- pan, zoom, pinch and the buttons -----------------------------------
  const pointers = new Map();
  let pinchStart = null;
  let hasDragged = false;   // a drag ends in a click the map must ignore

  stage.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".controls")) return;
    stage.setPointerCapture(event.pointerId);
    if (!pointers.size) hasDragged = false;
    pointers.set(event.pointerId, [event.clientX, event.clientY]);
    stage.classList.add("dragging");
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinchStart = { span: Math.hypot(a[0] - b[0], a[1] - b[1]), scale: state.scale };
    }
  });
  stage.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) return;
    const previous = pointers.get(event.pointerId);
    pointers.set(event.pointerId, [event.clientX, event.clientY]);
    if (pointers.size === 2 && pinchStart) {
      const [a, b] = [...pointers.values()];
      const span = Math.hypot(a[0] - b[0], a[1] - b[1]);
      state.scale = clampScale(pinchStart.scale * span / pinchStart.span);
    } else {
      setFollow(false);
      hasDragged = true;
      state.cx -= (event.clientX - previous[0]) / state.scale;
      state.cy += (event.clientY - previous[1]) / state.scale;
    }
    requestDraw();
  });
  const endPointer = (event) => {
    pointers.delete(event.pointerId);
    if (pointers.size < 2) pinchStart = null;
    if (!pointers.size) stage.classList.remove("dragging");
  };
  stage.addEventListener("pointerup", endPointer);
  stage.addEventListener("pointercancel", endPointer);

  function zoomAt(factor, sx, sy) {
    const [wx, wy] = toWorld(sx, sy);
    state.scale = clampScale(state.scale * factor);
    if (!state.follow) {
      state.cx = wx - (sx - stage.clientWidth / 2) / state.scale;
      state.cy = wy + (sy - stage.clientHeight / 2) / state.scale;
    }
    requestDraw();
  }
  stage.addEventListener("wheel", (event) => {
    event.preventDefault();
    const box = stage.getBoundingClientRect();
    zoomAt(Math.exp(-event.deltaY * .0015), event.clientX - box.left, event.clientY - box.top);
  }, { passive: false });

  function setFollow(isOn) {
    state.follow = isOn;
    document.getElementById("follow").setAttribute("aria-pressed", isOn);
  }

  // Selecting an object never changes the zoom, and the map pans only when the
  // object is off-screen (layout.md).
  let panFrame = null;
  function bringIntoView(target) {
    const pad = 56, w = stage.clientWidth, h = stage.clientHeight;
    const [sx, sy] = toScreen(target.x, target.y);
    const dx = sx < pad ? sx - pad : sx > w - pad ? sx - (w - pad) : 0;
    const dy = sy < pad ? sy - pad : sy > h - pad ? sy - (h - pad) : 0;
    if (!dx && !dy) return;
    setFollow(false);
    const from = [state.cx, state.cy];
    const to = [state.cx + dx / state.scale, state.cy - dy / state.scale];
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      [state.cx, state.cy] = to;
      return;
    }
    const start = performance.now(), span = 350;
    cancelAnimationFrame(panFrame);
    const step = (now) => {
      const part = Math.min(1, (now - start) / span);
      const eased = 1 - (1 - part) ** 3;
      state.cx = from[0] + (to[0] - from[0]) * eased;
      state.cy = from[1] + (to[1] - from[1]) * eased;
      draw();
      if (part < 1) panFrame = requestAnimationFrame(step);
    };
    panFrame = requestAnimationFrame(step);
  }

  api.toScreen = toScreen;
  api.requestDraw = requestDraw;
  api.select = (id) => {
    state.selected = state.selected === id ? null : id;
    const target = world.targets.find((item) => item.id === state.selected);
    if (target) bringIntoView(target);
    api.onPanels("targets");
    requestDraw();
  };

  stage.addEventListener("click", (event) => {
    if (hasDragged) return;
    if (state.selected && !event.target.closest(".controls, .marker")) {
      api.select(state.selected);           // clicking empty map deselects
    }
  });

  const centre = () => [stage.clientWidth / 2, stage.clientHeight / 2];
  document.getElementById("zoomIn").onclick = () => zoomAt(1.3, ...centre());
  document.getElementById("zoomOut").onclick = () => zoomAt(1 / 1.3, ...centre());
  document.getElementById("fit").onclick = () => { fit(); requestDraw(); };
  document.getElementById("follow").onclick = () => { setFollow(!state.follow); requestDraw(); };
  document.getElementById("laser").onclick = (event) => {
    state.showLaser = !state.showLaser;
    event.currentTarget.setAttribute("aria-pressed", state.showLaser);
    requestDraw();
  };

  window.addEventListener("resize", requestDraw);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", requestDraw);

  draw();
  connect();
})();
