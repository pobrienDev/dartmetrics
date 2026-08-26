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
