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
    """Get details of a specific run"""
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
        
        # Generate fresh download URLs if output exists
        if run.get('output') and run['status'] == 'COMPLETED':
            for format_type, s3_key in run['output'].items():
                if format_type in ['docx', 'pdf']:
                    run['output'][f'{format_type}_url'] = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': s3_key},
                        ExpiresIn=3600  # 1 hour
                    )
        
        # Clean up internal fields
        run.pop('pk', None)
        run.pop('sk', None)
        run.pop('gsi1pk', None)
        run.pop('gsi1sk', None)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(run, default=str)
        }
        
    except Exception as e:
        print(f"Error getting run: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }