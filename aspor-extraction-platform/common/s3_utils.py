"""
S3 utilities for ASPOR platform
"""
import boto3
import json
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
from .config import Config
from .security import SecurityValidator


class S3Helper:
    """S3 operations helper with error handling"""
    
    def __init__(self, bucket_name: str = None):
        self.s3_client = boto3.client('s3', region_name=Config.REGION)
        self.bucket_name = bucket_name or Config.DOCUMENTS_BUCKET
    
    def extract_text_from_file(self, s3_key: str) -> str:
        """
        Extract text content from S3 file
        Unified method to replace duplicated extract_text_from_s3 functions
        """
        try:
            # Validate file first
            is_valid, error = SecurityValidator.validate_file(s3_key)
            if not is_valid:
                raise ValueError(error)
            
            # Get object from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response['Body'].read()
            
            # Try to decode as text
            try:
                text = content.decode('utf-8')
                return SecurityValidator.sanitize_user_input(text)
            except UnicodeDecodeError:
                # Binary file, return placeholder
                return "Documento binario cargado para análisis."
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                print(f"File not found: {s3_key}")
                return "Archivo no encontrado."
            else:
                print(f"S3 error reading {s3_key}: {str(e)}")
                return "Error al leer el documento."
        except Exception as e:
            print(f"Unexpected error reading {s3_key}: {str(e)}")
            return "Documento de prueba para análisis ASPOR."
    
    def save_file(self, key: str, content: bytes, content_type: str = 'text/plain',
                  metadata: Dict[str, str] = None) -> bool:
        """Save file to S3 with metadata"""
        try:
            # Sanitize key
            key = SecurityValidator.sanitize_filename(key)
            
            put_params = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': content,
                'ContentType': content_type,
                'ServerSideEncryption': 'AES256'
            }
            
            if metadata:
                put_params['Metadata'] = metadata
            
            self.s3_client.put_object(**put_params)
            print(f"File saved to S3: {key}")
            return True
            
        except Exception as e:
            print(f"Error saving file to S3: {str(e)}")
            return False
    
    def generate_presigned_url(self, key: str, expiry: int = None, 
                              download: bool = False) -> Optional[str]:
        """Generate presigned URL for file access"""
        try:
            expiry = expiry or Config.DOWNLOAD_URL_EXPIRY
            
            params = {
                'Bucket': self.bucket_name,
                'Key': key
            }
            
            if download:
                filename = key.split('/')[-1]
                params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'
            
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expiry
            )
            return url
            
        except Exception as e:
            print(f"Error generating presigned URL: {str(e)}")
            return None
    
    def generate_presigned_post(self, key: str, expiry: int = None,
                               max_size: int = None) -> Optional[Dict[str, Any]]:
        """Generate presigned POST data for file upload"""
        try:
            expiry = expiry or Config.PRESIGNED_URL_EXPIRY
            max_size = max_size or (Config.MAX_FILE_SIZE_MB * 1024 * 1024)
            
            # Sanitize key
            key = SecurityValidator.sanitize_filename(key)
            
            conditions = [
                ["content-length-range", 0, max_size],
                {"success_action_status": "200"}
            ]
            
            response = self.s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=key,
                Conditions=conditions,
                ExpiresIn=expiry
            )
            
            response['s3_key'] = key
            return response
            
        except Exception as e:
            print(f"Error generating presigned POST: {str(e)}")
            return None
    
    def delete_file(self, key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            print(f"Deleted S3 object: {key}")
            return True
        except Exception as e:
            print(f"Error deleting S3 object {key}: {str(e)}")
            return False
    
    def file_exists(self, key: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def get_file_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get file metadata from S3"""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                'size': response['ContentLength'],
                'content_type': response.get('ContentType'),
                'last_modified': response['LastModified'].isoformat(),
                'metadata': response.get('Metadata', {})
            }
        except Exception as e:
            print(f"Error getting metadata for {key}: {str(e)}")
            return None