from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_internal_request
from app.schemas.auth import (
    AuthenticatedUserResponse,
    ErrorResponse,
    ForgotPasswordRequest,
    InternalUserCreateRequest,
    InternalUserResponse,
    InternalUserUpdateRequest,
    IntrospectionRequest,
    IntrospectionResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    OTPVerifyRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    SessionRevocationRequest,
    SessionRevocationResponse,
)
from app.utils.jwt import get_current_user
from app.services import auth_flow_service, auth_service


router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return auth_flow_service.register(payload, db)


@router.post(
    "/verify-otp",
    response_model=LoginResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def verify_otp(
    payload: OTPVerifyRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    return auth_flow_service.verify_otp(payload, response, db)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    return auth_flow_service.login(payload, response, db)


@router.get(
    "/me",
    response_model=AuthenticatedUserResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def me(current_user=Depends(get_current_user)):
    return auth_flow_service.get_authenticated_user_response(current_user)


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    return auth_flow_service.logout(response)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return auth_flow_service.forgot_password(payload, db)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    return auth_flow_service.reset_password(payload, db)


@router.get("/oauth/google")
def google_login(request: Request):
    return auth_flow_service.begin_oauth_login(request, "google")


@router.get("/oauth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    return await auth_flow_service.complete_oauth_callback(request, "google", db)


@router.get("/oauth/microsoft")
def microsoft_login(request: Request):
    return auth_flow_service.begin_oauth_login(request, "microsoft")


@router.get("/oauth/microsoft/callback")
async def microsoft_callback(request: Request, db: Session = Depends(get_db)):
    return await auth_flow_service.complete_oauth_callback(request, "microsoft", db)


@router.post("/internal/users", response_model=InternalUserResponse, status_code=status.HTTP_201_CREATED)
def create_internal_user(
    payload: InternalUserCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    user = auth_service.create_internal_user(payload, db)
    return InternalUserResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        session_version=user.session_version,
    )


@router.patch("/internal/users/{user_id}", response_model=InternalUserResponse)
def update_internal_user(
    user_id: str,
    payload: InternalUserUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    user = auth_service.update_internal_user(user_id, payload, db)
    return InternalUserResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        session_version=user.session_version,
    )


@router.post(
    "/internal/users/{user_id}/revoke-sessions",
    response_model=SessionRevocationResponse,
)
def revoke_internal_user_sessions(
    user_id: str,
    payload: SessionRevocationRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    user = auth_service.revoke_sessions(user_id, db, is_active=payload.is_active)
    return SessionRevocationResponse(
        user_id=user.id,
        is_active=user.is_active,
        session_version=user.session_version,
    )


@router.post("/internal/introspect", response_model=IntrospectionResponse)
def introspect(
    payload: IntrospectionRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    return auth_service.introspect_access_token(payload.token, db)


@router.delete("/internal/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_internal_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_request),
):
    auth_service.delete_user_by_id(user_id, db)
