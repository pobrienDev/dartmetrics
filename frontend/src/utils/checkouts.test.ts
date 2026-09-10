import { describe, expect, it } from 'vitest'

import { checkoutFor, isOneDartFinish } from './checkouts'

describe('checkoutFor', () => {
  it('knows the classic big finishes', () => {
    expect(checkoutFor(170, 3)).toEqual(['T20', 'T20', 'Bull'])
    expect(checkoutFor(141, 3)).toEqual(['T20', 'T19', 'D12'])
    expect(checkoutFor(100, 3)).toEqual(['T20', 'D20'])
  })

  it('finishes doubles and the bull with one dart', () => {
    expect(checkoutFor(40, 1)).toEqual(['D20'])
    expect(checkoutFor(50, 1)).toEqual(['Bull'])
    expect(checkoutFor(2, 1)).toEqual(['D1'])
    expect(isOneDartFinish(32)).toBe(true)
    expect(isOneDartFinish(33)).toBe(false)
    expect(isOneDartFinish(25)).toBe(false)
  })

  it('returns null for bogey numbers and scores out of range', () => {
    for (const bogey of [169, 168, 166, 165, 163, 162, 159]) {
      expect(checkoutFor(bogey, 3)).toBeNull()
    }
    expect(checkoutFor(171, 3)).toBeNull()
    expect(checkoutFor(1, 3)).toBeNull()
  })

  it('respects the darts left in the visit', () => {
    expect(checkoutFor(100, 1)).toBeNull()
    expect(checkoutFor(100, 2)).toEqual(['T20', 'D20'])
    expect(checkoutFor(141, 2)).toBeNull() // needs three darts
    expect(checkoutFor(0, 3)).toBeNull()
  })

  it('computes a two-dart route when the table route is too long', () => {
    // 120 is taught as T20 20 D20; no two-dart finish exists for it.
    expect(checkoutFor(120, 2)).toBeNull()
    // 110 with two darts: T20 then Bull.
    expect(checkoutFor(110, 2)).toEqual(['T20', 'Bull'])
    // 61 with two darts is in the table already (T15 D8).
    expect(checkoutFor(61, 2)).toEqual(['T15', 'D8'])
  })
})
