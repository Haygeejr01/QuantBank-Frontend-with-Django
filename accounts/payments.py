import uuid

import requests
from django.conf import settings


class FlutterwaveError(RuntimeError):
    pass


class FlutterwaveClient:
    def __init__(self):
        self.secret_key = settings.FLW_SECRET_KEY
        self.base_url = settings.FLW_BASE_URL
        self.direct_transfer_base_url = settings.FLW_DIRECT_TRANSFER_BASE_URL

    @property
    def configured(self):
        return bool(self.secret_key)

    def _headers(self, idempotency_key=None):
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
            headers["X-Trace-Id"] = str(uuid.uuid4())
        return headers

    def _request(self, method, url, payload=None, idempotency_key=None):
        if not self.configured:
            raise FlutterwaveError("Flutterwave credentials are not configured.")
        response = requests.request(
            method,
            url,
            json=payload,
            headers=self._headers(idempotency_key=idempotency_key),
            timeout=30,
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise FlutterwaveError("Flutterwave returned a non-JSON response.") from exc
        if response.status_code >= 400 or body.get("status") == "error":
            raise FlutterwaveError(body.get("message") or "Flutterwave request failed.")
        return body

    def create_payment_link(self, intent, request):
        redirect_url = request.build_absolute_uri("/api/flutterwave/callback/")
        payload = {
            "tx_ref": intent.reference,
            "amount": str(intent.amount),
            "currency": intent.currency,
            "redirect_url": redirect_url,
            "customer": {
                "email": intent.user.email or f"{intent.user.username}@example.invalid",
                "name": intent.user.get_full_name() or intent.user.username,
            },
            "customizations": {
                "title": "LumoPay Wallet Funding",
                "description": intent.description or "Fund your LumoPay account",
            },
            "meta": {
                "payment_intent_id": intent.id,
                "account_id": intent.account_id,
            },
        }
        return self._request("POST", f"{self.base_url}/payments", payload=payload)

    def verify_transaction(self, transaction_id):
        return self._request("GET", f"{self.base_url}/transactions/{transaction_id}/verify")

    def create_bill_payment(self, intent, customer, biller_code=None, item_code=None):
        payload = {
            "country": "NG",
            "customer": customer,
            "amount": str(intent.amount),
            "type": intent.metadata.get("service_type", "AIRTIME"),
            "reference": intent.reference,
        }
        if biller_code:
            payload["biller_code"] = biller_code
        if item_code:
            payload["item_code"] = item_code
        return self._request("POST", f"{self.base_url}/bills", payload=payload, idempotency_key=intent.idempotency_key)

    def create_bank_transfer(self, intent, beneficiary, callback_url):
        payload = {
            "action": "instant",
            "type": "bank",
            "callback_url": callback_url,
            "narration": intent.description or "LumoPay transfer",
            "payment_instruction": {
                "amount": {
                    "value": float(intent.amount),
                    "applies_to": "destination_currency",
                },
                "source_currency": intent.currency,
                "destination_currency": beneficiary.currency,
                "recipient": {
                    "type": "bank",
                    "name": {"first": beneficiary.name, "last": ""},
                    "currency": beneficiary.currency,
                    "bank": {
                        "account_number": beneficiary.account_number,
                        "code": beneficiary.bank_code,
                    },
                },
            },
            "meta": {
                "payment_intent_id": intent.id,
                "reference": intent.reference,
            },
        }
        return self._request(
            "POST",
            f"{self.direct_transfer_base_url}/direct-transfers",
            payload=payload,
            idempotency_key=intent.idempotency_key,
        )
