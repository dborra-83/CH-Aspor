import json
import boto3
import os
import uuid
from datetime import datetime

s3_client = boto3.client('s3')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')

# CORS headers
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
}

def handler(event, context):
    """Generate presigned URLs for file upload"""
    
    # Handle OPTIONS request for CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': ''
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
        file_count = body.get('file_count', 1)
        
        if file_count < 1 or file_count > 3:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'File count must be between 1 and 3'})
            }
        
        # Generate presigned URLs for each file
        uploads = []
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        
        for i in range(file_count):
            unique_id = str(uuid.uuid4())[:8]
            s3_key = f'uploads/{timestamp}/{unique_id}/file_{i+1}'
            
            # Generate presigned POST data
            presigned_post = s3_client.generate_presigned_post(
                Bucket=bucket_name,
                Key=s3_key,
                Fields={
                    'Content-Type': 'application/octet-stream',
                    'success_action_status': '200'
                },
                Conditions=[
                    {'Content-Type': 'application/octet-stream'},
                    ['content-length-range', 0, 26214400]  # Max 25MB
                ],
                ExpiresIn=3600  # URL expires in 1 hour
            )
            
            uploads.append({
                'url': presigned_post['url'],
                'fields': presigned_post['fields'],
                's3_key': s3_key
            })
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'uploads': uploads,
                'expires_in': 3600
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': 'Internal server error'})
        }