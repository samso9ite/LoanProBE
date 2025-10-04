"""
Custom exception handlers for the LoanPro API.

This module provides custom exception handling to improve error messages
and provide better user feedback for API requests, especially for missing
or invalid data in POST requests.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.http import Http404
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides detailed error messages
    for better user experience, especially for missing data in POST requests.
    
    Args:
        exc: The exception instance
        context: The context in which the exception occurred
        
    Returns:
        Response: A formatted error response with detailed messages
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'error': True,
            'message': 'An error occurred while processing your request.',
            'details': {},
            'status_code': response.status_code
        }
        
        # Handle validation errors (400 Bad Request)
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            custom_response_data['message'] = 'Validation failed. Please check the provided data.'
            
            # Handle field-specific errors
            if isinstance(response.data, dict):
                field_errors = {}
                general_errors = []
                
                for field, errors in response.data.items():
                    if field == 'non_field_errors':
                        general_errors.extend(errors if isinstance(errors, list) else [errors])
                    elif field == 'missing_fields':
                        custom_response_data['message'] = 'Required fields are missing.'
                        general_errors.extend(errors if isinstance(errors, list) else [errors])
                    else:
                        field_errors[field] = errors if isinstance(errors, list) else [errors]
                
                if field_errors:
                    custom_response_data['details']['field_errors'] = field_errors
                    
                if general_errors:
                    custom_response_data['details']['general_errors'] = general_errors
                    
                # Provide helpful suggestions for common errors
                if field_errors:
                    suggestions = []
                    for field in field_errors.keys():
                        if field in ['username', 'email', 'password']:
                            suggestions.append(f"Check your {field} format and requirements.")
                        elif field == 'phone_number':
                            suggestions.append("Ensure phone number contains at least 10 digits.")
                        elif field == 'amount':
                            suggestions.append("Verify the loan amount is within acceptable limits.")
                        elif field == 'otp_code':
                            suggestions.append("Make sure the OTP code is 6 digits and hasn't expired.")
                    
                    if suggestions:
                        custom_response_data['details']['suggestions'] = suggestions
            
            else:
                # Handle list of errors
                custom_response_data['details']['errors'] = response.data
        
        # Handle authentication errors (401 Unauthorized)
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            custom_response_data['message'] = 'Authentication failed. Please check your credentials.'
            custom_response_data['details']['suggestions'] = [
                'Verify your username and password are correct.',
                'Make sure your account is active.',
                'Try logging in again.'
            ]
        
        # Handle permission errors (403 Forbidden)
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            custom_response_data['message'] = 'You do not have permission to perform this action.'
            custom_response_data['details']['suggestions'] = [
                'Contact your administrator if you believe you should have access.',
                'Make sure you are logged in with the correct account.'
            ]
        
        # Handle not found errors (404 Not Found)
        elif response.status_code == status.HTTP_404_NOT_FOUND:
            custom_response_data['message'] = 'The requested resource was not found.'
            custom_response_data['details']['suggestions'] = [
                'Check the URL and try again.',
                'Make sure the resource exists and you have access to it.'
            ]
        
        # Handle method not allowed (405 Method Not Allowed)
        elif response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            custom_response_data['message'] = 'This HTTP method is not allowed for this endpoint.'
            custom_response_data['details']['allowed_methods'] = response.data.get('detail', '')
        
        # Handle server errors (500 Internal Server Error)
        elif response.status_code >= 500:
            custom_response_data['message'] = 'An internal server error occurred. Please try again later.'
            custom_response_data['details']['suggestions'] = [
                'Try again in a few moments.',
                'Contact support if the problem persists.'
            ]
            # Log server errors for debugging
            logger.error(f"Server error: {exc}", exc_info=True)
        
        # Add request information for debugging (in development)
        if context and hasattr(context.get('request'), 'method'):
            request = context['request']
            custom_response_data['details']['request_info'] = {
                'method': request.method,
                'path': request.path,
            }
        
        response.data = custom_response_data
    
    return response


def handle_missing_data_error(missing_fields, model_name=""):
    """
    Generate a standardized error response for missing required fields.
    
    Args:
        missing_fields (list): List of missing field names
        model_name (str): Name of the model/resource being created
        
    Returns:
        dict: Formatted error response
    """
    field_names = [field.replace('_', ' ').title() for field in missing_fields]
    
    return {
        'error': True,
        'message': f'Required fields are missing for {model_name}.' if model_name else 'Required fields are missing.',
        'details': {
            'missing_fields': missing_fields,
            'missing_field_names': field_names,
            'suggestions': [
                f'Please provide the following required fields: {", ".join(field_names)}',
                'Check the API documentation for field requirements.',
                'Ensure all required fields are included in your request body.'
            ]
        },
        'status_code': status.HTTP_400_BAD_REQUEST
    }