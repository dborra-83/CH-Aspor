import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

def handler(event, context):
    """Delete a specific run and its associated files"""
    try:
        run_id = event.get('pathParameters', {}).get('runId')
        user_id = event.get('queryStringParameters', {}).get('userId', 'default-user')
        
        if not run_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Run ID is required'})
            }
        
        # Query for the run
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
        
        # Delete associated S3 objects if they exist
        if run.get('output'):
            for format_type, s3_key in run['output'].items():
                if format_type in ['docx', 'pdf']:
                    try:
                        s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
                        print(f"Deleted S3 object: {s3_key}")
                    except Exception as e:
                        print(f"Error deleting S3 object {s3_key}: {str(e)}")
        
        # Delete from DynamoDB
        table.delete_item(
            Key={
                'pk': run['pk'],
                'sk': run['sk']
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': f'Run {run_id} deleted successfully'})
        }
        
    except Exception as e:
        print(f"Error deleting run: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }