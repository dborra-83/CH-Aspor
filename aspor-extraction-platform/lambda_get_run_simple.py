import json
import boto3
import os
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

def handler(event, context):
    """Get details of a specific run - simplified version"""
    try:
        run_id = event.get('pathParameters', {}).get('runId')
        user_id = event.get('queryStringParameters', {}).get('userId', 'default-user')
        
        print(f"Getting run: {run_id} for user: {user_id}")
        
        if not run_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Run ID is required'})
            }
        
        # Query for the run - scan all runs for this user and find the matching runId
        # Using scan because the SK contains timestamp which we don't know
        response = table.query(
            KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#')
        )
        
        # Filter in Python to find the matching runId
        matching_run = None
        for item in response.get('Items', []):
            if item.get('runId') == run_id:
                matching_run = item
                break
        
        response = {'Items': [matching_run]} if matching_run else {'Items': []}
        
        print(f"Query returned {len(response.get('Items', []))} items")
        
        if not response.get('Items'):
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Run not found'})
            }
        
        run = response['Items'][0]
        
        # Generate download URL for completed runs
        if run.get('status') == 'COMPLETED':
            output_format = run.get('outputFormat', 'docx')
            s3_key = f'outputs/{run_id}/report.{output_format}'
            
            try:
                # Generate presigned URL
                download_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': bucket_name,
                        'Key': s3_key,
                        'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{output_format}"'
                    },
                    ExpiresIn=3600
                )
                
                # Add to output
                if not run.get('output'):
                    run['output'] = {}
                run['output']['downloadUrl'] = download_url
                
                print(f"Generated download URL for {s3_key}")
                
            except Exception as e:
                print(f"Error generating URL: {str(e)}")
                # Still return the run even if URL generation fails
        
        # Remove internal fields
        internal_fields = ['pk', 'sk', 'gsi1pk', 'gsi1sk']
        for field in internal_fields:
            if field in run:
                del run[field]
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(run, default=str)
        }
        
    except Exception as e:
        print(f"Error getting run: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }