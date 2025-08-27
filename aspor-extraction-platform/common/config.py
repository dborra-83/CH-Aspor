"""
Centralized configuration management for ASPOR platform
"""
import os
from typing import Dict, Any


class Config:
    """Configuration management with environment variable support"""
    
    # Environment variables with defaults
    DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
    DOCUMENTS_BUCKET = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
    BEDROCK_MODEL = os.environ.get('BEDROCK_MODEL', 'anthropic.claude-3-haiku-20240307-v1:0')
    REGION = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Security settings
    ALLOWED_EXTENSIONS = ['pdf', 'docx', 'doc', 'txt']
    MAX_FILE_SIZE_MB = 25
    MAX_FILES_PER_RUN = 3
    PRESIGNED_URL_EXPIRY = 86400  # 24 hours
    DOWNLOAD_URL_EXPIRY = 3600    # 1 hour
    
    # API settings
    CORS_ORIGIN = os.environ.get('CORS_ORIGIN', '*')  # Should be restricted in production
    API_TIMEOUT = 900  # 15 minutes
    
    # Bedrock settings
    BEDROCK_CONFIG = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8000,
        "temperature": 0.3,
        "top_p": 0.95
    }
    
    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 60
    MAX_REQUESTS_PER_DAY = 1000
    
    @classmethod
    def get_headers(cls, additional_headers: Dict[str, str] = None) -> Dict[str, str]:
        """Get standard HTTP headers with CORS"""
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': cls.CORS_ORIGIN,
            'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
        }
        if additional_headers:
            headers.update(additional_headers)
        return headers
    
    @classmethod
    def validate_environment(cls) -> bool:
        """Validate required environment variables"""
        required = ['DYNAMODB_TABLE', 'DOCUMENTS_BUCKET']
        missing = [var for var in required if not os.environ.get(var)]
        
        if missing:
            print(f"Warning: Missing environment variables: {missing}")
            return False
        return True
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment"""
        return os.environ.get('ENVIRONMENT', 'dev').lower() == 'production'