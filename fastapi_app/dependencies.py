from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from common.config import settings
from common.db import SessionFactory

_api_key_header = APIKeyHeader(name=settings.FASTAPI_API_KEY_HEADER, auto_error=False)


async def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if key is None or key != settings.FASTAPI_API_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")



# yield lets it close/rollback the session after the request finishes - generators - 
async def get_session():
    async with SessionFactory() as session:
        yield session