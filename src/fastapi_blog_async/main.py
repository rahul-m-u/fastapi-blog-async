from typing import Annotated
from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine, get_db

from . import models

from .schema import PostCreate, PostResponse, PostUpdate
from .schema import UserCreate, UserResponse, UserUpdate


Base.metadata.create_all(engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount('/media', StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")


@app.get("/", include_in_schema=False, name="home")
@app.get("/feed", include_in_schema=False, name="feed")
def home(request: Request, db: Annotated[Session, Depends(get_db)]):
    query = db.execute(
        select(models.Post)
    )

    results = query.scalars().all()

    return templates.TemplateResponse(
        request,
        "feed.html",
        {
            "posts": results,
            "title": "Feed",
        }
    )

@app.get("/post/{post_id}", include_in_schema=False)
def post_detail(request: Request, post_id: int, db: Annotated[Session, Depends(get_db)]):
    query = db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )
    result = query.scalars().first()

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    return templates.TemplateResponse(
        request,
        "post.html",
        {
            "post": result,
            "title": result.title[:20],
        }
    )


@app.get(
    "/users/{user_id}/posts",
    include_in_schema=False,
    name="user_posts",
)
def user_post_page(request: Request, user_id: int, db: Annotated[Session, Depends(get_db)]):
    user_check = db.execute(
        select(models.Users).where(models.Users.id == user_id)
    )
    user_found = user_check.scalars().first()
    if not user_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    query = db.execute(
        select(models.Post).where(models.Post.user_id == user_id)
    )
    results = query.scalars().all()

    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {
            "posts": results,
            "user": user_found,
            "title": f"{user_found.name}'s Posts",
        }
    )


@app.get(
    "/api/users",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
)
def get_users(db: Session = Depends(get_db)):
    users = db.execute(
        select(models.Users)
    )
    results = users.scalars().all()
    return results


@app.post(
    "/api/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def create_user(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    username_check = db.execute(
        select(models.Users).where(models.Users.username == user.username)
    )
    username_found = username_check.scalars().first()
    if username_found:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    email_check = db.execute(
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
    db.commit()
    db.refresh(new_user)

    return new_user


@app.get(
    "/api/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    query = db.execute(
        select(models.Users).where(models.Users.id == user_id)
    )

    user = query.scalars().first()
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found",
    )


@app.patch(
    "/api/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    user_check = db.execute(
        select(models.Users).where(models.Users.id == user_id)
    )
    user_found = user_check.scalars().first()
    if not user_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user_data.username is not None and user_data.username != user_found.username:
        username_check = db.execute(
            select(models.Users).where(models.Users.username == user_data.username)
        )
        username_found = username_check.scalars().first()
        if username_found:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

    if user_data.email is not None and user_data.email != user_found.email:
        email_check = db.execute(
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
        setattr(user_found, key, value)


    db.commit()
    db.refresh(user_found)
    return user_found


@app.get(
    "/api/users/{user_id}/posts",
    response_model=list[PostResponse],
    status_code=status.HTTP_200_OK,
)
def get_user_posts(user_id: int, db: Session = Depends(get_db)):

    user_check = db.execute(
        select(models.Users).where(models.Users.id == user_id)
    )

    user_found = user_check.scalars().first()
    if not user_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    query = db.execute(
        select(models.Post).where(models.Post.user_id == user_id)
    )

    results = query.scalars().all()
    return results


@app.delete(
    '/api/users/{user_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user(user_id: int, db: Annotated[Session, Depends(get_db)]):
    query = db.execute(
        select(models.Users).where(models.Users.id == user_id)
    )
    user = query.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    db.delete(user)
    db.commit()


@app.get('/api/posts', response_model=list[PostResponse])
def get_posts(db: Annotated[Session, Depends(get_db)]):
    posts = db.execute(
        select(models.Post)
    )
    results = posts.scalars().all()
    return results


@app.post(
    "/api/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_post(post: PostCreate, db: Annotated[Session, Depends(get_db)]):

    user_check = db.execute(
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
    db.commit()
    db.refresh(new_post)
    return new_post


@app.get('/api/post/{post_id}', response_model=PostResponse)
def get_post(post_id: int, db: Annotated[Session, Depends(get_db)]):

    query = db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )

    result = query.scalars().first()

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    return result


@app.put(
    "/api/posts/{post_id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
)
def update_post_full(post_id: int, post_data: PostCreate, db: Annotated[Session, Depends(get_db)]):
    query = db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )
    post = query.scalars().first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.user_id != post.user_id:
        user_check = db.execute(
            select(models.Users).where(models.Users.id == post.user_id)
        )
        user_found = user_check.scalars().first()
        if not user_found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    post.title = post_data.title
    post.content = post_data.content
    post.user_id = post_data.user_id

    db.commit()
    db.refresh(post)
    return post


@app.patch(
    "/api/posts/{post_id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
)
def update_post_partial(post_id: int, post_data: PostUpdate, db: Annotated[Session, Depends(get_db)]):
    query = db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )
    post = query.scalars().first()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    updated_data = post_data.model_dump(exclude_unset=True)

    for key, value in updated_data.items():
        setattr(post, key, value)

    db.commit()
    db.refresh(post)
    return post


@app.delete(
    "/api/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_post(post_id: int, db: Annotated[Session, Depends(get_db)]):
    query = db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )
    post = query.scalars().first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    db.delete(post)
    db.commit()


@app.exception_handler(StarletteHTTPException)
def general_exception_handler(request: Request, exc: StarletteHTTPException):
    message = exc.detail if exc.detail else "Something went wrong, Please try again."

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": message}
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exc.status_code,
            "title": exc.status_code,
            "message": message,
        },
        status_code=exc.status_code,
    )

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exc.errors()}
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid Request. Please check your request input and try again.",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )

