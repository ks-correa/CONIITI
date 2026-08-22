from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models import OTPPurpose


def _non_empty(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Este campo no puede estar vacio.")
    return cleaned


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    role: str = Field(default="external")
    institution: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def normalize_full_name(self):
        final_name = self.full_name or self.name
        if not final_name:
            raise ValueError("El nombre es obligatorio.")
        cleaned = _non_empty(final_name)
        self.full_name = cleaned
        self.name = cleaned
        return self

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _non_empty(value) if value is not None else value

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        return _non_empty(value) if value is not None else value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        password = _non_empty(value)
        if not any(char.isalpha() for char in password):
            raise ValueError("La contrasena debe incluir al menos una letra.")
        if not any(char.isdigit() for char in password):
            raise ValueError("La contrasena debe incluir al menos un numero.")
        return password

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = _non_empty(value).lower()
        if normalized not in {"university_community", "external"}:
            raise ValueError("El auto-registro solo permite roles university_community o external.")
        return normalized


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _non_empty(value)


class RegisterResponse(BaseModel):
    message: str
    user_id: str
    email: EmailStr
    full_name: str
    role: str
    requires_otp: bool = True
    purpose: OTPPurpose = OTPPurpose.REGISTER
    delivery_mode: str | None = None
    debug_otp: str | None = None


class LoginResponse(BaseModel):
    message: str
    requires_otp: bool = False
    purpose: OTPPurpose | None = None
    delivery_mode: str | None = None
    debug_otp: str | None = None
    access_token: str | None = None
    token_type: str | None = None
    user_id: str | None = None
    email: EmailStr | None = None
    full_name: str | None = None
    role: str | None = None


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    purpose: OTPPurpose

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        code = _non_empty(value)
        if not code.isdigit():
            raise ValueError("El codigo OTP debe contener solo numeros.")
        if len(code) != 6:
            raise ValueError("El codigo OTP debe tener 6 digitos.")
        return code


class AuthenticatedUserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    institution: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    career: Optional[str] = None
    gender: Optional[str] = None
    document: Optional[str] = None
    institutional_code: Optional[str] = None
    profile_completed: bool = False
    is_verified: bool
    is_active: bool


class HealthResponse(BaseModel):
    status: str
    service: str


class ErrorResponse(BaseModel):
    detail: str


class MessageResponse(BaseModel):
    message: str
    requires_otp: bool = False


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=512)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        password = _non_empty(value)
        if not any(char.isalpha() for char in password):
            raise ValueError("La contrasena debe incluir al menos una letra.")
        if not any(char.isdigit() for char in password):
            raise ValueError("La contrasena debe incluir al menos un numero.")
        return password


class OAuthRedirectResponse(BaseModel):
    redirect_url: str


class InternalUserCreateRequest(BaseModel):
    user_id: Optional[str] = None
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    is_active: bool = True


class InternalUserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    is_active: Optional[bool] = None


class InternalUserResponse(BaseModel):
    user_id: str
    email: EmailStr
    full_name: str
    is_active: bool
    session_version: int


class SessionRevocationRequest(BaseModel):
    is_active: Optional[bool] = None


class SessionRevocationResponse(BaseModel):
    user_id: str
    is_active: bool
    session_version: int


class IntrospectionRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=4096)


class IntrospectionResponse(BaseModel):
    active: bool
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    session_version: Optional[int] = None
    expires_at: Optional[int] = None
