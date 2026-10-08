from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from starlette.concurrency import run_in_threadpool

from PIL import UnidentifiedImageError

from ..config import settings
from ..auth import (
    hash_password, verify_password,
    create_access_token, CURRENT_USER
)
from ..db import get_db

from .. import models

from ..schema import UserCreate, UserResponse, UserUpdate, PostResponse, Token
from ..image_utils import delete_profile_image, process_profile_image


router = APIRouter()


@router.get(
    "",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
)
async def get_users(db: AsyncSession = Depends(get_db)):
    users = await db.execute(
        select(models.Users)
    )
    results = users.scalars().all()
    return results


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    username_check = await db.execute(
        select(models.Users).where(func.lower(models.Users.username) == user.username.lower())
    )
    username_found = username_check.scalars().first()
    if username_found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    email_check = await db.execute(
        select(models.Users).where(models.Users.email == user.email)
    )
    email_found = email_check.scalars().first()
    if email_found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )

    new_user = models.Users(
        username=user.username,
        email=user.email,
        name=user.name,
        password_hash=hash_password(user.password)
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(models.Users).where(func.lower(models.Users.username) == form_data.username.lower())
    )

    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_exp = timedelta(minutes=settings.access_token_expire_minutes)

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_exp
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user(current_user: CURRENT_USER):
    return current_user


@router.get(
    "",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
)
async def get_users(db: AsyncSession = Depends(get_db)):
    users = await db.execute(
        select(models.Users)
    )
    results = users.scalars().all()
    return results


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    username_check = await db.execute(
        select(models.Users).where(models.Users.username == user.username)
    )
    username_found = username_check.scalars().first()
    if username_found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    email_check = await db.execute(
        select(models.Users).where(models.Users.email == user.email)
    )
    email_found = email_check.scalars().first()
    if email_found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )

    new_user = models.Users(
        username=user.username,
        email=user.email,
        name=user.name,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    query = await db.execute(
        select(models.Users).where(models.Users.id == user_id)
    )

    user = query.scalars().first()
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found",
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: CURRENT_USER,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to perform this action",
        )

    if user_data.username is not None and user_data.username != current_user.username:
        username_check = await db.execute(
            select(models.Users).where(models.Users.username == user_data.username)
        )
        username_found = username_check.scalars().first()
        if username_found:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

    if user_data.email is not None and user_data.email != current_user.email:
        email_check = await db.execute(
            select(models.Users).where(models.Users.email == user_data.email)
        )
        email_found = email_check.scalars().first()
        if email_found:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

    update_data = user_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(current_user, key, value)


    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get(
    "/{user_id}/posts",
    response_model=list[PostResponse],
    status_code=status.HTTP_200_OK,
)
async def get_user_posts(
    user_id: int,
    current_user: CURRENT_USER,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to perform this action",
        )

    query = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
    )

    results = query.scalars().all()
    return results


@router.delete(
    '/{user_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: int,
    current_user: CURRENT_USER,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to perform this action",
        )

    query = await db.execute(
        select(models.Users).where(models.Users.id == user_id)
    )
    user = query.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)
    await db.commit()


@router.patch("/{user_id}/picture", response_model=UserResponse)
async def upload_profile_picture(
    user_id: int,
    file: UploadFile,
    current_user: CURRENT_USER,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's picture",
        )

    content = await file.read()

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_upload_size_bytes // (1024 * 1024)}MB",
        )

    try:
        new_filename = await run_in_threadpool(process_profile_image, content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP).",
        ) from err

    old_filename = current_user.image_file

    current_user.image_file = new_filename
    await db.commit()
    await db.refresh(current_user)

    if old_filename:
        delete_profile_image(old_filename)

    return current_user


@router.delete("/{user_id}/picture", response_model=UserResponse)
async def delete_user_picture(
    user_id: int,
    current_user: CURRENT_USER,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user's picture",
        )

    old_filename = current_user.image_file

    if old_filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete",
        )

    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)

    delete_profile_image(old_filename)

    return current_user

