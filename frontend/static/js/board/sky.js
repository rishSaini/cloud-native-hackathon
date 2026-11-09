// The constellation: one <canvas>, one requestAnimationFrame loop, paused when the tab is hidden.
// Rooms are softly lit regions that fill from the bottom like water as seats are taken.
// Attendees are stars in their own color that breathe slowly and glide when moved.
// Decorative for screen readers: board.js renders the same facts as text.
//
// Performance: each star is one drawImage of a pre-rendered glow sprite (cached per hue),
// and the rooms are drawn to an offscreen layer only when room data or size changes.

import { personHue } from "../color.js";

const MOVE_MS = 500;
const BREATH_MS = [3000, 4000];
const HALLWAY = { id: "__hallway", name: "Hallway", seats: 0, taken: 0, status: "" };

// cubic-bezier(0.65, 0, 0.35, 1), the --ease token, solved for t.
function ease(x) {
  const p1x = 0.65, p1y = 0, p2x = 0.35, p2y = 1;
  const bx = (t) => 3 * (1 - t) * (1 - t) * t * p1x + 3 * (1 - t) * t * t * p2x + t * t * t;
  const by = (t) => 3 * (1 - t) * (1 - t) * t * p1y + 3 * (1 - t) * t * t * p2y + t * t * t;
  let lo = 0, hi = 1, t = x;
  for (let i = 0; i < 20; i++) {
    t = (lo + hi) / 2;
    if (bx(t) < x) lo = t; else hi = t;
  }
  return by(t);
}

// Two stable pseudo-random numbers in [0, 1) from an ID, so a star keeps its spot.
function hash2(id) {
  let a = 2166136261, b = 5381;
  for (const ch of id) {
    a = Math.imul(a ^ ch.charCodeAt(0), 16777619) >>> 0;
    b = ((b * 33) ^ ch.charCodeAt(0)) >>> 0;
  }
  return [(a % 10007) / 10007, (b % 10009) / 10009];
}

const STATUS_FILL = {
  OPEN: "rgba(108, 199, 154, 0.20)",
  FULL: "rgba(201, 138, 27, 0.26)",
  INCIDENT: "rgba(232, 138, 155, 0.26)",
  CLOSED: "rgba(185, 182, 217, 0.10)",
};
const STATUS_RING = {
  OPEN: "rgba(108, 199, 154, 0.45)",
  FULL: "rgba(201, 138, 27, 0.6)",
  INCIDENT: "rgba(232, 138, 155, 0.7)",
  CLOSED: "rgba(185, 182, 217, 0.3)",
};

export function createSky(canvas, { motion = true } = {}) {
  const ctx = canvas.getContext("2d");
  const roomsLayer = document.createElement("canvas");
  const sprites = new Map();
  const stars = new Map();       // displayId -> star
  let regions = new Map();       // roomId -> { x, y, r, room }
  let rooms = [];
  let attendees = [];
  let width = 0, height = 0, dpr = 1;
  let raf = 0;
  let animate = motion;
  let dirtyRooms = true;
  let lastStill = 0;
  let hallCount = 0;
  let groupList = [];             // break groups, in the order they formed
  const groupPos = new Map();     // groupId -> { x, y, t0, slot }
  let groupSlots = 0;
  let kubectlLabels = false;

  function sprite(hue) {
    if (sprites.has(hue)) return sprites.get(hue);
    const size = 28 * dpr;
    const c = document.createElement("canvas");
    c.width = c.height = Math.ceil(size);
    const g = c.getContext("2d");
    const mid = size / 2;
    const grad = g.createRadialGradient(mid, mid, 0, mid, mid, mid);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(0.18, `hsla(${hue}, 70%, 85%, 1)`);
    grad.addColorStop(0.4, `hsla(${hue}, 70%, 78%, 0.35)`);
    grad.addColorStop(1, `hsla(${hue}, 70%, 78%, 0)`);
    g.fillStyle = grad;
    g.fillRect(0, 0, size, size);
    sprites.set(hue, c);
    return c;
  }

  function layout() {
    const list = [...rooms];
    const cols = list.length <= 4 ? 2 : 3;
    const rowsN = Math.max(1, Math.ceil(list.length / cols));
    const cellW = width / cols;
    const cellH = height / rowsN;
    const maxSeats = Math.max(1, ...list.map((r) => r.seats || 1));
    const next = new Map();
    list.forEach((room, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const base = Math.min(cellW, cellH) * 0.36;
      const r = base * (0.6 + 0.4 * Math.sqrt((room.seats || 1) / maxSeats));
      next.set(room.id, { x: cellW * (col + 0.5), y: cellH * (row + 0.5) - 14, r, room });
    });
    // The hallway sits between the rooms, for people not placed in a room right now.
    // It grows with its headcount, but never reaches into a room.
    let clearance = Infinity;
    for (const reg of next.values()) clearance = Math.min(clearance, Math.hypot(reg.x - width / 2, reg.y - height / 2) - reg.r - 40);
    const wanted = Math.min(cellW, cellH) * 0.08 * Math.sqrt(Math.max(1, hallCount) / 10);
    const hallR = Math.max(24, Math.min(wanted, clearance, Math.min(cellW, cellH) * 0.45));
    next.set(HALLWAY.id, { x: width / 2, y: height / 2, r: hallR, room: { ...HALLWAY, taken: hallCount } });
    regions = next;
    dirtyRooms = true;
  }

  // Break tables: each group gets a stable slot on a loose grid over the whole sky,
  // sized for everyone being grouped, so earlier groups never jump when new ones form.
  function slotCenter(slot) {
    const total = Math.max(groupSlots, 1);
    const cols = Math.max(1, Math.ceil(Math.sqrt(total * (width / Math.max(1, height)))));
    const rowsN = Math.ceil(total / cols);
    const cw = (width - 60) / cols;
    const ch = (height - 60) / rowsN;
    const [u, v] = hash2(`slot-${slot}`);
    return {
      x: 30 + cw * ((slot % cols) + 0.5 + (u - 0.5) * 0.4),
      y: 30 + ch * (Math.floor(slot / cols) + 0.5 + (v - 0.5) * 0.4),
    };
  }

  function layoutGroups() {
    for (const g of groupList) {
      const p = groupPos.get(g.id);
      if (p) Object.assign(p, slotCenter(p.slot));
    }
  }

  function targetFor(a) {
    const gp = a.groupId && groupPos.get(a.groupId);
    if (gp) {
      const g = groupList.find((x) => x.id === a.groupId);
      const k = Math.max(1, g?.members.length || 1);
      const j = Math.max(0, g?.members.indexOf(a.displayId) ?? 0);
      const r = 9 + k * 1.5;
      const th = (j / k) * Math.PI * 2 + hash2(a.groupId)[0] * Math.PI;
      return { x: gp.x + r * Math.cos(th), y: gp.y + r * Math.sin(th) };
    }
    const region = regions.get(a.roomId) || regions.get(HALLWAY.id);
    if (!region) return { x: width / 2, y: height / 2 };
    const [u, v] = hash2(a.displayId);
    const rr = region.r * 0.82 * Math.sqrt(u);
    const th = v * Math.PI * 2;
    return { x: region.x + rr * Math.cos(th), y: region.y + rr * Math.sin(th) };
  }

  function placeStars(now) {
    const seen = new Set();
    for (const a of attendees) {
      seen.add(a.displayId);
      const t = targetFor(a);
      let s = stars.get(a.displayId);
      if (!s) {
        const hue = personHue(a.displayId);
        const [u] = hash2(a.displayId + "~");
        s = {
          x: t.x, y: t.y, fx: t.x, fy: t.y, tx: t.x, ty: t.y, t0: 0,
          hue, phase: u * Math.PI * 2,
          period: BREATH_MS[0] + u * (BREATH_MS[1] - BREATH_MS[0]),
          roomId: a.roomId,
        };
        stars.set(a.displayId, s);
      } else if (s.tx !== t.x || s.ty !== t.y) {
        s.fx = s.x; s.fy = s.y; s.tx = t.x; s.ty = t.y; s.t0 = now;
        if (!animate) { s.x = t.x; s.y = t.y; }
      }
      s.roomId = a.roomId;
    }
    for (const id of stars.keys()) if (!seen.has(id)) stars.delete(id);
  }

  function drawRooms() {
    roomsLayer.width = canvas.width;
    roomsLayer.height = canvas.height;
    const g = roomsLayer.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    for (const { x, y, r, room } of regions.values()) {
      const isHall = room.id === HALLWAY.id;
      const status = room.status || "OPEN";
      // Soft light
      const glow = g.createRadialGradient(x, y, r * 0.1, x, y, r * 1.35);
      glow.addColorStop(0, isHall ? "rgba(185,182,217,0.06)" : "rgba(244,241,255,0.09)");
      glow.addColorStop(1, "rgba(244,241,255,0)");
      g.fillStyle = glow;
      g.beginPath(); g.arc(x, y, r * 1.35, 0, Math.PI * 2); g.fill();
      if (isHall) {
        if (!room.taken) continue;
        g.textAlign = "center";
        g.fillStyle = "#B9B6D9";
        g.font = `500 14px "JetBrains Mono", ui-monospace, monospace`;
        g.fillText(`Hallway · ${room.taken} not in a room`, x, y + r + 24);
        continue;
      }
      // Water: fills from the bottom with the share of seats taken.
      const share = Math.max(0, Math.min(1, (room.taken || 0) / (room.seats || 1)));
      g.save();
      g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.clip();
      g.fillStyle = STATUS_FILL[status] || STATUS_FILL.OPEN;
      g.fillRect(x - r, y + r - share * 2 * r, r * 2, share * 2 * r);
      g.restore();
      // Rim
      g.strokeStyle = STATUS_RING[status] || STATUS_RING.OPEN;
      g.lineWidth = status === "INCIDENT" ? 2.5 : 1.5;
      if (status === "CLOSED") g.setLineDash([6, 6]);
      g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.stroke();
      g.setLineDash([]);
      // Label: name, then status as a word and the count.
      g.textAlign = "center";
      g.fillStyle = "#F4F1FF";
      g.font = `600 ${Math.max(16, r * 0.16)}px Nunito, system-ui, sans-serif`;
      g.fillText(kubectlLabels ? `node/${room.id}` : room.name, x, y + r + Math.max(24, r * 0.2));
      g.fillStyle = "#B9B6D9";
      g.font = `500 ${Math.max(13, r * 0.11)}px "JetBrains Mono", ui-monospace, monospace`;
      g.fillText(`${status} · ${room.taken} of ${room.seats}`, x, y + r + Math.max(46, r * 0.36));
    }
    dirtyRooms = false;
  }

  function frame(now) {
    raf = 0;
    if (dirtyRooms) drawRooms();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // During a break, most people are at tables: the rooms fade back.
    const groupedShare = attendees.length ? attendees.filter((a) => a.groupId).length / attendees.length : 0;
    ctx.globalAlpha = 1 - Math.min(0.65, groupedShare * 0.8);
    ctx.drawImage(roomsLayer, 0, 0);
    ctx.globalAlpha = 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const size = 14;
    // Constellations: faint lines join each group's stars, with a soft glow pulse when it forms.
    let pulsing = false;
    for (const g of groupList) {
      const pts = g.members.map((id) => stars.get(id)).filter(Boolean);
      if (pts.length < 2) continue;
      const pos = groupPos.get(g.id);
      const age = pos && animate ? now - pos.t0 : Infinity;
      const pulse = age < 1600 ? 1 - age / 1600 : 0;
      if (pulse > 0) pulsing = true;
      ctx.strokeStyle = `rgba(244, 241, 255, ${0.28 + 0.5 * pulse})`;
      ctx.lineWidth = 1 + 1.5 * pulse;
      ctx.beginPath();
      pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
      if (pts.length > 2) ctx.closePath();
      ctx.stroke();
      if (pulse > 0 && pos) {
        const glow = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, 34);
        glow.addColorStop(0, `rgba(244, 241, 255, ${0.35 * pulse})`);
        glow.addColorStop(1, "rgba(244, 241, 255, 0)");
        ctx.fillStyle = glow;
        ctx.beginPath(); ctx.arc(pos.x, pos.y, 34, 0, Math.PI * 2); ctx.fill();
      }
    }
    let moving = false;
    for (const s of stars.values()) {
      if (s.t0 && animate) {
        const p = Math.min(1, (now - s.t0) / MOVE_MS);
        const e = ease(p);
        s.x = s.fx + (s.tx - s.fx) * e;
        s.y = s.fy + (s.ty - s.fy) * e;
        if (p >= 1) s.t0 = 0; else moving = true;
      } else if (s.t0) {
        s.x = s.tx; s.y = s.ty; s.t0 = 0;
      }
      ctx.globalAlpha = animate ? 0.62 + 0.38 * (0.5 + 0.5 * Math.sin((now / s.period) * Math.PI * 2 + s.phase)) : 0.9;
      const scale = animate ? 0.92 + 0.12 * (0.5 + 0.5 * Math.sin((now / s.period) * Math.PI * 2 + s.phase)) : 1;
      const d = size * scale;
      ctx.drawImage(sprite(s.hue), s.x - d / 2, s.y - d / 2, d, d);
    }
    ctx.globalAlpha = 1;
    if (animate && !document.hidden) raf = requestAnimationFrame(frame);
    else if (moving || pulsing) raf = requestAnimationFrame(frame);
    lastStill = now;
  }

  function schedule() {
    if (!raf) raf = requestAnimationFrame(frame);
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    dpr = Math.min(2, window.devicePixelRatio || 1);
    width = Math.max(1, rect.width);
    height = Math.max(1, rect.height);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    sprites.clear();
    layout();
    layoutGroups();
    // Snap every star to its spot in the new layout (no glide on resize).
    for (const [displayId, s] of stars) {
      const t = targetFor({ displayId, roomId: s.roomId });
      s.x = s.tx = s.fx = t.x;
      s.y = s.ty = s.fy = t.y;
      s.t0 = 0;
    }
    placeStars(performance.now());
    schedule();
  }

  const ro = new ResizeObserver(resize);
  ro.observe(canvas);
  const onVisibility = () => { if (!document.hidden) schedule(); };
  document.addEventListener("visibilitychange", onVisibility);

  return {
    update(board) {
      const nextRooms = board.rooms || [];
      const roomsChanged = JSON.stringify(nextRooms.map((r) => [r.id, r.seats])) !== JSON.stringify(rooms.map((r) => [r.id, r.seats]));
      rooms = nextRooms;
      attendees = board.attendees || [];
      const roomIds = new Set(rooms.map((r) => r.id));
      const nextHall = attendees.filter((a) => !roomIds.has(a.roomId) && !a.groupId).length;
      // Groups: keep slots for known groups, add new ones (with a pulse), drop vanished ones.
      groupList = board.groups || [];
      groupSlots = Math.max(groupSlots, Math.ceil(attendees.length / 3), groupList.length);
      const live = new Set(groupList.map((g) => g.id));
      for (const id of groupPos.keys()) if (!live.has(id)) groupPos.delete(id);
      if (!groupList.length) groupSlots = 0;
      groupList.forEach((g, i) => {
        if (!groupPos.has(g.id)) groupPos.set(g.id, { ...slotCenter(i), slot: i, t0: performance.now() });
      });
      // Re-lay out when the hallway's size changes noticeably (in steps of 10 people).
      const hallChanged = Math.round(nextHall / 10) !== Math.round(hallCount / 10) || (nextHall === 0) !== (hallCount === 0);
      hallCount = nextHall;
      if (roomsChanged || hallChanged || !regions.size) layout();
      else {
        for (const room of rooms) { const reg = regions.get(room.id); if (reg) reg.room = room; }
        dirtyRooms = true;
      }
      placeStars(performance.now());
      schedule();
    },
    setKubectl(on) {
      kubectlLabels = on;
      dirtyRooms = true;
      schedule();
    },
    setMotion(on) {
      animate = on;
      schedule();
    },
    destroy() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    },
    get starCount() { return stars.size; },
    get lastFrameAt() { return lastStill; },
  };
}
