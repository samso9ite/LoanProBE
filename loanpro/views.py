# views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.db.models import Q, Sum, Avg, Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    User, Customer, Document, Loan, Payment, 
    OTPVerification, AuditLog
)
from .serializers import (
    UserSerializer, CustomerDetailSerializer, CustomerCreateSerializer,
    DocumentSerializer, LoanSerializer, LoanCreateSerializer, PaymentSerializer,
    OTPSerializer, OTPVerifySerializer, LoginSerializer, CreditScoreBreakdownSerializer,
    DashboardStatsSerializer, CustomerStatsSerializer, AuditLogSerializer
)
from .permissions import IsAdmin, IsAccountOfficer, IsCustomer

class AuthViewSet(viewsets.GenericViewSet):
    """Authentication viewset for login/logout"""
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
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
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        try:
            request.user.auth_token.delete()
        except:
            pass
        logout(request)
        return Response({'message': 'Logout successful'})

class OTPViewSet(viewsets.GenericViewSet):
    """OTP generation and verification"""
    permission_classes = [IsAccountOfficer]
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
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
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
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
    """Customer management viewset"""
    queryset = Customer.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CustomerCreateSerializer
        return CustomerDetailSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAccountOfficer()]
        elif self.action in ['list', 'retrieve']:
            return [IsAccountOfficer() | IsAdmin()]
        elif self.action in ['update', 'partial_update']:
            return [IsAdmin()]
        else:
            return [IsAdmin()]
    
    def perform_create(self, serializer):
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
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def verify_address(self, request, pk=None):
        """Admin manually verifies customer address"""
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