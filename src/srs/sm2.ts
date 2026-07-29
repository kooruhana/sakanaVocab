/** SM-2 spaced repetition with auto-scheduling (default grade = Good). */

import { Sm2State } from '../types';

export type ReviewQuality = 0 | 1 | 2 | 3 | 4 | 5;

/** Auto-schedule quality when the learner advances after reveal. */
export const AUTO_GOOD: ReviewQuality = 4;
/** Quality when the learner marks the word as forgotten. */
export const FORGOT: ReviewQuality = 1;

export function createInitialSm2(today: string): Sm2State {
  return {
    easiness: 2.5,
    repetitions: 0,
    interval: 0,
    dueDate: today,
  };
}

export function todayIso(date = new Date()): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T12:00:00.000Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/**
 * Classic SM-2 update.
 * quality: 0–5 (we use 1 = forgot, 4 = auto-good).
 */
export function reviewSm2(state: Sm2State, quality: ReviewQuality, today = todayIso()): Sm2State {
  let { easiness, repetitions, interval } = state;

  if (quality < 3) {
    repetitions = 0;
    interval = 1;
  } else {
    if (repetitions === 0) {
      interval = 1;
    } else if (repetitions === 1) {
      interval = 6;
    } else {
      interval = Math.max(1, Math.round(interval * easiness));
    }
    repetitions += 1;
  }

  easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
  if (easiness < 1.3) {
    easiness = 1.3;
  }

  return {
    easiness: Math.round(easiness * 100) / 100,
    repetitions,
    interval,
    dueDate: addDays(today, interval),
    lastReviewDate: today,
  };
}

export function isDue(state: Sm2State | undefined, today = todayIso()): boolean {
  if (!state) {
    return true;
  }
  return state.dueDate <= today;
}
