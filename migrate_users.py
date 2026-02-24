import os
import django
import mysql.connector
from decimal import Decimal

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'banking_system.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Account, Transaction

def migrate():
    # MySQL Connection (Matching fav.py)
    try:
        mycon = mysql.connector.connect(
            host='127.0.0.1',
            user="root",
            password="",
            database="banks"
        )
        cursor = mycon.cursor(dictionary=True)
        print("Connected to MySQL 'banks' database.")
    except Exception as e:
        print(f"Error connecting to MySQL: {e}")
        return

    banks = ['accessbank', 'polarisbank']
    
    for bank in banks:
        print(f"Migrating users from {bank}...")
        cursor.execute(f"SELECT * FROM {bank}")
        users_data = cursor.fetchall()
        
        for row in users_data:
            username = row['username']
            # Django usernames must be unique globally
            if User.objects.filter(username=username).exists():
                print(f"Skipping {username} (already exists).")
                continue
            
            # Create Django User
            user = User.objects.create_user(
                username=username,
                password=str(row['password']), # Cast to string to avoid TypeError for numeric passwords
                first_name=row['Firstname'],
                last_name=row['Lastname']
            )
            
            # Create or update associated Account using account_number as the identifier
            Account.objects.update_or_create(
                account_number=row['accountno'],
                defaults={
                    'user': user,
                    'bank_type': bank,
                    'balance': Decimal(str(row['accountbalance'])),
                    'bvn': row['Bvn'],
                    'gender': row['gender']
                }
            )
            print(f"Migrated {username} successfully.")

    # Optional: Migrate Transaction History
    try:
        print("Migrating transactions...")
        cursor.execute("SELECT * FROM transactions")
        transactions = cursor.fetchall()
        for tx in transactions:
            try:
                # Find matching account
                acc = Account.objects.get(user__username=tx['username'], bank_type=tx['bank'])
                Transaction.objects.create(
                    account=acc,
                    transaction_type=tx['transaction_type'],
                    amount=Decimal(str(tx['amount'])),
                    details=tx['details'],
                    timestamp=tx['date']
                )
            except Exception:
                continue
        print("Transactions migrated.")
    except Exception:
        print("No transactions table found or error during tx migration.")

    cursor.close()
    mycon.close()
    print("Migration Complete!")

if __name__ == "__main__":
    migrate()
