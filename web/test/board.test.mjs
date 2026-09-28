import { test } from "node:test";
import assert from "node:assert/strict";
import { Board, Engine, SIZE } from "../engine.js";

const at = (i, j) => i * SIZE + j;

function play(moves) {
  const b = new Board();
  for (const m of moves) b.play(m);
  return b;
}

test("winning line of a diagonal five", () => {
  const black = [0, 1, 2, 3, 4].map(k => at(k, k));
  const white = [0, 1, 2, 3].map(k => at(14, 2 * k));
  const moves = [];
  black.forEach((m, k) => { moves.push(m); if (white[k] !== undefined) moves.push(white[k]); });
  const b = play(moves);
  assert.ok(b.lastMoveWon());
  assert.deepEqual(b.winningLine(), black);
});

test("no winning line mid game", () => {
  const b = play([at(7, 7), at(7, 8)]);
  assert.ok(!b.lastMoveWon());
  assert.equal(b.winningLine(), null);
});

test("engine answers an open four threat and restores the board", () => {
  const b = play([at(7, 4), at(0, 0), at(7, 5), at(0, 14), at(7, 6), at(14, 0)]);
  const before = [...b.cells];
  const move = new Engine().bestMove(b, 1);
  assert.ok([at(7, 3), at(7, 7)].includes(move));
  assert.deepEqual([...b.cells], before);
});
