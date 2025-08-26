# permissions.py
from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsAccountOfficer(permissions.BasePermission):
    """
    Custom permission to only allow account officers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'account_officer'

class IsCustomer(permissions.BasePermission):
    """
    Custom permission to only allow customers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'customer'

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object.
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'customer'):
            return obj.customer.user == request.user
        return obj == request.user

class CanAccessCustomerData(permissions.BasePermission):
    """
    Permission to allow admins and account officers to access customer data,
    and customers to access their own data.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if user.role in ['admin', 'account_officer']:
            return True
        elif user.role == 'customer':
            # Customer can only access their own data
            if hasattr(obj, 'user'):
                return obj.user == user
            elif hasattr(obj, 'customer'):
                return obj.customer.user == user
        
        return False