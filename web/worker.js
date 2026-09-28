// runs the engine off the main thread; one engine per game so the
// transposition table carries over between moves
import { Board, Engine } from "./engine.js";

let engine = new Engine();

self.onmessage = ({ data }) => {
  if (data.type === "reset") {
    engine = new Engine();
    return;
  }
  const board = new Board();
  for (const m of data.moves) board.play(m);
  const move = engine.bestMove(board, data.time);
  self.postMessage({ id: data.id, move, info: engine.info });
};
