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
        
        # Query for the run using filter
        response = table.query(
            KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#'),
            FilterExpression=Attr('runId').eq(run_id)
        )
        
        if not response['Items']:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Run not found'})
            }
        
        run = response['Items'][0]
        
        # Generate fresh download URLs if output exists
        if run.get('output') and run.get('status') == 'COMPLETED':
            output = run['output']
            # Handle both dict and string formats
            if isinstance(output, dict):
                for format_type, s3_key in output.items():
                    if format_type in ['docx', 'pdf'] and s3_key:
                        try:
                            url = s3_client.generate_presigned_url(
                                'get_object',
                                Params={'Bucket': bucket_name, 'Key': s3_key},
                                ExpiresIn=3600  # 1 hour
                            )
                            run['output'][f'{format_type}_url'] = url
                        except Exception as url_error:
                            print(f"Error generating URL for {s3_key}: {str(url_error)}")
        
        # Always generate fresh download URL
        if run.get('status') == 'COMPLETED':
            output_format = run.get('outputFormat', 'docx')
            
            # Check if we have the S3 key in output
            if run.get('output') and isinstance(run['output'], dict):
                s3_key = run['output'].get(output_format) or run['output'].get('docx') or run['output'].get('pdf')
                if not s3_key:
                    # Try to construct the key
                    s3_key = f'outputs/{run_id}/report.{output_format}'
            else:
                # Construct default key
                s3_key = f'outputs/{run_id}/report.{output_format}'
            
            try:
                # Generate fresh presigned URL
                download_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': bucket_name,
                        'Key': s3_key,
                        'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{output_format}"'
                    },
                    ExpiresIn=3600  # 1 hour
                )
                
                if not run.get('output'):
                    run['output'] = {}
                run['output']['downloadUrl'] = download_url
                run['output'][output_format] = s3_key
                
                print(f"Generated download URL for {s3_key}")
            except Exception as e:
                print(f"Error generating download URL: {str(e)}")
        
        # Clean up internal fields (create a copy to avoid modification during iteration)
        fields_to_remove = ['pk', 'sk', 'gsi1pk', 'gsi1sk']
        for field in fields_to_remove:
            run.pop(field, None)
        
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