import hashlib
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .institutions import INSTITUTION_BY_CODE, INSTITUTIONS


class IdentityError(ValueError):
    pass


def normalize_identity_number(value, label):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) != 11:
        raise IdentityError(f"{label} must be exactly 11 digits.")
    return digits


def mask_identity_number(value):
    digits = str(value)
    return f"{digits[:3]}****{digits[-4:]}"


def hash_identity_number(value, salt):
    return salted_hmac(salt, str(value), secret=settings.SECRET_KEY).hexdigest()


def verify_customer_identity(user, bvn, nin, consent=False):
    if not consent:
        raise IdentityError("Please confirm your consent to verify your identity.")

    normalized_bvn = normalize_identity_number(bvn, "BVN")
    normalized_nin = normalize_identity_number(nin, "NIN")

    from .models import KycProfile

    profile, _ = KycProfile.objects.get_or_create(user=user)
    profile.masked_bvn = mask_identity_number(normalized_bvn)
    profile.bvn_hash = hash_identity_number(normalized_bvn, "lumopay.bvn")
    profile.masked_nin = mask_identity_number(normalized_nin)
    profile.nin_hash = hash_identity_number(normalized_nin, "lumopay.nin")
    profile.consent_at = timezone.now()
    profile.verified_at = timezone.now()
    profile.save()
    return profile


def _stable_number(seed, code):
    digest = hashlib.sha256(f"{seed}:{code}".encode("utf-8")).hexdigest()
    institution = INSTITUTION_BY_CODE.get(code, {})
    prefix = institution.get("prefix", "99")
    body = str(int(digest[:12], 16)).zfill(12)[:8]
    return f"{prefix}{body}"


def _stable_balance(seed, code):
    digest = hashlib.sha256(f"balance:{seed}:{code}".encode("utf-8")).hexdigest()
    amount = 15000 + (int(digest[:8], 16) % 850000)
    return Decimal(amount).quantize(Decimal("0.01"))


def discover_mock_accounts(user):
    from .models import Account, KycProfile

    try:
        profile = user.kyc_profile
    except KycProfile.DoesNotExist as exc:
        raise IdentityError("Verify your BVN and NIN before adding accounts.") from exc

    if not profile.is_verified:
        raise IdentityError("Verify your BVN and NIN before adding accounts.")

    linked_codes = set(Account.objects.filter(user=user).values_list("bank_type", flat=True))
    seed = f"{profile.bvn_hash}:{profile.nin_hash}:{user.id}"
    discovered = []
    for item in INSTITUTIONS:
        if item["code"] in linked_codes:
            continue
        discovered.append({
            "bank_type": item["code"],
            "bank_name": item["name"],
            "short_name": item["short_name"],
            "account_number": _stable_number(seed, item["code"]),
            "balance": str(_stable_balance(seed, item["code"])),
            "kind": item["kind"],
        })
    return discovered
