from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import secrets
from urllib.parse import urlencode

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.models import OTPPurpose
from app.schemas.auth import (
    AuthenticatedUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    OTPVerifyRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
)
from app.utils.jwt import (
    clear_access_cookie,
    clear_oauth_state_cookie,
    generate_oauth_state,
    set_access_cookie,
    set_oauth_state_cookie,
)
from app.services import auth_service, otp_service
from app.clients import email_service, oauth_service, users_client
from app.messaging import event_service


@dataclass(frozen=True)
class OAuthProviderDefinition:
    name: str
    default_redirect_uri: str
    authorization_url_builder: Callable[[str, str | None], str]
    code_exchange: Callable[[str, str | None], Awaitable[dict[str, str]]]
    auth_error_message: str
    incomplete_callback_message: str
    invalid_email_message: str


def _oauth_provider_definitions() -> dict[str, OAuthProviderDefinition]:
    return {
        "google": OAuthProviderDefinition(
            name="google",
            default_redirect_uri=settings.GOOGLE_REDIRECT_URI,
            authorization_url_builder=oauth_service.get_google_authorization_url,
            code_exchange=oauth_service.exchange_google_code,
            auth_error_message="Google no completo la autenticacion.",
            incomplete_callback_message="Callback de Google incompleto.",
            invalid_email_message="Google no devolvio un correo valido.",
        ),
        "microsoft": OAuthProviderDefinition(
            name="microsoft",
            default_redirect_uri=settings.MICROSOFT_REDIRECT_URI,
            authorization_url_builder=oauth_service.get_microsoft_authorization_url,
            code_exchange=oauth_service.exchange_microsoft_code,
            auth_error_message="Microsoft no completo la autenticacion.",
            incomplete_callback_message="Callback de Microsoft incompleto.",
            invalid_email_message="Microsoft no devolvio un correo valido.",
        ),
    }


def _get_oauth_provider(provider: str) -> OAuthProviderDefinition:
    try:
        return _oauth_provider_definitions()[provider]
    except KeyError as exc:
        raise ValueError(f"Proveedor OAuth no soportado: {provider}") from exc


def build_oauth_redirect_uri(_request: Request, provider: str) -> str:
    provider_config = _get_oauth_provider(provider)
    # Redirect URIs must be registered with the provider and are therefore
    # configuration, not values inferred from Host/X-Forwarded-* headers.
    return provider_config.default_redirect_uri


def _build_frontend_url(path: str, **params: str) -> str:
    query = urlencode({key: value for key, value in params.items() if value})
    base = settings.FRONTEND_URL.rstrip("/")
    normalized_path = "/" + path.lstrip("/")
    if query:
        return f"{base}{normalized_path}?{query}"
    return f"{base}{normalized_path}"


def _build_frontend_url_from_request(request: Request, path: str, **params: str) -> str:
    # OAuth redirects always return to the configured canonical frontend.
    # Origin/Referer and client-controlled cookies are intentionally ignored
    # to avoid turning the callback into an open redirect.
    return _build_frontend_url(path, **params)


def _build_oauth_error_redirect(request: Request, message: str) -> RedirectResponse:
    response = RedirectResponse(
        url=_build_frontend_url_from_request(request, settings.FRONTEND_LOGIN_PATH, error=message),
        status_code=status.HTTP_302_FOUND,
    )
    clear_oauth_state_cookie(response)
    return response


def _rollback_oauth_user(email: str, created: bool, db: Session) -> None:
    if not created or not email:
        return

    existing_user = auth_service.get_user_by_email(email, db)
    if not existing_user:
        return

    try:
        users_client.delete_profile(existing_user.id)
    except HTTPException:
        pass
    auth_service.delete_user(existing_user, db)


def _validate_oauth_state(request: Request, state: str) -> None:
    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or not secrets.compare_digest(cookie_state, state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado OAuth invalido o expirado.",
        )


def _normalized_role(profile: dict) -> str:
    return str(profile.get("role", "external")).strip().lower()


def _build_authenticated_response(
    response: Response,
    user,
    profile: dict,
    *,
    message: str,
) -> LoginResponse:
    role = _normalized_role(profile)
    token = auth_service.create_access_token_for_user(
        user,
        role=role,
        full_name=profile["full_name"],
    )
    set_access_cookie(response, token)
    return LoginResponse(
        message=message,
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=profile["full_name"],
        role=role,
    )


def _build_otp_challenge_response(user, profile: dict, delivery: dict[str, str | bool | None]) -> LoginResponse:
    delivered = bool(delivery.get("delivered"))
    message = "Se envio un codigo de verificacion a tu correo electronico."
    if not delivered:
        message = str(
            delivery.get("reason")
            or "No pudimos enviar el correo. Usa el codigo temporal mostrado para continuar."
        )

    _debug = str(delivery.get("debug_otp")) if delivery.get("debug_otp") and settings.ENVIRONMENT == "development" else None

    return LoginResponse(
        message=message,
        requires_otp=True,
        purpose=OTPPurpose.LOGIN,
        delivery_mode=str(delivery.get("delivery_mode")) if delivery.get("delivery_mode") else None,
        debug_otp=_debug,
        user_id=user.id,
        email=user.email,
        full_name=profile["full_name"],
        role=_normalized_role(profile),
    )


def _dispatch_login_otp(user, profile: dict, db: Session) -> LoginResponse:
    code = otp_service.generate_otp(user, OTPPurpose.LOGIN, db)
    delivery = email_service.send_otp_email(
        to_email=user.email,
        full_name=profile["full_name"],
        code=code,
        purpose=OTPPurpose.LOGIN.value,
    )
    return _build_otp_challenge_response(user, profile, delivery)


def _ensure_oauth_profile(user, full_name: str, created: bool) -> dict:
    if created:
        profile = users_client.create_profile(
            user_id=user.id,
            full_name=full_name,
            email=user.email,
            role="external",
        )
        event_service.publish_user_registered(user)
        return profile

    try:
        return users_client.get_profile(user.id)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        return users_client.create_profile(
            user_id=user.id,
            full_name=full_name,
            email=user.email,
            role="external",
        )


def register(payload: RegisterRequest, db: Session) -> RegisterResponse:
    user = auth_service.register_user(payload, db)

    try:
        users_client.create_profile(
            user_id=user.id,
            full_name=payload.full_name,
            email=payload.email,
            role=payload.role,
            institution=payload.institution,
        )
        event_service.publish_user_registered(user)
    except event_service.EventPublishError as exc:
        try:
            users_client.delete_profile(user.id)
        except HTTPException:
            pass
        auth_service.delete_user(user, db)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo completar el registro porque RabbitMQ no esta disponible.",
        ) from exc
    except HTTPException as exc:
        try:
            users_client.delete_profile(user.id)
        except HTTPException:
            pass
        auth_service.delete_user(user, db)
        raise exc

    try:
        code = otp_service.generate_otp(user, OTPPurpose.REGISTER, db)
        delivery = email_service.send_otp_email(
            to_email=user.email,
            full_name=user.full_name,
            code=code,
            purpose=OTPPurpose.REGISTER.value,
        )
    except HTTPException:
        try:
            users_client.delete_profile(user.id)
        except HTTPException:
            pass
        auth_service.delete_user(user, db)
        raise

    register_message = "Cuenta creada. Se envio un codigo de verificacion a tu correo electronico."
    if not delivery.get("delivered"):
        register_message = str(
            delivery.get("reason")
            or "No pudimos enviar el correo. Usa el codigo temporal mostrado para continuar."
        )

    return RegisterResponse(
        message=register_message,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=payload.role,
        requires_otp=True,
        purpose=OTPPurpose.REGISTER,
        delivery_mode=str(delivery.get("delivery_mode")) if delivery.get("delivery_mode") else None,
        debug_otp=str(delivery.get("debug_otp")) if delivery.get("debug_otp") and settings.ENVIRONMENT == "development" else None,
    )


def verify_otp(payload: OTPVerifyRequest, response: Response, db: Session) -> LoginResponse:
    user = auth_service.get_user_by_email(payload.email, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta inactiva.",
        )

    otp_service.verify_otp(user, payload.code, payload.purpose, db)
    auth_service.mark_user_verified(user, db)
    profile = users_client.get_profile(user.id)
    if profile.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta inactiva.",
        )

    return _build_authenticated_response(
        response,
        user,
        profile,
        message="Verificacion exitosa. Sesion iniciada.",
    )


def login(payload: LoginRequest, response: Response, db: Session) -> LoginResponse:
    user = auth_service.authenticate_user(payload.email, payload.password, db)
    profile = users_client.get_profile(user.id)
    if profile.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta inactiva.",
        )
    if auth_service.requires_login_otp(user, _normalized_role(profile)):
        return _dispatch_login_otp(user, profile, db)

    return _build_authenticated_response(
        response,
        user,
        profile,
        message="Autenticacion exitosa.",
    )


def get_authenticated_user_response(current_user) -> AuthenticatedUserResponse:
    profile = users_client.get_profile(current_user.id)
    return AuthenticatedUserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=profile["full_name"],
        role=_normalized_role(profile),
        institution=profile.get("institution"),
        first_name=profile.get("first_name"),
        last_name=profile.get("last_name"),
        career=profile.get("career"),
        gender=profile.get("gender"),
        document=profile.get("document"),
        institutional_code=profile.get("institutional_code"),
        profile_completed=bool(profile.get("profile_completed")),
        is_verified=current_user.is_verified,
        is_active=current_user.is_active,
    )


def logout(response: Response) -> MessageResponse:
    clear_access_cookie(response)
    return MessageResponse(message="Sesion cerrada correctamente.")


def forgot_password(payload: ForgotPasswordRequest, db: Session) -> MessageResponse:
    generic_message = "Si el correo esta registrado, recibiras instrucciones para restablecer tu contrasena."
    user = auth_service.get_user_by_email(payload.email, db)
    if not user or not user.is_active:
        return MessageResponse(message=generic_message)

    reset_token = auth_service.create_password_reset_token(user, db)
    reset_url = _build_frontend_url(
        settings.FRONTEND_RESET_PASSWORD_PATH,
        token=reset_token,
    )
    email_service.send_password_reset_email(
        to_email=user.email,
        full_name=user.full_name,
        reset_url=reset_url,
    )
    return MessageResponse(message=generic_message)


def reset_password(payload: ResetPasswordRequest, db: Session) -> MessageResponse:
    auth_service.reset_password(payload.token, payload.new_password, db)
    return MessageResponse(message="Contrasena actualizada correctamente. Ya puedes iniciar sesion.")


def begin_oauth_login(request: Request, provider: str) -> RedirectResponse:
    provider_config = _get_oauth_provider(provider)
    state = generate_oauth_state()
    redirect_uri = build_oauth_redirect_uri(request, provider)
    response = RedirectResponse(
        url=provider_config.authorization_url_builder(state, redirect_uri=redirect_uri),
        status_code=status.HTTP_302_FOUND,
    )
    set_oauth_state_cookie(response, state)
    return response


async def complete_oauth_callback(
    request: Request,
    provider: str,
    db: Session,
) -> RedirectResponse:
    provider_config = _get_oauth_provider(provider)
    error = request.query_params.get("error")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    created = False
    user_info: dict[str, str] = {}

    if error:
        return _build_oauth_error_redirect(request, provider_config.auth_error_message)
    if not code or not state:
        return _build_oauth_error_redirect(request, provider_config.incomplete_callback_message)

    try:
        redirect_uri = build_oauth_redirect_uri(request, provider)
        _validate_oauth_state(request, state)
        user_info = await provider_config.code_exchange(code, redirect_uri=redirect_uri)
        if not user_info.get("email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=provider_config.invalid_email_message,
            )

        user, created = auth_service.get_or_create_oauth_user(
            email=user_info["email"],
            full_name=user_info.get("full_name", ""),
            db=db,
        )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La cuenta esta inactiva.",
            )

        profile = _ensure_oauth_profile(
            user=user,
            full_name=user_info.get("full_name") or user.full_name,
            created=created,
        )
        if profile.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La cuenta esta inactiva.",
            )
        token = auth_service.create_access_token_for_user(
            user,
            role=_normalized_role(profile),
            full_name=profile["full_name"],
        )
        response = RedirectResponse(
            url=_build_frontend_url_from_request(request, settings.FRONTEND_LOGIN_PATH, oauth="success"),
            status_code=status.HTTP_302_FOUND,
        )
        set_access_cookie(response, token)
        clear_oauth_state_cookie(response)
        return response
    except event_service.EventPublishError:
        _rollback_oauth_user(user_info.get("email", ""), created, db)
        return _build_oauth_error_redirect(request, "No se pudo finalizar el registro OAuth.")
    except HTTPException as exc:
        _rollback_oauth_user(user_info.get("email", ""), created, db)
        return _build_oauth_error_redirect(request, exc.detail)
