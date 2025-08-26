# serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, Customer, Document, Loan, Payment, OTPVerification, AuditLog
import random
from datetime import datetime, timedelta

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'role', 'phone_number', 'is_phone_verified', 'created_at']
        read_only_fields = ['id', 'created_at', 'is_phone_verified']

class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = Document
        fields = ['id', 'document_type', 'file_path', 'uploaded_at', 
                 'uploaded_by', 'uploaded_by_name', 'is_verified']
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']

class CustomerDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    
    class Meta:
        model = Customer
        fields = ['id', 'user', 'account_number', 'account_type', 'account_type_display',
                 'tier', 'tier_display', 'credit_score', 'current_borrow_limit',
                 'address', 'is_address_verified', 'created_by', 'created_by_name',
                 'documents', 'created_at', 'updated_at']
        read_only_fields = ['id', 'account_number', 'credit_score', 'current_borrow_limit', 
                          'created_at', 'updated_at', 'created_by']

class CustomerCreateSerializer(serializers.ModelSerializer):
    # User fields
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(write_only=True)
    
    class Meta:
        model = Customer
        fields = ['username', 'password', 'email', 'first_name', 'last_name', 
                 'phone_number', 'account_type', 'address']
        
    def create(self, validated_data):
        # Extract user data
        user_data = {
            'username': validated_data.pop('username'),
            'password': validated_data.pop('password'),
            'email': validated_data.pop('email'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'phone_number': validated_data.pop('phone_number'),
            'role': 'customer'
        }
        
        # Create user
        user = User.objects.create_user(**user_data)
        
        # Create customer
        customer = Customer.objects.create(user=user, **validated_data)
        return customer

class LoanSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.user.get_full_name', read_only=True)
    customer_account = serializers.CharField(source='customer.account_number', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    monthly_payment = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outstanding_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Loan
        fields = ['id', 'customer', 'customer_name', 'customer_account', 'amount', 
                 'interest_rate', 'duration_months', 'status', 'status_display',
                 'requested_by', 'requested_by_name', 'approved_by', 'approved_by_name',
                 'disbursed_at', 'due_date', 'monthly_payment', 'total_amount',
                 'outstanding_balance', 'created_at', 'updated_at']
        read_only_fields = ['id', 'approved_by', 'disbursed_at', 'due_date', 
                          'created_at', 'updated_at']

class LoanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ['customer', 'amount', 'interest_rate', 'duration_months']
        
    def validate(self, data):
        customer = data['customer']
        amount = data['amount']
        
        # Check if customer has active loans
        active_loans = customer.loans.filter(status__in=['active', 'disbursed'])
        if active_loans.exists():
            raise serializers.ValidationError("Customer already has an active loan")
        
        # Check borrowing limit
        if amount > customer.current_borrow_limit:
            raise serializers.ValidationError(
                f"Loan amount exceeds customer's borrowing limit of ₦{customer.current_borrow_limit}"
            )
        
        return data

class PaymentSerializer(serializers.ModelSerializer):
    loan_id = serializers.UUIDField(source='loan.id', read_only=True)
    customer_name = serializers.CharField(source='loan.customer.user.get_full_name', read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    is_on_time = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Payment
        fields = ['id', 'loan', 'loan_id', 'customer_name', 'amount', 'due_date', 
                 'paid_date', 'status', 'is_partial', 'days_overdue', 'is_on_time',
                 'created_at']
        read_only_fields = ['id', 'created_at']

class OTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    
    def create(self, validated_data):
        phone_number = validated_data['phone_number']
        
        # Generate 6-digit OTP
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Set expiry time (5 minutes)
        expires_at = datetime.now() + timedelta(minutes=5)
        
        # Create OTP record
        otp = OTPVerification.objects.create(
            phone_number=phone_number,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        return otp

class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)
    
    def validate(self, data):
        phone_number = data['phone_number']
        otp_code = data['otp_code']
        
        try:
            otp = OTPVerification.objects.get(
                phone_number=phone_number,
                otp_code=otp_code,
                is_verified=False
            )
        except OTPVerification.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP code")
        
        if otp.is_expired():
            raise serializers.ValidationError("OTP has expired")
        
        data['otp_instance'] = otp
        return data

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        username = data['username']
        password = data['password']
        
        if username and password:
            user = authenticate(username=username, password=password)
            if user:
                if user.is_active:
                    data['user'] = user
                    return data
                else:
                    raise serializers.ValidationError("User account is disabled")
            else:
                raise serializers.ValidationError("Invalid credentials")
        else:
            raise serializers.ValidationError("Must include username and password")

class CreditScoreBreakdownSerializer(serializers.Serializer):
    """Serializer for credit score calculation breakdown"""
    current_score = serializers.IntegerField()
    base_score = serializers.IntegerField()
    on_time_payment_factor = serializers.IntegerField()
    loan_history_factor = serializers.IntegerField()
    tier_factor = serializers.IntegerField()
    late_payment_penalty = serializers.IntegerField()
    total_loans = serializers.IntegerField()
    on_time_payments = serializers.IntegerField()
    late_payments = serializers.IntegerField()

class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    total_customers = serializers.IntegerField()
    total_loans = serializers.IntegerField()
    active_loans = serializers.IntegerField()
    pending_loans = serializers.IntegerField()
    total_amount_disbursed = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_amount_collected = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_credit_score = serializers.DecimalField(max_digits=5, decimal_places=2)

class CustomerStatsSerializer(serializers.Serializer):
    """Serializer for customer dashboard statistics"""
    total_loans = serializers.IntegerField()
    active_loans = serializers.IntegerField()
    completed_loans = serializers.IntegerField()
    total_borrowed = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_repaid = serializers.DecimalField(max_digits=12, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    next_payment_due = serializers.DateField(allow_null=True)
    next_payment_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)

class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_name', 'action', 'action_display', 
                 'model_name', 'object_id', 'details', 'timestamp', 'ip_address']
        read_only_fields = ['id', 'timestamp']