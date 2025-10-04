"""
Django models for the LoanPro application.

This module defines the core data models for the loan management system,
including user management, customer profiles, loan applications, payments,
document management, OTP verification, and audit logging.

Models:
    User: Extended user model with role-based access control
    Customer: Customer profile with credit scoring and borrowing limits
    Document: Document management for customer verification
    Loan: Loan application and management
    Payment: Payment tracking and management
    OTPVerification: One-time password verification for security
    AuditLog: System audit trail for compliance and monitoring
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
import random
import string


class User(AbstractUser):
    """
    Extended user model with role-based access control.
    
    This model extends Django's AbstractUser to include additional fields
    for role management, phone verification, and audit tracking. It supports
    three main user roles: admin, account officer, and customer.
    
    Attributes:
        role (str): User's role in the system (admin/account_officer/customer)
        phone_number (str): Unique phone number for the user
        is_phone_verified (bool): Whether the phone number has been verified
        created_at (datetime): Timestamp when the user account was created
        updated_at (datetime): Timestamp when the user account was last updated
        
    Role Permissions:
        - Admin: Full system access and management capabilities
        - Account Officer: Customer management and loan processing
        - Customer: Personal account access and loan applications
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('relationship_officer', 'Relationship Officer'),
        ('account_officer', 'Account Officer'),
        ('customer', 'Customer'),
    ]
    
    # User role in the system - determines access permissions and capabilities
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES,
        help_text="User's role determining their access level and permissions"
    )
    
    # Unique phone number for SMS verification and communication
    phone_number = models.CharField(
        max_length=15, 
        unique=True, 
        null=True, 
        blank=True,
        help_text="User's phone number for verification and notifications"
    )
    
    # Phone verification status for security purposes
    is_phone_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's phone number has been verified via OTP"
    )
    
    # Audit timestamps for tracking account creation and updates
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the user account was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the user account was last updated"
    )

    def __str__(self):
        """
        String representation of the user.
        
        Returns:
            str: Username and role display for easy identification
        """
        return f"{self.username} ({self.get_role_display()})"


class KYCVerification(models.Model):
    """
    KYC (Know Your Customer) verification model for BVN and NIN validation.
    
    This model handles the verification of customer identity documents
    including Bank Verification Number (BVN) and National Identity Number (NIN).
    It tracks the verification status and stores verification details.
    
    Attributes:
        customer (Customer): Associated customer for this KYC verification
        bvn (str): Bank Verification Number for financial identity verification
        nin (str): National Identity Number for government identity verification
        bvn_verified (bool): Whether BVN has been successfully verified
        nin_verified (bool): Whether NIN has been successfully verified
        verification_status (str): Overall KYC verification status
        verified_by (User): Staff member who performed the verification
        verification_date (datetime): When the verification was completed
        verification_notes (str): Additional notes about the verification process
        created_at (datetime): When the KYC record was created
        updated_at (datetime): When the KYC record was last updated
    """
    
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('in_progress', 'Verification In Progress'),
        ('verified', 'Fully Verified'),
        ('rejected', 'Verification Rejected'),
        ('incomplete', 'Incomplete Information'),
    ]
    
    customer = models.OneToOneField(
        'Customer',
        on_delete=models.CASCADE,
        related_name='kyc_verification',
        help_text="Customer associated with this KYC verification"
    )
    
    # Bank Verification Number for financial identity verification
    bvn = models.CharField(
        max_length=11,
        null=True,
        blank=True,
        help_text="11-digit Bank Verification Number for financial identity verification"
    )
    
    # National Identity Number for government identity verification
    nin = models.CharField(
        max_length=11,
        null=True,
        blank=True,
        help_text="11-digit National Identity Number for government identity verification"
    )
    
    # Individual verification status for each document
    bvn_verified = models.BooleanField(
        default=False,
        help_text="Whether the BVN has been successfully verified"
    )
    
    nin_verified = models.BooleanField(
        default=False,
        help_text="Whether the NIN has been successfully verified"
    )
    
    # Overall verification status
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending',
        help_text="Overall KYC verification status"
    )
    
    # Staff member who performed the verification
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_kyc_records',
        help_text="Staff member who performed the KYC verification"
    )
    
    # Verification completion date
    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time when KYC verification was completed"
    )
    
    # Additional verification notes
    verification_notes = models.TextField(
        blank=True,
        help_text="Additional notes about the verification process or any issues"
    )
    
    # Audit timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the KYC verification record was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the KYC verification record was last updated"
    )
    
    class Meta:
        verbose_name = "KYC Verification"
        verbose_name_plural = "KYC Verifications"
    
    def is_fully_verified(self):
        """
        Check if customer is fully KYC verified.
        
        Returns:
            bool: True if both BVN and NIN are verified
        """
        return self.bvn_verified and self.nin_verified and self.verification_status == 'verified'
    
    def get_verification_progress(self):
        """
        Get verification progress percentage.
        
        Returns:
            int: Verification progress as percentage (0-100)
        """
        progress = 0
        if self.bvn and self.bvn_verified:
            progress += 50
        if self.nin and self.nin_verified:
            progress += 50
        return progress
    
    def __str__(self):
        """
        String representation of KYC verification.
        
        Returns:
            str: Customer name and verification status
        """
        return f"KYC for {self.customer.user.get_full_name()} - {self.get_verification_status_display()}"


class Customer(models.Model):
    """
    Customer profile model with credit scoring and borrowing limits.
    
    This model represents a customer in the loan system, containing their
    personal information, verification status, credit score, and borrowing
    limits. Customers are organized into tiers based on their verification
    level, which affects their borrowing capacity.
    
    Attributes:
        user (User): One-to-one relationship with the User model
        account_number (str): Unique account identifier for the customer
        account_type (str): Type of account (individual or business)
        tier (int): Verification tier (1-4) affecting borrowing limits
        credit_score (int): Credit score between 300-850
        current_borrow_limit (Decimal): Current borrowing limit in currency
        address (str): Physical address of the customer
        is_address_verified (bool): Whether the address has been verified
        created_by (User): Staff member who created the customer account
        created_at (datetime): Account creation timestamp
        updated_at (datetime): Last update timestamp
        
    Tier System:
        - Tier 1: Basic verification (₦50,000 limit)
        - Tier 2: Additional verification (₦200,000 limit)
        - Tier 3: Advanced verification (₦500,000 limit)
        - Tier 4: Full verification (₦1,000,000 limit)
    """
    
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

    # One-to-one relationship with User model for authentication
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        help_text="Associated user account for authentication and basic info"
    )
    
    # Unique account number for customer identification
    account_number = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True,
        help_text="Unique account number generated automatically"
    )
    
    # Account type determines available services and requirements
    account_type = models.CharField(
        max_length=20, 
        choices=ACCOUNT_TYPE_CHOICES,
        help_text="Type of customer account (individual or business)"
    )
    
    # Verification tier affects borrowing limits and available services
    tier = models.IntegerField(
        choices=TIER_CHOICES, 
        default=1,
        help_text="Customer verification tier (1-4) determining borrowing limits"
    )
    
    # Credit score for risk assessment and loan approval
    credit_score = models.IntegerField(
        default=300, 
        validators=[MinValueValidator(300), MaxValueValidator(850)],
        help_text="Customer credit score (300-850) used for loan risk assessment"
    )
    
    # Current borrowing limit based on tier and credit score
    current_borrow_limit = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Current maximum amount the customer can borrow"
    )
    
    # Physical address for verification and communication
    address = models.TextField(
        help_text="Customer's physical address for verification purposes"
    )
    
    # Address verification status for compliance
    is_address_verified = models.BooleanField(
        default=False,
        help_text="Whether the customer's address has been verified"
    )
    
    # Account approval status for self-registered customers
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        help_text="Account approval status for self-registered customers"
    )
    
    # Staff assignment for customer relationship management
    assigned_staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_customers',
        limit_choices_to={'role__in': ['manager', 'relationship_officer', 'account_officer']},
        help_text="Staff member assigned to manage this customer relationship"
    )
    
    # Date when customer was assigned to staff
    assigned_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time when customer was assigned to staff"
    )
    
    # Staff member who assigned the customer (for audit purposes)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_assignments_made',
        help_text="Staff member who made the customer assignment"
    )
    
    # Staff member who created the customer account for audit purposes
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_customers',
        help_text="Staff member who created this customer account"
    )
    
    # Audit timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the customer account was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the customer account was last updated"
    )

    def save(self, *args, **kwargs):
        """
        Override save method to auto-generate account number and set borrowing limit.
        
        This method ensures that every customer gets a unique account number
        and an appropriate borrowing limit based on their tier when first created.
        
        Args:
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        if not self.account_number:
            self.account_number = self.generate_account_number()
        if not self.current_borrow_limit:
            self.current_borrow_limit = self.get_base_limit_for_tier()
        super().save(*args, **kwargs)

    def generate_account_number(self):
        """
        Generate a unique 10-digit account number for the customer.
        
        This method creates a random 10-digit account number and ensures
        it's unique by checking against existing customer accounts.
        
        Returns:
            str: A unique 10-digit account number
            
        Example:
            >>> customer.generate_account_number()
            '1234567890'
        """
        while True:
            account_number = ''.join(random.choices(string.digits, k=10))
            if not Customer.objects.filter(account_number=account_number).exists():
                return account_number

    def get_base_limit_for_tier(self):
        """
        Get the base borrowing limit based on customer's verification tier.
        
        Each tier has a predefined borrowing limit that serves as the base
        for calculating the customer's actual borrowing capacity.
        
        Returns:
            Decimal: Base borrowing limit for the customer's tier
            
        Tier Limits:
            - Tier 1: ₦200,000 (Basic verification)
            - Tier 2: ₦500,000 (Additional verification)
            - Tier 3: ₦2,000,000 (Advanced verification)
            - Tier 4: ₦5,000,000 (Full verification)
            
        Example:
            >>> customer.tier = 3
            >>> customer.get_base_limit_for_tier()
            Decimal('2000000.00')
        """
        tier_limits = {
            1: Decimal('200000.00'),
            2: Decimal('500000.00'), 
            3: Decimal('2000000.00'),
            4: Decimal('5000000.00'),
        }
        return tier_limits.get(self.tier, Decimal('0.00'))

    def calculate_credit_score(self):
        """
        Calculate customer's credit score based on loan performance and history.
        
        This method evaluates multiple factors to determine a customer's creditworthiness:
        - Payment history (on-time vs late payments)
        - Loan history length (number of loans taken)
        - Customer tier level
        - Late payment penalties
        
        Returns:
            int: Credit score between 300-850
            
        Credit Score Factors:
            - Base score: 300 points
            - On-time payment ratio: +0 to +150 points
            - Loan history length: +0 to +50 points (10 points per loan, max 5 loans)
            - Tier level: +25 to +100 points (25 points per tier)
            - Late payment penalty: -0 to -200 points (20 points per late payment)
            
        Example:
            >>> customer.calculate_credit_score()
            675
        """
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
        """
        Update the customer's credit score and save the changes.
        
        This method recalculates the credit score using the current loan
        performance data and updates the customer record in the database.
        
        Example:
            >>> customer.update_credit_score()
            # Credit score updated and saved to database
        """
        self.credit_score = self.calculate_credit_score()
        self.save()

    def update_borrow_limit(self):
        """
        Update the customer's borrowing limit based on credit score performance.
        
        This method calculates a new borrowing limit by applying a performance
        multiplier to the base tier limit based on the customer's credit score.
        
        Performance Multipliers:
            - Credit score >= 750: 1.5x base limit
            - Credit score >= 650: 1.3x base limit  
            - Credit score >= 550: 1.1x base limit
            - Credit score < 550: 0.8x base limit
            
        Example:
            >>> customer.tier = 3  # Base limit: ₦2,000,000
            >>> customer.credit_score = 720
            >>> customer.update_borrow_limit()
            >>> customer.current_borrow_limit
            Decimal('2600000.00')  # ₦2,000,000 * 1.3
        """
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

    def is_kyc_verified(self):
        """
        Check if the customer has completed KYC verification.
        
        Returns:
            bool: True if KYC is fully verified, False otherwise
        """
        try:
            return self.kyc_verification.is_fully_verified()
        except KYCVerification.DoesNotExist:
            return False

    def is_account_approved(self):
        """
        Check if the customer account is approved.
        
        Returns:
            bool: True if account is approved, False otherwise
        """
        return self.approval_status == 'approved'

    def can_apply_for_loan(self):
        """
        Check if the customer is eligible to apply for loans.
        
        A customer can apply for loans if:
        - Their account is approved
        - They have completed KYC verification
        - They are assigned to a staff member
        
        Returns:
            bool: True if eligible for loan application, False otherwise
        """
        return (
            self.is_account_approved() and 
            self.is_kyc_verified() and 
            self.assigned_staff is not None
        )

    def get_kyc_status(self):
        """
        Get the current KYC verification status.
        
        Returns:
            str: KYC verification status or 'not_started' if no KYC record exists
        """
        try:
            return self.kyc_verification.verification_status
        except KYCVerification.DoesNotExist:
            return 'not_started'

    def assign_to_staff(self, staff_member, assigned_by_user):
        """
        Assign the customer to a staff member.
        
        Args:
            staff_member (User): Staff member to assign the customer to
            assigned_by_user (User): User making the assignment
        
        Raises:
            ValueError: If staff_member is not a valid staff role
        """
        from django.utils import timezone
        
        if staff_member.role not in ['manager', 'relationship_officer', 'account_officer']:
            raise ValueError("Staff member must have a valid staff role")
        
        self.assigned_staff = staff_member
        self.assigned_by = assigned_by_user
        self.assigned_date = timezone.now()
        self.save()

    def __str__(self):
        """
        Return string representation of the customer.
        
        Returns:
            str: Customer's full name and account number
            
        Example:
            >>> str(customer)
            'John Doe - 1234567890'
        """
        return f"{self.user.get_full_name()} - {self.account_number}"

class Document(models.Model):
    """
    Document model for storing customer verification documents.
    
    This model manages various types of documents required for customer
    verification and compliance. Each customer can upload multiple document
    types, but only one document per type is allowed.
    
    Attributes:
        customer (Customer): The customer who owns this document
        document_type (str): Type of document from predefined choices
        file_path (str): Path or URL to the stored document file
        uploaded_at (datetime): When the document was uploaded
        uploaded_by (User): Staff member who uploaded the document
        is_verified (bool): Whether the document has been verified
        
    Document Types:
        - id: National ID Card or International Passport
        - photo: Passport photograph
        - proof_of_address: Utility bill or bank statement
        - cac_docs: Corporate Affairs Commission documents (for businesses)
        - tax_id: Tax identification documents
        - financial_statements: Business financial statements
        - bank_statement: Recent bank statements
        - business_license: Business registration license
    """
    
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

    # Customer who owns this document
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='documents',
        help_text="Customer who owns this document"
    )
    
    # Type of document being uploaded
    document_type = models.CharField(
        max_length=30, 
        choices=DOCUMENT_TYPES,
        help_text="Type of document from predefined choices"
    )
    
    # File storage path or URL
    file_path = models.CharField(
        max_length=500,
        help_text="Path or URL where the document file is stored"
    )
    
    # Upload timestamp
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the document was uploaded"
    )
    
    # Staff member who uploaded the document
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        help_text="Staff member who uploaded this document"
    )
    
    # Verification status
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether this document has been verified by staff"
    )

    class Meta:
        unique_together = ['customer', 'document_type']

    def __str__(self):
        """
        Return string representation of the document.
        
        Returns:
            str: Customer name and document type
            
        Example:
            >>> str(document)
            'John Doe - ID Card'
        """
        return f"{self.customer.user.get_full_name()} - {self.get_document_type_display()}"

class Loan(models.Model):
    """
    Loan model representing customer loan applications and their lifecycle.
    
    This model manages the complete loan lifecycle from application to completion,
    including approval workflow, disbursement tracking, and payment management.
    Each loan has a unique UUID identifier and tracks its status through various stages.
    
    Attributes:
        id (UUID): Unique identifier for the loan
        customer (Customer): The customer who applied for the loan
        amount (Decimal): Principal loan amount requested
        interest_rate (Decimal): Annual interest rate percentage (default 15%)
        duration_months (int): Loan term in months
        status (str): Current status of the loan
        requested_by (User): User who submitted the loan request
        approved_by (User): Staff member who approved the loan
        disbursed_at (datetime): When the loan was disbursed
        due_date (date): Final due date for loan completion
        created_at (datetime): When the loan application was created
        updated_at (datetime): Last update timestamp
        
    Loan Status Flow:
        pending → approved/rejected → disbursed → active → completed/defaulted
        
    Status Definitions:
        - pending: Initial application status, awaiting review
        - approved: Loan approved by staff, ready for disbursement
        - rejected: Loan application rejected
        - disbursed: Funds have been disbursed to customer
        - active: Loan is active with ongoing payments
        - completed: All payments made, loan closed successfully
        - defaulted: Customer failed to meet payment obligations
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
    ]

    # Unique loan identifier
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for the loan"
    )
    
    # Customer who applied for the loan
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='loans',
        help_text="Customer who applied for this loan"
    )
    
    # Principal loan amount
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Principal loan amount requested by the customer"
    )
    
    # Annual interest rate
    interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=15.0,
        help_text="Annual interest rate percentage (default 15%)"
    )
    
    # Loan term in months
    duration_months = models.IntegerField(
        help_text="Loan term duration in months"
    )
    
    # Current loan status
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Current status of the loan in its lifecycle"
    )
    
    # User who submitted the loan request
    requested_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='requested_loans',
        help_text="User who submitted the loan application"
    )
    
    # Staff member who approved the loan
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_loans',
        help_text="Staff member who approved the loan"
    )
    
    # Disbursement timestamp
    disbursed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp when the loan funds were disbursed"
    )
    
    # Final due date
    due_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Final due date for loan completion"
    )
    
    # Audit timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the loan application was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the loan was last updated"
    )

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