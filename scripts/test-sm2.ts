import * as assert from 'assert';
import {
  AUTO_GOOD,
  FORGOT,
  addDays,
  createInitialSm2,
  reviewSm2,
  todayIso,
} from '../src/srs/sm2';

function run(): void {
  const today = '2026-07-29';
  let s = createInitialSm2(today);
  assert.strictEqual(s.dueDate, today);
  assert.strictEqual(s.repetitions, 0);

  s = reviewSm2(s, AUTO_GOOD, today);
  assert.strictEqual(s.repetitions, 1);
  assert.strictEqual(s.interval, 1);
  assert.strictEqual(s.dueDate, addDays(today, 1));

  s = reviewSm2(s, AUTO_GOOD, s.dueDate);
  assert.strictEqual(s.repetitions, 2);
  assert.strictEqual(s.interval, 6);

  s = reviewSm2(s, FORGOT, s.dueDate);
  assert.strictEqual(s.repetitions, 0);
  assert.strictEqual(s.interval, 1);

  assert.ok(todayIso().length === 10);
  console.log('sm2 tests passed');
}

run();
