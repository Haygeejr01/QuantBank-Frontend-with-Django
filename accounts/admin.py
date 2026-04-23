from django.contrib import admin
from .models import (
    Account,
    AuditLog,
    Beneficiary,
    Institution,
    KycProfile,
    PaymentIntent,
    ProviderEvent,
    Transaction,
    TwoFactorChallenge,
    UserSecurityProfile,
)


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "bank_code", "institution_type", "is_active")
    list_filter = ("institution_type", "is_active")
    search_fields = ("name", "short_name", "code", "bank_code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("account_number", "user", "institution", "bank_type", "balance", "is_frozen", "updated_at")
    list_filter = ("institution", "bank_type", "is_frozen", "gender")
    search_fields = ("account_number", "user__username", "user__first_name", "user__last_name")
    readonly_fields = ("pin_hash", "created_at", "updated_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "account", "transaction_type", "amount", "status", "channel", "timestamp")
    list_filter = ("transaction_type", "status", "channel", "currency")
    search_fields = ("reference", "details", "account__account_number", "provider_reference")
    readonly_fields = ("reference", "timestamp", "updated_at")


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "intent_type", "amount", "status", "provider", "created_at")
    list_filter = ("intent_type", "status", "provider", "currency")
    search_fields = ("reference", "provider_reference", "user__username", "account__account_number")
    readonly_fields = ("reference", "created_at", "updated_at")


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ("name", "bank_name", "account_number", "user", "currency")
    search_fields = ("name", "bank_name", "account_number", "user__username")


@admin.register(ProviderEvent)
class ProviderEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "event_type", "reference", "processed", "created_at")
    list_filter = ("provider", "event_type", "processed")
    search_fields = ("event_id", "reference")
    readonly_fields = ("payload", "created_at", "processed_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "account", "target_reference", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "target_reference", "actor__username", "account__account_number")
    readonly_fields = ("actor", "account", "action", "target_reference", "ip_address", "user_agent", "metadata", "created_at")


@admin.register(KycProfile)
class KycProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "masked_bvn", "masked_nin", "verified_at", "updated_at")
    search_fields = ("user__username", "user__email", "masked_bvn", "masked_nin")
    readonly_fields = ("masked_bvn", "bvn_hash", "masked_nin", "nin_hash", "consent_at", "verified_at", "created_at", "updated_at")


@admin.register(UserSecurityProfile)
class UserSecurityProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "preferred_2fa_method", "email_2fa_enabled", "totp_enabled", "sms_enabled", "updated_at")
    list_filter = ("preferred_2fa_method", "email_2fa_enabled", "totp_enabled", "sms_enabled")
    search_fields = ("user__username", "user__email", "phone_number")
    readonly_fields = ("totp_secret", "created_at", "updated_at")


@admin.register(TwoFactorChallenge)
class TwoFactorChallengeAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "method", "purpose", "status", "expires_at", "created_at")
    list_filter = ("method", "purpose", "status")
    search_fields = ("reference", "user__username")
    readonly_fields = ("code_hash", "reference", "created_at", "used_at")
