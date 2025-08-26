import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ['DYNAMODB_TABLE']
bucket_name = os.environ['DOCUMENTS_BUCKET']
table = dynamodb.Table(table_name)

def handler(event, context):
    """Delete a run (soft delete by default)"""
    try:
        run_id = event.get('pathParameters', {}).get('runId')
        user_id = event.get('queryStringParameters', {}).get('userId', 'default-user')
        hard_delete = event.get('queryStringParameters', {}).get('hardDelete', 'false').lower() == 'true'
        
        if not run_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Run ID is required'})
            }
        
        # Find the run
        response = table.query(
            KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#'),
            FilterExpression='runId = :runId',
            ExpressionAttributeValues={':runId': run_id}
        )
        
        if not response['Items']:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Run not found'})
            }
        
        run = response['Items'][0]
        
        if hard_delete:
            # Delete S3 objects
            if run.get('output'):
                for format_type, s3_key in run['output'].items():
                    if format_type in ['docx', 'pdf']:
                        try:
                            s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
                        except Exception as s3_error:
                            print(f"Error deleting S3 object {s3_key}: {str(s3_error)}")
            
            # Delete from DynamoDB
            table.delete_item(
                Key={
                    'pk': run['pk'],
                    'sk': run['sk']
                }
            )
            
            message = 'Run permanently deleted'
        else:
            # Soft delete - just mark as deleted
            table.update_item(
                Key={
                    'pk': run['pk'],
                    'sk': run['sk']
                },
                UpdateExpression='SET #status = :status, #deletedAt = :deletedAt',
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#deletedAt': 'deletedAt'
                },
                ExpressionAttributeValues={
                    ':status': 'DELETED',
                    ':deletedAt': datetime.utcnow().isoformat()
                }
            )
            
            message = 'Run marked as deleted'
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': message,
                'runId': run_id
            })
        }
        
    except Exception as e:
        print(f"Error deleting run: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }