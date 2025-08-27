"""
Security utilities and validators for ASPOR platform
"""
import re
import os
from typing import List, Tuple, Optional
from .config import Config


class SecurityValidator:
    """Security validation and sanitization utilities"""
    
    @staticmethod
    def validate_file(file_key: str, file_size: int = None) -> Tuple[bool, Optional[str]]:
        """
        Validate file type and size
        Returns: (is_valid, error_message)
        """
        # Check file extension
        if not file_key:
            return False, "No file key provided"
        
        extension = file_key.split('.')[-1].lower() if '.' in file_key else ''
        
        if extension not in Config.ALLOWED_EXTENSIONS:
            return False, f"File type '{extension}' not allowed. Allowed types: {', '.join(Config.ALLOWED_EXTENSIONS)}"
        
        # Check file size if provided
        if file_size:
            max_size_bytes = Config.MAX_FILE_SIZE_MB * 1024 * 1024
            if file_size > max_size_bytes:
                return False, f"File size exceeds maximum of {Config.MAX_FILE_SIZE_MB}MB"
        
        # Check for path traversal attempts
        if '..' in file_key or file_key.startswith('/'):
            return False, "Invalid file path"
        
        return True, None
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent injection attacks"""
        # Remove any path components
        filename = os.path.basename(filename)
        
        # Remove special characters except dots and hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Limit length
        max_length = 255
        if len(sanitized) > max_length:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:max_length-len(ext)-1] + ext
        
        return sanitized
    
    @staticmethod
    def sanitize_user_input(text: str, max_length: int = 10000) -> str:
        """Sanitize user input text"""
        if not text:
            return ""
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Limit length
        text = text[:max_length]
        
        # Remove control characters except newlines and tabs
        text = ''.join(char for char in text if char in '\n\t' or ord(char) >= 32)
        
        return text
    
    @staticmethod
    def validate_model_type(model: str) -> Tuple[bool, Optional[str]]:
        """Validate model selection"""
        allowed_models = ['A', 'B']
        if model not in allowed_models:
            return False, f"Invalid model type. Must be one of: {', '.join(allowed_models)}"
        return True, None
    
    @staticmethod
    def validate_output_format(format_type: str) -> Tuple[bool, Optional[str]]:
        """Validate output format"""
        allowed_formats = ['docx', 'pdf', 'txt']
        if format_type not in allowed_formats:
            return False, f"Invalid output format. Must be one of: {', '.join(allowed_formats)}"
        return True, None
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters"""
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&apos;",
            ">": "&gt;",
            "<": "&lt;",
        }
        return "".join(html_escape_table.get(c, c) for c in text)
    
    @staticmethod
    def validate_run_id(run_id: str) -> Tuple[bool, Optional[str]]:
        """Validate run ID format (UUID)"""
        uuid_pattern = re.compile(
            r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(run_id):
            return False, "Invalid run ID format"
        return True, None
    
    @staticmethod
    def validate_user_id(user_id: str) -> str:
        """Validate and sanitize user ID"""
        # Remove special characters
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', user_id)
        
        # Limit length
        sanitized = sanitized[:50]
        
        # Default if empty
        return sanitized if sanitized else 'default-user'
    
    @staticmethod
    def mask_sensitive_data(text: str) -> str:
        """Mask potentially sensitive data in logs"""
        # Mask email addresses
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '***@***.***', text)
        
        # Mask phone numbers (Chilean format)
        text = re.sub(r'\+?56?\s?9?\s?\d{4}\s?\d{4}', '***-****-****', text)
        
        # Mask RUT (Chilean ID)
        text = re.sub(r'\d{1,2}\.\d{3}\.\d{3}-[\dkK]', '**.***.***-*', text)
        
        # Mask credit card numbers
        text = re.sub(r'\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}', '****-****-****-****', text)
        
        return text
    
    @staticmethod
    def get_safe_error_message(error: Exception, is_production: bool = None) -> str:
        """Get safe error message for client response"""
        if is_production is None:
            is_production = Config.is_production()
        
        if is_production:
            # Generic message in production
            error_messages = {
                'ValidationError': 'Invalid input provided',
                'NotFoundError': 'Resource not found',
                'PermissionError': 'Permission denied',
                'TimeoutError': 'Request timeout',
            }
            error_type = type(error).__name__
            return error_messages.get(error_type, 'An error occurred processing your request')
        else:
            # More detailed message in development
            return str(error)[:500]  # Limit length