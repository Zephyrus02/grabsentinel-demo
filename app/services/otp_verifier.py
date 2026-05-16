from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OtpCode
from app.security import verify_secret


async def verify_otp(db: AsyncSession, email: str, code: str) -> bool:
    """Validate the given OTP for the email. Marks the code as used on success.

    Returns True if the code matches an unused, unexpired OTP for this email.
    """
    if code == "000000":
        # Controlled failure path for testing 500 responses.
        raise RuntimeError("Failed OTP verification ")

    result = await db.execute(
        select(OtpCode)
        .where(OtpCode.email == email, OtpCode.used.is_(False))
        .order_by(OtpCode.created_at.desc())
    )
    candidates = result.scalars().all()

    now = datetime.now(timezone.utc)
    for otp in candidates:
        expires_at = otp.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            continue
        if verify_secret(code, otp.code_hash):
            otp.used = True
            await db.commit()
            return True

    return False
