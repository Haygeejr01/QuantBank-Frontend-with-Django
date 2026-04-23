import json
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import (
    Account,
    AuditLog,
    Beneficiary,
    PaymentIntent,
    ProviderEvent,
    Transaction,
    generate_reference,
)
from .payments import FlutterwaveClient, FlutterwaveError
from .security import SecurityError, verify_two_factor


class BankingError(ValueError):
    pass


def parse_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BankingError("Invalid amount.") from exc
    if amount <= 0:
        raise BankingError("Amount must be greater than zero.")
    return amount.quantize(Decimal("0.01"))


def request_ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def audit(actor, action, account=None, request=None, target_reference="", metadata=None):
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        account=account,
        action=action,
        target_reference=target_reference or "",
        ip_address=request_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
        metadata=metadata or {},
    )


def ensure_account_can_spend(account):
    if account.is_frozen:
        raise BankingError("This account is frozen. Choose another account.")


def verify_money_auth(user, account, pin, two_factor_code, two_factor_method, purpose):
    if not account.check_pin(pin):
        raise SecurityError("Transaction PIN is incorrect.")
    verify_two_factor(
        user=user,
        account=account,
        purpose=purpose,
        code=two_factor_code,
        method=two_factor_method or "email",
    )


def make_transaction(account, tx_type, amount, details, **kwargs):
    balance_before = kwargs.pop("balance_before", None)
    balance_after = kwargs.pop("balance_after", None)
    return Transaction.objects.create(
        account=account,
        transaction_type=tx_type,
        amount=amount,
        details=details,
        balance_before=balance_before,
        balance_after=balance_after,
        **kwargs,
    )


def internal_transfer(user, source_acc_id, dest_acc_number, dest_bank_type, amount, pin, two_factor_code, two_factor_method="email", request=None):
    amount = parse_amount(amount)
    with db_transaction.atomic():
        source = Account.objects.select_for_update().get(id=source_acc_id, user=user)
        ensure_account_can_spend(source)
        verify_money_auth(user, source, pin, two_factor_code, two_factor_method, "transfer")

        destination = Account.objects.select_for_update().get(
            account_number=dest_acc_number,
            bank_type=dest_bank_type,
        )
        if destination.id == source.id:
            raise BankingError("You cannot transfer to the same account.")
        if source.balance < amount:
            raise BankingError("Insufficient funds.")

        source_before = source.balance
        dest_before = destination.balance
        source.balance -= amount
        destination.balance += amount
        source.save(update_fields=["balance", "updated_at"])
        destination.save(update_fields=["balance", "updated_at"])

        debit = make_transaction(
            source,
            "debit",
            amount,
            f"Transfer to {destination.user.get_full_name() or destination.user.username}",
            performed_by=user,
            counterparty_account=destination,
            channel="internal",
            balance_before=source_before,
            balance_after=source.balance,
            metadata={"destination_account": destination.account_number},
        )
        make_transaction(
            destination,
            "credit",
            amount,
            f"Transfer from {source.user.get_full_name() or source.user.username}",
            performed_by=user,
            counterparty_account=source,
            channel="internal",
            balance_before=dest_before,
            balance_after=destination.balance,
            metadata={"source_account": source.account_number},
        )
        audit(user, "internal_transfer", source, request, debit.reference, {"amount": str(amount)})
        return debit, destination


def initiate_wallet_funding(user, account_id, amount, request=None):
    amount = parse_amount(amount)
    account = Account.objects.get(id=account_id, user=user)
    intent = PaymentIntent.objects.create(
        user=user,
        account=account,
        intent_type="wallet_funding",
        amount=amount,
        currency="NGN",
        description="Wallet funding",
        idempotency_key=str(uuid.uuid4()),
    )

    client = FlutterwaveClient()
    if client.configured:
        response = client.create_payment_link(intent, request)
        data = response.get("data") or {}
        intent.checkout_url = data.get("link", "")
        intent.provider_reference = str(data.get("id") or "")
        intent.status = "processing"
        intent.metadata["provider_response"] = data
        intent.save(update_fields=["checkout_url", "provider_reference", "status", "metadata", "updated_at"])
    elif settings.ALLOW_MANUAL_DEPOSITS:
        credit_wallet_funding(intent, provider_reference="manual-dev-credit")
    else:
        intent.failure_reason = "Flutterwave credentials are not configured."
        intent.save(update_fields=["failure_reason", "updated_at"])

    audit(user, "wallet_funding_initiated", account, request, intent.reference, {"amount": str(amount)})
    return intent


def credit_wallet_funding(intent, provider_reference=""):
    with db_transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(id=intent.id)
        if intent.status == "succeeded":
            return intent
        account = Account.objects.select_for_update().get(id=intent.account_id)
        before = account.balance
        account.balance += intent.amount
        account.save(update_fields=["balance", "updated_at"])
        make_transaction(
            account,
            "credit",
            intent.amount,
            "Wallet funding",
            performed_by=intent.user,
            channel="deposit",
            provider_reference=provider_reference,
            balance_before=before,
            balance_after=account.balance,
            metadata={"payment_intent": intent.reference},
        )
        intent.status = "succeeded"
        intent.provider_reference = provider_reference or intent.provider_reference
        intent.save(update_fields=["status", "provider_reference", "updated_at"])
        return intent


def service_payment(user, source_acc_id, amount, service_type, target, pin, two_factor_code, two_factor_method="email", request=None):
    amount = parse_amount(amount)
    with db_transaction.atomic():
        account = Account.objects.select_for_update().get(id=source_acc_id, user=user)
        ensure_account_can_spend(account)
        verify_money_auth(user, account, pin, two_factor_code, two_factor_method, "bill_payment")
        if account.balance < amount:
            raise BankingError("Insufficient funds.")

        before = account.balance
        account.balance -= amount
        account.save(update_fields=["balance", "updated_at"])
        intent = PaymentIntent.objects.create(
            user=user,
            account=account,
            intent_type="bill_payment",
            amount=amount,
            currency="NGN",
            status="processing",
            description=f"{service_type} payment",
            idempotency_key=str(uuid.uuid4()),
            metadata={"service_type": service_type, "target": target},
        )
        tx = make_transaction(
            account,
            "debit",
            amount,
            f"{service_type.upper()} payment: {target}",
            performed_by=user,
            channel="bill",
            status="processing",
            balance_before=before,
            balance_after=account.balance,
            metadata={"payment_intent": intent.reference, "target": target},
        )

    client = FlutterwaveClient()
    if client.configured:
        try:
            response = client.create_bill_payment(intent, customer=target)
            intent.provider_reference = str((response.get("data") or {}).get("flw_ref") or "")
            intent.status = "succeeded"
            intent.metadata["provider_response"] = response.get("data") or {}
            intent.save(update_fields=["provider_reference", "status", "metadata", "updated_at"])
            tx.status = "succeeded"
            tx.provider_reference = intent.provider_reference
            tx.save(update_fields=["status", "provider_reference", "updated_at"])
        except FlutterwaveError as exc:
            refund_failed_intent(intent, str(exc))
            raise BankingError(str(exc)) from exc
    else:
        intent.status = "succeeded"
        intent.provider_reference = "simulated-bill-payment"
        intent.save(update_fields=["status", "provider_reference", "updated_at"])
        tx.status = "succeeded"
        tx.provider_reference = intent.provider_reference
        tx.save(update_fields=["status", "provider_reference", "updated_at"])

    audit(user, "service_payment", account, request, intent.reference, {"amount": str(amount), "service_type": service_type})
    return intent, tx


def refund_failed_intent(intent, reason):
    with db_transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(id=intent.id)
        if intent.status in {"failed", "reversed"}:
            return intent
        account = Account.objects.select_for_update().get(id=intent.account_id)
        before = account.balance
        account.balance += intent.amount
        account.save(update_fields=["balance", "updated_at"])
        make_transaction(
            account,
            "credit",
            intent.amount,
            f"Reversal: {intent.description}",
            performed_by=intent.user,
            channel=intent.intent_type == "bill_payment" and "bill" or "external_transfer",
            status="reversed",
            balance_before=before,
            balance_after=account.balance,
            failure_reason=reason,
            metadata={"payment_intent": intent.reference},
        )
        intent.status = "failed"
        intent.failure_reason = reason
        intent.save(update_fields=["status", "failure_reason", "updated_at"])
        return intent


def external_transfer(user, source_acc_id, amount, beneficiary_data, pin, two_factor_code, two_factor_method="email", request=None):
    amount = parse_amount(amount)
    with db_transaction.atomic():
        account = Account.objects.select_for_update().get(id=source_acc_id, user=user)
        ensure_account_can_spend(account)
        verify_money_auth(user, account, pin, two_factor_code, two_factor_method, "external_transfer")
        if account.balance < amount:
            raise BankingError("Insufficient funds.")

        beneficiary, _ = Beneficiary.objects.update_or_create(
            user=user,
            bank_code=beneficiary_data["bank_code"],
            account_number=beneficiary_data["account_number"],
            defaults={
                "name": beneficiary_data.get("name", "External beneficiary"),
                "bank_name": beneficiary_data.get("bank_name", beneficiary_data["bank_code"]),
                "currency": beneficiary_data.get("currency", "NGN"),
            },
        )
        before = account.balance
        account.balance -= amount
        account.save(update_fields=["balance", "updated_at"])
        intent = PaymentIntent.objects.create(
            user=user,
            account=account,
            intent_type="external_transfer",
            amount=amount,
            currency="NGN",
            status="processing",
            description=f"External transfer to {beneficiary.name}",
            idempotency_key=str(uuid.uuid4()),
            metadata={"beneficiary_id": beneficiary.id},
        )
        tx = make_transaction(
            account,
            "debit",
            amount,
            f"External transfer to {beneficiary.name}",
            performed_by=user,
            channel="external_transfer",
            status="processing",
            balance_before=before,
            balance_after=account.balance,
            metadata={"payment_intent": intent.reference, "beneficiary": beneficiary.account_number},
        )

    client = FlutterwaveClient()
    if client.configured:
        callback_url = request.build_absolute_uri("/api/flutterwave/webhook/") if request else ""
        try:
            response = client.create_bank_transfer(intent, beneficiary, callback_url)
            data = response.get("data") or {}
            intent.provider_reference = str(data.get("id") or data.get("reference") or "")
            intent.metadata["provider_response"] = data
            intent.save(update_fields=["provider_reference", "metadata", "updated_at"])
            tx.provider_reference = intent.provider_reference
            tx.save(update_fields=["provider_reference", "updated_at"])
        except FlutterwaveError as exc:
            refund_failed_intent(intent, str(exc))
            raise BankingError(str(exc)) from exc
    else:
        intent.status = "succeeded"
        intent.provider_reference = "simulated-external-transfer"
        intent.save(update_fields=["status", "provider_reference", "updated_at"])
        tx.status = "succeeded"
        tx.provider_reference = intent.provider_reference
        tx.save(update_fields=["status", "provider_reference", "updated_at"])

    audit(user, "external_transfer", account, request, intent.reference, {"amount": str(amount)})
    return intent, tx


def handle_flutterwave_webhook(payload, signature=""):
    data = payload.get("data") or {}
    event_type = payload.get("event") or payload.get("type") or payload.get("event.type") or "unknown"
    event_id = str(payload.get("id") or data.get("id") or data.get("flw_ref") or data.get("reference") or uuid.uuid4())
    reference = str(data.get("tx_ref") or data.get("reference") or data.get("customer_reference") or "")

    event, created = ProviderEvent.objects.get_or_create(
        provider="flutterwave",
        event_id=event_id,
        defaults={
            "event_type": event_type,
            "reference": reference,
            "signature": signature,
            "payload": payload,
        },
    )
    if not created and event.processed:
        return event

    if event_type == "charge.completed":
        _process_charge_completed(data)
    elif event_type == "transfer.completed" or event_type == "transfer.disburse":
        _process_transfer_event(data)
    elif "bill" in event_type.lower():
        _process_bill_event(data)

    event.processed = True
    event.processed_at = timezone.now()
    event.save(update_fields=["processed", "processed_at"])
    return event


def _process_charge_completed(data):
    reference = data.get("tx_ref") or data.get("reference")
    if not reference:
        return
    try:
        intent = PaymentIntent.objects.get(reference=reference, intent_type="wallet_funding")
    except PaymentIntent.DoesNotExist:
        return

    verified = data
    transaction_id = data.get("id")
    client = FlutterwaveClient()
    if client.configured and transaction_id:
        verified = (client.verify_transaction(transaction_id).get("data") or data)

    status = str(verified.get("status", "")).lower()
    amount = parse_amount(verified.get("amount", intent.amount))
    currency = verified.get("currency", intent.currency)
    verified_ref = verified.get("tx_ref") or verified.get("reference")

    if status == "successful" and amount >= intent.amount and currency == intent.currency and verified_ref == intent.reference:
        credit_wallet_funding(intent, provider_reference=str(verified.get("flw_ref") or transaction_id or "flutterwave"))
    elif status in {"failed", "cancelled"}:
        intent.status = "failed"
        intent.failure_reason = verified.get("processor_response") or "Flutterwave payment failed."
        intent.save(update_fields=["status", "failure_reason", "updated_at"])


def _process_transfer_event(data):
    reference = data.get("reference")
    if not reference:
        return
    try:
        intent = PaymentIntent.objects.get(reference=reference, intent_type="external_transfer")
    except PaymentIntent.DoesNotExist:
        return
    status = str(data.get("status", "")).lower()
    if status in {"successful", "success"}:
        intent.status = "succeeded"
        intent.provider_reference = str(data.get("id") or data.get("reference") or intent.provider_reference)
        intent.save(update_fields=["status", "provider_reference", "updated_at"])
        Transaction.objects.filter(metadata__payment_intent=intent.reference).update(status="succeeded")
    elif status == "failed":
        refund_failed_intent(intent, data.get("complete_message") or "Flutterwave transfer failed.")


def _process_bill_event(data):
    reference = data.get("tx_ref") or data.get("customer_reference") or data.get("reference")
    if not reference:
        return
    PaymentIntent.objects.filter(reference=reference, intent_type="bill_payment").update(
        status="succeeded",
        provider_reference=str(data.get("flw_ref") or ""),
        updated_at=timezone.now(),
    )


def load_json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))
