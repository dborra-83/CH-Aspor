import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
table = dynamodb.Table(table_name)

def handler(event, context):
    """List all runs for a user"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        user_id = query_params.get('userId', 'default-user')
        limit = min(int(query_params.get('limit', 50)), 100)  # Increased default and max
        last_evaluated_key = query_params.get('lastKey')
        
        # Build query parameters
        query_kwargs = {
            'KeyConditionExpression': Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#'),
            'Limit': limit,
            'ScanIndexForward': False  # Most recent first
        }
        
        if last_evaluated_key:
            try:
                query_kwargs['ExclusiveStartKey'] = json.loads(last_evaluated_key)
            except:
                pass  # Ignore invalid lastKey
        
        # Query DynamoDB
        response = table.query(**query_kwargs)
        
        # Clean up items and add display info
        items = []
        for item in response['Items']:
            # Add display-friendly fields
            if item.get('fileNames'):
                item['displayName'] = ', '.join(item['fileNames'][:2])
                if len(item['fileNames']) > 2:
                    item['displayName'] += f' (+{len(item["fileNames"])-2} more)'
            else:
                item['displayName'] = f"Run {item.get('runId', '')[:8]}..."
            
            # Add model name
            if item.get('model') == 'A':
                item['modelName'] = 'Contragarantías/ASPOR'
            elif item.get('model') == 'B':
                item['modelName'] = 'Informes Sociales'
            else:
                item['modelName'] = item.get('model', 'Unknown')
            
            # Remove internal fields
            item.pop('pk', None)
            item.pop('sk', None)
            item.pop('gsi1pk', None)
            item.pop('gsi1sk', None)
            items.append(item)
        
        result = {
            'runs': items,
            'count': len(items),
            'hasMore': 'LastEvaluatedKey' in response
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
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }