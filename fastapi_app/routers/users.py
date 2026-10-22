import base64
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models import DjangoUser, DjangoUserProfile
from fastapi_app.dependencies import get_session
from fastapi_app.schemas import UserPhotoOut, UserProfileOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/get/profile/{userid}", response_model=UserProfileOut)
async def get_profile(userid: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DjangoUser, DjangoUserProfile)
        .join(DjangoUserProfile, DjangoUserProfile.user_id == DjangoUser.id)
        .where(DjangoUser.id == userid)
    )
    row = result.first()
    if row is None:
        raise HTTPException(404, "User not found")
    user, profile = row
    return UserProfileOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        bio=profile.bio,
    )


@router.get("/get/photo/{userid}", response_model=UserPhotoOut)
async def get_photo(userid: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DjangoUserProfile).where(DjangoUserProfile.user_id == userid)
    )
    profile = result.scalar_one_or_none()
    if profile is None or not profile.photo:
        raise HTTPException(404, "Photo not found")

    photo_path = os.path.join("media", profile.photo)  
    if not os.path.isfile(photo_path):
        raise HTTPException(404, "Photo file missing on disk")

    with open(photo_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return UserPhotoOut(id=userid, photo_base64=encoded)