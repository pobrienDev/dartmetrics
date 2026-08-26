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
