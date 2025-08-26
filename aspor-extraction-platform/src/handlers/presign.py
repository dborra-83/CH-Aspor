import json
import boto3
import os
from datetime import datetime
import uuid

s3_client = boto3.client('s3')
bucket_name = os.environ['DOCUMENTS_BUCKET']
max_files = int(os.environ.get('MAX_FILES', 3))
max_file_size_mb = int(os.environ.get('MAX_FILE_SIZE_MB', 25))

def handler(event, context):
    """Generate presigned URLs for file uploads"""
    try:
        body = json.loads(event.get('body', '{}'))
        file_count = body.get('file_count', 1)
        
        # Validate file count
        if file_count > max_files or file_count < 1:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': f'File count must be between 1 and {max_files}'
                })
            }
        
        # Generate presigned URLs
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        session_id = str(uuid.uuid4())[:8]
        presigned_urls = []
        
        for i in range(file_count):
            file_key = f"uploads/{timestamp}-{session_id}/file-{i+1}"
            
            # Generate presigned POST URL
            presigned_post = s3_client.generate_presigned_post(
                Bucket=bucket_name,
                Key=file_key,
                Fields={
                    'Content-Type': 'application/octet-stream'
                },
                Conditions=[
                    {'Content-Type': 'application/octet-stream'},
                    ['content-length-range', 0, max_file_size_mb * 1024 * 1024]
                ],
                ExpiresIn=3600  # 1 hour
            )
            
            presigned_urls.append({
                'file_index': i + 1,
                'url': presigned_post['url'],
                'fields': presigned_post['fields'],
                's3_key': file_key,
                'max_size_mb': max_file_size_mb
            })
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'session_id': f"{timestamp}-{session_id}",
                'presigned_urls': presigned_urls,
                'expires_in': 3600
            })
        }
        
    except Exception as e:
        print(f"Error generating presigned URLs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }