# LumoPay

LumoPay is a Django fintech prototype for managing multiple bank and wallet accounts from one place. Users can create an account, link simulated Nigerian bank accounts with BVN/NIN verification, choose which account to pay with, transfer money, buy airtime/data, pay bills, and review transaction history.

## Current Stack

- Django 5.2
- SQLite for local development
- PostgreSQL-ready settings through `DATABASE_URL`
- Flutterwave sandbox-ready payment service layer
- WhiteNoise/static-file support for production

## Local Setup

```powershell
cd 'C:\Users\`Hp\OneDrive\Documents\mybankapp'
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver
```

If `python` is not on PATH, use:

```powershell
& 'C:\Users\`Hp\AppData\Local\Programs\Python\Python313\python.exe' manage.py runserver
```

## Main Features

- Professional LumoPay dashboard with formatted total balance.
- Linked account cards with checkmark-style selection for payments.
- Institution directory for Nigerian banks and fintech wallets.
- BVN/NIN mock verification with masked values and hashes only.
- Transfer, airtime, data, bills, deposit, freeze/unfreeze, PIN reset, and transaction history flows.
- PIN and 2FA checks for money movement.

## Production Direction

- Use Render Blueprint with managed PostgreSQL.
- Keep secrets in environment variables only.
- Replace mock BVN/NIN and linked-account discovery with licensed verification/provider APIs before live use.
- Keep Flutterwave in sandbox until live credentials, compliance, and webhook verification are ready.
