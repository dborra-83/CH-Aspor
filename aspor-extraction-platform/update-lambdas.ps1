# PowerShell script to update all Lambda functions with simplified code

Write-Host "Updating Lambda functions with simplified code..." -ForegroundColor Yellow

# Create temporary directory for zip files
$tempDir = "lambda-zips"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Lambda functions to update
$functions = @(
    @{Name="aspor-create-run"; File="lambda_code.py"},
    @{Name="aspor-get-run"; File="lambda_get_run.py"},
    @{Name="aspor-list-runs"; File="lambda_list_runs.py"},
    @{Name="aspor-delete-run"; File="lambda_delete_run.py"},
    @{Name="aspor-presign"; File="lambda_presign.py"}
)

foreach ($func in $functions) {
    Write-Host "Updating $($func.Name)..." -ForegroundColor Cyan
    
    # Create zip file
    $zipFile = "$tempDir\$($func.Name).zip"
    
    # Copy the Python file to a temporary location with the name 'lambda_code.py'
    # AWS Lambda expects the handler to be in lambda_code.handler format
    $tempFile = "$tempDir\lambda_code.py"
    Copy-Item $func.File $tempFile -Force
    
    # Create zip archive
    Compress-Archive -Path $tempFile -DestinationPath $zipFile -Force
    
    # Update Lambda function code
    try {
        $cmd = "aws lambda update-function-code --function-name $($func.Name) --zip-file fileb://$zipFile --region us-east-1"
        Invoke-Expression $cmd | Out-Null
        
        Write-Host "  Updated $($func.Name)" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to update $($func.Name): $_" -ForegroundColor Red
    }
    
    # Clean up temp file
    Remove-Item $tempFile -Force
}

# Clean up
Remove-Item $tempDir -Recurse -Force

Write-Host "All Lambda functions updated!" -ForegroundColor Green
Write-Host "You can now test the application at your CloudFront URL" -ForegroundColor Yellow