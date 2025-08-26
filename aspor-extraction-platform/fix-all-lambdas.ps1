# PowerShell script to fix all Lambda functions

Write-Host "Fixing all Lambda functions..." -ForegroundColor Yellow

$functions = @(
    @{Name="aspor-create-run"; File="lambda_code.py"},
    @{Name="aspor-get-run"; File="lambda_get_run.py"},
    @{Name="aspor-list-runs"; File="lambda_list_runs.py"},
    @{Name="aspor-delete-run"; File="lambda_delete_run.py"},
    @{Name="aspor-presign"; File="lambda_presign.py"}
)

foreach ($func in $functions) {
    Write-Host "Updating $($func.Name)..." -ForegroundColor Cyan
    
    # Create temp directory
    $tempDir = "temp-lambda-$($func.Name)"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    # Copy Python file as lambda_code.py
    Copy-Item $func.File "$tempDir\lambda_code.py" -Force
    
    # Create zip
    $zipFile = "$($func.Name).zip"
    Compress-Archive -Path "$tempDir\lambda_code.py" -DestinationPath $zipFile -Force
    
    # Update Lambda
    aws lambda update-function-code --function-name $func.Name --zip-file "fileb://$zipFile" --region us-east-1 | Out-Null
    
    Write-Host "  Updated $($func.Name)" -ForegroundColor Green
    
    # Cleanup
    Remove-Item $tempDir -Recurse -Force
    Remove-Item $zipFile -Force
}

Write-Host "All Lambda functions fixed!" -ForegroundColor Green