import accounts.models
import django.contrib.auth.hashers
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def hash_existing_pins(apps, schema_editor):
    Account = apps.get_model('accounts', 'Account')
    for account in Account.objects.all():
        raw_pin = getattr(account, 'pin', None) or '0000'
        account.pin_hash = django.contrib.auth.hashers.make_password(str(raw_pin))
        account.save(update_fields=['pin_hash'])


def create_security_profiles(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserSecurityProfile = apps.get_model('accounts', 'UserSecurityProfile')
    for user in User.objects.all():
        UserSecurityProfile.objects.get_or_create(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_account_is_frozen_account_pin_alter_account_id_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='transaction',
            options={'ordering': ['-timestamp']},
        ),
        migrations.AddField(
            model_name='account',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='account',
            name='pin_hash',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='account',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(hash_existing_pins, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='account',
            name='pin',
        ),
        migrations.AddField(
            model_name='transaction',
            name='balance_after',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='balance_before',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='channel',
            field=models.CharField(choices=[('internal', 'Internal Transfer'), ('deposit', 'Wallet Funding'), ('bill', 'Bill Payment'), ('external_transfer', 'External Transfer'), ('manual', 'Manual Adjustment')], default='internal', max_length=30),
        ),
        migrations.AddField(
            model_name='transaction',
            name='currency',
            field=models.CharField(default='NGN', max_length=3),
        ),
        migrations.AddField(
            model_name='transaction',
            name='failure_reason',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='transaction',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=80, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='transaction',
            name='provider_reference',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='transaction',
            name='reference',
            field=models.CharField(blank=True, max_length=80, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('reversed', 'Reversed')], default='succeeded', max_length=20),
        ),
        migrations.AddField(
            model_name='transaction',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='counterparty_account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='counterparty_transactions', to='accounts.account'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='performed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='performed_transactions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=80)),
                ('target_reference', models.CharField(blank=True, max_length=120)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='accounts.account')),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Beneficiary',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('bank_code', models.CharField(max_length=20)),
                ('bank_name', models.CharField(max_length=120)),
                ('account_number', models.CharField(max_length=20)),
                ('currency', models.CharField(default='NGN', max_length=3)),
                ('provider_metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='beneficiaries', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['bank_name', 'account_number'], 'unique_together': {('user', 'bank_code', 'account_number')}},
        ),
        migrations.CreateModel(
            name='PaymentIntent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intent_type', models.CharField(choices=[('wallet_funding', 'Wallet Funding'), ('bill_payment', 'Bill Payment'), ('external_transfer', 'External Transfer')], max_length=30)),
                ('provider', models.CharField(default='flutterwave', max_length=30)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='NGN', max_length=3)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('reversed', 'Reversed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('reference', models.CharField(default=accounts.models.generate_reference, max_length=80, unique=True)),
                ('idempotency_key', models.CharField(blank=True, max_length=80, null=True, unique=True)),
                ('provider_reference', models.CharField(blank=True, max_length=120)),
                ('checkout_url', models.URLField(blank=True)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('failure_reason', models.CharField(blank=True, max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_intents', to='accounts.account')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_intents', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ProviderEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='flutterwave', max_length=30)),
                ('event_id', models.CharField(max_length=120)),
                ('event_type', models.CharField(max_length=80)),
                ('reference', models.CharField(blank=True, max_length=120)),
                ('signature', models.CharField(blank=True, max_length=255)),
                ('payload', models.JSONField(default=dict)),
                ('processed', models.BooleanField(default=False)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={'ordering': ['-created_at'], 'unique_together': {('provider', 'event_id')}},
        ),
        migrations.CreateModel(
            name='UserSecurityProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('preferred_2fa_method', models.CharField(choices=[('email', 'Email OTP'), ('totp', 'Authenticator App'), ('sms', 'SMS OTP')], default='email', max_length=20)),
                ('email_2fa_enabled', models.BooleanField(default=True)),
                ('totp_enabled', models.BooleanField(default=False)),
                ('sms_enabled', models.BooleanField(default=False)),
                ('totp_secret', models.CharField(blank=True, max_length=64)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='security_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TwoFactorChallenge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(choices=[('email', 'Email OTP'), ('totp', 'Authenticator App'), ('sms', 'SMS OTP')], max_length=20)),
                ('purpose', models.CharField(choices=[('login', 'Login'), ('transfer', 'Transfer'), ('bill_payment', 'Bill Payment'), ('external_transfer', 'External Transfer'), ('pin_reset', 'PIN Reset')], max_length=30)),
                ('code_hash', models.CharField(max_length=128)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('used', 'Used'), ('expired', 'Expired')], default='pending', max_length=20)),
                ('reference', models.CharField(default=accounts.models.generate_reference, max_length=80, unique=True)),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='two_factor_challenges', to='accounts.account')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='two_factor_challenges', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.RunPython(create_security_profiles, migrations.RunPython.noop),
    ]
