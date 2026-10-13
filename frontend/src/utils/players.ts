import type { PlayerState } from '../api/types'

/** Bot players are called "Medium Bot" etc.; the scoring screen's badge already says bot. */
export function shortName(player: PlayerState): string {
  return player.bot_difficulty ? player.display_name.replace(/\s+bot$/i, '') : player.display_name
}
