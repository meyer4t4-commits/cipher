"""
User authentication API endpoints.
Handles registration, login, and profile management.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================================
# Pydantic Models
# ============================================================================


class UserRegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    name: str = Field(..., min_length=1, max_length=100)


class UserLoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User profile response (safe to return to client)."""

    id: int
    email: str | None
    username: str
    name: str | None
    tier: str
    is_active: bool
    voice_minutes_used: float
    tokens_used: int
    conversations_count: int

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Response with JWT token and user data."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserUpdateRequest(BaseModel):
    """Request body for updating user profile."""

    email: EmailStr | None = None
    name: str | None = Field(None, min_length=1, max_length=100)


# ============================================================================
# Dependencies
# ============================================================================


async def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate JWT token from Authorization header.
    Returns the current authenticated user.

    Expects: Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Register a new user.

    - **email**: User's email address (must be unique)
    - **password**: Minimum 8 characters
    - **name**: User's display name

    Returns JWT token and user data on success.
    """
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        logger.warning(f"Registration attempt with duplicate email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create username from email (first part before @)
    username_base = request.email.split("@")[0]
    username = username_base
    counter = 1

    # Ensure username is unique
    while db.query(User).filter(User.username == username).first():
        username = f"{username_base}{counter}"
        counter += 1

    # Create new user
    hashed_pw = hash_password(request.password)
    new_user = User(
        email=request.email,
        username=username,
        hashed_password=hashed_pw,
        name=request.name,
        is_active=True,
        tier="free",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"User registered: {new_user.email} (id={new_user.id})")

    # Create access token
    access_token = create_access_token(data={"sub": str(new_user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(new_user),
    }


@router.post("/login", response_model=AuthResponse)
async def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Authenticate user with email and password.

    Returns JWT token and user data on success.
    """
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        logger.warning(f"Login attempt for inactive user: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    logger.info(f"User logged in: {user.email} (id={user.id})")

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user's profile.

    Requires valid JWT in Authorization header.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_profile(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    Update current user's profile.

    Only email and name can be updated.
    Requires valid JWT in Authorization header.
    """
    # Check if new email is already taken (if provided)
    if request.email and request.email != current_user.email:
        existing = db.query(User).filter(User.email == request.email).first()
        if existing:
            logger.warning(f"Email update attempt with duplicate email: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )
        current_user.email = request.email

    # Update name if provided
    if request.name is not None:
        current_user.name = request.name

    db.commit()
    db.refresh(current_user)

    logger.info(f"User profile updated: {current_user.email} (id={current_user.id})")

    return current_user
