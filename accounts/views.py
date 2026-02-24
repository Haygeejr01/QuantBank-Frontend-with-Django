from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Account, Transaction
from decimal import Decimal
from django.http import JsonResponse
from django.db import transaction as db_transaction
from django.views.decorators.http import require_POST
import json
import random
import string

def index(request):
    return render(request, 'accounts/index.html')

def user_login(request):
    if request.method == 'POST':
        uname = request.POST.get('username')
        passw = request.POST.get('password')
        user = authenticate(request, username=uname, password=passw)
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid credentials. Please try again.")
    return render(request, 'accounts/login.html')

@login_required
def dashboard(request):
    user_accounts = request.user.accounts.all()
    
    # Calculate total balance
    total_balance = sum(acc.balance for acc in user_accounts)
    
    # Fetch transactions for all user accounts
    transactions = Transaction.objects.filter(account__in=user_accounts).order_by('-timestamp')[:10]
    
    return render(request, 'accounts/dashboard.html', {
        'accounts': user_accounts, 
        'transactions': transactions,
        'total_balance': total_balance
    })

def user_signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        uname = request.POST.get('username')
        passw = request.POST.get('password')
        f_name = request.POST.get('first_name')
        l_name = request.POST.get('last_name')
        bank_type = request.POST.get('bank_type', 'accessbank')
        gender = request.POST.get('gender', 'others')

        if User.objects.filter(username=uname).exists():
            messages.error(request, "Identity handle already registered in the neural network.")
            return render(request, 'accounts/signup.html')

        try:
            with db_transaction.atomic():
                # Create Django User
                user = User.objects.create_user(
                    username=uname, 
                    password=passw, 
                    first_name=f_name, 
                    last_name=l_name
                )
                
                # Generate Random Account Number (10 digits)
                # Following user's logic: random choice from list or just random digits
                # Let's generate a 10-digit number starting with a bank prefix
                prefix = '01' if bank_type == 'accessbank' else '02'
                rest = ''.join(random.choices(string.digits, k=8))
                acct_number = prefix + rest
                
                # Ensure uniqueness
                while Account.objects.filter(account_number=acct_number).exists():
                    rest = ''.join(random.choices(string.digits, k=8))
                    acct_number = prefix + rest
                
                # Generate Random BVN (11 digits)
                bvn = ''.join(random.choices(string.digits, k=11))
                
                # Create Bank Account
                Account.objects.create(
                    user=user,
                    bank_type=bank_type,
                    account_number=acct_number,
                    bvn=bvn,
                    gender=gender,
                    balance=0.00 # Initial balance
                )
                
                # Auto-login after signup
                auth_login(request, user)
                messages.success(request, f"Welcome to the network, {f_name}! Your {bank_type.replace('bank', ' bank').capitalize()} account {acct_number} is now active.")
                return redirect('dashboard')
        except Exception as e:
            messages.error(request, f"Neural synchronization failed: {str(e)}")
            
    return render(request, 'accounts/signup.html')

def user_logout(request):
    auth_logout(request)
    return redirect('index')

@login_required
def lookup_account(request):
    account_number = request.GET.get('account_number')
    bank_type = request.GET.get('bank_type')
    try:
        acc = Account.objects.get(account_number=account_number, bank_type=bank_type)
        return JsonResponse({
            'success': True,
            'owner_name': acc.user.get_full_name() or acc.user.username
        })
    except Account.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Account not found'})

@login_required
def discover_banks(request):
    account_number = request.GET.get('account_number')
    if not account_number:
        return JsonResponse({'success': False, 'message': 'Account number required'})
    
    # Find all bank types that have an account with this number
    banks = Account.objects.filter(account_number=account_number).values('bank_type').distinct()
    bank_list = []
    for b in banks:
        # Get the human readable name
        display_name = dict(Account.BANK_CHOICES).get(b['bank_type'], b['bank_type'])
        bank_list.append({
            'type': b['bank_type'],
            'name': display_name
        })
    
    return JsonResponse({
        'success': True,
        'banks': bank_list
    })

@login_required
@require_POST
def process_transfer(request):
    try:
        data = json.loads(request.body)
        source_acc_id = data.get('source_acc_id')
        dest_acc_number = data.get('dest_acc_number')
        dest_bank_type = data.get('dest_bank_type')
        amount = Decimal(str(data.get('amount')))

        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Invalid amount'}, status=400)

        with db_transaction.atomic():
            source_acc = Account.objects.select_for_update().get(id=source_acc_id, user=request.user)
            if source_acc.balance < amount:
                return JsonResponse({'success': False, 'message': 'Insufficient funds'}, status=400)

            try:
                dest_acc = Account.objects.select_for_update().get(account_number=dest_acc_number, bank_type=dest_bank_type)
            except Account.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Recipient account not found'}, status=404)
            
            # Perform Transfer
            source_acc.balance -= amount
            dest_acc.balance += amount
            
            source_acc.save()
            dest_acc.save()

            # Record Transactions
            t1 = Transaction.objects.create(
                account=source_acc,
                transaction_type='debit',
                amount=amount,
                details=f"Transfer to {dest_acc.user.get_full_name() or dest_acc.user.username}"
            )
            Transaction.objects.create(
                account=dest_acc,
                transaction_type='credit',
                amount=amount,
                details=f"Transfer from {source_acc.user.get_full_name() or source_acc.user.username}"
            )

        return JsonResponse({
            'success': True, 
            'message': 'Transfer successful',
            'transaction_id': t1.id,
            'amount': str(amount),
            'recipient': dest_acc.user.get_full_name() or dest_acc.user.username,
            'bank': dest_acc.get_bank_type_display(),
            'timestamp': t1.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@require_POST
def process_service_payment(request):
    """Generic handler for Airtime, Data, and Bills"""
    try:
        data = json.loads(request.body)
        source_acc_id = data.get('source_acc_id')
        amount = Decimal(str(data.get('amount')))
        service_type = data.get('service_type') # 'airtime', 'data', 'bills'
        target_identifier = data.get('target') # Phone number or biller code
        
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Invalid amount'}, status=400)

        with db_transaction.atomic():
            source_acc = Account.objects.select_for_update().get(id=source_acc_id, user=request.user)
            if source_acc.balance < amount:
                return JsonResponse({'success': False, 'message': 'Insufficient funds'}, status=400)

            # Deduct balance
            source_acc.balance -= amount
            source_acc.save()

            # Create transaction record
            details = f"{service_type.upper()} settlement: {target_identifier}"
            tx = Transaction.objects.create(
                account=source_acc,
                transaction_type='debit',
                amount=amount,
                details=details
            )

        return JsonResponse({
            'success': True,
            'message': f'{service_type.capitalize()} payment successful',
            'amount': str(amount),
            'timestamp': tx.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@require_POST
def process_deposit(request):
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')
        amount = Decimal(str(data.get('amount')))

        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Invalid amount'}, status=400)

        with db_transaction.atomic():
            acc = Account.objects.select_for_update().get(id=account_id, user=request.user)
            acc.balance += amount
            acc.save()

            tx = Transaction.objects.create(
                account=acc,
                transaction_type='credit',
                amount=amount,
                details=f"Deposit: Direct Settlement"
            )

        return JsonResponse({
            'success': True,
            'message': 'Deposit successful',
            'amount': str(amount),
            'timestamp': tx.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
def get_transaction_history(request):
    user_accounts = request.user.accounts.all()
    transactions = Transaction.objects.filter(account__in=user_accounts).order_by('-timestamp')
    
    tx_entries = []
    for tx in transactions:
        tx_entries.append({
            'id': tx.id,
            'type': tx.transaction_type,
            'amount': str(tx.amount),
            'details': tx.details,
            'timestamp': tx.timestamp.strftime('%d %b, %H:%M'),
            'bank': tx.account.get_bank_type_display(),
            'account_number': tx.account.account_number
        })
    
    return JsonResponse({
        'success': True,
        'transactions': tx_entries
    })

@login_required
def get_transaction_detail(request, tx_id):
    try:
        # User must own the account associated with the transaction
        tx = Transaction.objects.get(id=tx_id, account__user=request.user)
        return JsonResponse({
            'success': True,
            'id': tx.id,
            'type': tx.transaction_type,
            'amount': str(tx.amount),
            'details': tx.details,
            'timestamp': tx.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'bank': tx.account.get_bank_type_display(),
            'account_number': tx.account.account_number
        })
    except Transaction.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Transaction not found'}, status=404)

@login_required
def accounts_list(request):
    accounts = Account.objects.filter(user=request.user)
    return render(request, 'accounts/accounts_list.html', {'accounts': accounts})

@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html')

@login_required
def edit_profile(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, "Neural identity updated successfully.")
        return redirect('profile')
    return render(request, 'accounts/edit_profile.html')

@login_required
def neuro_ai(request):
    return render(request, 'accounts/neuro_ai.html')

@login_required
def bills_view(request):
    user_accounts = request.user.accounts.all()
    return render(request, 'accounts/bills.html', {'accounts': user_accounts})

@login_required
@require_POST
def toggle_freeze(request):
    """Toggle the frozen status of an account"""
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')
        
        account = Account.objects.get(id=account_id, user=request.user)
        account.is_frozen = not account.is_frozen
        account.save()
        
        status = "frozen" if account.is_frozen else "unfrozen"
        return JsonResponse({
            'success': True,
            'is_frozen': account.is_frozen,
            'message': f'Account has been {status} successfully.'
        })
    except Account.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Account not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@require_POST
def reset_pin(request):
    """Reset the PIN for an account"""
    try:
        data = json.loads(request.body)
        account_id = data.get('account_id')
        current_pin = data.get('current_pin')
        new_pin = data.get('new_pin')
        confirm_pin = data.get('confirm_pin')
        
        if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
            return JsonResponse({'success': False, 'message': 'PIN must be exactly 4 digits.'})
        
        if new_pin != confirm_pin:
            return JsonResponse({'success': False, 'message': 'New PINs do not match.'})
        
        account = Account.objects.get(id=account_id, user=request.user)
        
        # Verify current PIN (for first-time users, default is '0000')
        if account.pin != current_pin:
            return JsonResponse({'success': False, 'message': 'Current PIN is incorrect.'})
        
        account.pin = new_pin
        account.save()
        
        return JsonResponse({
            'success': True,
            'message': 'PIN has been reset successfully.'
        })
    except Account.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Account not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
