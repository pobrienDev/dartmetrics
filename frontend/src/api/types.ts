// Mirrors the backend's Pydantic response schemas.

export interface UserResponse {
  id: string
  email: string
  display_name: string
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export type BotDifficulty = 'noob' | 'easy' | 'medium' | 'hard' | 'pro'

export interface PlayerResponse {
  id: string
  user_id: string | null
  display_name: string
  nickname: string | null
  is_active: boolean
  bot_difficulty: BotDifficulty | null // set for computer opponents
  created_at: string
}

// The backend's error envelope: {"error": {"code": ..., "message": ...}}
export interface ApiErrorBody {
  error: { code: string; message: string }
}

// --- Matches ---------------------------------------------------------------

export type MatchStatus = 'scheduled' | 'in_progress' | 'completed' | 'cancelled'
export type GameType = 'x01' | 'cricket' | 'halve_it'

export interface PlayerState {
  player_id: string
  display_name: string
  legs_won: number
  remaining_score: number | null // x01 only
  marks: Record<string, number> | null // cricket only: target -> 0..3
  score: number | null // halve_it only
  round: number | null // halve_it only (1-based)
  round_target: string | null // halve_it only, e.g. "outer_black"
  bot_difficulty: BotDifficulty | null // set when this player is a bot
  is_active_turn: boolean
}

export interface LegState {
  id: string
  leg_number: number
  status: string
  starting_player_id: string
  winner_player_id: string | null
}

export interface MatchState {
  id: string
  game_type: GameType
  status: MatchStatus
  best_of_legs: number
  legs_required_to_win: number
  winner_player_id: string | null
  players: PlayerState[]
  current_leg: LegState | null
}

export type DartMultiplier = 'miss' | 'single' | 'double' | 'triple'

export interface DartRequest {
  segment: number | null
  multiplier: DartMultiplier
  band?: 'inner' | 'outer' | null // halve_it band rounds, singles only
}

export interface TurnSummary {
  id: string
  player_id: string
  turn_number: number
  turn_start_score: number
  turn_end_score: number
  points_scored: number
  is_bust: boolean
  is_checkout: boolean
}

export interface VisitResponse {
  turn: TurnSummary
  state: MatchState
}

// A bot's visit also reports the darts it threw.
export interface BotVisitResponse extends VisitResponse {
  darts: DartRequest[]
}

export interface MatchListItem {
  id: string
  game_type: GameType
  status: MatchStatus
  best_of_legs: number
  winner_player_id: string | null
  created_at: string
  players: { player_id: string; display_name: string; legs_won: number }[]
}

export interface MatchListResponse {
  items: MatchListItem[]
  total: number
  limit: number
  offset: number
}

export interface PlayerStats {
  player_id: string
  display_name: string
  matches_played: number
  matches_won: number
  win_percentage: number | null
  legs_played: number
  legs_won: number
  leg_win_percentage: number | null
  best_leg_darts: number | null
  total_darts: number
  three_dart_average: number | null
  first_nine_average: number | null
  highest_visit: number | null
  count_100_plus: number
  count_140_plus: number
  count_180: number
  checkout_attempts: number
  checkout_successes: number
  checkout_percentage: number | null
}
