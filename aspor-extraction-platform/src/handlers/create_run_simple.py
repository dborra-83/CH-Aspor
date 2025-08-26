import json
import boto3
import os
from datetime import datetime
import uuid

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ['DYNAMODB_TABLE']
bucket_name = os.environ['DOCUMENTS_BUCKET']
table = dynamodb.Table(table_name)

def handler(event, context):
    """Create and process a new extraction run - Simplified version"""
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        model = body.get('model')  # 'A' or 'B'
        files = body.get('files', [])
        output_format = body.get('outputFormat', 'docx')
        user_id = body.get('userId', 'default-user')
        
        # Validate inputs
        if model not in ['A', 'B']:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Model must be A or B'})
            }
        
        if not files or len(files) > int(os.environ.get('MAX_FILES', 3)):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': f'Must provide 1-{os.environ.get("MAX_FILES", 3)} files'})
            }
        
        # Create run ID
        run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Create DynamoDB entry
        run_item = {
            'pk': f'USER#{user_id}',
            'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}',
            'runId': run_id,
            'model': model,
            'files': files,
            'outputFormat': output_format,
            'status': 'PENDING',
            'startedAt': timestamp.isoformat(),
            'userId': user_id,
            'gsi1pk': 'ALL_RUNS',
            'gsi1sk': f'{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'
        }
        
        table.put_item(Item=run_item)
        
        # For now, just return success with a mock download URL
        # The actual processing would happen here
        mock_output_key = f'outputs/{run_id}/report.{output_format}'
        
        # Generate presigned URL for mock download
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': mock_output_key},
            ExpiresIn=86400  # 24 hours
        )
        
        # Update DynamoDB with mock completion
        table.update_item(
            Key={
                'pk': f'USER#{user_id}',
                'sk': f'RUN#{timestamp.strftime("%Y%m%d%H%M%S")}#{run_id}'
            },
            UpdateExpression='SET #status = :status, #output = :output, #endedAt = :endedAt',
            ExpressionAttributeNames={
                '#status': 'status',
                '#output': 'output',
                '#endedAt': 'endedAt'
            },
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':output': {
                    output_format: mock_output_key,
                    'downloadUrl': download_url
                },
                ':endedAt': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'runId': run_id,
                'status': 'COMPLETED',
                'downloadUrl': download_url,
                'outputFormat': output_format,
                'message': 'Demo mode - no actual processing'
            })
        }
        
    except Exception as e:
        print(f"Error creating run: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }