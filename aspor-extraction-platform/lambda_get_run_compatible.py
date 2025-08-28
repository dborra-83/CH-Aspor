import json
import boto3
import os
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

table_name = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
bucket_name = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
table = dynamodb.Table(table_name)

# CORS headers
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
}

def handler(event, context):
    """Get details of a specific run including analysis text"""
    
    print(f"Get run event: {json.dumps(event)}")
    
    # Handle OPTIONS request for CORS preflight
    if event.get('httpMethod') == 'OPTIONS' or event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': ''
        }
    
    try:
        # Get run_id from path parameters
        run_id = None
        if event.get('pathParameters'):
            run_id = event['pathParameters'].get('runId')
        
        # Also check rawPath for HTTP API
        if not run_id and event.get('rawPath'):
            # Extract from path like /runs/{runId}
            path_parts = event['rawPath'].split('/')
            if len(path_parts) >= 3 and path_parts[-2] == 'runs':
                run_id = path_parts[-1]
        
        # Get user_id from query parameters
        user_id = 'web-user'  # Default
        if event.get('queryStringParameters'):
            user_id = event['queryStringParameters'].get('userId', 'web-user')
        
        print(f"Looking for run {run_id} for user {user_id}")
        
        if not run_id:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'Run ID is required'})
            }
        
        # Query for the run using filter
        try:
            response = table.query(
                KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#'),
                FilterExpression=Attr('runId').eq(run_id),
                Limit=10  # Limit results for performance
            )
            
            print(f"Query returned {len(response.get('Items', []))} items")
            
            if not response['Items']:
                # Try with default user if not found
                if user_id != 'web-user':
                    print("Retrying with default user web-user")
                    response = table.query(
                        KeyConditionExpression=Key('pk').eq('USER#web-user') & Key('sk').begins_with('RUN#'),
                        FilterExpression=Attr('runId').eq(run_id),
                        Limit=10
                    )
                
                if not response['Items']:
                    return {
                        'statusCode': 404,
                        'headers': CORS_HEADERS,
                        'body': json.dumps({'error': 'Run not found', 'runId': run_id})
                    }
            
            run = response['Items'][0]
            print(f"Found run with status: {run.get('status')}")
            
        except Exception as query_error:
            print(f"Query error: {str(query_error)}")
            return {
                'statusCode': 500,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'Database query error', 'details': str(query_error)[:200]})
            }
        
        # Try to get analysis text from S3 if run is completed
        analysis_text = None
        if run.get('status') == 'COMPLETED':
            try:
                # Try multiple possible locations for the analysis text
                possible_keys = [
                    f'outputs/{run_id}/analysis.txt',
                    f'extracted/{run_id}/extracted_text.txt'
                ]
                
                for analysis_key in possible_keys:
                    try:
                        print(f"Attempting to fetch analysis from S3: {analysis_key}")
                        analysis_obj = s3_client.get_object(
                            Bucket=bucket_name,
                            Key=analysis_key
                        )
                        analysis_text = analysis_obj['Body'].read().decode('utf-8')
                        print(f"Successfully retrieved analysis text: {len(analysis_text)} characters")
                        break
                    except:
                        continue
                
            except Exception as e:
                print(f"Could not retrieve analysis text: {str(e)}")
                # Not critical - analysis might not be saved as text file
        
        # Generate fresh download URLs if output exists
        if run.get('output') and run.get('status') == 'COMPLETED':
            try:
                output = run['output']
                
                # Handle both dict and string formats
                if isinstance(output, dict):
                    # New format with multiple outputs
                    for format_type, s3_key in output.items():
                        if format_type in ['docx', 'pdf', 'txt'] and s3_key:
                            try:
                                # Skip if it's a URL, not an S3 key
                                if s3_key.startswith('http'):
                                    continue
                                    
                                url = s3_client.generate_presigned_url(
                                    'get_object',
                                    Params={
                                        'Bucket': bucket_name,
                                        'Key': s3_key,
                                        'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{format_type}"'
                                    },
                                    ExpiresIn=3600
                                )
                                run[f'{format_type}DownloadUrl'] = url
                                
                                # Set the main downloadUrl based on output format
                                if format_type == run.get('outputFormat', 'docx'):
                                    run['downloadUrl'] = url
                                    
                            except Exception as e:
                                print(f"Error generating presigned URL for {format_type}: {str(e)}")
                                
                elif isinstance(output, str) and not output.startswith('http'):
                    # Legacy format - single S3 key
                    try:
                        format_type = run.get('outputFormat', 'docx')
                        url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={
                                'Bucket': bucket_name,
                                'Key': output,
                                'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{format_type}"'
                            },
                            ExpiresIn=3600
                        )
                        run['downloadUrl'] = url
                    except Exception as e:
                        print(f"Error generating presigned URL: {str(e)}")
                        
            except Exception as e:
                print(f"Error processing output URLs: {str(e)}")
        
        # Add analysis text to response if available
        if analysis_text:
            run['analysisText'] = analysis_text
        
        # Add processing status fields if they exist
        processing_fields = [
            'fileUploadSuccess', 'textractStarted', 'textractSuccess',
            'bedrockStarted', 'bedrockSuccess', 'outputGenerated',
            'processingComplete', 'extractedTextLength', 'pagesProcessed',
            'totalProcessingTime', 'textractStatus', 'bedrockStatus'
        ]
        
        # Include all tracking fields in response
        response_data = {}
        for field in processing_fields:
            if field in run:
                response_data[field] = run[field]
        
        # Add core fields
        response_data.update({
            'runId': run_id,
            'status': run.get('status', 'UNKNOWN'),
            'model': run.get('model'),
            'fileNames': run.get('fileNames', []),
            'startedAt': run.get('startedAt'),
            'endedAt': run.get('endedAt')
        })
        
        # Add download URL if available
        if 'downloadUrl' in run:
            response_data['downloadUrl'] = run['downloadUrl']
        
        # Add analysis text if available
        if analysis_text:
            response_data['analysisText'] = analysis_text
        
        # Add any error information
        if 'error' in run:
            response_data['error'] = run['error']
        if 'textractError' in run:
            response_data['textractError'] = run['textractError']
        if 'bedrockError' in run:
            response_data['bedrockError'] = run['bedrockError']
        
        print(f"Returning run data with {len(response_data)} fields")
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        print(f"Error getting run: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)[:200] if not os.environ.get('PRODUCTION') else None
            })
        }