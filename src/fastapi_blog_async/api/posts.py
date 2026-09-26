from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db

from .. import models

from ..schema import PostCreate, PostResponse, PostUpdate


router = APIRouter()


@router.get("", response_model=list[PostResponse])
async def get_posts(db: Annotated[AsyncSession, Depends(get_db)]):
    posts = await db.execute(
        select(models.Post).options(selectinload(models.Post.author))
    )
    results = posts.scalars().all()
    return results


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_post(post: PostCreate, db: Annotated[AsyncSession, Depends(get_db)]):

    user_check = await db.execute(
        select(models.Users).where(models.Users.id == post.user_id)
    )
    user_found = user_check.scalars().first()
    if not user_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found',
        )

    new_post = models.Post(
        title=post.title,
        content=post.content,
        user_id=post.user_id,
    )

    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])
    return new_post


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    query = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )

    result = query.scalars().first()

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    return result


@router.put(
    "/{post_id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
)
async def update_post_full(post_id: int, post_data: PostCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    query = await db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )
    post = query.scalars().first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.user_id != post.user_id:
        user_check = await db.execute(
            select(models.Users).where(models.Users.id == post.user_id)
        )
        user_found = user_check.scalars().first()
        if not user_found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    post.title = post_data.title
    post.content = post_data.content
    post.user_id = post_data.user_id

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


@router.patch(
    "/{post_id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
)
async def update_post_partial(post_id: int, post_data: PostUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    query = await db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )
    post = query.scalars().first()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    updated_data = post_data.model_dump(exclude_unset=True)

    for key, value in updated_data.items():
        setattr(post, key, value)

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    query = await db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )
    post = query.scalars().first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    await db.delete(post)
    await db.commit()


