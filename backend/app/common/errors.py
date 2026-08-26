"""Domain error types (dev plan section 17.1).

Each error carries a stable machine-readable code. The API layer will
map these to HTTP responses later; services raise them without knowing
anything about HTTP.
"""


class DomainError(Exception):
    code = "DOMAIN_ERROR"


class MatchNotActive(DomainError):
    code = "MATCH_NOT_ACTIVE"


class LegNotActive(DomainError):
    code = "LEG_NOT_ACTIVE"


class PlayerNotInMatch(DomainError):
    code = "PLAYER_NOT_IN_MATCH"


class NotPlayersTurn(DomainError):
    code = "NOT_PLAYER_TURN"


class InvalidTurn(DomainError):
    code = "INVALID_TURN"
