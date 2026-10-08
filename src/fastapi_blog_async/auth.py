from typing import Annotated

import jwt
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .db import get_db
from .config import settings
from . import models

password_hash = PasswordHash.recommended()

oauth_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key.get_secret_value(), algorithm=settings.algorithm)

    return encoded_jwt


def verify_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )

    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    return payload.get("sub")


async def get_current_user(
    token: Annotated[str, Depends(oauth_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> models.Users:

    user_id_str = verify_access_token(token)

    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        user_id_int = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = await db.execute(
        select(models.Users).where(models.Users.id == user_id_int)
    )

    user = query.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CURRENT_USER = Annotated[models.Users, Depends(get_current_user)]






