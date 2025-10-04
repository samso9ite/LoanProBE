# views.py
"""
LoanPro API Views

This module contains all the API viewsets for the LoanPro loan management system.
It provides endpoints for authentication, customer management, loan processing,
payment tracking, OTP verification, and administrative functions.

The API follows RESTful conventions and includes comprehensive permission controls
based on user roles (Admin, Account Officer, Customer).
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.db.models import Q, Sum, Avg, Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

# Swagger documentation imports
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    User, Customer, Document, Loan, Payment, 
    OTPVerification, AuditLog, KYCVerification
)
from .serializers import (
    UserSerializer, CustomerDetailSerializer, CustomerCreateSerializer,
    DocumentSerializer, LoanSerializer, LoanCreateSerializer, PaymentSerializer,
    OTPSerializer, OTPVerifySerializer, LoginSerializer, CreditScoreBreakdownSerializer,
    DashboardStatsSerializer, CustomerStatsSerializer, AuditLogSerializer,
    CustomerSelfRegistrationSerializer, KYCVerificationSerializer, 
    CustomerAssignmentSerializer, StaffCustomerRegistrationSerializer
)
from .permissions import IsAdmin, IsAccountOfficer, IsCustomer

class AuthViewSet(viewsets.GenericViewSet):
    """
    Authentication ViewSet
    
    Handles user authentication operations including login and logout.
    Provides token-based authentication for API access.
    
    Endpoints:
    - POST /auth/login/ - User login with username/password
    - POST /auth/logout/ - User logout (requires authentication)
    """
    
    @swagger_auto_schema(
        operation_description="Authenticate user and return access token",
        operation_summary="User Login",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Username for authentication',
                    example='john_doe'
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='User password',
                    example='securepassword123'
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="Login successful",
                examples={
                    "application/json": {
                        "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
                        "user": {
                            "id": 1,
                            "username": "john_doe",
                            "email": "john@example.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "role": "customer"
                        },
                        "message": "Login successful"
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid credentials or missing data",
                examples={
                    "application/json": {
                        "username": ["This field is required."],
                        "password": ["This field is required."]
                    }
                }
            )
        },
        tags=['Authentication']
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """
        Authenticate user with username and password.
        
        Returns an authentication token that should be included in the
        Authorization header for subsequent API requests as:
        Authorization: Token <token_key>
        
        Args:
            request: HTTP request containing username and password
            
        Returns:
            Response: Authentication token and user details on success,
                     validation errors on failure
        """
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data,
                'message': 'Login successful'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_description="Logout user and invalidate authentication token",
        operation_summary="User Logout",
        responses={
            200: openapi.Response(
                description="Logout successful",
                examples={
                    "application/json": {
                        "message": "Logout successful"
                    }
                }
            ),
            401: openapi.Response(
                description="Authentication required",
                examples={
                    "application/json": {
                        "detail": "Authentication credentials were not provided."
                    }
                }
            )
        },
        tags=['Authentication']
    )
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """
        Logout the authenticated user.
        
        Invalidates the user's authentication token, requiring them to
        login again for future API access.
        
        Args:
            request: HTTP request with valid authentication token
            
        Returns:
            Response: Success message confirming logout
        """
        try:
            request.user.auth_token.delete()
        except:
            pass
        logout(request)
        return Response({'message': 'Logout successful'})

class OTPViewSet(viewsets.GenericViewSet):
    """
    OTP (One-Time Password) ViewSet
    
    Handles OTP generation and verification for phone number validation.
    Only Account Officers can generate OTPs for customer phone verification.
    
    Endpoints:
    - POST /otp/generate/ - Generate OTP for phone number
    - POST /otp/verify/ - Verify OTP code
    """
    permission_classes = [IsAccountOfficer]
    
    @swagger_auto_schema(
        operation_description="Generate OTP for phone number verification",
        operation_summary="Generate OTP",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone_number'],
            properties={
                'phone_number': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Phone number to send OTP to',
                    example='+2348012345678'
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="OTP generated and sent successfully",
                examples={
                    "application/json": {
                        "message": "OTP sent successfully",
                        "otp_code": "123456",
                        "expires_at": "2024-01-15T10:30:00Z"
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid phone number or missing data",
                examples={
                    "application/json": {
                        "phone_number": ["This field is required."]
                    }
                }
            ),
            403: openapi.Response(
                description="Permission denied - Account Officer role required",
                examples={
                    "application/json": {
                        "detail": "You do not have permission to perform this action."
                    }
                }
            )
        },
        tags=['OTP Verification']
    )
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Generate OTP for phone number verification.
        
        Creates a 6-digit OTP code that expires in 10 minutes.
        In production, this would integrate with an SMS service.
        
        Args:
            request: HTTP request containing phone_number
            
        Returns:
            Response: Success message with OTP details (remove otp_code in production)
        """
        serializer = OTPSerializer(data=request.data)
        if serializer.is_valid():
            otp = serializer.save()
            
            # Here you would integrate with SMS service
            # For now, return the OTP in response (remove in production)
            return Response({
                'message': 'OTP sent successfully',
                'otp_code': otp.otp_code,  # Remove this in production
                'expires_at': otp.expires_at
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_description="Verify OTP code for phone number",
        operation_summary="Verify OTP",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone_number', 'otp_code'],
            properties={
                'phone_number': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Phone number that received the OTP',
                    example='+2348012345678'
                ),
                'otp_code': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='6-digit OTP code',
                    example='123456'
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="OTP verified successfully",
                examples={
                    "application/json": {
                        "message": "OTP verified successfully"
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid OTP, expired OTP, or missing data",
                examples={
                    "application/json": {
                        "non_field_errors": ["Invalid or expired OTP"]
                    }
                }
            ),
            403: openapi.Response(
                description="Permission denied - Account Officer role required",
                examples={
                    "application/json": {
                        "detail": "You do not have permission to perform this action."
                    }
                }
            )
        },
        tags=['OTP Verification']
    )
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify OTP code for phone number.
        
        Validates the OTP code and marks the phone number as verified.
        Updates the user's phone verification status if user exists.
        
        Args:
            request: HTTP request containing phone_number and otp_code
            
        Returns:
            Response: Success message on verification, error on invalid OTP
        """
        serializer = OTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            otp = serializer.validated_data['otp_instance']
            otp.is_verified = True
            otp.save()
            
            # Update user phone verification status
            try:
                user = User.objects.get(phone_number=otp.phone_number)
                user.is_phone_verified = True
                user.save()
            except User.DoesNotExist:
                pass
            
            return Response({'message': 'OTP verified successfully'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CustomerViewSet(viewsets.ModelViewSet):
    """
    Customer Management ViewSet
    
    Provides CRUD operations for customer management with role-based permissions.
    Account Officers can create and view customers, while Admins have full access.
    
    Endpoints:
    - GET /customers/ - List all customers (Admin/Account Officer)
    - POST /customers/ - Create new customer (Account Officer)
    - GET /customers/{id}/ - Retrieve customer details (Admin/Account Officer)
    - PUT/PATCH /customers/{id}/ - Update customer (Admin only)
    - DELETE /customers/{id}/ - Delete customer (Admin only)
    - POST /customers/{id}/verify_address/ - Verify customer address (Admin only)
    - GET /customers/{id}/credit_score_breakdown/ - Get credit score details
    - GET /customers/{id}/dashboard_stats/ - Get customer statistics
    """
    queryset = Customer.objects.all()
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.
        
        Returns:
            CustomerCreateSerializer for create action
            CustomerDetailSerializer for all other actions
        """
        if self.action == 'create':
            return CustomerCreateSerializer
        return CustomerDetailSerializer
    
    def get_permissions(self):
        """
        Return appropriate permissions based on action.
        
        Returns:
            List of permission classes based on the current action
        """
        if self.action == 'create':
            return [IsAccountOfficer()]
        elif self.action in ['list', 'retrieve']:
            from rest_framework.permissions import OR
            return [OR(IsAccountOfficer(), IsAdmin())]
        elif self.action in ['update', 'partial_update']:
            return [IsAdmin()]
        else:
            return [IsAdmin()]
    
    @swagger_auto_schema(
        operation_description="Create a new customer account",
        operation_summary="Create Customer",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password', 'email', 'first_name', 'last_name', 'phone_number', 'account_type', 'address'],
            properties={
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Unique username for the customer',
                    example='john_doe'
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Strong password for the account',
                    example='SecurePass123!'
                ),
                'email': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description='Customer email address',
                    example='john.doe@example.com'
                ),
                'first_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer first name',
                    example='John'
                ),
                'last_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer last name',
                    example='Doe'
                ),
                'phone_number': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer phone number',
                    example='+2348012345678'
                ),
                'account_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['individual', 'business'],
                    description='Type of customer account',
                    example='individual'
                ),
                'address': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer physical address',
                    example='123 Main Street, Lagos, Nigeria'
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Customer created successfully",
                examples={
                    "application/json": {
                        "id": 1,
                        "user": {
                            "id": 1,
                            "username": "john_doe",
                            "email": "john.doe@example.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "role": "customer"
                        },
                        "account_number": "1234567890",
                        "account_type": "individual",
                        "tier": 1,
                        "credit_score": 300,
                        "current_borrow_limit": "200000.00"
                    }
                }
            ),
            400: openapi.Response(
                description="Validation errors or missing required fields",
                examples={
                    "application/json": {
                        "username": ["This field is required."],
                        "email": ["Enter a valid email address."]
                    }
                }
            ),
            403: openapi.Response(
                description="Permission denied - Account Officer role required",
                examples={
                    "application/json": {
                        "detail": "You do not have permission to perform this action."
                    }
                }
            )
        },
        tags=['Customer Management']
    )
    def create(self, request, *args, **kwargs):
        """
        Create a new customer account.
        
        Creates both a User and Customer record. The customer is automatically
        assigned a tier 1 status and base borrowing limit.
        
        Args:
            request: HTTP request containing customer data
            
        Returns:
            Response: Created customer details or validation errors
        """
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """
        Perform additional operations after customer creation.
        
        Sets the created_by field and logs the creation in audit trail.
        
        Args:
            serializer: Validated customer serializer
        """
        customer = serializer.save()
        customer.created_by = self.request.user
        customer.save()
        
        # Log audit trail
        AuditLog.objects.create(
            user=self.request.user,
            action='create',
            model_name='Customer',
            object_id=str(customer.id),
            details={'account_number': customer.account_number},
            ip_address=self.get_client_ip()
        )
    
    def get_client_ip(self):
        """
        Extract client IP address from request headers.
        
        Returns:
            str: Client IP address
        """
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    @swagger_auto_schema(
        operation_description="Manually verify customer address (Admin only)",
        operation_summary="Verify Customer Address",
        responses={
            200: openapi.Response(
                description="Address verified successfully",
                examples={
                    "application/json": {
                        "message": "Address verified successfully"
                    }
                }
            ),
            403: openapi.Response(
                description="Permission denied - Admin role required",
                examples={
                    "application/json": {
                        "detail": "You do not have permission to perform this action."
                    }
                }
            ),
            404: openapi.Response(
                description="Customer not found",
                examples={
                    "application/json": {
                        "detail": "Not found."
                    }
                }
            )
        },
        tags=['Customer Management']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def verify_address(self, request, pk=None):
        """
        Admin manually verifies customer address.
        
        Marks the customer's address as verified and logs the action
        in the audit trail for compliance tracking.
        
        Args:
            request: HTTP request from admin user
            pk: Customer ID
            
        Returns:
            Response: Success message confirming address verification
        """
        customer = self.get_object()
        customer.is_address_verified = True
        customer.save()
        
        # Log audit trail
        AuditLog.objects.create(
            user=request.user,
            action='verify',
            model_name='Customer',
            object_id=str(customer.id),
            details={'address_verified': True},
            ip_address=self.get_client_ip()
        )
        
        return Response({'message': 'Address verified successfully'})
    
    @action(detail=True, methods=['get'])
    def credit_score_breakdown(self, request, pk=None):
        """Get detailed credit score calculation breakdown"""
        customer = self.get_object()
        
        # Check permissions
        if request.user.role == 'customer':
            if request.user != customer.user:
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        elif request.user.role not in ['admin', 'account_officer']:
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
        loans = customer.loans.all()
        base_score = 300
        on_time_payments = 0
        late_payments = 0
        
        for loan in loans:
            payments = loan.payments.all()
            for payment in payments:
                if payment.is_on_time():
                    on_time_payments += 1
                else:
                    late_payments += 1
        
        # Calculate factors
        on_time_payment_factor = 0
        if on_time_payments + late_payments > 0:
            on_time_ratio = on_time_payments / (on_time_payments + late_payments)
            on_time_payment_factor = int(on_time_ratio * 150)
        
        loan_history_factor = min(loans.count() * 10, 50)
        tier_factor = customer.tier * 25
        late_payment_penalty = min(late_payments * 20, 200)
        
        breakdown_data = {
            'current_score': customer.credit_score,
            'base_score': base_score,
            'on_time_payment_factor': on_time_payment_factor,
            'loan_history_factor': loan_history_factor,
            'tier_factor': tier_factor,
            'late_payment_penalty': late_payment_penalty,
            'total_loans': loans.count(),
            'on_time_payments': on_time_payments,
            'late_payments': late_payments
        }
        
        serializer = CreditScoreBreakdownSerializer(breakdown_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def dashboard_stats(self, request, pk=None):
        """Get customer dashboard statistics"""
        customer = self.get_object()
        
        # Check permissions - only customer can access their own stats
        if request.user.role == 'customer' and request.user != customer.user:
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
        loans = customer.loans.all()
        active_loans = loans.filter(status__in=['active', 'disbursed'])
        completed_loans = loans.filter(status='completed')
        
        total_borrowed = loans.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_repaid = Payment.objects.filter(
            loan__customer=customer, 
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        outstanding_balance = sum([loan.get_outstanding_balance() for loan in active_loans])
        
        # Get next payment due
        next_payment = Payment.objects.filter(
            loan__customer=customer,
            status='pending'
        ).order_by('due_date').first()
        
        stats_data = {
            'total_loans': loans.count(),
            'active_loans': active_loans.count(),
            'completed_loans': completed_loans.count(),
            'total_borrowed': total_borrowed,
            'total_repaid': total_repaid,
            'outstanding_balance': outstanding_balance,
            'next_payment_due': next_payment.due_date if next_payment else None,
            'next_payment_amount': next_payment.amount if next_payment else None
        }
        
        serializer = CustomerStatsSerializer(stats_data)
        return Response(serializer.data)

class DocumentViewSet(viewsets.ModelViewSet):
    """Document management viewset"""
    serializer_class = DocumentSerializer
    
    def get_queryset(self):
        if self.request.user.role == 'customer':
            return Document.objects.filter(customer__user=self.request.user)
        return Document.objects.all()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [IsAccountOfficer()]
        elif self.action in ['list', 'retrieve']:
            return [IsAccountOfficer() | IsAdmin() | IsCustomer()]
        else:
            return [IsAdmin()]
    
    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

class LoanViewSet(viewsets.ModelViewSet):
    """Loan management viewset"""
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LoanCreateSerializer
        return LoanSerializer
    
    def get_queryset(self):
        if self.request.user.role == 'customer':
            return Loan.objects.filter(customer__user=self.request.user)
        elif self.request.user.role == 'account_officer':
            return Loan.objects.filter(requested_by=self.request.user)
        return Loan.objects.all()
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAccountOfficer()]
        elif self.action in ['approve', 'reject', 'disburse']:
            return [IsAdmin()]
        else:
            return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        loan = serializer.save(requested_by=self.request.user)
        
        # Log audit trail
        AuditLog.objects.create(
            user=self.request.user,
            action='create',
            model_name='Loan',
            object_id=str(loan.id),
            details={'customer': loan.customer.account_number, 'amount': str(loan.amount)},
            ip_address=self.get_client_ip()
        )
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        """Admin approves a loan request"""
        loan = self.get_object()
        
        if loan.status != 'pending':
            return Response(
                {'error': 'Only pending loans can be approved'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if customer's address is verified
        if not loan.customer.is_address_verified:
            return Response(
                {'error': 'Customer address must be verified before loan approval'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        loan.status = 'approved'
        loan.approved_by = request.user
        loan.save()
        
        # Log audit trail
        AuditLog.objects.create(
            user=request.user,
            action='approve',
            model_name='Loan',
            object_id=str(loan.id),
            details={'status': 'approved'},
            ip_address=self.get_client_ip()
        )
        
        return Response({'message': 'Loan approved successfully'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        """Admin rejects a loan request"""
        loan = self.get_object()
        
        if loan.status != 'pending':
            return Response(
                {'error': 'Only pending loans can be rejected'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        loan.status = 'rejected'
        loan.approved_by = request.user
        loan.save()
        
        # Log audit trail
        AuditLog.objects.create(
            user=request.user,
            action='reject',
            model_name='Loan',
            object_id=str(loan.id),
            details={'status': 'rejected', 'reason': reason},
            ip_address=self.get_client_ip()
        )
        
        return Response({'message': 'Loan rejected successfully'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def disburse(self, request, pk=None):
        """Admin disburses an approved loan"""
        loan = self.get_object()
        
        if loan.status != 'approved':
            return Response(
                {'error': 'Only approved loans can be disbursed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        loan.status = 'disbursed'
        loan.disbursed_at = timezone.now()
        loan.save()
        
        # Create payment schedule
        self.create_payment_schedule(loan)
        
        # Update customer's account number if not set
        if not loan.customer.account_number:
            loan.customer.save()  # This will generate account number
        
        # Log audit trail
        AuditLog.objects.create(
            user=request.user,
            action='update',
            model_name='Loan',
            object_id=str(loan.id),
            details={'status': 'disbursed', 'disbursed_at': str(loan.disbursed_at)},
            ip_address=self.get_client_ip()
        )
        
        return Response({'message': 'Loan disbursed successfully'})
    
    def create_payment_schedule(self, loan):
        """Create payment schedule for disbursed loan"""
        monthly_payment = loan.calculate_monthly_payment()
        
        for month in range(loan.duration_months):
            due_date = loan.disbursed_at.date() + timedelta(days=30 * (month + 1))
            
            Payment.objects.create(
                loan=loan,
                amount=monthly_payment,
                due_date=due_date,
                status='pending'
            )
    
    @action(detail=True, methods=['post'])
    def request_another_loan(self, request, pk=None):
        """Customer requests another loan after first payment"""
        if request.user.role != 'customer':
            return Response({'error': 'Only customers can request loans'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        current_loan = self.get_object()
        customer = current_loan.customer
        
        # Check if user owns this loan
        if customer.user != request.user:
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if at least one payment has been made
        completed_payments = current_loan.payments.filter(status='completed').count()
        if completed_payments == 0:
            return Response(
                {'error': 'At least one payment must be completed before requesting another loan'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if customer already has a pending loan request
        pending_loans = customer.loans.filter(status='pending')
        if pending_loans.exists():
            return Response(
                {'error': 'You already have a pending loan request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create loan request data
        loan_data = {
            'customer': customer.id,
            'amount': request.data.get('amount'),
            'interest_rate': request.data.get('interest_rate', 15.0),
            'duration_months': request.data.get('duration_months')
        }
        
        serializer = LoanCreateSerializer(data=loan_data)
        if serializer.is_valid():
            # Update customer's credit score and borrow limit
            customer.update_credit_score()
            customer.update_borrow_limit()
            
            loan = serializer.save(requested_by=customer.created_by)  # Request via account officer
            
            return Response({
                'message': 'Loan request submitted successfully',
                'loan_id': loan.id
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PaymentViewSet(viewsets.ModelViewSet):
    """Payment management viewset"""
    serializer_class = PaymentSerializer
    
    def get_queryset(self):
        if self.request.user.role == 'customer':
            return Payment.objects.filter(loan__customer__user=self.request.user)
        return Payment.objects.all()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [IsAdmin()]
        else:
            return [permissions.IsAuthenticated()]
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def mark_paid(self, request, pk=None):
        """Mark payment as completed"""
        payment = self.get_object()
        
        if payment.status == 'completed':
            return Response(
                {'error': 'Payment is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment.status = 'completed'
        payment.paid_date = timezone.now().date()
        payment.save()
        
        # Update customer credit score after payment
        payment.loan.customer.update_credit_score()
        payment.loan.customer.update_borrow_limit()
        
        # Check if loan is fully paid
        outstanding = payment.loan.get_outstanding_balance()
        if outstanding <= 0:
            payment.loan.status = 'completed'
            payment.loan.save()
        
        return Response({'message': 'Payment marked as completed'})

class AdminDashboardViewSet(viewsets.GenericViewSet):
    """Admin dashboard statistics"""
    permission_classes = [IsAdmin]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get admin dashboard statistics"""
        today = timezone.now().date()
        
        total_customers = Customer.objects.count()
        total_loans = Loan.objects.count()
        active_loans = Loan.objects.filter(status__in=['active', 'disbursed']).count()
        pending_loans = Loan.objects.filter(status='pending').count()
        
        total_disbursed = Loan.objects.filter(
            status__in=['disbursed', 'active', 'completed']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        total_collected = Payment.objects.filter(
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        avg_credit_score = Customer.objects.aggregate(
            avg=Avg('credit_score'))['avg'] or 0
        
        stats_data = {
            'total_customers': total_customers,
            'total_loans': total_loans,
            'active_loans': active_loans,
            'pending_loans': pending_loans,
            'total_amount_disbursed': total_disbursed,
            'total_amount_collected': total_collected,
            'average_credit_score': round(avg_credit_score, 2)
        }
        
        serializer = DashboardStatsSerializer(stats_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get loans pending approval"""
        pending_loans = Loan.objects.filter(status='pending').order_by('-created_at')
        serializer = LoanSerializer(pending_loans, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def address_verifications(self, request):
        """Get customers with unverified addresses"""
        customers = Customer.objects.filter(is_address_verified=False)
        serializer = CustomerDetailSerializer(customers, many=True)
        return Response(serializer.data)

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Audit log viewset for tracking system activities"""
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
    
    def get_queryset(self):
        queryset = AuditLog.objects.all().order_by('-timestamp')
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(timestamp__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__date__lte=end_date)
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by action
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        return queryset


class CustomerSelfRegistrationViewSet(viewsets.GenericViewSet):
    """
    Customer Self-Registration ViewSet
    
    Allows customers to register themselves without staff intervention.
    Registered customers will have pending approval status and need to
    complete KYC verification before applying for loans.
    
    Endpoints:
    - POST /customer-registration/ - Self-register as a customer
    """
    
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerSelfRegistrationSerializer
    
    @swagger_auto_schema(
        operation_description="Register as a new customer",
        operation_summary="Customer Self Registration",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password', 'email', 'first_name', 'last_name', 'phone_number', 'account_type', 'address'],
            properties={
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Unique username for the customer',
                    example='john_doe'
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Strong password for the account',
                    example='SecurePass123!'
                ),
                'email': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description='Customer email address',
                    example='john.doe@example.com'
                ),
                'first_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer first name',
                    example='John'
                ),
                'last_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer last name',
                    example='Doe'
                ),
                'phone_number': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer phone number',
                    example='+2348012345678'
                ),
                'account_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['individual', 'business'],
                    description='Type of customer account',
                    example='individual'
                ),
                'address': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer physical address',
                    example='123 Main Street, Lagos, Nigeria'
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Registration successful",
                examples={
                    "application/json": {
                        "id": 1,
                        "user": {
                            "id": 1,
                            "username": "john_doe",
                            "email": "john.doe@example.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "role": "customer"
                        },
                        "account_number": "ACC-2024-001",
                        "approval_status": "pending",
                        "message": "Registration successful. Your account is pending approval."
                    }
                }
            ),
            400: openapi.Response(
                description="Validation errors or missing required fields",
                examples={
                    "application/json": {
                        "username": ["Username 'john_doe' is already taken."],
                        "email": ["Email address is already registered."]
                    }
                }
            )
        },
        tags=['Customer Registration']
    )
    @action(detail=False, methods=['post'])
    def register(self, request):
        """
        Register a new customer account.
        
        Creates both User and Customer records with pending approval status.
        The customer will need account approval and KYC verification before
        applying for loans.
        
        Args:
            request: HTTP request containing customer registration data
            
        Returns:
            Response: Created customer details or validation errors
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            customer = serializer.save()
            
            # Log audit trail
            AuditLog.objects.create(
                user=customer.user,
                action='self_register',
                model_name='Customer',
                object_id=str(customer.id),
                details={'account_number': customer.account_number, 'approval_status': 'pending'},
                ip_address=self.get_client_ip()
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get_client_ip(self):
        """Get client IP address for audit logging"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class StaffCustomerRegistrationViewSet(viewsets.GenericViewSet):
    """
    Staff Customer Registration ViewSet
    
    Allows staff members to register customers on their behalf.
    Staff-registered customers are automatically approved and assigned
    to the registering staff member.
    
    Endpoints:
    - POST /staff-customer-registration/ - Register customer as staff
    """
    
    permission_classes = [IsAccountOfficer | IsAdmin]
    serializer_class = StaffCustomerRegistrationSerializer
    
    @swagger_auto_schema(
        operation_description="Register a customer as staff member",
        operation_summary="Staff Customer Registration",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password', 'email', 'first_name', 'last_name', 'phone_number', 'account_type', 'address'],
            properties={
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Unique username for the customer',
                    example='jane_smith'
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Strong password for the account',
                    example='SecurePass123!'
                ),
                'email': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description='Customer email address',
                    example='jane.smith@example.com'
                ),
                'first_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer first name',
                    example='Jane'
                ),
                'last_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer last name',
                    example='Smith'
                ),
                'phone_number': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer phone number',
                    example='+2348012345679'
                ),
                'account_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['individual', 'business'],
                    description='Type of customer account',
                    example='individual'
                ),
                'tier': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['bronze', 'silver', 'gold', 'platinum'],
                    description='Customer tier (optional)',
                    example='bronze'
                ),
                'address': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Customer physical address',
                    example='456 Oak Street, Abuja, Nigeria'
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Customer registered successfully by staff",
                examples={
                    "application/json": {
                        "id": 2,
                        "user": {
                            "id": 2,
                            "username": "jane_smith",
                            "email": "jane.smith@example.com",
                            "first_name": "Jane",
                            "last_name": "Smith",
                            "role": "customer"
                        },
                        "account_number": "ACC-2024-002",
                        "approval_status": "approved",
                        "assigned_staff": 1,
                        "assigned_staff_name": "Account Officer",
                        "message": "Customer registered and approved successfully."
                    }
                }
            ),
            400: openapi.Response(
                description="Validation errors or missing required fields",
                examples={
                    "application/json": {
                        "username": ["Username 'jane_smith' is already taken."],
                        "email": ["Email address is already registered."]
                    }
                }
            ),
            403: openapi.Response(
                description="Permission denied - Staff role required",
                examples={
                    "application/json": {
                        "detail": "You do not have permission to perform this action."
                    }
                }
            )
        },
        tags=['Staff Operations']
    )
    @action(detail=False, methods=['post'])
    def register(self, request):
        """
        Register a customer as a staff member.
        
        Creates both User and Customer records with automatic approval
        and assignment to the registering staff member.
        
        Args:
            request: HTTP request containing customer registration data
            
        Returns:
            Response: Created customer details or validation errors
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            customer = serializer.save()
            
            # Log audit trail
            AuditLog.objects.create(
                user=request.user,
                action='staff_register_customer',
                model_name='Customer',
                object_id=str(customer.id),
                details={
                    'account_number': customer.account_number, 
                    'approval_status': 'approved',
                    'assigned_staff': request.user.get_full_name()
                },
                ip_address=self.get_client_ip()
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get_client_ip(self):
        """Get client IP address for audit logging"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class KYCVerificationViewSet(viewsets.ModelViewSet):
    """
    KYC Verification ViewSet
    
    Handles Know Your Customer (KYC) verification processes including
    BVN and NIN submission and verification by staff members.
    
    Endpoints:
    - GET /kyc/ - List KYC verifications (staff only)
    - POST /kyc/ - Submit KYC verification (customers)
    - GET /kyc/{id}/ - Retrieve KYC verification details
    - PUT/PATCH /kyc/{id}/ - Update KYC verification (staff only)
    - POST /kyc/{id}/verify/ - Verify KYC documents (staff only)
    """
    
    serializer_class = KYCVerificationSerializer
    
    def get_queryset(self):
        """Filter KYC verifications based on user role"""
        if self.request.user.role == 'customer':
            # Customers can only see their own KYC verification
            return KYCVerification.objects.filter(customer__user=self.request.user)
        elif self.request.user.role in ['account_officer', 'manager', 'relationship_officer']:
            # Staff can see KYC verifications for their assigned customers
            return KYCVerification.objects.filter(
                customer__assigned_staff=self.request.user
            )
        else:
            # Admins can see all KYC verifications
            return KYCVerification.objects.all()
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action == 'create':
            return [IsCustomer()]
        elif self.action in ['update', 'partial_update', 'verify']:
            return [IsAccountOfficer | IsAdmin()]
        else:
            return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create KYC verification for the authenticated customer"""
        # Get the customer record for the authenticated user
        try:
            customer = Customer.objects.get(user=self.request.user)
        except Customer.DoesNotExist:
            raise serializers.ValidationError("Customer record not found for this user.")
        
        serializer.save(customer=customer)
        
        # Log audit trail
        AuditLog.objects.create(
            user=self.request.user,
            action='kyc_submit',
            model_name='KYCVerification',
            object_id=str(serializer.instance.id),
            details={'customer': customer.account_number},
            ip_address=self.get_client_ip()
        )
    
    @swagger_auto_schema(
        operation_description="Verify KYC documents (staff only)",
        operation_summary="Verify KYC",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'bvn_verified': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Whether BVN is verified',
                    example=True
                ),
                'nin_verified': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Whether NIN is verified',
                    example=True
                ),
                'verification_status': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['pending', 'in_progress', 'verified', 'rejected', 'incomplete'],
                    description='Overall verification status',
                    example='verified'
                ),
                'verification_notes': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Notes about the verification',
                    example='All documents verified successfully'
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="KYC verification updated successfully",
                examples={
                    "application/json": {
                        "message": "KYC verification updated successfully",
                        "verification_status": "verified"
                    }
                }
            ),
            400: openapi.Response(
                description="Validation errors",
                examples={
                    "application/json": {
                        "verification_status": ["Invalid verification status."]
                    }
                }
            ),
            403: openapi.Response(
                description="Permission denied - Staff role required",
                examples={
                    "application/json": {
                        "detail": "You do not have permission to perform this action."
                    }
                }
            )
        },
        tags=['KYC Verification']
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAccountOfficer | IsAdmin])
    def verify(self, request, pk=None):
        """
        Verify KYC documents for a customer.
        
        Allows staff members to update verification status and add notes
        about the KYC verification process.
        
        Args:
            request: HTTP request containing verification data
            pk: KYC verification ID
            
        Returns:
            Response: Success message or validation errors
        """
        kyc_verification = self.get_object()
        
        # Update verification fields
        bvn_verified = request.data.get('bvn_verified')
        nin_verified = request.data.get('nin_verified')
        verification_status = request.data.get('verification_status')
        verification_notes = request.data.get('verification_notes')
        
        if bvn_verified is not None:
            kyc_verification.bvn_verified = bvn_verified
        if nin_verified is not None:
            kyc_verification.nin_verified = nin_verified
        if verification_status:
            kyc_verification.verification_status = verification_status
        if verification_notes:
            kyc_verification.verification_notes = verification_notes
        
        # Set verified_by and verification_date
        kyc_verification.verified_by = request.user
        kyc_verification.verification_date = timezone.now()
        kyc_verification.save()
        
        # Log audit trail
        AuditLog.objects.create(
            user=request.user,
            action='kyc_verify',
            model_name='KYCVerification',
            object_id=str(kyc_verification.id),
            details={
                'customer': kyc_verification.customer.account_number,
                'verification_status': verification_status,
                'bvn_verified': bvn_verified,
                'nin_verified': nin_verified
            },
            ip_address=self.get_client_ip()
        )
        
        return Response({
            'message': 'KYC verification updated successfully',
            'verification_status': kyc_verification.verification_status
        })
    
    def get_client_ip(self):
        """Get client IP address for audit logging"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class CustomerAssignmentViewSet(viewsets.GenericViewSet):
    """
    Customer Assignment ViewSet
    
    Allows higher-level staff members to assign approved customers
    to specific staff members or relationship officers.
    
    Endpoints:
    - POST /customer-assignment/ - Assign customer to staff
    - GET /customer-assignment/pending/ - Get customers pending assignment
    """
    
    permission_classes = [IsAdmin]  # Only admins can assign customers
    serializer_class = CustomerAssignmentSerializer
    
    @swagger_auto_schema(
        operation_description="Assign approved customer to staff member",
        operation_summary="Assign Customer to Staff",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['customer_id', 'staff_id'],
            properties={
                'customer_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the customer to assign',
                    example=1
                ),
                'staff_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the staff member to assign to',
                    example=2
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="Customer assigned successfully",
                examples={
                    "application/json": {
                        "customer_name": "John Doe",
                        "staff_name": "Jane Smith",
                        "staff_role": "relationship_officer",
                        "assigned_date": "2024-01-15T10:30:00Z",
                        "assigned_by": "Admin User",
                        "message": "Customer assigned successfully to Jane Smith (Relationship Officer)"
                    }
                }
            ),
            400: openapi.Response(
                description="Validation errors or assignment not allowed",
                examples={
                    "application/json": {
                        "customer_id": ["Customer with ID 1 not found."],
                        "staff_id": ["Staff member with ID 2 not found."]
                    }
                }
            ),
            403: openapi.Response(
                description="Permission denied - Admin role required",
                examples={
                    "application/json": {
                        "detail": "You do not have permission to perform this action."
                    }
                }
            )
        },
        tags=['Staff Operations']
    )
    @action(detail=False, methods=['post'])
    def assign(self, request):
        """
        Assign an approved customer to a staff member.
        
        Only approved customers can be assigned to staff members.
        The staff member must have appropriate role (account_officer,
        manager, or relationship_officer).
        
        Args:
            request: HTTP request containing customer and staff IDs
            
        Returns:
            Response: Assignment details or validation errors
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            assignment_data = serializer.save()
            
            # Log audit trail
            AuditLog.objects.create(
                user=request.user,
                action='customer_assign',
                model_name='Customer',
                object_id=str(assignment_data['customer_id']),
                details={
                    'assigned_to': assignment_data['staff_name'],
                    'staff_role': assignment_data['staff_role']
                },
                ip_address=self.get_client_ip()
            )
            
            return Response(assignment_data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_description="Get customers pending staff assignment",
        operation_summary="Get Pending Assignments",
        responses={
            200: openapi.Response(
                description="List of customers pending assignment",
                examples={
                    "application/json": [
                        {
                            "id": 1,
                            "user": {
                                "id": 1,
                                "username": "john_doe",
                                "email": "john@example.com",
                                "first_name": "John",
                                "last_name": "Doe"
                            },
                            "account_number": "ACC-2024-001",
                            "approval_status": "approved",
                            "assigned_staff": None,
                            "created_at": "2024-01-15T09:00:00Z"
                        }
                    ]
                }
            ),
            403: openapi.Response(
                description="Permission denied - Admin role required",
                examples={
                    "application/json": {
                        "detail": "You do not have permission to perform this action."
                    }
                }
            )
        },
        tags=['Staff Operations']
    )
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """
        Get customers that are approved but not yet assigned to staff.
        
        Returns a list of customers with approved status but no assigned
        staff member, allowing admins to see who needs assignment.
        
        Args:
            request: HTTP request
            
        Returns:
            Response: List of customers pending assignment
        """
        pending_customers = Customer.objects.filter(
            approval_status='approved',
            assigned_staff__isnull=True
        ).order_by('-created_at')
        
        serializer = CustomerDetailSerializer(pending_customers, many=True)
        return Response(serializer.data)
    
    def get_client_ip(self):
        """Get client IP address for audit logging"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip