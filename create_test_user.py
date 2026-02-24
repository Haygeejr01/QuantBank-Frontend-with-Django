import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'banking_system.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Account

username = 'testverification'
password = 'testpassword123'

if not User.objects.filter(username=username).exists():
    user = User.objects.create_user(username=username, password=password, first_name='Verifier')
    print(f"User {username} created")
    # Create account to ensure dashboard listing is populated
    Account.objects.create(
        user=user, 
        bank_type='accessbank', 
        account_number='9988776655', 
        balance=50000.00
    )
    print("Account created")
else:
    print(f"User {username} exists")
