import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import OTPCode, OTPPurpose
from app.models.auth_user import AuthUser


def generate_otp(user: AuthUser, purpose: OTPPurpose, db: Session) -> str:
    db.query(OTPCode).filter(
        OTPCode.user_id == user.id,
        OTPCode.purpose == purpose,
        OTPCode.used.is_(False),
    ).update({"used": True}, synchronize_session=False)

    code_value = "".join(secrets.choice(string.digits) for _ in range(6))
    otp_record = OTPCode(
        user_id=user.id,
        code=code_value,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES),
    )
    db.add(otp_record)
    db.commit()
    return code_value


def verify_otp(user: AuthUser, code: str, purpose: OTPPurpose, db: Session) -> None:
    otp_record = (
        db.query(OTPCode)
        .filter(
            OTPCode.user_id == user.id,
            OTPCode.code == code,
            OTPCode.purpose == purpose,
            OTPCode.used.is_(False),
        )
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo invalido o ya utilizado.",
        )

    if otp_record.is_expired():
        otp_record.used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El codigo ha expirado. Inicia sesion de nuevo para solicitar otro.",
        )

    otp_record.used = True
    db.commit()
