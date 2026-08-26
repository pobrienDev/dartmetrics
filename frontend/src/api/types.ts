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

export interface PlayerResponse {
  id: string
  user_id: string | null
  display_name: string
  nickname: string | null
  is_active: boolean
  created_at: string
}

// The backend's error envelope: {"error": {"code": ..., "message": ...}}
export interface ApiErrorBody {
  error: { code: string; message: string }
}

// --- Matches ---------------------------------------------------------------

export type MatchStatus = 'scheduled' | 'in_progress' | 'completed' | 'cancelled'

export interface PlayerState {
  player_id: string
  display_name: string
  legs_won: number
  remaining_score: number | null
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

export interface MatchListItem {
  id: string
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
