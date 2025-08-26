import json
import boto3
import os
import uuid
from datetime import datetime

s3_client = boto3.client('s3')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')

def handler(event, context):
    """Generate presigned URLs for file upload"""
    try:
        body = json.loads(event.get('body', '{}'))
        file_count = body.get('file_count', 1)
        
        if file_count < 1 or file_count > 3:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'File count must be between 1 and 3'})
            }
        
        # Generate presigned URLs for each file
        presigned_urls = []
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        
        for i in range(file_count):
            unique_id = str(uuid.uuid4())[:8]
            s3_key = f'uploads/{timestamp}/{unique_id}/file_{i+1}'
            
            # Generate presigned POST data
            presigned_post = s3_client.generate_presigned_post(
                Bucket=bucket_name,
                Key=s3_key,
                ExpiresIn=3600  # URL expires in 1 hour
            )
            
            presigned_urls.append({
                'url': presigned_post['url'],
                'fields': presigned_post['fields'],
                's3_key': s3_key
            })
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'presigned_urls': presigned_urls
            })
        }
        
    except Exception as e:
        print(f"Error generating presigned URLs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }