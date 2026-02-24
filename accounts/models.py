from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Account(models.Model):
    BANK_CHOICES = [
        ('accessbank', 'Access Bank'),
        ('polarisbank', 'Polaris Bank'),
    ]
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('others', 'Others'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    bank_type = models.CharField(max_length=20, choices=BANK_CHOICES)
    account_number = models.CharField(max_length=15, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    bvn = models.CharField(max_length=11)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    is_frozen = models.BooleanField(default=False)
    pin = models.CharField(max_length=4, default='0000')

    class Meta:
        unique_together = ('user', 'bank_type')


    def __str__(self):
        return f"{self.user.username} - {self.bank_type} ({self.account_number})"

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    details = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.account.user.username}"
