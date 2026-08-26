import { describe, expect, it } from 'vitest'

import { boardClosed, marksAfterDarts, markSymbol } from './cricket'

const open = { '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '20': 0, '25': 0 }

describe('marksAfterDarts', () => {
  it('adds marks per multiplier and caps at three', () => {
    const marks = marksAfterDarts(open, [
      { segment: 20, multiplier: 'triple' },
      { segment: 20, multiplier: 'triple' }, // already closed: inert
      { segment: 19, multiplier: 'double' },
    ])
    expect(marks['20']).toBe(3)
    expect(marks['19']).toBe(2)
  })

  it('ignores non-targets and misses', () => {
    const marks = marksAfterDarts(open, [
      { segment: 14, multiplier: 'triple' },
      { segment: null, multiplier: 'miss' },
    ])
    expect(marks).toEqual(open)
  })

  it('does not mutate the input', () => {
    marksAfterDarts(open, [{ segment: 20, multiplier: 'single' }])
    expect(open['20']).toBe(0)
  })
})

describe('boardClosed', () => {
  it('is true only when every target has three marks', () => {
    const closed = Object.fromEntries(Object.keys(open).map((k) => [k, 3]))
    expect(boardClosed(closed)).toBe(true)
    expect(boardClosed({ ...closed, '25': 2 })).toBe(false)
  })
})

describe('markSymbol', () => {
  it('renders classic notation', () => {
    expect([0, 1, 2, 3].map(markSymbol)).toEqual(['·', '╱', '✕', '◎'])
  })
})
