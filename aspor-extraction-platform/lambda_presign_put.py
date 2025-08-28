import json
import boto3
import os
import uuid
from datetime import datetime

s3_client = boto3.client('s3', region_name='us-east-1')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')

# CORS headers
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS,PUT'
}

def handler(event, context):
    """Generate presigned URLs for file upload using PUT method"""
    
    # Handle OPTIONS request for CORS preflight
    if event.get('httpMethod') == 'OPTIONS' or event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': ''
        }
    
    try:
        # Parse body
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except:
                body = {}
        
        file_count = body.get('file_count', 1)
        
        if file_count < 1 or file_count > 3:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'File count must be between 1 and 3'})
            }
        
        # Generate presigned URLs for each file using PUT method
        uploads = []
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        
        for i in range(file_count):
            unique_id = str(uuid.uuid4())[:8]
            s3_key = f'uploads/{timestamp}/{unique_id}/file_{i+1}'
            
            # Generate presigned PUT URL - much simpler than POST
            try:
                presigned_url = s3_client.generate_presigned_url(
                    'put_object',
                    Params={
                        'Bucket': bucket_name,
                        'Key': s3_key,
                        'ContentType': 'application/octet-stream'
                    },
                    ExpiresIn=3600  # 1 hour
                )
                
                uploads.append({
                    'url': presigned_url,
                    'method': 'PUT',
                    's3_key': s3_key
                })
                
                print(f"Generated presigned PUT URL for key: {s3_key}")
                
            except Exception as e:
                print(f"Error generating presigned URL: {str(e)}")
                raise
        
        response_body = {
            'uploads': uploads,
            'expires_in': 3600
        }
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"Lambda error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e) if not os.environ.get('PRODUCTION') else None
            })
        }