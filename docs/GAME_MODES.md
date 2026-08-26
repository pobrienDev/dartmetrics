# Game mode specifications

Authoritative rules for the additional game modes, in the spirit of the
Phase 0 specification: no implementation may invent rules not written
here. 501 rules live in the README.

## Cricket — race to close (no points)

- Two players, alternating visits of up to three darts.
- Targets: 15, 16, 17, 18, 19, 20, Bull. Each target needs **3 marks**
  to close.
- Marks per dart: single = 1, double = 2, triple = 3. Outer bull = 1
  mark, inner bull = 2 marks. Darts at 1-14 or at already-closed
  targets score nothing.
- Marks beyond 3 on a single dart are discarded (no points variant):
  a triple on a target with 2 marks simply closes it.
- **Win:** the leg ends immediately on the dart that closes the
  player's final open target (mid-visit, like a 501 checkout).
- Matches are best-of-N legs with alternating starters, as in 501.

### Acceptance examples

| Given | When | Expected |
|---|---|---|
| 20 open, 0 marks | T20 | 20 closed |
| 20 open, 2 marks | T20 | 20 closed (overflow discarded) |
| 20 closed | any 20 | no effect |
| dart at 14 or below | any | no effect |
| bull 1 mark | inner bull (50) | bull closed |
| all closed except bull, 2 marks | outer bull (25) | leg won, mid-visit |
| leg won on dart 2 | — | dart 3 never thrown |

## Halve It — house rules

- Two players; both play every round, starter first, then opponent.
  Scores start at 0.
- Each round is exactly **three darts** (no early end).
- A dart "qualifies" if it hits the round's target area. **Qualifying
  darts add their face value** (D16 adds 32, T5 adds 15, etc.).
- **If none of the three darts qualify, the player's total is halved,
  rounding up** (45 → 23).
- After both players complete round 9, the higher total wins.
- **Tie-break:** additional Red Bull rounds are played until one
  player outscores the other in a round.
- Matches default to a single game; best-of-N is allowed and behaves
  like 501 legs.

### Round sequence

| # | Round | Qualifying area |
|---|---|---|
| 1 | Outer black | Large single band, black segments (20 18 13 10 2 3 7 8 14 12) |
| 2 | Outer white | Large single band, white segments (1 4 6 15 17 19 16 11 9 5) |
| 3 | Inner black | Small single band (between triple ring and bull), black segments |
| 4 | Inner white | Small single band, white segments |
| 5 | Doubles | Any double ring |
| 6 | Triples | Any triple ring |
| 7 | 63 | The three darts must total **exactly 63**: success adds 63, anything else halves |
| 8 | Green bull | Outer bull (25) only |
| 9 | Red bull | Inner bull (50) only |

Notes: bull hits do not qualify in rounds 1-4 (they are not numbered
segments); doubles/triples do not qualify in rounds 1-4 either — those
rounds are specifically about the single bands.

### Data-model note

Rounds 1-4 distinguish which single band a dart landed in, which 501
and Cricket never needed. Dart input gains an optional band
(`inner`/`outer`) recorded for single hits; games that don't care
ignore it, and it is nullable in storage.

### Acceptance examples

| Round | Darts | Effect |
|---|---|---|
| Outer black | outer-single 20, outer-single 1, miss | +20 (the 1 is white) |
| Outer black | inner-single 20 ×3 | halved (wrong band) |
| Doubles | D16, single 20, D5 | +42 |
| Triples | no triple hit | halved, round up |
| 63 | T19, 3, 3 (=63) | +63 |
| 63 | 60, 2, 2 (=64) | halved |
| Green bull | inner bull ×3 | halved (red is not green) |
| Red bull | 25, 25, 50 | +50 (only the inner bull qualifies) |
