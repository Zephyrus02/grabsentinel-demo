import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import OtpCode
from app.security import hash_secret
from app.services.mailer import send_otp_email


def _generate_code(length: int) -> str:
    """Generate a numeric OTP of the given length."""
    upper = 10**length
    return f"{secrets.randbelow(upper):0{length}d}"


async def generate_and_send_otp(db: AsyncSession, email: str) -> None:
    """Create a new OTP for the email, invalidate any prior unused codes, and send it.

    This service only deals with creation/dispatch — verification lives separately
    in `otp_verifier.py`.
    """
    # Invalidate any previous unused codes for this email so only the latest one works.
    await db.execute(
        update(OtpCode)
        .where(OtpCode.email == email, OtpCode.used.is_(False))
        .values(used=True)
    )

    code = _generate_code(settings.OTP_LENGTH)
    otp_row = OtpCode(
        email=email,
        code_hash=hash_secret(code),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        used=False,
    )
    db.add(otp_row)
    await db.commit()

    # Send the email after successfully persisting so we don't leak codes for
    # rows that failed to commit.
    send_otp_email(email, code)
