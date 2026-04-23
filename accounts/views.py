import json
import random
import string
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction as db_transaction

from .identity import IdentityError, discover_mock_accounts, verify_customer_identity
from .institutions import INSTITUTION_BY_CODE, INSTITUTIONS, institution_prefix
from .models import Account, Institution, KycProfile, Transaction
from .security import (
    SecurityError,
    create_two_factor_challenge,
    get_security_profile,
    get_totp_uri,
    verify_flutterwave_signature,
)
from .services import (
    BankingError,
    external_transfer,
    handle_flutterwave_webhook,
    initiate_wallet_funding,
    internal_transfer,
    load_json_body,
    service_payment,
    audit,
)


def index(request):
    return render(request, 'accounts/index.html')


def health_check(request):
    return JsonResponse({"status": "ok"})


def user_login(request):
    if request.method == 'POST':
        uname = request.POST.get('username')
        passw = request.POST.get('password')
        user = authenticate(request, username=uname, password=passw)
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')
        messages.error(request, "Invalid credentials. Please try again.")
    return render(request, 'accounts/login.html')


@login_required
def dashboard(request):
    user_accounts = request.user.accounts.select_related("institution").order_by("bank_type", "account_number")
    total_balance = sum(acc.balance for acc in user_accounts)
    transactions = Transaction.objects.filter(account__in=user_accounts).select_related('account').order_by('-timestamp')[:10]
    kyc_profile, _ = KycProfile.objects.get_or_create(user=request.user)

    return render(request, 'accounts/dashboard.html', {
        'accounts': user_accounts,
        'transactions': transactions,
        'total_balance': total_balance,
        'kyc_profile': kyc_profile,
        'institutions': Institution.objects.filter(is_active=True).order_by("name"),
    })


def _ensure_institution(bank_type):
    meta = INSTITUTION_BY_CODE.get(bank_type) or INSTITUTIONS[0]
    institution, _ = Institution.objects.update_or_create(
        code=meta["code"],
        defaults={
            "name": meta["name"],
            "short_name": meta["short_name"],
            "bank_code": meta["bank_code"],
            "account_prefix": meta["prefix"],
            "institution_type": meta["kind"],
            "is_active": True,
        },
    )
    return institution


def _generate_unique_account_number(bank_type):
    prefix = institution_prefix(bank_type)
    while True:
        acct_number = prefix + ''.join(random.choices(string.digits, k=8))
        if not Account.objects.filter(account_number=acct_number).exists():
            return acct_number


def user_signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        uname = request.POST.get('username')
        passw = request.POST.get('password')
        f_name = request.POST.get('first_name')
        l_name = request.POST.get('last_name')
        bank_type = request.POST.get('bank_type', 'accessbank')
        if bank_type not in INSTITUTION_BY_CODE:
            bank_type = 'accessbank'
        gender = request.POST.get('gender', 'others')

        if User.objects.filter(username=uname).exists():
            messages.error(request, "Identity handle already registered.")
            return render(request, 'accounts/signup.html')

        try:
            with db_transaction.atomic():
                user = User.objects.create_user(
                    username=uname,
                    password=passw,
                    first_name=f_name,
                    last_name=l_name,
                    email=request.POST.get('email', ''),
                )
                institution = _ensure_institution(bank_type)
                account = Account(
                    user=user,
                    institution=institution,
                    bank_type=bank_type,
                    account_number=_generate_unique_account_number(bank_type),
                    bvn='',
                    gender=gender,
                    balance=0,
                )
                account.set_pin("0000")
                account.save()
                get_security_profile(user)

                auth_login(request, user)
                messages.success(
                    request,
                    f"Welcome, {f_name or uname}. Your {account.bank_name} account is ready. Default transaction PIN: 0000.",
                )
                return redirect('dashboard')
        except Exception as exc:
            messages.error(request, f"Account creation failed: {exc}")

    return render(request, 'accounts/signup.html')


def user_logout(request):
    auth_logout(request)
    return redirect('index')


@login_required
def lookup_account(request):
    account_number = request.GET.get('account_number')
    bank_type = request.GET.get('bank_type')
    try:
        acc = Account.objects.select_related('user').get(account_number=account_number, bank_type=bank_type)
        return JsonResponse({
            'success': True,
            'owner_name': acc.user.get_full_name() or acc.user.username,
            'bank': acc.bank_name,
        })
    except Account.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Account not found'})


@login_required
def discover_banks(request):
    account_number = request.GET.get('account_number')
    if not account_number:
        return JsonResponse({'success': False, 'message': 'Account number required'})

    accounts = Account.objects.filter(account_number=account_number).select_related("institution")
    bank_list = [
        {
            'type': account.bank_type,
            'name': account.bank_name,
        }
        for account in accounts
    ]
    return JsonResponse({'success': True, 'banks': bank_list})


@login_required
@require_GET
def institution_list(request):
    if not Institution.objects.exists():
        for item in INSTITUTIONS:
            _ensure_institution(item["code"])
    institutions = Institution.objects.filter(is_active=True).order_by("name")
    return JsonResponse({
        "success": True,
        "institutions": [
            {
                "code": institution.code,
                "name": institution.name,
                "short_name": institution.short_name or institution.name,
                "bank_code": institution.bank_code,
                "type": institution.institution_type,
            }
            for institution in institutions
        ],
    })


@login_required
@require_POST
def verify_kyc(request):
    try:
        data = load_json_body(request)
        profile = verify_customer_identity(
            request.user,
            bvn=data.get("bvn"),
            nin=data.get("nin"),
            consent=bool(data.get("consent")),
        )
        audit(request.user, "identity_verified", request=request)
        return JsonResponse({
            "success": True,
            "message": "Identity verified.",
            "masked_bvn": profile.masked_bvn,
            "masked_nin": profile.masked_nin,
            "verified_at": profile.verified_at.strftime("%Y-%m-%d %H:%M:%S"),
        })
    except (IdentityError, json.JSONDecodeError) as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@login_required
@require_POST
def discover_linked_accounts(request):
    try:
        accounts = discover_mock_accounts(request.user)
        return JsonResponse({"success": True, "accounts": accounts})
    except IdentityError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@login_required
@require_POST
def link_discovered_accounts(request):
    try:
        data = load_json_body(request)
        selected = data.get("bank_types") or []
        if isinstance(selected, str):
            selected = [selected]
        if not selected:
            raise IdentityError("Choose at least one account to add.")

        discovered = {item["bank_type"]: item for item in discover_mock_accounts(request.user)}
        missing = [bank_type for bank_type in selected if bank_type not in discovered]
        if missing:
            raise IdentityError("One or more selected accounts cannot be added.")

        profile = request.user.kyc_profile
        first_account = request.user.accounts.order_by("id").first()
        linked = []
        with db_transaction.atomic():
            for bank_type in selected:
                item = discovered[bank_type]
                institution = _ensure_institution(bank_type)
                account = Account(
                    user=request.user,
                    institution=institution,
                    bank_type=bank_type,
                    account_number=item["account_number"],
                    balance=Decimal(item["balance"]),
                    bvn=profile.masked_bvn,
                    gender=first_account.gender if first_account else "others",
                )
                if first_account and first_account.pin_hash:
                    account.pin_hash = first_account.pin_hash
                else:
                    account.set_pin("0000")
                account.save()
                linked.append({
                    "id": account.id,
                    "bank_type": account.bank_type,
                    "bank_name": account.bank_name,
                    "account_number": account.account_number,
                    "balance": str(account.balance),
                })
            audit(request.user, "accounts_linked", request=request, metadata={"count": len(linked)})

        return JsonResponse({"success": True, "accounts": linked, "message": "Accounts added."})
    except (IdentityError, json.JSONDecodeError) as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@login_required
@require_POST
def request_two_factor(request):
    try:
        data = load_json_body(request)
        method = data.get("method", "email")
        purpose = data.get("purpose", "transfer")
        account = None
        if data.get("account_id"):
            account = Account.objects.get(id=data.get("account_id"), user=request.user)
        challenge, code = create_two_factor_challenge(request.user, purpose, method, account)
        response = {
            "success": True,
            "method": method,
            "message": "Verification code prepared." if method == "sms" else "Verification code sent.",
        }
        if challenge:
            response["reference"] = challenge.reference
        if code and request.user.is_staff:
            response["debug_code"] = code
        return JsonResponse(response)
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@login_required
@require_POST
def setup_totp(request):
    profile = get_security_profile(request.user)
    profile.totp_enabled = True
    profile.preferred_2fa_method = "totp"
    profile.save(update_fields=["totp_enabled", "preferred_2fa_method", "updated_at"])
    return JsonResponse({
        "success": True,
        "provisioning_uri": get_totp_uri(request.user),
        "message": "Authenticator app setup is ready.",
    })


@login_required
@require_POST
def process_transfer(request):
    try:
        data = load_json_body(request)
        tx, recipient = internal_transfer(
            user=request.user,
            source_acc_id=data.get('source_acc_id'),
            dest_acc_number=data.get('dest_acc_number'),
            dest_bank_type=data.get('dest_bank_type'),
            amount=data.get('amount'),
            pin=data.get('pin'),
            two_factor_code=data.get('two_factor_code'),
            two_factor_method=data.get('two_factor_method', 'email'),
            request=request,
        )
        return JsonResponse({
            'success': True,
            'message': 'Transfer successful',
            'transaction_id': tx.id,
            'reference': tx.reference,
            'amount': str(tx.amount),
            'recipient': recipient.user.get_full_name() or recipient.user.username,
            'bank': recipient.bank_name,
            'timestamp': tx.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        })
    except (Account.DoesNotExist, BankingError, SecurityError, json.JSONDecodeError) as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@login_required
@require_POST
def process_service_payment(request):
    try:
        data = load_json_body(request)
        intent, tx = service_payment(
            user=request.user,
            source_acc_id=data.get('source_acc_id'),
            amount=data.get('amount'),
            service_type=data.get('service_type', 'airtime'),
            target=data.get('target'),
            pin=data.get('pin'),
            two_factor_code=data.get('two_factor_code'),
            two_factor_method=data.get('two_factor_method', 'email'),
            request=request,
        )
        return JsonResponse({
            'success': True,
            'message': f'{intent.description.capitalize()} successful',
            'amount': str(intent.amount),
            'reference': intent.reference,
            'timestamp': tx.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        })
    except (Account.DoesNotExist, BankingError, SecurityError, json.JSONDecodeError) as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@login_required
@require_POST
def process_deposit(request):
    try:
        data = load_json_body(request)
        intent = initiate_wallet_funding(request.user, data.get('account_id'), data.get('amount'), request=request)
        return JsonResponse({
            'success': intent.status in {'processing', 'succeeded', 'pending'},
            'message': 'Wallet funding initiated' if intent.checkout_url else 'Wallet funding recorded',
            'status': intent.status,
            'amount': str(intent.amount),
            'reference': intent.reference,
            'checkout_url': intent.checkout_url,
        })
    except (Account.DoesNotExist, BankingError, json.JSONDecodeError) as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@login_required
@require_POST
def process_external_transfer(request):
    try:
        data = load_json_body(request)
        intent, tx = external_transfer(
            user=request.user,
            source_acc_id=data.get('source_acc_id'),
            amount=data.get('amount'),
            beneficiary_data=data.get('beneficiary') or {},
            pin=data.get('pin'),
            two_factor_code=data.get('two_factor_code'),
            two_factor_method=data.get('two_factor_method', 'email'),
            request=request,
        )
        return JsonResponse({
            'success': True,
            'message': 'External transfer initiated',
            'status': intent.status,
            'reference': intent.reference,
            'transaction_id': tx.id,
        })
    except (KeyError, Account.DoesNotExist, BankingError, SecurityError, json.JSONDecodeError) as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=500)


@csrf_exempt
@require_POST
def flutterwave_webhook(request):
    raw_body = request.body
    if not verify_flutterwave_signature(raw_body, request.headers):
        return HttpResponse(status=401)
    try:
        payload = json.loads(raw_body.decode('utf-8'))
        event = handle_flutterwave_webhook(
            payload,
            signature=request.headers.get("flutterwave-signature") or request.headers.get("verif-hash") or "",
        )
        return JsonResponse({"success": True, "processed": event.processed})
    except Exception:
        return HttpResponse(status=200)


@require_GET
def flutterwave_callback(request):
    status = request.GET.get("status")
    tx_ref = request.GET.get("tx_ref")
    if status == "successful":
        messages.success(request, f"Payment {tx_ref or ''} is being verified.")
    else:
        messages.error(request, "Payment was not completed.")
    return redirect('dashboard')


@login_required
def get_transaction_history(request):
    user_accounts = request.user.accounts.all()
    transactions = Transaction.objects.filter(account__in=user_accounts).select_related('account').order_by('-timestamp')

    tx_entries = [{
        'id': tx.id,
        'reference': tx.reference,
        'type': tx.transaction_type,
        'status': tx.status,
        'channel': tx.channel,
        'amount': str(tx.amount),
        'details': tx.details,
        'timestamp': tx.timestamp.strftime('%d %b, %H:%M'),
        'bank': tx.account.bank_name,
        'account_number': tx.account.account_number,
    } for tx in transactions]
    return JsonResponse({'success': True, 'transactions': tx_entries})


@login_required
def get_transaction_detail(request, tx_id):
    try:
        tx = Transaction.objects.get(id=tx_id, account__user=request.user)
        return JsonResponse({
            'success': True,
            'id': tx.id,
            'reference': tx.reference,
            'type': tx.transaction_type,
            'status': tx.status,
            'channel': tx.channel,
            'amount': str(tx.amount),
            'details': tx.details,
            'timestamp': tx.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'bank': tx.account.bank_name,
            'account_number': tx.account.account_number,
        })
    except Transaction.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Transaction not found'}, status=404)


@login_required
def accounts_list(request):
    accounts = Account.objects.filter(user=request.user).select_related("institution").order_by("bank_type", "account_number")
    kyc_profile, _ = KycProfile.objects.get_or_create(user=request.user)
    return render(request, 'accounts/accounts_list.html', {'accounts': accounts, 'kyc_profile': kyc_profile})


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
        profile = get_security_profile(user)
        profile.phone_number = request.POST.get('phone_number', profile.phone_number)
        profile.save(update_fields=['phone_number', 'updated_at'])
        messages.success(request, "Profile updated successfully.")
        return redirect('profile')
    return render(request, 'accounts/edit_profile.html')


@login_required
def insights(request):
    return render(request, 'accounts/neuro_ai.html')


@login_required
def neuro_ai(request):
    return redirect('insights')


@login_required
def bills_view(request):
    user_accounts = request.user.accounts.all()
    return render(request, 'accounts/bills.html', {'accounts': user_accounts})


@login_required
@require_POST
def toggle_freeze(request):
    try:
        data = load_json_body(request)
        account = Account.objects.get(id=data.get('account_id'), user=request.user)
        account.is_frozen = not account.is_frozen
        account.save(update_fields=['is_frozen', 'updated_at'])
        audit(request.user, "account_freeze_toggled", account, request, metadata={"is_frozen": account.is_frozen})
        status = "frozen" if account.is_frozen else "unfrozen"
        return JsonResponse({
            'success': True,
            'is_frozen': account.is_frozen,
            'message': f'Account has been {status} successfully.',
        })
    except Account.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Account not found.'}, status=404)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)


@login_required
@require_POST
def reset_pin(request):
    try:
        data = load_json_body(request)
        account = Account.objects.get(id=data.get('account_id'), user=request.user)
        current_pin = data.get('current_pin')
        new_pin = data.get('new_pin')
        confirm_pin = data.get('confirm_pin')

        if not new_pin or len(str(new_pin)) != 4 or not str(new_pin).isdigit():
            return JsonResponse({'success': False, 'message': 'PIN must be exactly 4 digits.'}, status=400)
        if new_pin != confirm_pin:
            return JsonResponse({'success': False, 'message': 'New PINs do not match.'}, status=400)
        if not account.check_pin(current_pin):
            return JsonResponse({'success': False, 'message': 'Current PIN is incorrect.'}, status=400)

        account.set_pin(new_pin)
        account.save(update_fields=['pin_hash', 'updated_at'])
        audit(request.user, "pin_reset", account, request)
        return JsonResponse({'success': True, 'message': 'PIN has been reset successfully.'})
    except Account.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Account not found.'}, status=404)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
