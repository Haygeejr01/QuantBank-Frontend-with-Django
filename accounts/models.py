from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
import base64
import secrets

from .institutions import INSTITUTION_CHOICES, institution_name


def generate_reference(prefix="NB"):
    return f"{prefix}-{timezone.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(6).upper()}"


class Institution(models.Model):
    INSTITUTION_TYPES = [
        ('bank', 'Bank'),
        ('wallet', 'Wallet'),
    ]

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=40, blank=True)
    bank_code = models.CharField(max_length=20, blank=True)
    institution_type = models.CharField(max_length=20, choices=INSTITUTION_TYPES, default='bank')
    account_prefix = models.CharField(max_length=4, default='99')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Account(models.Model):
    BANK_CHOICES = INSTITUTION_CHOICES
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('others', 'Others'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.SET_NULL, related_name='accounts')
    bank_type = models.CharField(max_length=40, choices=BANK_CHOICES)
    account_number = models.CharField(max_length=15, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    bvn = models.CharField(max_length=11, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    is_frozen = models.BooleanField(default=False)
    pin_hash = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'bank_type')

    def __str__(self):
        return f"{self.user.username} - {self.bank_type} ({self.account_number})"

    @property
    def bank_name(self):
        return self.institution.name if self.institution_id else institution_name(self.bank_type)

    @property
    def bank_short_name(self):
        if self.institution_id and self.institution.short_name:
            return self.institution.short_name
        return self.bank_name

    @property
    def masked_number(self):
        return f"**** {self.account_number[-4:]}"

    def save(self, *args, **kwargs):
        if not self.pin_hash:
            self.set_pin("0000")
        super().save(*args, **kwargs)

    def set_pin(self, raw_pin):
        self.pin_hash = make_password(str(raw_pin))

    def check_pin(self, raw_pin):
        if not raw_pin:
            return False
        return check_password(str(raw_pin), self.pin_hash)


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]
    CHANNEL_CHOICES = [
        ('internal', 'Internal Transfer'),
        ('deposit', 'Wallet Funding'),
        ('bill', 'Bill Payment'),
        ('external_transfer', 'External Transfer'),
        ('manual', 'Manual Adjustment'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    performed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='performed_transactions')
    counterparty_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name='counterparty_transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='succeeded')
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default='internal')
    reference = models.CharField(max_length=80, unique=True, null=True, blank=True)
    idempotency_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    details = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.account.user.username}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_reference("TX")
        super().save(*args, **kwargs)


class PaymentIntent(models.Model):
    INTENT_TYPES = [
        ('wallet_funding', 'Wallet Funding'),
        ('bill_payment', 'Bill Payment'),
        ('external_transfer', 'External Transfer'),
    ]
    STATUS_CHOICES = Transaction.STATUS_CHOICES + [
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_intents')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='payment_intents')
    intent_type = models.CharField(max_length=30, choices=INTENT_TYPES)
    provider = models.CharField(max_length=30, default='flutterwave')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=80, unique=True, default=generate_reference)
    idempotency_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    checkout_url = models.URLField(blank=True)
    description = models.CharField(max_length=255, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.intent_type} {self.reference} ({self.status})"


class Beneficiary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='beneficiaries')
    name = models.CharField(max_length=120)
    bank_code = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=120)
    account_number = models.CharField(max_length=20)
    currency = models.CharField(max_length=3, default='NGN')
    provider_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'bank_code', 'account_number')
        ordering = ['bank_name', 'account_number']

    def __str__(self):
        return f"{self.name} - {self.bank_name} ({self.account_number})"


class ProviderEvent(models.Model):
    provider = models.CharField(max_length=30, default='flutterwave')
    event_id = models.CharField(max_length=120)
    event_type = models.CharField(max_length=80)
    reference = models.CharField(max_length=120, blank=True)
    signature = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('provider', 'event_id')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider}:{self.event_type}:{self.event_id}"


class AuditLog(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')
    action = models.CharField(max_length=80)
    target_reference = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} by {self.actor or 'system'}"


class KycProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='kyc_profile')
    masked_bvn = models.CharField(max_length=11, blank=True)
    bvn_hash = models.CharField(max_length=128, blank=True)
    masked_nin = models.CharField(max_length=11, blank=True)
    nin_hash = models.CharField(max_length=128, blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_verified(self):
        return bool(self.verified_at and self.bvn_hash and self.nin_hash)

    def __str__(self):
        return f"KYC for {self.user.username}"


class UserSecurityProfile(models.Model):
    TWO_FACTOR_METHODS = [
        ('email', 'Email OTP'),
        ('totp', 'Authenticator App'),
        ('sms', 'SMS OTP'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_profile')
    phone_number = models.CharField(max_length=20, blank=True)
    preferred_2fa_method = models.CharField(max_length=20, choices=TWO_FACTOR_METHODS, default='email')
    email_2fa_enabled = models.BooleanField(default=True)
    totp_enabled = models.BooleanField(default=False)
    sms_enabled = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def ensure_totp_secret(self):
        if not self.totp_secret:
            self.totp_secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
            self.save(update_fields=['totp_secret', 'updated_at'])
        return self.totp_secret

    def __str__(self):
        return f"Security profile for {self.user.username}"


class TwoFactorChallenge(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('used', 'Used'),
        ('expired', 'Expired'),
    ]
    PURPOSE_CHOICES = [
        ('login', 'Login'),
        ('transfer', 'Transfer'),
        ('bill_payment', 'Bill Payment'),
        ('external_transfer', 'External Transfer'),
        ('pin_reset', 'PIN Reset'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='two_factor_challenges')
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.CASCADE, related_name='two_factor_challenges')
    method = models.CharField(max_length=20, choices=UserSecurityProfile.TWO_FACTOR_METHODS)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=80, unique=True, default=generate_reference)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def verify(self, raw_code):
        if self.status != 'pending' or self.is_expired():
            if self.status == 'pending':
                self.status = 'expired'
                self.save(update_fields=['status'])
            return False
        if not check_password(str(raw_code), self.code_hash):
            return False
        self.status = 'used'
        self.used_at = timezone.now()
        self.save(update_fields=['status', 'used_at'])
        return True

    def __str__(self):
        return f"{self.method} challenge for {self.user.username}"
