from fastapi import Header, HTTPException, status

from app.core.config import settings


async def verify_toolbox_api_key(x_toolbox_key: str = Header(default="", alias="X-Toolbox-Key")):
    expected = settings.TOOLBOX_API_KEY
    if not expected:
        return
    if x_toolbox_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid toolbox API key",
        )
