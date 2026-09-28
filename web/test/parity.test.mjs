// the javascript engine must give exactly the python engine's answers on the
// positions in fixtures.json (regenerate with: python tests/export_fixtures.py)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Board, Engine, evaluate } from "../engine.js";

const cases = JSON.parse(readFileSync(new URL("./fixtures.json", import.meta.url)));

function setup(c) {
  const b = new Board();
  for (const m of c.moves) b.play(m);
  const e = new Engine();
  e.board = b;
  e.nodes = 0;
  e.deadline = Infinity;
  e.rootLen = b.moves.length;
  return [b, e];
}

cases.forEach((c, k) => {
  test(`position ${k} (${c.moves.length} stones)`, () => {
    const [b, e] = setup(c);
    assert.deepEqual([[...b.counts[1]], [...b.counts[2]]], c.counts);
    assert.equal(evaluate(b), c.eval);
    assert.deepEqual([b.winCells(1), b.winCells(2)], c.win_cells);
    assert.deepEqual([b.fourCells(1), b.fourCells(2)], c.four_cells);
    assert.deepEqual(e.orderMoves(null, true), c.order_root);
    assert.deepEqual(e.orderMoves(null, false), c.order);
    assert.equal(e.vcfSearch(10), c.vcf);
    const [, v] = setup(c);
    v.vctLimit = 20000;
    let vct;
    try {
      vct = v.vctAttack(4);
    } catch (err) {
      if (!err.vctLimit) throw err;
      vct = "limit";
    }
    assert.equal(vct, c.vct);
    const searcher = new Engine();
    assert.equal(searcher.iterativeDeepening(b, Infinity, c.depth), c.best);
    assert.deepEqual(searcher.info, c.info);
  });
});
