import { describe, expect, it } from 'vitest'

import { dartLabel, dartScore, visitMustEnd } from './darts'

describe('dartScore', () => {
  it.each([
    [{ segment: 20, multiplier: 'triple' }, 60],
    [{ segment: 20, multiplier: 'double' }, 40],
    [{ segment: 20, multiplier: 'single' }, 20],
    [{ segment: 25, multiplier: 'double' }, 50], // inner bull
    [{ segment: 25, multiplier: 'single' }, 25], // outer bull
    [{ segment: null, multiplier: 'miss' }, 0],
  ] as const)('scores %j as %i', (dart, expected) => {
    expect(dartScore(dart)).toBe(expected)
  })
})

describe('dartLabel', () => {
  it.each([
    [{ segment: 20, multiplier: 'triple' }, 'T20'],
    [{ segment: 12, multiplier: 'double' }, 'D12'],
    [{ segment: 5, multiplier: 'single' }, '5'],
    [{ segment: null, multiplier: 'miss' }, 'Miss'],
  ] as const)('labels %j as %s', (dart, expected) => {
    expect(dartLabel(dart)).toBe(expected)
  })
})

describe('visitMustEnd', () => {
  it('ends after the third dart regardless of score', () => {
    expect(visitMustEnd(3, 301)).toBe(true)
  })
  it('ends when the score reaches exactly zero (possible checkout)', () => {
    expect(visitMustEnd(1, 0)).toBe(true)
  })
  it('ends when the score would be 1 or negative (certain bust)', () => {
    expect(visitMustEnd(2, 1)).toBe(true)
    expect(visitMustEnd(1, -5)).toBe(true)
  })
  it('continues mid-visit on a normal score', () => {
    expect(visitMustEnd(1, 441)).toBe(false)
    expect(visitMustEnd(2, 2)).toBe(false) // 2 is still finishable
  })
})
