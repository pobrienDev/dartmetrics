"""Domain error types (dev plan section 17.1).

Each error carries a stable machine-readable code. The API layer will
map these to HTTP responses later; services raise them without knowing
anything about HTTP.
"""


class DomainError(Exception):
    code = "DOMAIN_ERROR"
    http_status = 400


class MatchNotActive(DomainError):
    code = "MATCH_NOT_ACTIVE"
    http_status = 409


class LegNotActive(DomainError):
    code = "LEG_NOT_ACTIVE"
    http_status = 409


class PlayerNotInMatch(DomainError):
    code = "PLAYER_NOT_IN_MATCH"


class NotPlayersTurn(DomainError):
    code = "NOT_PLAYER_TURN"
    http_status = 409


class InvalidTurn(DomainError):
    code = "INVALID_TURN"


class EmailAlreadyRegistered(DomainError):
    code = "EMAIL_ALREADY_REGISTERED"
    http_status = 409


class InvalidCredentials(DomainError):
    code = "INVALID_CREDENTIALS"
    http_status = 401


class NotAuthenticated(DomainError):
    code = "NOT_AUTHENTICATED"
    http_status = 401


class Forbidden(DomainError):
    code = "FORBIDDEN"
    http_status = 403


class PlayerNotFound(DomainError):
    code = "PLAYER_NOT_FOUND"
    http_status = 404


class PlayerProfileExists(DomainError):
    code = "PLAYER_PROFILE_EXISTS"
    http_status = 409


class MissingPlayerProfile(DomainError):
    code = "PLAYER_PROFILE_REQUIRED"
    http_status = 409


class MatchNotFound(DomainError):
    code = "MATCH_NOT_FOUND"
    http_status = 404


class InvalidMatchSetup(DomainError):
    code = "INVALID_MATCH_SETUP"


class MatchAccessDenied(DomainError):
    code = "MATCH_ACCESS_DENIED"
    http_status = 403


class UndoNotAvailable(DomainError):
    code = "UNDO_NOT_AVAILABLE"
    http_status = 409


class InvalidRequest(DomainError):
    code = "INVALID_REQUEST"
