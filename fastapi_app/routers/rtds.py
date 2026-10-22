from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models import RTDS
from fastapi_app.dependencies import get_session
from fastapi_app.schemas import RTDSOut

router = APIRouter(prefix="/RTDS", tags=["rtds-endpoints"])


@router.get("/get/current/{id}", response_model=RTDSOut)
async def get_current(id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(RTDS).where(RTDS.symbol == id).order_by(RTDS.source_ts.desc()).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "No data for this instrument")
    return row


@router.get("/get/historical/{id}", response_model=list[RTDSOut])
async def get_historical(id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(RTDS).where(RTDS.symbol == id).order_by(RTDS.source_ts)
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(404, "No data for this instrument")
    return rows