# PowerShell script to deploy processing function

Write-Host "Deploying document processing capability..." -ForegroundColor Yellow

# First, let's check if Bedrock is available
Write-Host "Checking Bedrock availability..." -ForegroundColor Cyan
$bedrockModels = aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'claude')].[modelId, modelName]" --output table 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Bedrock may not be enabled. Processing will use mock responses." -ForegroundColor Yellow
} else {
    Write-Host "Bedrock models available:" -ForegroundColor Green
    Write-Host $bedrockModels
}

# Create the processing Lambda function
Write-Host "`nCreating processing Lambda function..." -ForegroundColor Cyan

# Package the function
$tempDir = "temp-process"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
Copy-Item lambda_process_run.py "$tempDir\lambda_code.py" -Force

# Add requirements if needed
$requirements = @"
boto3
python-docx
"@
$requirements | Out-File "$tempDir\requirements.txt" -Encoding UTF8

# Create zip
Compress-Archive -Path "$tempDir\*" -DestinationPath "process-function.zip" -Force

# Check if function exists
$functionExists = aws lambda get-function --function-name aspor-process-run --region us-east-1 2>$null

if ($functionExists) {
    Write-Host "Updating existing process function..." -ForegroundColor Yellow
    aws lambda update-function-code `
        --function-name aspor-process-run `
        --zip-file fileb://process-function.zip `
        --region us-east-1 | Out-Null
} else {
    Write-Host "Creating new process function..." -ForegroundColor Yellow
    
    # Get the execution role from another Lambda
    $roleArn = aws lambda get-function-configuration `
        --function-name aspor-create-run `
        --query 'Role' `
        --output text `
        --region us-east-1
    
    if (-not $roleArn) {
        Write-Host "Error: Could not find execution role. Please ensure stack is deployed." -ForegroundColor Red
        exit 1
    }
    
    aws lambda create-function `
        --function-name aspor-process-run `
        --runtime python3.12 `
        --role $roleArn `
        --handler lambda_code.handler `
        --timeout 900 `
        --memory-size 3008 `
        --environment "Variables={DYNAMODB_TABLE=aspor-extractions,DOCUMENTS_BUCKET=aspor-documents-520754296204}" `
        --zip-file fileb://process-function.zip `
        --region us-east-1 | Out-Null
    
    # Add permissions for Bedrock and Textract
    Write-Host "Adding permissions for Bedrock and Textract..." -ForegroundColor Cyan
    
    $policyDocument = @{
        Version = "2012-10-17"
        Statement = @(
            @{
                Effect = "Allow"
                Action = @(
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                )
                Resource = "arn:aws:bedrock:*::foundation-model/*"
            },
            @{
                Effect = "Allow"
                Action = @(
                    "textract:DetectDocumentText",
                    "textract:AnalyzeDocument",
                    "textract:StartDocumentTextDetection",
                    "textract:GetDocumentTextDetection"
                )
                Resource = "*"
            }
        )
    } | ConvertTo-Json -Depth 10
    
    $policyDocument | Out-File "bedrock-policy.json" -Encoding UTF8
    
    # Attach inline policy
    aws iam put-role-policy `
        --role-name (Split-Path $roleArn -Leaf) `
        --policy-name AsporBedrockTextractPolicy `
        --policy-document file://bedrock-policy.json `
        --region us-east-1
    
    Remove-Item "bedrock-policy.json" -Force
}

Write-Host "Process function deployed!" -ForegroundColor Green

# Update create-run function to use v2
Write-Host "`nUpdating create-run function to use async processing..." -ForegroundColor Cyan
Copy-Item lambda_code_v2.py "$tempDir\lambda_code.py" -Force
Compress-Archive -Path "$tempDir\lambda_code.py" -DestinationPath "create-run-v2.zip" -Force
aws lambda update-function-code `
    --function-name aspor-create-run `
    --zip-file fileb://create-run-v2.zip `
    --region us-east-1 | Out-Null

# Update environment variable
aws lambda update-function-configuration `
    --function-name aspor-create-run `
    --environment "Variables={DYNAMODB_TABLE=aspor-extractions,DOCUMENTS_BUCKET=aspor-documents-520754296204,PROCESS_FUNCTION=aspor-process-run}" `
    --region us-east-1 | Out-Null

Write-Host "Create-run function updated!" -ForegroundColor Green

# Clean up
Remove-Item $tempDir -Recurse -Force
Remove-Item "process-function.zip" -Force
Remove-Item "create-run-v2.zip" -Force

Write-Host "`nDeployment complete!" -ForegroundColor Green
Write-Host "The platform now supports:" -ForegroundColor Yellow
Write-Host "  - Document text extraction with AWS Textract" -ForegroundColor Cyan
Write-Host "  - AI analysis with Bedrock Claude (if enabled)" -ForegroundColor Cyan
Write-Host "  - DOCX/PDF report generation" -ForegroundColor Cyan
Write-Host "  - Asynchronous processing for large documents" -ForegroundColor Cyan

Write-Host "`nTest the updated platform at: https://d3qiqro0ukto58.cloudfront.net" -ForegroundColor Yellow