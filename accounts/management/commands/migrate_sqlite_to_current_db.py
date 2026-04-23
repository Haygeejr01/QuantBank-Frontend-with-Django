import sqlite3
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Account, Transaction, UserSecurityProfile


class Command(BaseCommand):
    help = "Import users, accounts, and transactions from the legacy db.sqlite3 file into the configured database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="Path to the legacy SQLite database.",
        )

    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.exists():
            raise CommandError(f"SQLite source not found: {source}")

        connection = sqlite3.connect(source)
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        user_map = {}
        account_map = {}

        with transaction.atomic():
            for row in cursor.execute("SELECT * FROM auth_user ORDER BY id"):
                user, _ = User.objects.update_or_create(
                    username=row["username"],
                    defaults={
                        "password": row["password"],
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                        "email": row["email"],
                        "is_staff": bool(row["is_staff"]),
                        "is_active": bool(row["is_active"]),
                        "is_superuser": bool(row["is_superuser"]),
                        "last_login": row["last_login"],
                        "date_joined": row["date_joined"],
                    },
                )
                UserSecurityProfile.objects.get_or_create(user=user)
                user_map[row["id"]] = user

            for row in cursor.execute("SELECT * FROM accounts_account ORDER BY id"):
                user = user_map.get(row["user_id"])
                if not user:
                    continue
                account, _ = Account.objects.update_or_create(
                    account_number=row["account_number"],
                    defaults={
                        "user": user,
                        "bank_type": row["bank_type"],
                        "balance": Decimal(str(row["balance"])),
                        "bvn": row["bvn"],
                        "gender": row["gender"],
                        "is_frozen": bool(row["is_frozen"]) if "is_frozen" in row.keys() else False,
                    },
                )
                if "pin_hash" in row.keys() and row["pin_hash"]:
                    account.pin_hash = row["pin_hash"]
                elif "pin" in row.keys() and row["pin"]:
                    account.set_pin(row["pin"])
                account.save()
                account_map[row["id"]] = account

            for row in cursor.execute("SELECT * FROM accounts_transaction ORDER BY id"):
                account = account_map.get(row["account_id"])
                if not account:
                    continue
                reference = row["reference"] if "reference" in row.keys() and row["reference"] else f"LEGACY-{row['id']}"
                Transaction.objects.update_or_create(
                    reference=reference,
                    defaults={
                        "account": account,
                        "performed_by": account.user,
                        "transaction_type": row["transaction_type"],
                        "amount": Decimal(str(row["amount"])),
                        "details": row["details"],
                        "status": row["status"] if "status" in row.keys() and row["status"] else "succeeded",
                        "channel": row["channel"] if "channel" in row.keys() and row["channel"] else "manual",
                        "provider_reference": row["provider_reference"] if "provider_reference" in row.keys() else "",
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(user_map)} users, {len(account_map)} accounts, and legacy transactions from {source}."
        ))
