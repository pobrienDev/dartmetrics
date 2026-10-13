"""Shared helpers for the API integration tests."""

PASSWORD = "correct horse battery staple"

# Darts as the API takes them.
T20 = {"segment": 20, "multiplier": "triple"}
T19 = {"segment": 19, "multiplier": "triple"}
D12 = {"segment": 12, "multiplier": "double"}
S20 = {"segment": 20, "multiplier": "single"}


def signup(client, email: str, display_name: str) -> dict:
    """Register and log in; returns the auth headers for that account."""
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": display_name},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
