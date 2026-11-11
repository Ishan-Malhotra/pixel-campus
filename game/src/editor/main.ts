/**
 * Campus Map Editor ("god mode").
 * Upload images, cut pieces out of them (crop + background removal), place them on a tile-grid canvas,
 * layer them, and export the assembled campus as one PNG (+ a layout JSON). Autosaves in the browser.
 */
import './editor.css';

// ------------------------------------------------------------------ model
interface Asset { id: string; name: string; dataUrl: string; w: number; h: number }
interface Rect { x: number; y: number; w: number; h: number }
interface KeyBg { on: boolean; r: number; g: number; b: number; tol: number; edgeOnly: boolean }
interface Block {
  id: string; assetId: string; name: string;
  x: number; y: number; crop: Rect; scale: number;
  flipX: boolean; flipY: boolean; opacity: number; locked: boolean; hidden: boolean; key: KeyBg;
}
interface Project { version: 1; width: number; height: number; tile: number; bg: string; assets: Asset[]; blocks: Block[] }

const TILE = 16;
let P: Project = { version: 1, width: 128, height: 96, tile: TILE, bg: '#6fd27a', assets: [], blocks: [] };
const images = new Map<string, HTMLImageElement>();          // assetId -> loaded image
const processed = new Map<string, HTMLCanvasElement>();      // block render cache (crop + bg removal)
let selId: string | null = null;
const undoStack: string[] = [];

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const uid = () => Math.random().toString(36).slice(2, 10);
const sel = () => P.blocks.find(b => b.id === selId) ?? null;

// ------------------------------------------------------------------ storage (IndexedDB autosave)
const DB = 'campus-editor', STORE = 'kv';
function idb(): Promise<IDBDatabase> {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE);
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}
async function idbSet(key: string, val: unknown) {
  const db = await idb();
  await new Promise<void>((res, rej) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(val, key);
    tx.oncomplete = () => res(); tx.onerror = () => rej(tx.error);
  });
}
async function idbGet<T>(key: string): Promise<T | undefined> {
  const db = await idb();
  return new Promise((res, rej) => {
    const r = db.transaction(STORE).objectStore(STORE).get(key);
    r.onsuccess = () => res(r.result as T | undefined); r.onerror = () => rej(r.error);
  });
}
let saveTimer = 0;
function autosave() {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    idbSet('project', P).then(() => status(`Autosaved · ${P.blocks.length} pieces`)).catch(e => status('Autosave failed: ' + e));
  }, 600);
}
function status(msg: string) { $('status').textContent = msg; }

// ------------------------------------------------------------------ undo
function pushUndo() {
  undoStack.push(JSON.stringify({ blocks: P.blocks, width: P.width, height: P.height, bg: P.bg }));
  if (undoStack.length > 120) undoStack.shift();
}
function undo() {
  const s = undoStack.pop();
  if (!s) return;
  const o = JSON.parse(s);
  P.blocks = o.blocks; P.width = o.width; P.height = o.height; P.bg = o.bg;
  processed.clear();
  if (selId && !sel()) selId = null;
  refreshAll();
}

// ------------------------------------------------------------------ assets
function loadImage(a: Asset): Promise<HTMLImageElement> {
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => { images.set(a.id, im); res(im); };
    im.onerror = rej;
    im.src = a.dataUrl;
  });
}
function fileToDataUrl(f: Blob): Promise<string> {
  return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result as string); r.onerror = rej; r.readAsDataURL(f); });
}
async function addAsset(name: string, dataUrl: string) {
  const a: Asset = { id: uid(), name, dataUrl, w: 0, h: 0 };
  const im = await loadImage(a);
  a.w = im.naturalWidth; a.h = im.naturalHeight;
  P.assets.push(a);
  renderLibrary(); autosave();
  return a;
}
async function addFiles(files: FileList | File[]) {
  for (const f of Array.from(files)) {
    if (!f.type.startsWith('image/')) continue;
    await addAsset(f.name.replace(/\.[^.]+$/, ''), await fileToDataUrl(f));
  }
  status(`Library: ${P.assets.length} images`);
}
async function addStarter() {
  const list: { name: string; file: string }[] = await (await fetch('editor-assets/manifest.json')).json();
  for (const it of list) {
    if (P.assets.some(a => a.name === it.name)) continue;
    const blob = await (await fetch('editor-assets/' + it.file)).blob();
    await addAsset(it.name, await fileToDataUrl(blob));
  }
  status('Starter images added');
}
function renderLibrary() {
  const el = $('library');
  el.innerHTML = '';
  for (const a of P.assets) {
    const d = document.createElement('div');
    d.className = 'asset';
    d.title = `${a.name} (${a.w}×${a.h})`;
    d.innerHTML = `<img src="${a.dataUrl}" alt=""><div class="nm">${a.name}</div><button class="x danger" title="Remove from library">×</button>`;
    d.onclick = (e) => {
      if ((e.target as HTMLElement).classList.contains('x')) {
        if (P.blocks.some(b => b.assetId === a.id) && !confirm(`Pieces on the map use "${a.name}". Remove them too?`)) return;
        pushUndo();
        P.blocks = P.blocks.filter(b => b.assetId !== a.id);
        P.assets = P.assets.filter(x => x.id !== a.id);
        renderLibrary(); refreshAll(); return;
      }
      placeAsset(a);
    };
    el.appendChild(d);
  }
}

// ------------------------------------------------------------------ blocks
function placeAsset(a: Asset) {
  pushUndo();
  const c = screenToWorld(canvas.clientWidth / 2, canvas.clientHeight / 2);
  const s = snapV();
  const b: Block = {
    id: uid(), assetId: a.id, name: a.name,
    x: Math.round((c.x - a.w / 2) / s) * s, y: Math.round((c.y - a.h / 2) / s) * s,
    crop: { x: 0, y: 0, w: a.w, h: a.h }, scale: 1, flipX: false, flipY: false, opacity: 1, locked: false, hidden: false,
    key: { on: false, r: 0, g: 0, b: 0, tol: 40, edgeOnly: true },
  };
  P.blocks.push(b);
  selId = b.id;
  refreshAll();
}
const bw = (b: Block) => b.crop.w * b.scale;
const bh = (b: Block) => b.crop.h * b.scale;

/** crop + background removal, cached per block settings */
function blockCanvas(b: Block): HTMLCanvasElement | null {
  const im = images.get(b.assetId);
  if (!im) return null;
  const k = b.key;
  const sig = `${b.id}|${b.crop.x},${b.crop.y},${b.crop.w},${b.crop.h}|${k.on ? `${k.r},${k.g},${k.b},${k.tol},${k.edgeOnly}` : 'off'}`;
  const hit = processed.get(sig);
  if (hit) return hit;
  for (const key of processed.keys()) if (key.startsWith(b.id + '|')) processed.delete(key);
  const c = document.createElement('canvas');
  c.width = Math.max(1, b.crop.w); c.height = Math.max(1, b.crop.h);
  const x = c.getContext('2d', { willReadFrequently: true })!;
  x.imageSmoothingEnabled = false;
  x.drawImage(im, b.crop.x, b.crop.y, b.crop.w, b.crop.h, 0, 0, b.crop.w, b.crop.h);
  if (k.on) {
    const d = x.getImageData(0, 0, c.width, c.height);
    removeBackground(d, k);
    x.putImageData(d, 0, 0);
  }
  processed.set(sig, c);
  return c;
}
function removeBackground(d: ImageData, k: KeyBg) {
  const { width: w, height: h, data } = d;
  const near = (i: number) => Math.abs(data[i] - k.r) + Math.abs(data[i + 1] - k.g) + Math.abs(data[i + 2] - k.b) <= k.tol;
  if (!k.edgeOnly) {
    for (let i = 0; i < data.length; i += 4) if (near(i)) data[i + 3] = 0;
    return;
  }
  const seen = new Uint8Array(w * h);
  const stack: number[] = [];
  for (let x = 0; x < w; x++) { stack.push(x, (h - 1) * w + x); }
  for (let y = 0; y < h; y++) { stack.push(y * w, y * w + w - 1); }
  while (stack.length) {
    const p = stack.pop()!;
    if (seen[p]) continue;
    seen[p] = 1;
    const i = p * 4;
    if (!near(i)) continue;
    data[i + 3] = 0;
    const x = p % w, y = (p / w) | 0;
    if (x > 0) stack.push(p - 1);
    if (x < w - 1) stack.push(p + 1);
    if (y > 0) stack.push(p - w);
    if (y < h - 1) stack.push(p + w);
  }
}

// ------------------------------------------------------------------ view
const canvas = $<HTMLCanvasElement>('canvas');
const ctx = canvas.getContext('2d')!;
const view = { x: -40, y: -40, zoom: 1 };
function resize() {
  const r = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(r.width * dpr); canvas.height = Math.round(r.height * dpr);
  draw();
}
const screenToWorld = (sx: number, sy: number) => ({ x: sx / view.zoom + view.x, y: sy / view.zoom + view.y });
const snapV = () => Number(($('snap') as HTMLSelectElement).value);

function draw() {
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = '#11151f';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(dpr * view.zoom, 0, 0, dpr * view.zoom, -view.x * dpr * view.zoom, -view.y * dpr * view.zoom);
  ctx.imageSmoothingEnabled = false;
  const W = P.width * TILE, H = P.height * TILE;
  ctx.fillStyle = P.bg;
  ctx.fillRect(0, 0, W, H);
  for (const b of P.blocks) {
    if (b.hidden) continue;
    const c = blockCanvas(b);
    if (!c) continue;
    ctx.save();
    ctx.globalAlpha = b.opacity;
    ctx.translate(b.x + (b.flipX ? bw(b) : 0), b.y + (b.flipY ? bh(b) : 0));
    ctx.scale(b.flipX ? -1 : 1, b.flipY ? -1 : 1);
    ctx.drawImage(c, 0, 0, bw(b), bh(b));
    ctx.restore();
  }
  const px = 1 / view.zoom;
  if (($('showGrid') as HTMLInputElement).checked && view.zoom >= 0.5) {
    ctx.strokeStyle = 'rgba(0,0,0,0.18)';
    ctx.lineWidth = px;
    ctx.beginPath();
    const step = view.zoom >= 2 ? TILE : TILE * 4;
    for (let x = 0; x <= W; x += step) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
    for (let y = 0; y <= H; y += step) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
    ctx.stroke();
  }
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 2 * px;
  ctx.strokeRect(0, 0, W, H);
  if (($('showBounds') as HTMLInputElement).checked) {
    ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.lineWidth = px;
    for (const b of P.blocks) if (!b.hidden) ctx.strokeRect(b.x, b.y, bw(b), bh(b));
  }
  const s = sel();
  if (s) {
    ctx.strokeStyle = s.locked ? '#ff8a5a' : '#ffd35a';
    ctx.lineWidth = 2 * px;
    ctx.setLineDash([6 * px, 4 * px]);
    ctx.strokeRect(s.x, s.y, bw(s), bh(s));
    ctx.setLineDash([]);
  }
  if (cropDrag) {
    ctx.strokeStyle = '#5affc8'; ctx.lineWidth = 2 * px;
    const r = normRect(cropDrag.a, cropDrag.b);
    ctx.strokeRect(r.x, r.y, r.w, r.h);
  }
  $('zoomLabel').textContent = `${Math.round(view.zoom * 100)}%  ·  map ${P.width}×${P.height} tiles`;
}
function normRect(a: { x: number; y: number }, b: { x: number; y: number }): Rect {
  return { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y) };
}

// ------------------------------------------------------------------ interaction
let mode: 'none' | 'move' | 'pan' | 'crop' = 'none';
let dragStart = { x: 0, y: 0, bx: 0, by: 0, vx: 0, vy: 0 };
let spaceDown = false;
let cropArmed = false, pickArmed = false;
let cropDrag: { a: { x: number; y: number }; b: { x: number; y: number } } | null = null;

function hitTest(wx: number, wy: number): Block | null {
  for (let i = P.blocks.length - 1; i >= 0; i--) {
    const b = P.blocks[i];
    if (b.hidden || b.locked) continue;
    if (wx >= b.x && wx < b.x + bw(b) && wy >= b.y && wy < b.y + bh(b)) {
      // ignore clicks on transparent pixels so you can grab pieces underneath
      const c = blockCanvas(b);
      if (c) {
        let lx = (wx - b.x) / b.scale, ly = (wy - b.y) / b.scale;
        if (b.flipX) lx = b.crop.w - 1 - lx;
        if (b.flipY) ly = b.crop.h - 1 - ly;
        const a = c.getContext('2d')!.getImageData(Math.floor(lx), Math.floor(ly), 1, 1).data[3];
        if (a === 0) continue;
      }
      return b;
    }
  }
  return null;
}
/** world point -> source-image pixel of a block (before crop) */
function worldToSource(b: Block, wx: number, wy: number) {
  let lx = (wx - b.x) / b.scale, ly = (wy - b.y) / b.scale;
  if (b.flipX) lx = b.crop.w - lx;
  if (b.flipY) ly = b.crop.h - ly;
  return { x: Math.round(lx + b.crop.x), y: Math.round(ly + b.crop.y) };
}

canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('mousedown', (e) => {
  const r = canvas.getBoundingClientRect();
  const w = screenToWorld(e.clientX - r.left, e.clientY - r.top);
  if (e.button === 2 || e.button === 1 || spaceDown) {
    mode = 'pan'; dragStart = { x: e.clientX, y: e.clientY, bx: 0, by: 0, vx: view.x, vy: view.y };
    canvas.style.cursor = 'grabbing';
    return;
  }
  const s = sel();
  if (pickArmed && s) {
    const src = worldToSource(s, w.x, w.y);
    const im = images.get(s.assetId)!;
    const c = document.createElement('canvas'); c.width = 1; c.height = 1;
    const x = c.getContext('2d')!; x.drawImage(im, src.x, src.y, 1, 1, 0, 0, 1, 1);
    const [cr, cg, cb] = x.getImageData(0, 0, 1, 1).data;
    pushUndo();
    s.key = { ...s.key, on: true, r: cr, g: cg, b: cb };
    pickArmed = false; $('btnPick').classList.remove('active');
    refreshAll();
    return;
  }
  if (cropArmed && s) {
    mode = 'crop';
    cropDrag = { a: w, b: w };
    return;
  }
  const hit = hitTest(w.x, w.y);
  selId = hit ? hit.id : null;
  if (hit) {
    pushUndo();
    mode = 'move';
    dragStart = { x: w.x, y: w.y, bx: hit.x, by: hit.y, vx: 0, vy: 0 };
  }
  refreshPanels(); draw();
});
window.addEventListener('mousemove', (e) => {
  const r = canvas.getBoundingClientRect();
  const w = screenToWorld(e.clientX - r.left, e.clientY - r.top);
  $('cursorLabel').textContent = `x ${Math.floor(w.x)}  y ${Math.floor(w.y)}  ·  tile ${Math.floor(w.x / TILE)}, ${Math.floor(w.y / TILE)}`;
  if (mode === 'pan') {
    view.x = dragStart.vx - (e.clientX - dragStart.x) / view.zoom;
    view.y = dragStart.vy - (e.clientY - dragStart.y) / view.zoom;
    draw();
  } else if (mode === 'move') {
    const s = sel(); if (!s) return;
    const sn = e.altKey ? 1 : snapV();
    s.x = Math.round((dragStart.bx + (w.x - dragStart.x)) / sn) * sn;
    s.y = Math.round((dragStart.by + (w.y - dragStart.y)) / sn) * sn;
    refreshProps(); draw();
  } else if (mode === 'crop' && cropDrag) {
    cropDrag.b = w; draw();
  }
});
window.addEventListener('mouseup', () => {
  if (mode === 'crop' && cropDrag) {
    const s = sel();
    const rr = normRect(cropDrag.a, cropDrag.b);
    if (s && rr.w > 2 && rr.h > 2) {
      pushUndo();
      const a = worldToSource(s, rr.x, rr.y), b = worldToSource(s, rr.x + rr.w, rr.y + rr.h);
      const nx = Math.max(0, Math.min(a.x, b.x)), ny = Math.max(0, Math.min(a.y, b.y));
      const asset = P.assets.find(x => x.id === s.assetId)!;
      const nw = Math.min(asset.w - nx, Math.abs(b.x - a.x)), nh = Math.min(asset.h - ny, Math.abs(b.y - a.y));
      s.x = Math.round(rr.x); s.y = Math.round(rr.y);
      s.crop = { x: nx, y: ny, w: Math.max(1, nw), h: Math.max(1, nh) };
    }
    cropDrag = null; cropArmed = false; $('btnCrop').classList.remove('active');
    refreshAll();
  } else if (mode === 'move') {
    autosave(); refreshLayers();
  }
  mode = 'none';
  canvas.style.cursor = spaceDown ? 'grab' : 'default';
});
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const r = canvas.getBoundingClientRect();
  const sx = e.clientX - r.left, sy = e.clientY - r.top;
  const before = screenToWorld(sx, sy);
  const f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
  view.zoom = Math.min(16, Math.max(0.05, view.zoom * f));
  view.x = before.x - sx / view.zoom; view.y = before.y - sy / view.zoom;
  draw();
}, { passive: false });

window.addEventListener('keydown', (e) => {
  const tag = (e.target as HTMLElement).tagName;
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
  const s = sel();
  const mod = e.ctrlKey || e.metaKey;
  if (e.code === 'Space') { spaceDown = true; canvas.style.cursor = 'grab'; e.preventDefault(); return; }
  if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(); return; }
  if (mod && e.key.toLowerCase() === 'd' && s) { e.preventDefault(); duplicate(); return; }
  if (e.key.toLowerCase() === 'g' && !mod) { const g = $<HTMLInputElement>('showGrid'); g.checked = !g.checked; draw(); return; }
  if (!s) return;
  const step = e.shiftKey ? TILE : 1;
  const mv: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
  if (mv[e.key]) { e.preventDefault(); pushUndo(); s.x += mv[e.key][0]; s.y += mv[e.key][1]; refreshProps(); draw(); autosave(); return; }
  if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); del(); return; }
  if (e.key === ']') { layer(1); return; }
  if (e.key === '[') { layer(-1); return; }
});
window.addEventListener('keyup', (e) => { if (e.code === 'Space') { spaceDown = false; canvas.style.cursor = 'default'; } });

function duplicate() {
  const s = sel(); if (!s) return;
  pushUndo();
  const c: Block = JSON.parse(JSON.stringify(s));
  c.id = uid(); c.x += TILE; c.y += TILE; c.name = s.name + ' copy';
  P.blocks.splice(P.blocks.indexOf(s) + 1, 0, c);
  selId = c.id; refreshAll();
}
function del() {
  const s = sel(); if (!s) return;
  pushUndo();
  P.blocks = P.blocks.filter(b => b !== s); selId = null; refreshAll();
}
function layer(d: number) {
  const s = sel(); if (!s) return;
  const i = P.blocks.indexOf(s), j = i + d;
  if (j < 0 || j >= P.blocks.length) return;
  pushUndo();
  [P.blocks[i], P.blocks[j]] = [P.blocks[j], P.blocks[i]];
  refreshAll();
}

// ------------------------------------------------------------------ panels
function refreshProps() {
  const s = sel();
  $('noSel').hidden = !!s; $('selPanel').hidden = !s;
  if (!s) return;
  const set = (id: string, v: string | number) => { const el = $<HTMLInputElement>(id); if (document.activeElement !== el) el.value = String(v); };
  set('pName', s.name); set('pX', s.x); set('pY', s.y); set('pOpacity', s.opacity);
  ($('pScale') as HTMLSelectElement).value = String(s.scale);
  $<HTMLInputElement>('pFlip').checked = s.flipX; $<HTMLInputElement>('pFlipV').checked = s.flipY; $<HTMLInputElement>('pLock').checked = s.locked;
  set('cX', s.crop.x); set('cY', s.crop.y); set('cW', s.crop.w); set('cH', s.crop.h);
  $<HTMLInputElement>('kOn').checked = s.key.on; $<HTMLInputElement>('kEdge').checked = s.key.edgeOnly;
  set('kTol', s.key.tol); $('kTolVal').textContent = String(s.key.tol);
  $('kSwatch').style.background = `rgb(${s.key.r},${s.key.g},${s.key.b})`;
}
function refreshLayers() {
  const el = $('layers');
  el.innerHTML = '';
  for (let i = P.blocks.length - 1; i >= 0; i--) {
    const b = P.blocks[i];
    const li = document.createElement('li');
    if (b.id === selId) li.className = 'sel';
    li.innerHTML = `<span class="eye" title="Show/hide">${b.hidden ? '◌' : '●'}</span><span class="nm">${b.name}</span><span class="hint">${b.locked ? '🔒' : ''}</span>`;
    li.onclick = (e) => {
      if ((e.target as HTMLElement).classList.contains('eye')) { pushUndo(); b.hidden = !b.hidden; refreshAll(); return; }
      selId = b.id; refreshAll();
    };
    el.appendChild(li);
  }
}
function refreshPanels() { refreshProps(); refreshLayers(); }
function refreshAll() { refreshPanels(); draw(); autosave(); }
function refreshMapInputs() {
  $<HTMLInputElement>('mapW').value = String(P.width); $<HTMLInputElement>('mapH').value = String(P.height);
  $<HTMLInputElement>('mapBg').value = P.bg;
}

function bindNum(id: string, apply: (s: Block, v: number) => void) {
  $(id).addEventListener('change', () => {
    const s = sel(); if (!s) return;
    const v = Number(($(id) as HTMLInputElement).value);
    if (Number.isNaN(v)) return;
    pushUndo(); apply(s, v); refreshAll();
  });
}
bindNum('pX', (s, v) => (s.x = Math.round(v)));
bindNum('pY', (s, v) => (s.y = Math.round(v)));
bindNum('cX', (s, v) => (s.crop.x = Math.max(0, Math.round(v))));
bindNum('cY', (s, v) => (s.crop.y = Math.max(0, Math.round(v))));
bindNum('cW', (s, v) => (s.crop.w = Math.max(1, Math.round(v))));
bindNum('cH', (s, v) => (s.crop.h = Math.max(1, Math.round(v))));
bindNum('pScale', (s, v) => (s.scale = v));
$('pOpacity').addEventListener('input', () => { const s = sel(); if (!s) return; s.opacity = Number($<HTMLInputElement>('pOpacity').value); draw(); autosave(); });
$('pName').addEventListener('change', () => { const s = sel(); if (!s) return; s.name = $<HTMLInputElement>('pName').value; refreshAll(); });
for (const [id, k] of [['pFlip', 'flipX'], ['pFlipV', 'flipY'], ['pLock', 'locked']] as const) {
  $(id).addEventListener('change', () => { const s = sel(); if (!s) return; pushUndo(); s[k] = $<HTMLInputElement>(id).checked; refreshAll(); });
}
$('kOn').addEventListener('change', () => { const s = sel(); if (!s) return; pushUndo(); s.key.on = $<HTMLInputElement>('kOn').checked; refreshAll(); });
$('kEdge').addEventListener('change', () => { const s = sel(); if (!s) return; pushUndo(); s.key.edgeOnly = $<HTMLInputElement>('kEdge').checked; refreshAll(); });
$('kTol').addEventListener('input', () => { const s = sel(); if (!s) return; s.key.tol = Number($<HTMLInputElement>('kTol').value); $('kTolVal').textContent = String(s.key.tol); draw(); autosave(); });
$('btnPick').onclick = () => { pickArmed = !pickArmed; cropArmed = false; $('btnPick').classList.toggle('active', pickArmed); $('btnCrop').classList.remove('active'); status(pickArmed ? 'Click the background colour on the selected piece' : ''); };
$('btnCrop').onclick = () => { cropArmed = !cropArmed; pickArmed = false; $('btnCrop').classList.toggle('active', cropArmed); $('btnPick').classList.remove('active'); status(cropArmed ? 'Drag a box over the selected piece to keep just that part' : ''); };
$('btnUncrop').onclick = () => { const s = sel(); if (!s) return; const a = P.assets.find(x => x.id === s.assetId)!; pushUndo(); s.crop = { x: 0, y: 0, w: a.w, h: a.h }; refreshAll(); };
$('btnDup').onclick = duplicate;
$('btnDel').onclick = del;
$('btnUp').onclick = () => layer(1);
$('btnDown').onclick = () => layer(-1);

$('mapW').addEventListener('change', () => { pushUndo(); P.width = Math.max(8, Number($<HTMLInputElement>('mapW').value) | 0); refreshAll(); });
$('mapH').addEventListener('change', () => { pushUndo(); P.height = Math.max(8, Number($<HTMLInputElement>('mapH').value) | 0); refreshAll(); });
$('mapBg').addEventListener('input', () => { P.bg = $<HTMLInputElement>('mapBg').value; draw(); autosave(); });
for (const id of ['showGrid', 'showBounds', 'snap']) $(id).addEventListener('change', draw);

// library + project buttons
$('btnUpload').onclick = () => $('fileInput').click();
$('fileInput').addEventListener('change', (e) => { const f = (e.target as HTMLInputElement).files; if (f) addFiles(f); (e.target as HTMLInputElement).value = ''; });
$('btnStarter').onclick = () => addStarter().catch(err => status('Could not load starter images: ' + err));
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', e => { e.preventDefault(); if (e.dataTransfer?.files.length) addFiles(e.dataTransfer.files); });

function download(name: string, blob: Blob) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
function renderMapCanvas(): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = P.width * TILE; c.height = P.height * TILE;
  const x = c.getContext('2d')!;
  x.imageSmoothingEnabled = false;
  x.fillStyle = P.bg; x.fillRect(0, 0, c.width, c.height);
  for (const b of P.blocks) {
    if (b.hidden) continue;
    const bc = blockCanvas(b); if (!bc) continue;
    x.save(); x.globalAlpha = b.opacity;
    x.translate(b.x + (b.flipX ? bw(b) : 0), b.y + (b.flipY ? bh(b) : 0));
    x.scale(b.flipX ? -1 : 1, b.flipY ? -1 : 1);
    x.drawImage(bc, 0, 0, bw(b), bh(b));
    x.restore();
  }
  return c;
}
$('btnExportPng').onclick = () => {
  status('Rendering…');
  renderMapCanvas().toBlob(b => { if (b) { download('campus_map.png', b); status(`Exported campus_map.png (${P.width * TILE}×${P.height * TILE} px)`); } }, 'image/png');
};
$('btnExportJson').onclick = () => {
  const layout = {
    width: P.width, height: P.height, tile: TILE, bg: P.bg,
    assets: P.assets.map(a => ({ id: a.id, name: a.name, w: a.w, h: a.h })),
    blocks: P.blocks,
  };
  download('campus_layout.json', new Blob([JSON.stringify(layout, null, 1)], { type: 'application/json' }));
};
$('btnSave').onclick = () => download('campus_project.json', new Blob([JSON.stringify(P)], { type: 'application/json' }));
$('btnLoad').onclick = () => $('projectInput').click();
$('projectInput').addEventListener('change', async (e) => {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return;
  try { await openProject(JSON.parse(await f.text())); status('Project opened'); } catch (err) { status('Could not open: ' + err); }
  (e.target as HTMLInputElement).value = '';
});
$('btnNew').onclick = async () => {
  if (!confirm('Start a new empty map? (Your library images are kept.)')) return;
  pushUndo(); P.blocks = []; selId = null; refreshAll();
};

async function openProject(p: Project) {
  P = p; images.clear(); processed.clear(); selId = null;
  await Promise.all(P.assets.map(loadImage));
  renderLibrary(); refreshMapInputs(); refreshAll();
}

// ------------------------------------------------------------------ boot
window.addEventListener('resize', resize);
(async () => {
  const saved = await idbGet<Project>('project').catch(() => undefined);
  if (saved && saved.version === 1) await openProject(saved);
  else { refreshMapInputs(); renderLibrary(); refreshPanels(); }
  resize();
  status(saved ? 'Restored your last session' : 'New map. Add images from the Library to begin.');
})();
