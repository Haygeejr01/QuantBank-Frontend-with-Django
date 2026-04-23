import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


INSTITUTIONS = [
    ("accessbank", "Access Bank", "Access", "044", "01", "bank"),
    ("gtbank", "Guaranty Trust Bank", "GTBank", "058", "02", "bank"),
    ("zenithbank", "Zenith Bank", "Zenith", "057", "03", "bank"),
    ("uba", "United Bank for Africa", "UBA", "033", "04", "bank"),
    ("firstbank", "First Bank of Nigeria", "FirstBank", "011", "05", "bank"),
    ("opay", "OPay", "OPay", "100004", "06", "wallet"),
    ("moniepoint", "Moniepoint Microfinance Bank", "Moniepoint", "50515", "07", "wallet"),
    ("kuda", "Kuda Microfinance Bank", "Kuda", "50211", "08", "wallet"),
    ("palmpay", "PalmPay", "PalmPay", "100033", "09", "wallet"),
    ("polarisbank", "Polaris Bank", "Polaris", "076", "10", "bank"),
    ("stanbicibtc", "Stanbic IBTC Bank", "Stanbic", "221", "11", "bank"),
    ("sterlingbank", "Sterling Bank", "Sterling", "232", "12", "bank"),
    ("fidelitybank", "Fidelity Bank", "Fidelity", "070", "13", "bank"),
    ("fcmb", "First City Monument Bank", "FCMB", "214", "14", "bank"),
    ("unionbank", "Union Bank of Nigeria", "Union Bank", "032", "15", "bank"),
    ("wema", "Wema Bank", "Wema", "035", "16", "bank"),
    ("alat", "ALAT by Wema", "ALAT", "035A", "17", "wallet"),
    ("providus", "Providus Bank", "Providus", "101", "18", "bank"),
    ("keystone", "Keystone Bank", "Keystone", "082", "19", "bank"),
    ("ecobank", "Ecobank Nigeria", "Ecobank", "050", "20", "bank"),
    ("standardchartered", "Standard Chartered Bank", "Standard Chartered", "068", "21", "bank"),
    ("unitybank", "Unity Bank", "Unity", "215", "22", "bank"),
    ("jaizbank", "Jaiz Bank", "Jaiz", "301", "23", "bank"),
    ("globusbank", "Globus Bank", "Globus", "103", "24", "bank"),
    ("titantrust", "Titan Trust Bank", "Titan Trust", "102", "25", "bank"),
    ("suntrust", "SunTrust Bank", "SunTrust", "100", "26", "bank"),
    ("tajbank", "TAJBank", "TAJBank", "302", "27", "bank"),
    ("premiumtrust", "PremiumTrust Bank", "PremiumTrust", "105", "28", "bank"),
    ("optimusbank", "Optimus Bank", "Optimus", "107", "29", "bank"),
    ("parallexbank", "Parallex Bank", "Parallex", "104", "30", "bank"),
]


def seed_lumopay_data(apps, schema_editor):
    Institution = apps.get_model("accounts", "Institution")
    Account = apps.get_model("accounts", "Account")
    User = apps.get_model("auth", "User")
    KycProfile = apps.get_model("accounts", "KycProfile")

    institution_map = {}
    for code, name, short_name, bank_code, prefix, kind in INSTITUTIONS:
        institution, _ = Institution.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "short_name": short_name,
                "bank_code": bank_code,
                "account_prefix": prefix,
                "institution_type": kind,
                "is_active": True,
            },
        )
        institution_map[code] = institution

    for account in Account.objects.all():
        institution = institution_map.get(account.bank_type)
        if institution and not account.institution_id:
            account.institution = institution
            account.save(update_fields=["institution"])

    for user in User.objects.all():
        KycProfile.objects.get_or_create(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_production_banking_security"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Institution",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("short_name", models.CharField(blank=True, max_length=40)),
                ("bank_code", models.CharField(blank=True, max_length=20)),
                ("institution_type", models.CharField(choices=[("bank", "Bank"), ("wallet", "Wallet")], default="bank", max_length=20)),
                ("account_prefix", models.CharField(default="99", max_length=4)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="KycProfile",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("masked_bvn", models.CharField(blank=True, max_length=11)),
                ("bvn_hash", models.CharField(blank=True, max_length=128)),
                ("masked_nin", models.CharField(blank=True, max_length=11)),
                ("nin_hash", models.CharField(blank=True, max_length=128)),
                ("consent_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="kyc_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name="account",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accounts", to="accounts.institution"),
        ),
        migrations.AlterField(
            model_name="account",
            name="bank_type",
            field=models.CharField(choices=[(code, name) for code, name, _short, _bank_code, _prefix, _kind in INSTITUTIONS], max_length=40),
        ),
        migrations.AlterField(
            model_name="account",
            name="bvn",
            field=models.CharField(blank=True, max_length=11),
        ),
        migrations.RunPython(seed_lumopay_data, migrations.RunPython.noop),
    ]
