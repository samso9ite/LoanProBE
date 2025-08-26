# models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
import random
import string

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('account_officer', 'Account Officer'),
        ('customer', 'Customer'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Customer(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
    ]
    
    TIER_CHOICES = [
        (1, 'Tier 1 - Basic verification'),
        (2, 'Tier 2 - Additional verification'), 
        (3, 'Tier 3 - Advanced verification'),
        (4, 'Tier 4 - Full verification'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20, unique=True, blank=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    tier = models.IntegerField(choices=TIER_CHOICES, default=1)
    credit_score = models.IntegerField(default=300, validators=[MinValueValidator(300), MaxValueValidator(850)])
    current_borrow_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    address = models.TextField()
    is_address_verified = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_customers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self.generate_account_number()
        if not self.current_borrow_limit:
            self.current_borrow_limit = self.get_base_limit_for_tier()
        super().save(*args, **kwargs)

    def generate_account_number(self):
        """Generate unique 10-digit account number"""
        while True:
            account_number = ''.join(random.choices(string.digits, k=10))
            if not Customer.objects.filter(account_number=account_number).exists():
                return account_number

    def get_base_limit_for_tier(self):
        """Get base borrowing limit based on tier"""
        tier_limits = {
            1: Decimal('200000.00'),
            2: Decimal('500000.00'), 
            3: Decimal('2000000.00'),
            4: Decimal('5000000.00'),
        }
        return tier_limits.get(self.tier, Decimal('0.00'))

    def calculate_credit_score(self):
        """Calculate credit score based on loan performance"""
        loans = self.loans.all()
        if not loans:
            return 300  # Base score
        
        score = 300  # Base score
        total_loans = loans.count()
        on_time_payments = 0
        late_payments = 0
        total_amount = Decimal('0.00')
        
        for loan in loans:
            total_amount += loan.amount
            payments = loan.payments.all()
            
            for payment in payments:
                if payment.is_on_time():
                    on_time_payments += 1
                else:
                    late_payments += 1
        
        # On-time payment factor (+150 max)
        if on_time_payments + late_payments > 0:
            on_time_ratio = on_time_payments / (on_time_payments + late_payments)
            score += int(on_time_ratio * 150)
        
        # Loan history length factor (+50 max)
        if total_loans > 0:
            history_factor = min(total_loans * 10, 50)
            score += history_factor
        
        # Tier level factor (+100 max)
        tier_factor = self.tier * 25
        score += tier_factor
        
        # Late payment penalty (-200 max)
        if late_payments > 0:
            penalty = min(late_payments * 20, 200)
            score -= penalty
        
        return min(max(score, 300), 850)  # Keep between 300-850

    def update_credit_score(self):
        """Update credit score and save"""
        self.credit_score = self.calculate_credit_score()
        self.save()

    def update_borrow_limit(self):
        """Update borrowing limit based on performance"""
        base_limit = self.get_base_limit_for_tier()
        
        # Performance multiplier based on credit score
        if self.credit_score >= 750:
            multiplier = Decimal('1.5')
        elif self.credit_score >= 650:
            multiplier = Decimal('1.3')
        elif self.credit_score >= 550:
            multiplier = Decimal('1.1')
        else:
            multiplier = Decimal('0.8')
        
        self.current_borrow_limit = base_limit * multiplier
        self.save()

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.account_number}"

class Document(models.Model):
    DOCUMENT_TYPES = [
        ('id', 'ID Card'),
        ('photo', 'Passport Photo'),
        ('proof_of_address', 'Proof of Address'),
        ('cac_docs', 'CAC Documents'),
        ('tax_id', 'Tax ID'),
        ('financial_statements', 'Financial Statements'),
        ('bank_statement', 'Bank Statement'),
        ('business_license', 'Business License'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    file_path = models.CharField(max_length=500)  # Store file path/URL
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        unique_together = ['customer', 'document_type']

    def __str__(self):
        return f"{self.customer.account_number} - {self.get_document_type_display()}"

class Loan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loans')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15.0)  # Annual percentage
    duration_months = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_loans')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans')
    disbursed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.status == 'disbursed' and not self.due_date:
            self.due_date = (datetime.now() + timedelta(days=30 * self.duration_months)).date()
        super().save(*args, **kwargs)

    def calculate_monthly_payment(self):
        """Calculate monthly payment amount"""
        if self.duration_months == 0:
            return self.amount
        
        monthly_rate = self.interest_rate / Decimal('100') / Decimal('12')
        if monthly_rate == 0:
            return self.amount / self.duration_months
        
        payment = (self.amount * monthly_rate * (1 + monthly_rate) ** self.duration_months) / \
                 ((1 + monthly_rate) ** self.duration_months - 1)
        return payment

    def get_total_amount(self):
        """Get total amount to be repaid"""
        return self.calculate_monthly_payment() * self.duration_months

    def get_outstanding_balance(self):
        """Calculate outstanding balance"""
        total_paid = self.payments.filter(status='completed').aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        return self.get_total_amount() - total_paid

    def __str__(self):
        return f"Loan {self.id} - {self.customer.account_number} - ₦{self.amount}"

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('overdue', 'Overdue'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_partial = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_on_time(self):
        """Check if payment was made on time"""
        if self.paid_date and self.due_date:
            return self.paid_date <= self.due_date
        return False

    def days_overdue(self):
        """Calculate days overdue"""
        if self.status == 'completed' and self.paid_date:
            if self.paid_date > self.due_date:
                return (self.paid_date - self.due_date).days
        elif self.status in ['pending', 'overdue']:
            today = datetime.now().date()
            if today > self.due_date:
                return (today - self.due_date).days
        return 0

    def __str__(self):
        return f"Payment {self.id} - {self.loan.id} - ₦{self.amount}"

class OTPVerification(models.Model):
    phone_number = models.CharField(max_length=15)
    otp_code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return datetime.now() > self.expires_at

    def __str__(self):
        return f"OTP for {self.phone_number} - {self.otp_code}"

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('verify', 'Verify'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"