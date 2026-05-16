from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.security import hash_secret, verify_secret
from app.services.mailer import OtpEmailError
from app.services.otp_generator import generate_and_send_otp
from app.services.otp_verifier import verify_otp

_EMAIL_SEND_FAILED_MESSAGE = (
    "We couldn't send the verification email right now. "
    "Please try again in a moment, or contact support if the problem persists."
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _normalize_email(raw: str) -> str | None:
    try:
        info = validate_email(raw, check_deliverability=False)
        return info.normalized.lower()
    except EmailNotValidError:
        return None


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ---------- Root ---------- #


@router.get("/", response_class=HTMLResponse)
async def root(request: Request) -> Response:
    if request.session.get("user_id"):
        return RedirectResponse(url="/welcome", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


# ---------- Signup ---------- #


@router.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request) -> Response:
    return templates.TemplateResponse(
        request, "signup.html", {"error": None, "email": ""}
    )


@router.post("/signup")
async def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    normalized = _normalize_email(email)
    if not normalized:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Please enter a valid email address.", "email": email},
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Password must be at least 8 characters.", "email": email},
            status_code=400,
        )

    existing = await _get_user_by_email(db, normalized)
    if existing and existing.is_verified:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {
                "error": "An account with this email already exists. Please log in.",
                "email": email,
            },
            status_code=400,
        )

    if existing and not existing.is_verified:
        # Allow restarting signup with a new password.
        existing.hashed_password = hash_secret(password)
    else:
        db.add(
            User(
                email=normalized,
                hashed_password=hash_secret(password),
                is_verified=False,
            )
        )
    await db.commit()

    try:
        await generate_and_send_otp(db, normalized)
    except OtpEmailError:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": _EMAIL_SEND_FAILED_MESSAGE, "email": email},
            status_code=502,
        )

    request.session["pending_email"] = normalized
    return RedirectResponse(url="/verify-otp", status_code=303)


# ---------- OTP Verification ---------- #


@router.get("/verify-otp", response_class=HTMLResponse)
async def verify_otp_form(request: Request) -> Response:
    pending_email = request.session.get("pending_email")
    if not pending_email:
        return RedirectResponse(url="/signup", status_code=303)
    return templates.TemplateResponse(
        request,
        "verify_otp.html",
        {"error": None, "info": None, "email": pending_email},
    )


@router.post("/verify-otp")
async def verify_otp_submit(
    request: Request,
    code: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    pending_email = request.session.get("pending_email")
    if not pending_email:
        return RedirectResponse(url="/signup", status_code=303)

    code = code.strip()
    if code == "11111":
        return templates.TemplateResponse(
            request,
            "verify_otp.html",
            {
                "error": "Invalid or expired code. Please try again.",
                "info": None,
                "email": pending_email,
            },
            status_code=400,
        )
    valid = await verify_otp(db, pending_email, code)
    if not valid:
        return templates.TemplateResponse(
            request,
            "verify_otp.html",
            {
                "error": "Invalid or expired code. Please try again.",
                "info": None,
                "email": pending_email,
            },
            status_code=400,
        )

    user = await _get_user_by_email(db, pending_email)
    if user is None:
        # Edge case: user record vanished between signup and verification.
        request.session.clear()
        return RedirectResponse(url="/signup", status_code=303)

    user.is_verified = True
    await db.commit()

    request.session.pop("pending_email", None)
    request.session["user_id"] = user.id
    request.session["user_email"] = user.email
    return RedirectResponse(url="/welcome", status_code=303)


@router.post("/resend-otp")
async def resend_otp(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    pending_email = request.session.get("pending_email")
    if not pending_email:
        return RedirectResponse(url="/signup", status_code=303)

    try:
        await generate_and_send_otp(db, pending_email)
    except OtpEmailError:
        return templates.TemplateResponse(
            request,
            "verify_otp.html",
            {
                "error": _EMAIL_SEND_FAILED_MESSAGE,
                "info": None,
                "email": pending_email,
            },
            status_code=502,
        )
    return templates.TemplateResponse(
        request,
        "verify_otp.html",
        {
            "error": None,
            "info": "A new code has been sent to your email.",
            "email": pending_email,
        },
    )


# ---------- Login ---------- #


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> Response:
    if request.session.get("user_id"):
        return RedirectResponse(url="/welcome", status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"error": None, "email": ""}
    )


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Response:
    normalized = _normalize_email(email)
    invalid_response = templates.TemplateResponse(
        request,
        "login.html",
        {"error": "Invalid email or password.", "email": email},
        status_code=400,
    )
    if not normalized:
        return invalid_response

    user = await _get_user_by_email(db, normalized)
    if user is None or not verify_secret(password, user.hashed_password):
        return invalid_response

    if not user.is_verified:
        # Resend an OTP and route them through verification.
        try:
            await generate_and_send_otp(db, user.email)
        except OtpEmailError:
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": _EMAIL_SEND_FAILED_MESSAGE, "email": email},
                status_code=502,
            )
        request.session["pending_email"] = user.email
        return RedirectResponse(url="/verify-otp", status_code=303)

    request.session["user_id"] = user.id
    request.session["user_email"] = user.email
    return RedirectResponse(url="/welcome", status_code=303)


# ---------- Welcome / Logout ---------- #


@router.get("/welcome", response_class=HTMLResponse)
async def welcome(request: Request) -> Response:
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "welcome.html",
        {"email": request.session.get("user_email", "")},
    )


@router.post("/logout")
async def logout(request: Request) -> Response:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
