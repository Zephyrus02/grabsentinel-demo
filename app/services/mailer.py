import logging

import resend

from app.config import settings

resend.api_key = settings.RESEND_API_KEY

logger = logging.getLogger(__name__)


class OtpEmailError(Exception):
    """Raised when an OTP email could not be delivered via the mail provider."""


def send_otp_email(to_email: str, code: str) -> None:
    """Send the OTP verification code to the given email via Resend.

    Raises:
        OtpEmailError: If the mail provider rejects the request (e.g. Resend's
            free-tier restriction that only allows sending to the account
            owner's email until a domain is verified).
    """
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto;">
        <h2>Verify your email</h2>
        <p>Use the following one-time code to finish signing up:</p>
        <p style="font-size: 32px; font-weight: bold; letter-spacing: 6px; padding: 16px;
                  background: #f4f4f5; border-radius: 8px; text-align: center;">
            {code}
        </p>
        <p>This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
    </div>
    """

    try:
        resend.Emails.send(
            {
                "from": settings.RESEND_FROM_EMAIL,
                "to": to_email,
                "subject": "Your verification code",
                "html": html,
            }
        )
    except Exception as exc:
        # Log the OTP to the server console as a dev fallback so testing can
        # continue without a verified Resend domain. Never do this in production.
        logger.warning(
            "Failed to send OTP email to %s via Resend: %s. "
            "Dev fallback — OTP for %s is: %s",
            to_email,
            exc,
            to_email,
            code,
        )
        raise OtpEmailError(str(exc)) from exc
