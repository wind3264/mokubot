// engine vs engine match for comparing engine settings:
//   node tools/match.mjs '{"beam":12}' '{"beam":20}' [pairs] [depth]
// each random opening is played twice with colors swapped; games run in
// parallel worker threads at a fixed depth so results are reproducible
import { Worker, isMainThread, parentPort, workerData } from "node:worker_threads";
import { availableParallelism } from "node:os";
import { Board, Engine, SIZE } from "../engine.js";

function mulberry32(seed) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function opening(seed, n = 3, radius = 3) {
  const rand = mulberry32(seed), c = Math.floor(SIZE / 2), out = [];
  while (out.length < n) {
    const idx = (c - radius + Math.floor(rand() * (2 * radius + 1))) * SIZE + c - radius + Math.floor(rand() * (2 * radius + 1));
    if (!out.includes(idx)) out.push(idx);
  }
  return out;
}

function playGame(blackOpts, whiteOpts, moves, depth, time) {
  const b = new Board();
  for (const m of moves) b.play(m);
  const engines = [new Engine(blackOpts), new Engine(whiteOpts)];
  while (!b.lastMoveWon() && b.moves.length < SIZE * SIZE) {
    b.play(engines[b.moves.length % 2].bestMove(b, time, depth));
  }
  return b.lastMoveWon() ? (b.moves.length % 2 === 1 ? 1 : 0) : 0.5; // 1 = black won
}

if (isMainThread) {
  const a = JSON.parse(process.argv[2] || "{}"), bOpts = JSON.parse(process.argv[3] || "{}");
  const pairs = Number(process.argv[4] || 50), depth = Number(process.argv[5] || 4);
  const time = Number(process.argv[6] || 1e9);
  const jobs = [];
  for (let k = 0; k < pairs; k++) {
    jobs.push({ black: a, white: bOpts, seed: k, aBlack: true });
    jobs.push({ black: bOpts, white: a, seed: k, aBlack: false });
  }
  let score = 0, done = 0, next = 0;
  const threads = Math.min(Number(process.env.THREADS) || availableParallelism() - 1, jobs.length);
  await new Promise(resolve => {
    for (let t = 0; t < threads; t++) {
      const w = new Worker(new URL(import.meta.url), { workerData: { depth, time } });
      const feed = () => (next < jobs.length ? w.postMessage(jobs[next++]) : w.terminate());
      w.on("message", ({ job, result }) => {
        score += job.aBlack ? result : 1 - result;
        if (++done === jobs.length) resolve();
        feed();
      });
      feed();
    }
  });
  const n = jobs.length, p = score / n;
  const elo = p <= 0 || p >= 1 ? NaN : -400 * Math.log10(1 / p - 1);
  const se = Math.sqrt(p * (1 - p) / n);
  console.log(`A scores ${score}/${n} = ${(100 * p).toFixed(1)}% +- ${(196 * se).toFixed(1)}  (elo ${elo.toFixed(0)})`);
} else {
  parentPort.on("message", job => {
    const result = playGame(job.black, job.white, opening(job.seed), workerData.depth, workerData.time);
    parentPort.postMessage({ job, result });
  });
}
