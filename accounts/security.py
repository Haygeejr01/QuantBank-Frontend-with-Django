import base64
import hashlib
import hmac
import random
from datetime import timedelta

import pyotp
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.utils import timezone

from .models import TwoFactorChallenge, UserSecurityProfile


class SecurityError(ValueError):
    pass


def get_security_profile(user):
    profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
    return profile


def generate_numeric_code(length=6):
    return "".join(random.choice("0123456789") for _ in range(length))


def create_two_factor_challenge(user, purpose, method="email", account=None):
    method = method or get_security_profile(user).preferred_2fa_method
    if method == "totp":
        return None, None

    code = generate_numeric_code()
    challenge = TwoFactorChallenge.objects.create(
        user=user,
        account=account,
        method=method,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
    )

    if method == "email":
        recipient = user.email
        if recipient:
            send_mail(
                "Your NeuroBank verification code",
                f"Your NeuroBank verification code is {code}. It expires in {settings.OTP_EXPIRY_MINUTES} minutes.",
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=True,
            )
    elif method == "sms":
        # SMS delivery is intentionally adapter-backed. The challenge is created
        # now; live delivery should be connected through settings.SMS_PROVIDER.
        challenge.metadata["sms_provider"] = settings.SMS_PROVIDER or "not_configured"
        challenge.save(update_fields=["metadata"])

    return challenge, code


def get_totp_secret(profile):
    return profile.ensure_totp_secret()


def get_totp_uri(user):
    profile = get_security_profile(user)
    secret = get_totp_secret(profile)
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email or user.username,
        issuer_name="NeuroBank",
    )


def verify_two_factor(user, purpose, code, method="email", account=None):
    if not settings.TRANSACTION_2FA_REQUIRED:
        return True
    if not code:
        raise SecurityError("Two-factor verification code is required.")

    method = method or get_security_profile(user).preferred_2fa_method
    if method == "totp":
        profile = get_security_profile(user)
        secret = get_totp_secret(profile)
        if pyotp.TOTP(secret).verify(str(code), valid_window=1):
            return True
        raise SecurityError("Authenticator code is invalid or expired.")

    challenge = (
        TwoFactorChallenge.objects.filter(
            user=user,
            account=account,
            purpose=purpose,
            method=method,
            status="pending",
        )
        .order_by("-created_at")
        .first()
    )
    if not challenge or not challenge.verify(code):
        raise SecurityError("Two-factor verification code is invalid or expired.")
    return True


def verify_flutterwave_signature(raw_body, headers):
    secret = settings.FLW_WEBHOOK_SECRET
    if not secret:
        return settings.DEBUG

    signature = headers.get("flutterwave-signature")
    if signature:
        digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode()
        if hmac.compare_digest(signature, expected):
            return True

    legacy_signature = headers.get("verif-hash") or headers.get("verifi-hash")
    return bool(legacy_signature and hmac.compare_digest(legacy_signature, secret))
