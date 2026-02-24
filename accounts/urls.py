from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/lookup/', views.lookup_account, name='lookup_account'),
    path('api/discover-banks/', views.discover_banks, name='discover_banks'),
    path('api/transfer/', views.process_transfer, name='process_transfer'),
    path('api/service-payment/', views.process_service_payment, name='service_payment'),
    path('api/deposit/', views.process_deposit, name='process_deposit'),
    path('api/transaction-history/', views.get_transaction_history, name='transaction_history'),
    path('api/transaction/<int:tx_id>/', views.get_transaction_detail, name='transaction_detail'),
    path('accounts/', views.accounts_list, name='accounts_list'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('neuro-ai/', views.neuro_ai, name='neuro_ai'),
    path('bills/', views.bills_view, name='bills_view'),
    path('api/toggle-freeze/', views.toggle_freeze, name='toggle_freeze'),
    path('api/reset-pin/', views.reset_pin, name='reset_pin'),
]
