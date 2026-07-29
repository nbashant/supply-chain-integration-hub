from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from supply_chain_hub.settings.config import get_settings


def require_partner_token(
    token: Annotated[str | None, Header(alias="X-Partner-Token")] = None,
) -> None:
    expected = get_settings().partner_api_token
    if token is None or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid partner token is required.",
            headers={"WWW-Authenticate": "APIKey"},
        )
