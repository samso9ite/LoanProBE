# serializers.py
"""
Serializers for the LoanPro API.

This module contains all serializers used for data validation, serialization,
and deserialization in the LoanPro loan management system. Each serializer
includes comprehensive validation, error handling, and documentation.

Serializers included:
- UserSerializer: User data serialization
- DocumentSerializer: Document management
- CustomerDetailSerializer: Customer detail view
- CustomerCreateSerializer: Customer registration
- LoanSerializer: Loan data serialization
- LoanCreateSerializer: Loan application
- PaymentSerializer: Payment tracking
- OTPSerializer: OTP generation
- OTPVerifySerializer: OTP verification
- LoginSerializer: User authentication
- CreditScoreBreakdownSerializer: Credit score analysis
- DashboardStatsSerializer: Dashboard statistics
- CustomerStatsSerializer: Customer statistics
- AuditLogSerializer: Audit trail
"""

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, Customer, Document, Loan, Payment, OTPVerification, AuditLog, KYCVerification
import random
from datetime import datetime, timedelta

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model data.
    
    Used for displaying user information in API responses.
    Excludes sensitive fields like password and includes role-based information.
    
    Example Response:
    {
        "id": 1,
        "username": "john_doe",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "role": "customer",
        "phone_number": "+1234567890",
        "is_phone_verified": true,
        "created_at": "2024-01-15T10:30:00Z"
    }
    """
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'role', 'phone_number', 'is_phone_verified', 'created_at']
        read_only_fields = ['id', 'created_at', 'is_phone_verified']

class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for Document model data.
    
    Handles document upload and verification status.
    Includes uploader information for audit purposes.
    
    Example Response:
    {
        "id": 1,
        "document_type": "id_card",
        "file_path": "/documents/customer_123/id_card_20240115.pdf",
        "uploaded_at": "2024-01-15T14:20:00Z",
        "uploaded_by": 2,
        "uploaded_by_name": "Jane Smith",
        "is_verified": true
    }
    """
    
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = Document
        fields = ['id', 'document_type', 'file_path', 'uploaded_at', 
                 'uploaded_by', 'uploaded_by_name', 'is_verified']
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']

class CustomerDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Customer model.
    
    Provides comprehensive customer information including user details,
    account information, credit score, and associated documents.
    Used for customer profile views and detailed API responses.
    
    Example Response:
    {
        "id": 1,
        "user": {
            "id": 1,
            "username": "john_doe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "customer",
            "phone_number": "+1234567890",
            "is_phone_verified": true,
            "created_at": "2024-01-15T10:30:00Z"
        },
        "account_number": "ACC-2024-001",
        "account_type": "individual",
        "account_type_display": "Individual",
        "tier": "bronze",
        "tier_display": "Bronze",
        "credit_score": 720,
        "current_borrow_limit": 50000.00,
        "address": "123 Main St, City, State 12345",
        "is_address_verified": true,
        "created_by": 2,
        "created_by_name": "Jane Smith",
        "documents": [
            {
                "id": 1,
                "document_type": "id_card",
                "file_path": "/documents/customer_123/id_card.pdf",
                "uploaded_at": "2024-01-15T14:20:00Z",
                "uploaded_by": 2,
                "uploaded_by_name": "Jane Smith",
                "is_verified": true
            }
        ],
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T15:45:00Z"
    }
    """
    
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
    """
    Serializer for creating new customers.
    
    Handles customer registration with comprehensive validation.
    Creates both User and Customer records in a single transaction.
    Includes detailed error messages for all validation scenarios.
    
    Example Request:
    {
        "username": "john_doe",
        "password": "SecurePass123!",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone_number": "+1234567890",
        "account_type": "individual",
        "address": "123 Main St, City, State 12345"
    }
    
    Example Response (Success):
    {
        "id": 1,
        "account_number": "ACC-2024-001",
        "account_type": "individual",
        "tier": "bronze",
        "credit_score": 600,
        "current_borrow_limit": 10000.00,
        "address": "123 Main St, City, State 12345",
        "is_address_verified": false,
        "created_at": "2024-01-15T10:30:00Z"
    }
    
    Example Response (Validation Error):
    {
        "username": ["Username 'john_doe' is already taken. Please choose a different username."],
        "email": ["Email address 'john@example.com' is already registered."],
        "phone_number": ["Phone number format is invalid. Use format: +1234567890"]
    }
    """
    
    # User fields with improved validation messages
    username = serializers.CharField(
        write_only=True,
        min_length=3,
        max_length=150,
        error_messages={
            'required': 'Username is required to create a customer account.',
            'blank': 'Username cannot be empty.',
            'min_length': 'Username must be at least 3 characters long.',
            'max_length': 'Username cannot exceed 150 characters.'
        }
    )
    password = serializers.CharField(
        write_only=True, 
        validators=[validate_password],
        error_messages={
            'required': 'Password is required to create a customer account.',
            'blank': 'Password cannot be empty.'
        }
    )
    email = serializers.EmailField(
        write_only=True,
        error_messages={
            'required': 'Email address is required to create a customer account.',
            'blank': 'Email address cannot be empty.',
            'invalid': 'Please enter a valid email address.'
        }
    )
    first_name = serializers.CharField(
        write_only=True,
        min_length=1,
        max_length=30,
        error_messages={
            'required': 'First name is required to create a customer account.',
            'blank': 'First name cannot be empty.',
            'max_length': 'First name cannot exceed 30 characters.'
        }
    )
    last_name = serializers.CharField(
        write_only=True,
        min_length=1,
        max_length=30,
        error_messages={
            'required': 'Last name is required to create a customer account.',
            'blank': 'Last name cannot be empty.',
            'max_length': 'Last name cannot exceed 30 characters.'
        }
    )
    phone_number = serializers.CharField(
        write_only=True,
        min_length=10,
        max_length=15,
        error_messages={
            'required': 'Phone number is required to create a customer account.',
            'blank': 'Phone number cannot be empty.',
            'min_length': 'Phone number must be at least 10 digits long.',
            'max_length': 'Phone number cannot exceed 15 characters.'
        }
    )
    
    class Meta:
        model = Customer
        fields = ['username', 'password', 'email', 'first_name', 'last_name', 
                 'phone_number', 'account_type', 'address']
        error_messages = {
            'account_type': {
                'required': 'Account type is required. Choose either "individual" or "business".',
                'invalid_choice': 'Account type must be either "individual" or "business".'
            },
            'address': {
                'required': 'Physical address is required to create a customer account.',
                'blank': 'Address cannot be empty.'
            }
        }
        
    def validate_username(self, value):
        """
        Validate username uniqueness and format.
        
        Args:
            value (str): Username to validate
            
        Returns:
            str: Validated username
            
        Raises:
            ValidationError: If username exists or format is invalid
        """
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                f"Username '{value}' is already taken. Please choose a different username."
            )
        
        if not value.replace('_', '').replace('-', '').isalnum():
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, underscores, and hyphens."
            )
        
        return value
    
    def validate_email(self, value):
        """
        Validate email uniqueness.
        
        Args:
            value (str): Email to validate
            
        Returns:
            str: Validated email
            
        Raises:
            ValidationError: If email already exists
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                f"Email address '{value}' is already registered."
            )
        return value
    
    def validate_phone_number(self, value):
        """
        Validate phone number format.
        
        Args:
            value (str): Phone number to validate
            
        Returns:
            str: Validated phone number
            
        Raises:
            ValidationError: If phone number format is invalid
        """
        import re
        
        # Remove all non-digit characters for validation
        digits_only = re.sub(r'\D', '', value)
        
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise serializers.ValidationError(
                "Phone number must contain between 10 and 15 digits."
            )
        
        # Check if phone number already exists
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "Phone number is already registered."
            )
        
        # Basic format validation (should start with + for international)
        if not value.startswith('+') and len(digits_only) > 10:
            raise serializers.ValidationError(
                "Phone number format is invalid. Use format: +1234567890"
            )
        
        return value
    
    def validate(self, attrs):
        """
        Perform cross-field validation.
        
        Args:
            attrs (dict): All field values
            
        Returns:
            dict: Validated attributes
            
        Raises:
            ValidationError: If required fields are missing
        """
        required_fields = ['username', 'password', 'email', 'first_name', 'last_name', 'phone_number']
        missing_fields = [field for field in required_fields if not attrs.get(field)]
        
        if missing_fields:
            raise serializers.ValidationError({
                'non_field_errors': f"Missing required fields: {', '.join(missing_fields)}"
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Create User and Customer records.
        
        Args:
            validated_data (dict): Validated data
            
        Returns:
            Customer: Created customer instance
        """
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
    """
    Serializer for Loan model data.
    
    Provides comprehensive loan information including customer details,
    approval status, payment calculations, and loan lifecycle data.
    Used for loan listing and detail views.
    
    Example Response:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "customer": 1,
        "customer_name": "John Doe",
        "customer_account": "ACC-2024-001",
        "amount": 50000.00,
        "interest_rate": 12.50,
        "duration_months": 24,
        "status": "active",
        "status_display": "Active",
        "requested_by": 1,
        "requested_by_name": "John Doe",
        "approved_by": 2,
        "approved_by_name": "Jane Smith",
        "disbursed_at": "2024-01-15T10:30:00Z",
        "due_date": "2026-01-15",
        "monthly_payment": 2347.22,
        "total_amount": 56333.28,
        "outstanding_balance": 45000.00,
        "created_at": "2024-01-15T09:00:00Z",
        "updated_at": "2024-01-15T10:30:00Z"
    }
    """
    
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
    """
    Serializer for creating new loan applications.
    
    Handles loan application submission with comprehensive validation.
    Validates loan amounts against customer tier limits and ensures
    reasonable interest rates and durations.
    
    Example Request:
    {
        "customer": 1,
        "amount": 50000.00,
        "interest_rate": 12.50,
        "duration_months": 24
    }
    
    Example Response (Success):
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "customer": 1,
        "amount": 50000.00,
        "interest_rate": 12.50,
        "duration_months": 24,
        "status": "pending",
        "created_at": "2024-01-15T09:00:00Z"
    }
    
    Example Response (Validation Error):
    {
        "amount": ["Loan amount $75,000.00 exceeds your current borrow limit of $50,000.00."],
        "duration_months": ["For loans over $50,000, maximum duration is 60 months."],
        "non_field_errors": ["Customer has an active loan. Only one active loan per customer is allowed."]
    }
    """
    
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=1000.00,
        max_value=1000000.00,
        error_messages={
            'required': 'Loan amount is required to submit a loan application.',
            'invalid': 'Please enter a valid loan amount.',
            'min_value': 'Minimum loan amount is $1,000.00.',
            'max_value': 'Maximum loan amount is $1,000,000.00.',
            'max_digits': 'Loan amount cannot exceed 12 digits total.',
            'max_decimal_places': 'Loan amount can have at most 2 decimal places.'
        }
    )
    
    interest_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0.01,
        max_value=50.00,
        error_messages={
            'required': 'Interest rate is required to submit a loan application.',
            'invalid': 'Please enter a valid interest rate.',
            'min_value': 'Interest rate must be at least 0.01%.',
            'max_value': 'Interest rate cannot exceed 50.00%.'
        }
    )
    
    duration_months = serializers.IntegerField(
        min_value=6,
        max_value=360,
        error_messages={
            'required': 'Loan duration (in months) is required to submit a loan application.',
            'invalid': 'Please enter a valid number of months.',
            'min_value': 'Minimum loan duration is 6 months.',
            'max_value': 'Maximum loan duration is 360 months (30 years).'
        }
    )
    
    class Meta:
        model = Loan
        fields = ['customer', 'amount', 'interest_rate', 'duration_months']
        error_messages = {
            'customer': {
                'required': 'Customer is required to submit a loan application.',
                'invalid': 'Please select a valid customer.'
            }
        }

    def validate(self, data):
        """
        Perform comprehensive loan validation.
        
        Args:
            data (dict): Loan application data
            
        Returns:
            dict: Validated data
            
        Raises:
            ValidationError: If validation fails
        """
        customer = data.get('customer')
        amount = data.get('amount')
        duration_months = data.get('duration_months')
        
        if not customer:
            raise serializers.ValidationError({
                'customer': 'Customer is required to submit a loan application.'
            })
        
        if not amount:
            raise serializers.ValidationError({
                'amount': 'Loan amount is required to submit a loan application.'
            })
        
        if not duration_months:
            raise serializers.ValidationError({
                'duration_months': 'Loan duration is required to submit a loan application.'
            })
        
        # Check if customer account is approved
        if not customer.is_account_approved():
            raise serializers.ValidationError({
                'non_field_errors': 'Customer account must be approved before applying for loans. Please contact support for account approval.'
            })
        
        # Check if customer has completed KYC verification
        if not customer.is_kyc_verified():
            kyc_status = customer.get_kyc_status()
            if kyc_status == 'no_kyc':
                raise serializers.ValidationError({
                    'non_field_errors': 'KYC verification is required before applying for loans. Please complete your BVN and NIN verification.'
                })
            elif kyc_status == 'partial':
                raise serializers.ValidationError({
                    'non_field_errors': 'Incomplete KYC verification. Please complete both BVN and NIN verification before applying for loans.'
                })
            elif kyc_status == 'pending':
                raise serializers.ValidationError({
                    'non_field_errors': 'Your KYC verification is pending review. Please wait for verification to complete before applying for loans.'
                })
            else:
                raise serializers.ValidationError({
                    'non_field_errors': 'KYC verification is required before applying for loans. Please complete your verification process.'
                })
        
        # Check if customer has an active loan
        active_loan = Loan.objects.filter(customer=customer, status='active').first()
        if active_loan:
            raise serializers.ValidationError({
                'non_field_errors': 'Customer has an active loan. Only one active loan per customer is allowed.'
            })
        
        # Check if amount exceeds customer's borrow limit
        if amount > customer.current_borrow_limit:
            raise serializers.ValidationError({
                'amount': f'Loan amount ${amount:,.2f} exceeds your current borrow limit of ${customer.current_borrow_limit:,.2f}.'
            })
        
        # Validate duration based on amount
        if amount > 50000 and duration_months > 60:
            raise serializers.ValidationError({
                'duration_months': 'For loans over $50,000, maximum duration is 60 months.'
            })
        
        if amount <= 10000 and duration_months > 36:
            raise serializers.ValidationError({
                'duration_months': 'For loans $10,000 or less, maximum duration is 36 months.'
            })
        
        return data

class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for Payment model data.
    
    Tracks loan payment information including due dates, payment status,
    and overdue calculations. Used for payment history and tracking.
    
    Example Response:
    {
        "id": 1,
        "loan": "550e8400-e29b-41d4-a716-446655440000",
        "loan_id": "550e8400-e29b-41d4-a716-446655440000",
        "customer_name": "John Doe",
        "amount": 2347.22,
        "due_date": "2024-02-15",
        "paid_date": "2024-02-14T16:30:00Z",
        "status": "paid",
        "is_partial": false,
        "days_overdue": 0,
        "is_on_time": true,
        "created_at": "2024-01-15T10:30:00Z"
    }
    """
    
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
    """
    Serializer for OTP generation requests.
    
    Handles phone number validation and OTP code generation
    for phone number verification during registration.
    
    Example Request:
    {
        "phone_number": "+1234567890"
    }
    
    Example Response:
    {
        "message": "OTP sent successfully to +1234567890",
        "expires_at": "2024-01-15T10:40:00Z"
    }
    """
    
    phone_number = serializers.CharField(max_length=15)
    
    def create(self, validated_data):
        """
        Generate and send OTP code.
        
        Args:
            validated_data (dict): Phone number data
            
        Returns:
            dict: OTP creation result
        """
        phone_number = validated_data['phone_number']
        
        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        
        # Create or update OTP record
        otp_verification, created = OTPVerification.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'otp_code': otp_code,
                'expires_at': datetime.now() + timedelta(minutes=10),
                'is_verified': False
            }
        )
        
        if not created:
            otp_verification.otp_code = otp_code
            otp_verification.expires_at = datetime.now() + timedelta(minutes=10)
            otp_verification.is_verified = False
            otp_verification.save()
        
        return {
            'phone_number': phone_number,
            'otp_code': otp_code,  # In production, don't return this
            'expires_at': otp_verification.expires_at
        }

class OTPVerifySerializer(serializers.Serializer):
    """
    Serializer for OTP verification.
    
    Validates OTP codes against stored values and marks
    phone numbers as verified upon successful validation.
    
    Example Request:
    {
        "phone_number": "+1234567890",
        "otp_code": "123456"
    }
    
    Example Response (Success):
    {
        "message": "Phone number verified successfully",
        "is_verified": true
    }
    
    Example Response (Error):
    {
        "otp_code": ["Invalid OTP code. Please check and try again."],
        "non_field_errors": ["OTP has expired. Please request a new code."]
    }
    """
    
    phone_number = serializers.CharField(
        min_length=10,
        max_length=15,
        error_messages={
            'required': 'Phone number is required to verify OTP.',
            'blank': 'Phone number cannot be empty.',
            'min_length': 'Phone number must be at least 10 digits long.',
            'max_length': 'Phone number cannot exceed 15 characters.'
        }
    )
    otp_code = serializers.CharField(
        min_length=6,
        max_length=6,
        error_messages={
            'required': 'OTP code is required for verification.',
            'blank': 'OTP code cannot be empty.',
            'min_length': 'OTP code must be exactly 6 digits.',
            'max_length': 'OTP code must be exactly 6 digits.'
        }
    )
    
    def validate_otp_code(self, value):
        """
        Validate OTP code format.
        
        Args:
            value (str): OTP code to validate
            
        Returns:
            str: Validated OTP code
            
        Raises:
            ValidationError: If OTP format is invalid
        """
        if not value.isdigit():
            raise serializers.ValidationError(
                "OTP code must contain only digits."
            )
        return value
    
    def validate(self, attrs):
        """
        Validate OTP against stored record.
        
        Args:
            attrs (dict): Phone number and OTP code
            
        Returns:
            dict: Validated attributes
            
        Raises:
            ValidationError: If OTP is invalid or expired
        """
        phone_number = attrs.get('phone_number')
        otp_code = attrs.get('otp_code')
        
        if not phone_number or not otp_code:
            raise serializers.ValidationError({
                'non_field_errors': 'Both phone number and OTP code are required.'
            })
        
        try:
            otp_verification = OTPVerification.objects.get(phone_number=phone_number)
        except OTPVerification.DoesNotExist:
            raise serializers.ValidationError({
                'phone_number': 'No OTP found for this phone number. Please request a new OTP.'
            })
        
        if otp_verification.is_verified:
            raise serializers.ValidationError({
                'non_field_errors': 'Phone number is already verified.'
            })
        
        if otp_verification.expires_at < datetime.now():
            raise serializers.ValidationError({
                'non_field_errors': 'OTP has expired. Please request a new code.'
            })
        
        if otp_verification.otp_code != otp_code:
            raise serializers.ValidationError({
                'otp_code': 'Invalid OTP code. Please check and try again.'
            })
        
        return attrs
    
    def validate(self, data):
        """
        Mark OTP as verified and update user record.
        
        Args:
            data (dict): Validated data
            
        Returns:
            dict: Verification result
        """
        phone_number = data['phone_number']
        
        # Mark OTP as verified
        otp_verification = OTPVerification.objects.get(phone_number=phone_number)
        otp_verification.is_verified = True
        otp_verification.save()
        
        # Update user's phone verification status
        try:
            user = User.objects.get(phone_number=phone_number)
            user.is_phone_verified = True
            user.save()
        except User.DoesNotExist:
            pass  # User might not exist yet during registration
        
        return {
            'phone_number': phone_number,
            'is_verified': True,
            'message': 'Phone number verified successfully'
        }

class LoginSerializer(serializers.Serializer):
    """
    Serializer for user authentication.
    
    Validates user credentials and returns authentication tokens.
    Supports both username and email login.
    
    Example Request:
    {
        "username": "john_doe",
        "password": "SecurePass123!"
    }
    
    Example Response (Success):
    {
        "user": {
            "id": 1,
            "username": "john_doe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "customer"
        },
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "message": "Login successful"
    }
    
    Example Response (Error):
    {
        "non_field_errors": ["Invalid username or password. Please check your credentials and try again."]
    }
    """
    
    username = serializers.CharField(
        min_length=3,
        max_length=150,
        error_messages={
            'required': 'Username is required to log in.',
            'blank': 'Username cannot be empty.',
            'min_length': 'Username must be at least 3 characters long.',
            'max_length': 'Username cannot exceed 150 characters.'
        }
    )
    password = serializers.CharField(
        min_length=1,
        error_messages={
            'required': 'Password is required to log in.',
            'blank': 'Password cannot be empty.'
        }
    )
    
    def validate(self, attrs):
        """
        Validate user credentials.
        
        Args:
            attrs (dict): Username and password
            
        Returns:
            dict: Validated attributes with user
            
        Raises:
            ValidationError: If credentials are invalid
        """
        username = attrs.get('username')
        password = attrs.get('password')
        
        if not username or not password:
            raise serializers.ValidationError({
                'non_field_errors': 'Both username and password are required.'
            })
        
        # Try to authenticate user
        user = authenticate(username=username, password=password)
        
        if not user:
            # Try with email as username
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if not user:
            raise serializers.ValidationError({
                'non_field_errors': 'Invalid username or password. Please check your credentials and try again.'
            })
        
        if not user.is_active:
            raise serializers.ValidationError({
                'non_field_errors': 'User account is disabled. Please contact support.'
            })
        
        attrs['user'] = user
        return attrs
    
    def validate(self, data):
        """
        Return user data for successful authentication.
        
        Args:
            data (dict): Validated data
            
        Returns:
            dict: User authentication data
        """
        return {
            'user': data['user'],
            'message': 'Login successful'
        }

class CreditScoreBreakdownSerializer(serializers.Serializer):
    """
    Serializer for credit score breakdown analysis.
    
    Provides detailed breakdown of credit score calculation
    including all contributing factors and penalties.
    
    Example Response:
    {
        "current_score": 720,
        "base_score": 600,
        "on_time_payment_factor": 80,
        "loan_history_factor": 40,
        "tier_factor": 20,
        "late_payment_penalty": -20,
        "total_loans": 5,
        "on_time_payments": 48,
        "late_payments": 2
    }
    """
    
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
    """
    Serializer for dashboard statistics.
    
    Provides comprehensive system-wide statistics for
    administrative dashboard views.
    
    Example Response:
    {
        "total_customers": 1250,
        "total_loans": 3420,
        "active_loans": 892,
        "pending_loans": 45,
        "total_amount_disbursed": 15750000.00,
        "total_amount_collected": 8920000.00,
        "average_credit_score": 685.50
    }
    """
    
    total_customers = serializers.IntegerField()
    total_loans = serializers.IntegerField()
    active_loans = serializers.IntegerField()
    pending_loans = serializers.IntegerField()
    total_amount_disbursed = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_amount_collected = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_credit_score = serializers.DecimalField(max_digits=5, decimal_places=2)

class CustomerStatsSerializer(serializers.Serializer):
    """
    Serializer for individual customer statistics.
    
    Provides customer-specific loan and payment statistics
    for customer dashboard and profile views.
    
    Example Response:
    {
        "total_loans": 3,
        "active_loans": 1,
        "completed_loans": 2,
        "total_borrowed": 125000.00,
        "total_repaid": 89500.00,
        "outstanding_balance": 35500.00,
        "next_payment_due": "2024-02-15",
        "next_payment_amount": 2347.22
    }
    """
    
    total_loans = serializers.IntegerField()
    active_loans = serializers.IntegerField()
    completed_loans = serializers.IntegerField()
    total_borrowed = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_repaid = serializers.DecimalField(max_digits=12, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    next_payment_due = serializers.DateField(allow_null=True)
    next_payment_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)

class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for audit log entries.
    
    Tracks all system actions for compliance and security purposes.
    Includes user information and detailed action descriptions.
    
    Example Response:
    {
        "id": 1,
        "user": 2,
        "user_name": "Jane Smith",
        "action": "loan_approved",
        "action_display": "Loan Approved",
        "model_name": "Loan",
        "object_id": "550e8400-e29b-41d4-a716-446655440000",
        "details": "Approved loan application for $50,000",
        "timestamp": "2024-01-15T10:30:00Z",
        "ip_address": "192.168.1.100"
    }
    """
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_name', 'action', 'action_display', 
                 'model_name', 'object_id', 'details', 'timestamp', 'ip_address']
        read_only_fields = ['id', 'timestamp']

class CustomerSelfRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for customer self-registration.
    
    Allows customers to register themselves with basic information.
    Creates both User and Customer records with pending approval status.
    
    Example Request:
    {
        "username": "johndoe",
        "password": "SecurePass123!",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone_number": "+1234567890",
        "account_type": "individual",
        "address": "123 Main St, City, State"
    }
    
    Example Success Response:
    {
        "id": 1,
        "user": {
            "id": 1,
            "username": "johndoe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "phone_number": "+1234567890"
        },
        "account_number": "1234567890",
        "account_type": "individual",
        "approval_status": "pending",
        "message": "Registration successful. Your account is pending approval."
    }
    
    Example Validation Error Response:
    {
        "username": ["A user with that username already exists."],
        "email": ["User with this email already exists."],
        "phone_number": ["User with this phone number already exists."]
    }
    """
    
    # User fields
    username = serializers.CharField(
        write_only=True,
        min_length=3,
        max_length=150,
        error_messages={
            'required': 'Username is required for registration.',
            'blank': 'Username cannot be empty.',
            'min_length': 'Username must be at least 3 characters long.',
            'max_length': 'Username cannot exceed 150 characters.'
        }
    )
    password = serializers.CharField(
        write_only=True, 
        validators=[validate_password],
        error_messages={
            'required': 'Password is required for registration.',
            'blank': 'Password cannot be empty.'
        }
    )
    email = serializers.EmailField(
        write_only=True,
        error_messages={
            'required': 'Email address is required for registration.',
            'blank': 'Email address cannot be empty.',
            'invalid': 'Please enter a valid email address.'
        }
    )
    first_name = serializers.CharField(
        write_only=True,
        min_length=1,
        max_length=30,
        error_messages={
            'required': 'First name is required for registration.',
            'blank': 'First name cannot be empty.',
            'max_length': 'First name cannot exceed 30 characters.'
        }
    )
    last_name = serializers.CharField(
        write_only=True,
        min_length=1,
        max_length=30,
        error_messages={
            'required': 'Last name is required for registration.',
            'blank': 'Last name cannot be empty.',
            'max_length': 'Last name cannot exceed 30 characters.'
        }
    )
    phone_number = serializers.CharField(
        write_only=True,
        min_length=10,
        max_length=15,
        error_messages={
            'required': 'Phone number is required for registration.',
            'blank': 'Phone number cannot be empty.',
            'min_length': 'Phone number must be at least 10 digits long.',
            'max_length': 'Phone number cannot exceed 15 characters.'
        }
    )
    
    # Customer fields
    account_type = serializers.ChoiceField(
        choices=Customer.ACCOUNT_TYPE_CHOICES,
        error_messages={
            'required': 'Account type is required. Choose either "individual" or "business".',
            'invalid_choice': 'Account type must be either "individual" or "business".'
        }
    )
    address = serializers.CharField(
        error_messages={
            'required': 'Physical address is required for registration.',
            'blank': 'Address cannot be empty.'
        }
    )
    
    # Read-only fields for response
    user = UserSerializer(read_only=True)
    message = serializers.CharField(read_only=True)

    class Meta:
        model = Customer
        fields = ['username', 'password', 'email', 'first_name', 'last_name', 
                 'phone_number', 'account_type', 'address', 'id', 'user', 
                 'account_number', 'approval_status', 'message']
        read_only_fields = ['id', 'account_number', 'approval_status']

    def validate_username(self, value):
        """
        Validate that the username is unique.
        
        Args:
            value (str): Username to validate
            
        Returns:
            str: Validated username
            
        Raises:
            ValidationError: If username already exists
        """
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with that username already exists."
            )
        return value

    def validate_email(self, value):
        """
        Validate that the email is unique.
        
        Args:
            value (str): Email to validate
            
        Returns:
            str: Validated email
            
        Raises:
            ValidationError: If email already exists
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "User with this email already exists."
            )
        return value

    def validate_phone_number(self, value):
        """
        Validate that the phone number is unique and properly formatted.
        
        Args:
            value (str): Phone number to validate
            
        Returns:
            str: Validated phone number
            
        Raises:
            ValidationError: If phone number already exists or is invalid
        """
        import re
        
        # Remove any non-digit characters for validation
        digits_only = re.sub(r'\D', '', value)
        
        if len(digits_only) < 10:
            raise serializers.ValidationError(
                "Phone number must contain at least 10 digits."
            )
        
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "User with this phone number already exists."
            )
        
        return value

    def create(self, validated_data):
        """
        Create a new customer with self-registration.
        
        Creates both User and Customer records. The customer account
        will have pending approval status and no staff assignment.
        
        Args:
            validated_data (dict): Validated registration data
            
        Returns:
            Customer: Created customer instance with user data
        """
        # Extract user data
        user_data = {
            'username': validated_data.pop('username'),
            'email': validated_data.pop('email'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'phone_number': validated_data.pop('phone_number'),
            'role': 'customer'
        }
        password = validated_data.pop('password')
        
        # Create user
        user = User.objects.create_user(
            password=password,
            **user_data
        )
        
        # Create customer with pending approval
        customer = Customer.objects.create(
            user=user,
            approval_status='pending',  # Self-registered customers need approval
            **validated_data
        )
        
        # Add success message
        customer.message = "Registration successful. Your account is pending approval."
        
        return customer


class StaffCustomerRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for staff to register customers on their behalf.
    
    Allows staff members to register customers with automatic approval
    and immediate assignment to the registering staff member.
    
    Example Request:
    {
        "username": "johndoe",
        "password": "SecurePass123!",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone_number": "+1234567890",
        "account_type": "individual",
        "address": "123 Main St, City, State",
        "tier": "bronze"
    }
    
    Example Success Response:
    {
        "id": 1,
        "user": {
            "id": 1,
            "username": "johndoe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "phone_number": "+1234567890"
        },
        "account_number": "1234567890",
        "account_type": "individual",
        "tier": "bronze",
        "approval_status": "approved",
        "assigned_staff": 2,
        "assigned_staff_name": "Jane Smith",
        "message": "Customer registered successfully and assigned to you."
    }
    """
    
    # User fields
    username = serializers.CharField(
        write_only=True,
        min_length=3,
        max_length=150,
        error_messages={
            'required': 'Username is required for registration.',
            'blank': 'Username cannot be empty.',
            'min_length': 'Username must be at least 3 characters long.',
            'max_length': 'Username cannot exceed 150 characters.'
        }
    )
    password = serializers.CharField(
        write_only=True, 
        validators=[validate_password],
        error_messages={
            'required': 'Password is required for registration.',
            'blank': 'Password cannot be empty.'
        }
    )
    email = serializers.EmailField(
        write_only=True,
        error_messages={
            'required': 'Email address is required for registration.',
            'blank': 'Email address cannot be empty.',
            'invalid': 'Please enter a valid email address.'
        }
    )
    first_name = serializers.CharField(
        write_only=True,
        min_length=1,
        max_length=30,
        error_messages={
            'required': 'First name is required for registration.',
            'blank': 'First name cannot be empty.',
            'max_length': 'First name cannot exceed 30 characters.'
        }
    )
    last_name = serializers.CharField(
        write_only=True,
        min_length=1,
        max_length=30,
        error_messages={
            'required': 'Last name is required for registration.',
            'blank': 'Last name cannot be empty.',
            'max_length': 'Last name cannot exceed 30 characters.'
        }
    )
    phone_number = serializers.CharField(
        write_only=True,
        min_length=10,
        max_length=15,
        error_messages={
            'required': 'Phone number is required for registration.',
            'blank': 'Phone number cannot be empty.',
            'min_length': 'Phone number must be at least 10 digits long.',
            'max_length': 'Phone number cannot exceed 15 characters.'
        }
    )
    
    # Customer fields
    account_type = serializers.ChoiceField(
        choices=Customer.ACCOUNT_TYPE_CHOICES,
        error_messages={
            'required': 'Account type is required. Choose either "individual" or "business".',
            'invalid_choice': 'Account type must be either "individual" or "business".'
        }
    )
    tier = serializers.ChoiceField(
        choices=Customer.TIER_CHOICES,
        required=False,
        error_messages={
            'invalid_choice': 'Invalid tier. Choose from: bronze, silver, gold, platinum.'
        }
    )
    address = serializers.CharField(
        error_messages={
            'required': 'Physical address is required for registration.',
            'blank': 'Address cannot be empty.'
        }
    )
    
    # Read-only fields for response
    user = UserSerializer(read_only=True)
    assigned_staff_name = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)

    class Meta:
        model = Customer
        fields = ['username', 'password', 'email', 'first_name', 'last_name', 
                 'phone_number', 'account_type', 'tier', 'address', 'id', 'user', 
                 'account_number', 'approval_status', 'assigned_staff', 
                 'assigned_staff_name', 'message']
        read_only_fields = ['id', 'account_number', 'approval_status', 'assigned_staff']

    def validate_username(self, value):
        """
        Validate that the username is unique.
        
        Args:
            value (str): Username to validate
            
        Returns:
            str: Validated username
            
        Raises:
            ValidationError: If username already exists
        """
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with that username already exists."
            )
        return value

    def validate_email(self, value):
        """
        Validate that the email is unique.
        
        Args:
            value (str): Email to validate
            
        Returns:
            str: Validated email
            
        Raises:
            ValidationError: If email already exists
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "User with this email already exists."
            )
        return value

    def validate_phone_number(self, value):
        """
        Validate that the phone number is unique and properly formatted.
        
        Args:
            value (str): Phone number to validate
            
        Returns:
            str: Validated phone number
            
        Raises:
            ValidationError: If phone number already exists or is invalid
        """
        import re
        
        # Remove any non-digit characters for validation
        digits_only = re.sub(r'\D', '', value)
        
        if len(digits_only) < 10:
            raise serializers.ValidationError(
                "Phone number must contain at least 10 digits."
            )
        
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "User with this phone number already exists."
            )
        
        return value

    def create(self, validated_data):
        """
        Create a new customer registered by staff.
        
        Creates both User and Customer records with automatic approval
        and assignment to the registering staff member.
        
        Args:
            validated_data (dict): Validated registration data
            
        Returns:
            Customer: Created customer instance with user data
        """
        # Get the registering staff member from context
        registering_staff = self.context['request'].user
        
        # Extract user data
        user_data = {
            'username': validated_data.pop('username'),
            'email': validated_data.pop('email'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'phone_number': validated_data.pop('phone_number'),
            'role': 'customer'
        }
        password = validated_data.pop('password')
        
        # Create user
        user = User.objects.create_user(
            password=password,
            **user_data
        )
        
        # Create customer with automatic approval and staff assignment
        customer = Customer.objects.create(
            user=user,
            approval_status='approved',  # Staff-registered customers are auto-approved
            assigned_staff=registering_staff,
            assigned_by=registering_staff,
            created_by=registering_staff,
            **validated_data
        )
        
        # Set assignment date
        from django.utils import timezone
        customer.assigned_date = timezone.now()
        customer.save()
        
        # Add success message and staff info
        customer.message = "Customer registered successfully and assigned to you."
        customer.assigned_staff_name = registering_staff.get_full_name()
        
        return customer


class KYCVerificationSerializer(serializers.ModelSerializer):
    """
    Serializer for KYC verification submission and management.
    
    Allows customers to submit BVN and NIN for verification,
    and staff to update verification status.
    
    Example Request (Customer Submission):
    {
        "bvn": "12345678901",
        "nin": "12345678901"
    }
    
    Example Request (Staff Verification):
    {
        "bvn_verified": true,
        "nin_verified": true,
        "verification_status": "verified",
        "verification_notes": "All documents verified successfully"
    }
    
    Example Response:
    {
        "id": 1,
        "customer": 1,
        "customer_name": "John Doe",
        "bvn": "12345678901",
        "nin": "12345678901",
        "bvn_verified": true,
        "nin_verified": true,
        "verification_status": "verified",
        "verification_progress": 100,
        "verified_by": 2,
        "verified_by_name": "Jane Smith",
        "verification_date": "2023-01-01T12:00:00Z",
        "verification_notes": "All documents verified successfully",
        "created_at": "2023-01-01T10:00:00Z",
        "updated_at": "2023-01-01T12:00:00Z"
    }
    """
    
    customer_name = serializers.CharField(source='customer.user.get_full_name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True)
    verification_progress = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = KYCVerification
        fields = ['id', 'customer', 'customer_name', 'bvn', 'nin', 'bvn_verified', 
                 'nin_verified', 'verification_status', 'verification_progress',
                 'verified_by', 'verified_by_name', 'verification_date', 
                 'verification_notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'customer', 'verification_progress', 'created_at', 'updated_at']
        extra_kwargs = {
            'bvn': {
                'error_messages': {
                    'required': 'BVN is required for KYC verification.',
                    'blank': 'BVN cannot be empty.',
                    'max_length': 'BVN must be exactly 11 digits.',
                    'min_length': 'BVN must be exactly 11 digits.'
                }
            },
            'nin': {
                'error_messages': {
                    'required': 'NIN is required for KYC verification.',
                    'blank': 'NIN cannot be empty.',
                    'max_length': 'NIN must be exactly 11 digits.',
                    'min_length': 'NIN must be exactly 11 digits.'
                }
            },
            'verification_status': {
                'error_messages': {
                    'invalid_choice': 'Invalid verification status. Choose from: pending, in_progress, verified, rejected, incomplete.'
                }
            }
        }

    def validate_bvn(self, value):
        """
        Validate BVN format.
        
        Args:
            value (str): BVN to validate
            
        Returns:
            str: Validated BVN
            
        Raises:
            ValidationError: If BVN format is invalid
        """
        if value and not value.isdigit():
            raise serializers.ValidationError("BVN must contain only digits.")
        
        if value and len(value) != 11:
            raise serializers.ValidationError("BVN must be exactly 11 digits.")
        
        return value

    def validate_nin(self, value):
        """
        Validate NIN format.
        
        Args:
            value (str): NIN to validate
            
        Returns:
            str: Validated NIN
            
        Raises:
            ValidationError: If NIN format is invalid
        """
        if value and not value.isdigit():
            raise serializers.ValidationError("NIN must contain only digits.")
        
        if value and len(value) != 11:
            raise serializers.ValidationError("NIN must be exactly 11 digits.")
        
        return value

    def update(self, instance, validated_data):
        """
        Update KYC verification record.
        
        If verification status is being set to 'verified' and both
        BVN and NIN are verified, automatically set verification date.
        
        Args:
            instance (KYCVerification): KYC instance to update
            validated_data (dict): Validated update data
            
        Returns:
            KYCVerification: Updated KYC instance
        """
        from django.utils import timezone
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Auto-set verification date if fully verified
        if (instance.verification_status == 'verified' and 
            instance.bvn_verified and instance.nin_verified and 
            not instance.verification_date):
            instance.verification_date = timezone.now()
        
        instance.save()
        return instance

class CustomerAssignmentSerializer(serializers.Serializer):
    """
    Serializer for assigning customers to staff members.
    
    Allows higher-level staff to assign customers to relationship officers
    or account officers for customer relationship management.
    
    Example Request:
    {
        "customer_id": 1,
        "staff_id": 2
    }
    
    Example Response:
    {
        "customer_id": 1,
        "customer_name": "John Doe",
        "staff_id": 2,
        "staff_name": "Jane Smith",
        "staff_role": "Relationship Officer",
        "assigned_date": "2023-01-01T12:00:00Z",
        "assigned_by": "Admin User",
        "message": "Customer successfully assigned to staff member."
    }
    """
    
    customer_id = serializers.IntegerField(
        error_messages={
            'required': 'Customer ID is required for assignment.',
            'invalid': 'Please provide a valid customer ID.'
        }
    )
    staff_id = serializers.IntegerField(
        error_messages={
            'required': 'Staff ID is required for assignment.',
            'invalid': 'Please provide a valid staff ID.'
        }
    )
    
    # Read-only response fields
    customer_name = serializers.CharField(read_only=True)
    staff_name = serializers.CharField(read_only=True)
    staff_role = serializers.CharField(read_only=True)
    assigned_date = serializers.DateTimeField(read_only=True)
    assigned_by = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)

    def validate_customer_id(self, value):
        """
        Validate that the customer exists and is approved.
        
        Args:
            value (int): Customer ID to validate
            
        Returns:
            int: Validated customer ID
            
        Raises:
            ValidationError: If customer doesn't exist or is not approved
        """
        try:
            customer = Customer.objects.get(id=value)
            if customer.approval_status != 'approved':
                raise serializers.ValidationError(
                    "Customer must be approved before assignment."
                )
        except Customer.DoesNotExist:
            raise serializers.ValidationError("Customer not found.")
        
        return value

    def validate_staff_id(self, value):
        """
        Validate that the staff member exists and has appropriate role.
        
        Args:
            value (int): Staff ID to validate
            
        Returns:
            int: Validated staff ID
            
        Raises:
            ValidationError: If staff doesn't exist or has invalid role
        """
        try:
            staff = User.objects.get(id=value)
            if staff.role not in ['manager', 'relationship_officer', 'account_officer']:
                raise serializers.ValidationError(
                    "Staff member must be a manager, relationship officer, or account officer."
                )
        except User.DoesNotExist:
            raise serializers.ValidationError("Staff member not found.")
        
        return value

    def create(self, validated_data):
        """
        Assign customer to staff member.
        
        Args:
            validated_data (dict): Validated assignment data
            
        Returns:
            dict: Assignment result with customer and staff details
        """
        customer = Customer.objects.get(id=validated_data['customer_id'])
        staff = User.objects.get(id=validated_data['staff_id'])
        assigned_by_user = self.context['request'].user
        
        # Perform assignment
        customer.assign_to_staff(staff, assigned_by_user)
        
        return {
            'customer_id': customer.id,
            'customer_name': customer.user.get_full_name(),
            'staff_id': staff.id,
            'staff_name': staff.get_full_name(),
            'staff_role': staff.get_role_display(),
            'assigned_date': customer.assigned_date,
            'assigned_by': assigned_by_user.get_full_name(),
            'message': 'Customer successfully assigned to staff member.'
        }