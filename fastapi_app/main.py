from fastapi import FastAPI, Depends

from fastapi_app.dependencies import require_api_key
from fastapi_app.routers import rtds, users

app = FastAPI(title="fastapi API")

app.include_router(users.router, prefix="/api", dependencies=[Depends(require_api_key)])
app.include_router(rtds.router, prefix="/api", dependencies=[Depends(require_api_key)])