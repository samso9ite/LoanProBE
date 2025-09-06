# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'auth', views.AuthViewSet, basename='auth')
router.register(r'otp', views.OTPViewSet, basename='otp')
router.register(r'customers', views.CustomerViewSet)
router.register(r'documents', views.DocumentViewSet, basename='documents')
router.register(r'loans', views.LoanViewSet, basename='loans')
router.register(r'payments', views.PaymentViewSet, basename='payments')
router.register(r'admin-dashboard', views.AdminDashboardViewSet, basename='admin-dashboard')
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-logs')

urlpatterns = [
    path('', include(router.urls)),
]