import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Account, AuditLog, KycProfile, PaymentIntent, Transaction
from .security import create_two_factor_challenge


@override_settings(
    TRANSACTION_2FA_REQUIRED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FLW_SECRET_KEY="",
    FLW_WEBHOOK_SECRET="test-webhook-secret",
    ALLOW_MANUAL_DEPOSITS=True,
)
class BankingFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="amy",
            password="pass12345",
            email="amy@example.com",
            first_name="Amy",
        )
        self.recipient_user = User.objects.create_user(
            username="ben",
            password="pass12345",
            email="ben@example.com",
            first_name="Ben",
        )
        self.account = Account.objects.create(
            user=self.user,
            bank_type="accessbank",
            account_number="0100000001",
            balance=Decimal("100000.00"),
            bvn="12345678901",
            gender="female",
        )
        self.account.set_pin("1234")
        self.account.save()
        self.recipient = Account.objects.create(
            user=self.recipient_user,
            bank_type="polarisbank",
            account_number="0200000002",
            balance=Decimal("2000.00"),
            bvn="10987654321",
            gender="male",
        )

    def login(self):
        self.assertTrue(self.client.login(username="amy", password="pass12345"))

    def post_json(self, url, payload, **headers):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def challenge_code(self, purpose, method="email", account=None):
        _challenge, code = create_two_factor_challenge(
            self.user,
            purpose=purpose,
            method=method,
            account=account or self.account,
        )
        return code

    def test_signup_creates_user_account_and_default_hashed_pin(self):
        response = self.client.post(reverse("signup"), {
            "username": "newuser",
            "password": "pass12345",
            "first_name": "New",
            "last_name": "User",
            "email": "new@example.com",
            "bank_type": "accessbank",
            "gender": "others",
        })

        self.assertEqual(response.status_code, 302)
        account = Account.objects.get(user__username="newuser")
        self.assertTrue(account.check_pin("0000"))
        self.assertNotEqual(account.pin_hash, "0000")

    def test_dashboard_renders_for_authenticated_user(self):
        self.login()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quick actions")
        self.assertContains(response, "NGN 100,000.00")
        self.assertNotContains(response, "{{ total_balance")
        banned_terms = ["source account", "neural", "protocol", "uplink", "vault", "node", "ledger"]
        rendered = response.content.decode("utf-8").lower()
        for term in banned_terms:
            self.assertNotIn(term, rendered)

    def test_institution_directory_endpoint_returns_banks_and_wallets(self):
        self.login()
        response = self.client.get(reverse("institution_list"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        codes = {item["code"] for item in payload["institutions"]}
        self.assertIn("accessbank", codes)
        self.assertIn("opay", codes)

    def test_kyc_verification_masks_and_hashes_identity_numbers(self):
        self.login()
        response = self.post_json(reverse("verify_kyc"), {
            "bvn": "12345678901",
            "nin": "10987654321",
            "consent": True,
        })

        self.assertEqual(response.status_code, 200, response.content)
        profile = KycProfile.objects.get(user=self.user)
        self.assertEqual(profile.masked_bvn, "123****8901")
        self.assertEqual(profile.masked_nin, "109****4321")
        self.assertNotIn("12345678901", profile.bvn_hash)
        self.assertNotIn("10987654321", profile.nin_hash)
        self.assertTrue(profile.is_verified)

    def test_verified_user_can_discover_and_tick_linked_accounts(self):
        self.login()
        self.post_json(reverse("verify_kyc"), {
            "bvn": "12345678901",
            "nin": "10987654321",
            "consent": True,
        })
        discover = self.post_json(reverse("discover_linked_accounts"), {})
        self.assertEqual(discover.status_code, 200, discover.content)
        discovered_accounts = discover.json()["accounts"]
        self.assertGreater(len(discovered_accounts), 1)
        bank_type = next(item["bank_type"] for item in discovered_accounts if item["bank_type"] != self.account.bank_type)

        link = self.post_json(reverse("link_discovered_accounts"), {
            "bank_types": [bank_type],
        })

        self.assertEqual(link.status_code, 200, link.content)
        self.assertTrue(Account.objects.filter(user=self.user, bank_type=bank_type).exists())
        linked_account = Account.objects.get(user=self.user, bank_type=bank_type)
        self.assertEqual(linked_account.bvn, "123****8901")
        self.assertTrue(linked_account.check_pin("1234"))

    def test_internal_transfer_requires_pin_and_2fa_then_moves_balance_atomically(self):
        self.login()
        code = self.challenge_code("transfer")
        response = self.post_json(reverse("process_transfer"), {
            "source_acc_id": self.account.id,
            "dest_acc_number": self.recipient.account_number,
            "dest_bank_type": self.recipient.bank_type,
            "amount": "15000",
            "pin": "1234",
            "two_factor_method": "email",
            "two_factor_code": code,
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.account.refresh_from_db()
        self.recipient.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("85000.00"))
        self.assertEqual(self.recipient.balance, Decimal("17000.00"))
        self.assertEqual(Transaction.objects.filter(channel="internal").count(), 2)
        self.assertTrue(AuditLog.objects.filter(action="internal_transfer").exists())

    def test_wrong_pin_blocks_money_movement(self):
        self.login()
        code = self.challenge_code("transfer")
        response = self.post_json(reverse("process_transfer"), {
            "source_acc_id": self.account.id,
            "dest_acc_number": self.recipient.account_number,
            "dest_bank_type": self.recipient.bank_type,
            "amount": "15000",
            "pin": "9999",
            "two_factor_method": "email",
            "two_factor_code": code,
        })

        self.assertEqual(response.status_code, 400)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("100000.00"))

    def test_frozen_account_cannot_transfer(self):
        self.account.is_frozen = True
        self.account.save()
        self.login()
        code = self.challenge_code("transfer")
        response = self.post_json(reverse("process_transfer"), {
            "source_acc_id": self.account.id,
            "dest_acc_number": self.recipient.account_number,
            "dest_bank_type": self.recipient.bank_type,
            "amount": "15000",
            "pin": "1234",
            "two_factor_method": "email",
            "two_factor_code": code,
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("frozen", response.json()["message"].lower())

    def test_service_payment_debits_and_records_transaction(self):
        self.login()
        code = self.challenge_code("bill_payment")
        response = self.post_json(reverse("service_payment"), {
            "source_acc_id": self.account.id,
            "amount": "1000",
            "service_type": "airtime",
            "target": "08031234567",
            "pin": "1234",
            "two_factor_method": "email",
            "two_factor_code": code,
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("99000.00"))
        self.assertTrue(PaymentIntent.objects.filter(intent_type="bill_payment", status="succeeded").exists())

    def test_wallet_funding_manual_dev_mode_credits_account(self):
        self.login()
        response = self.post_json(reverse("process_deposit"), {
            "account_id": self.account.id,
            "amount": "2500",
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("102500.00"))
        self.assertTrue(PaymentIntent.objects.filter(intent_type="wallet_funding", status="succeeded").exists())

    def test_flutterwave_webhook_is_idempotent_for_wallet_funding(self):
        intent = PaymentIntent.objects.create(
            user=self.user,
            account=self.account,
            intent_type="wallet_funding",
            amount=Decimal("5000.00"),
            status="processing",
            reference="NB-WEBHOOK-1",
        )
        payload = {
            "event": "charge.completed",
            "data": {
                "id": 123,
                "tx_ref": intent.reference,
                "status": "successful",
                "amount": "5000.00",
                "currency": "NGN",
                "flw_ref": "FLW123",
            },
        }

        for _ in range(2):
            response = self.post_json(
                reverse("flutterwave_webhook"),
                payload,
                HTTP_VERIF_HASH="test-webhook-secret",
            )
            self.assertEqual(response.status_code, 200)

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("105000.00"))
        self.assertEqual(Transaction.objects.filter(channel="deposit", amount=Decimal("5000.00")).count(), 1)

    def test_bad_flutterwave_signature_is_rejected(self):
        response = self.post_json(
            reverse("flutterwave_webhook"),
            {"event": "charge.completed", "data": {}},
            HTTP_VERIF_HASH="bad-secret",
        )
        self.assertEqual(response.status_code, 401)

    def test_health_check(self):
        response = self.client.get(reverse("health_check"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
