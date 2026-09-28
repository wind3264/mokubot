import { Board, SIZE, BLACK, WHITE } from "./engine.js";

const THINK_SECONDS = 1.5;
const MIN_REPLY_MS = 300;
const CELL = 40;
const MARGIN = 40;
const STAR_POINTS = [[3, 3], [3, 11], [7, 7], [11, 3], [11, 11]];
const SVG_NS = "http://www.w3.org/2000/svg";
const STORAGE_KEY = "mokubot-game";

const svg = document.getElementById("board");
const statusEl = document.getElementById("status");
const undoButton = document.getElementById("undo");

let moves = [];
let human = BLACK;
let thinking = false;
let requestId = 0;
let hover = null;

const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });

function el(name, attrs, parent) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

const at = k => MARGIN + k * CELL;

function drawGrid() {
  el("rect", { class: "bg", x: 0, y: 0, width: 640, height: 640 }, svg);
  const grid = el("g", { class: "grid" }, svg);
  for (let k = 0; k < SIZE; k++) {
    el("line", { x1: at(0), y1: at(k), x2: at(SIZE - 1), y2: at(k) }, grid);
    el("line", { x1: at(k), y1: at(0), x2: at(k), y2: at(SIZE - 1) }, grid);
  }
  for (const [i, j] of STAR_POINTS) el("circle", { class: "star", cx: at(j), cy: at(i), r: 3.5 }, svg);
  for (let k = 0; k < SIZE; k++) {
    const col = el("text", { class: "label", x: at(k), y: at(SIZE - 1) + 28, "text-anchor": "middle" }, svg);
    col.textContent = "abcdefghijklmno"[k];
    const row = el("text", { class: "label", x: at(0) - 24, y: at(k) + 4, "text-anchor": "middle" }, svg);
    row.textContent = SIZE - k;
  }
}

const layer = el("g", {});

function board() {
  const b = new Board();
  for (const m of moves) b.play(m);
  return b;
}

function result(b) {
  if (b.moves.length && b.lastMoveWon()) return b.cells[b.moves[b.moves.length - 1]];
  if (b.isFull()) return 0;
  return null;
}

function render() {
  const b = board();
  const winner = result(b);
  layer.replaceChildren();
  b.moves.forEach(idx => {
    const i = Math.floor(idx / SIZE), j = idx % SIZE;
    el("circle", { class: b.cells[idx] === BLACK ? "black" : "white", cx: at(j), cy: at(i), r: 17.5 }, layer);
  });
  if (winner) {
    const line = b.winningLine();
    const [first, last] = [line[0], line[line.length - 1]];
    el("line", {
      class: "win",
      x1: at(first % SIZE), y1: at(Math.floor(first / SIZE)),
      x2: at(last % SIZE), y2: at(Math.floor(last / SIZE)),
    }, layer);
  } else if (b.moves.length) {
    const idx = b.moves[b.moves.length - 1];
    el("circle", { class: "last", cx: at(idx % SIZE), cy: at(Math.floor(idx / SIZE)), r: 4 }, layer);
  }
  if (hover !== null && canPlay(b) && !b.cells[hover]) {
    el("circle", {
      class: `ghost ${human === BLACK ? "black" : "white"}`,
      cx: at(hover % SIZE), cy: at(Math.floor(hover / SIZE)), r: 17.5,
    }, layer);
  }

  if (winner === human) statusEl.textContent = "You win.";
  else if (winner) statusEl.textContent = "mokubot wins.";
  else if (winner === 0) statusEl.textContent = "Draw.";
  else if (thinking) statusEl.textContent = "Thinking…";
  else statusEl.textContent = moves.length ? "Your move." : `You play ${human === BLACK ? "black" : "white"}. Your move.`;

  svg.classList.toggle("waiting", !canPlay(b));
  undoButton.disabled = thinking || !moves.some((_, k) => (k % 2 === 0 ? BLACK : WHITE) === human);
}

function canPlay(b) {
  return !thinking && result(b) === null && b.side === human;
}

function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ moves, human }));
  } catch { /* storage unavailable; the game just won't survive a reload */ }
}

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved && Array.isArray(saved.moves) && (saved.human === BLACK || saved.human === WHITE)) {
      const b = new Board();
      for (const m of saved.moves) {
        if (!Number.isInteger(m) || m < 0 || m >= SIZE * SIZE || b.cells[m] || result(b) !== null) return;
        b.play(m);
      }
      moves = saved.moves;
      human = saved.human;
    }
  } catch { /* ignore unreadable state */ }
}

function engineTurn() {
  const b = board();
  if (result(b) !== null || b.side === human) return;
  thinking = true;
  render();
  const id = ++requestId;
  const started = performance.now();
  worker.onmessage = ({ data }) => {
    if (data.id !== requestId) return;
    const wait = Math.max(0, MIN_REPLY_MS - (performance.now() - started));
    setTimeout(() => {
      if (id !== requestId) return;
      thinking = false;
      moves = [...moves, data.move];
      save();
      render();
    }, wait);
  };
  worker.postMessage({ id, moves, time: THINK_SECONDS });
}

function cellFromEvent(event) {
  const rect = svg.getBoundingClientRect();
  const scale = 640 / rect.width;
  const x = (event.clientX - rect.left) * scale, y = (event.clientY - rect.top) * scale;
  const j = Math.round((x - MARGIN) / CELL), i = Math.round((y - MARGIN) / CELL);
  if (i < 0 || i >= SIZE || j < 0 || j >= SIZE) return null;
  if (Math.hypot(x - at(j), y - at(i)) > CELL * 0.55) return null;
  return i * SIZE + j;
}

svg.addEventListener("pointermove", event => {
  if (event.pointerType !== "mouse") return;
  const cell = cellFromEvent(event);
  if (cell !== hover) {
    hover = cell;
    render();
  }
});

svg.addEventListener("pointerleave", () => {
  hover = null;
  render();
});

svg.addEventListener("click", event => {
  const cell = cellFromEvent(event);
  const b = board();
  if (cell === null || !canPlay(b) || b.cells[cell]) return;
  moves = [...moves, cell];
  save();
  render();
  engineTurn();
});

function newGame(color) {
  requestId++;
  thinking = false;
  moves = [];
  human = color;
  worker.postMessage({ type: "reset" });
  save();
  render();
  engineTurn();
}

document.getElementById("new-black").addEventListener("click", () => newGame(BLACK));
document.getElementById("new-white").addEventListener("click", () => newGame(WHITE));

undoButton.addEventListener("click", () => {
  if (thinking) return;
  // take back the engine's reply (if any) and the player's last move
  const next = [...moves];
  do next.pop(); while (next.length && (next.length % 2 === 0 ? BLACK : WHITE) !== human);
  moves = next;
  save();
  render();
  engineTurn();
});

drawGrid();
svg.appendChild(layer);
load();
render();
engineTurn();
