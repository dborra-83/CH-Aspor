import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table_name = os.environ['DYNAMODB_TABLE']
table = dynamodb.Table(table_name)

def handler(event, context):
    """List all runs for a user"""
    try:
        query_params = event.get('queryStringParameters', {})
        user_id = query_params.get('userId', 'default-user')
        limit = int(query_params.get('limit', 20))
        last_evaluated_key = query_params.get('lastKey')
        
        # Build query parameters
        query_kwargs = {
            'KeyConditionExpression': Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#'),
            'Limit': limit,
            'ScanIndexForward': False  # Most recent first
        }
        
        if last_evaluated_key:
            query_kwargs['ExclusiveStartKey'] = json.loads(last_evaluated_key)
        
        # Query DynamoDB
        response = table.query(**query_kwargs)
        
        # Clean up items
        items = []
        for item in response['Items']:
            # Remove internal fields
            item.pop('pk', None)
            item.pop('sk', None)
            item.pop('gsi1pk', None)
            item.pop('gsi1sk', None)
            items.append(item)
        
        result = {
            'runs': items,
            'count': len(items)
        }
        
        # Add pagination key if there are more items
        if 'LastEvaluatedKey' in response:
            result['lastKey'] = json.dumps(response['LastEvaluatedKey'])
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(result, default=str)
        }
        
    except Exception as e:
        print(f"Error listing runs: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }