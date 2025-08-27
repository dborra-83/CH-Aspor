# PowerShell script to update Lambda functions with optimized code and common library
Write-Host "Updating Lambda functions with optimized code..." -ForegroundColor Cyan

# Check if deployment packages exist
if (-not (Test-Path "lambda-create-run.zip")) {
    Write-Host "Deployment packages not found. Creating them now..." -ForegroundColor Yellow
    .\create-deployment-package.ps1
}

# Lambda functions to update with their packages
$functions = @(
    @{Name="aspor-create-run"; Package="lambda-create-run.zip"},
    @{Name="aspor-get-run"; Package="lambda-get-run.zip"},
    @{Name="aspor-list-runs"; Package="lambda-list-runs.zip"},
    @{Name="aspor-delete-run"; Package="lambda-delete-run.zip"},
    @{Name="aspor-presign"; Package="lambda-presign.zip"}
)

$successCount = 0
$failureCount = 0

foreach ($func in $functions) {
    Write-Host "Updating $($func.Name)..." -ForegroundColor Yellow
    
    if (-not (Test-Path $func.Package)) {
        Write-Host "  Package $($func.Package) not found, skipping..." -ForegroundColor Red
        $failureCount++
        continue
    }
    
    try {
        # Update Lambda function code
        $result = aws lambda update-function-code `
            --function-name $func.Name `
            --zip-file "fileb://$($func.Package)" `
            --region us-east-1 `
            --output json | ConvertFrom-Json
        
        if ($result.LastUpdateStatus -eq "Successful" -or $result.State -eq "Active") {
            Write-Host "  ✓ Updated $($func.Name) successfully" -ForegroundColor Green
            Write-Host "    Runtime: $($result.Runtime), Size: $($result.CodeSize) bytes" -ForegroundColor Gray
            $successCount++
        } else {
            Write-Host "  ⚠ Updated $($func.Name) but status is: $($result.LastUpdateStatus)" -ForegroundColor Yellow
            $successCount++
        }
    } catch {
        Write-Host "  ✗ Failed to update $($func.Name): $_" -ForegroundColor Red
        $failureCount++
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Deployment Summary:" -ForegroundColor Cyan
Write-Host "  Successful: $successCount functions" -ForegroundColor Green
if ($failureCount -gt 0) {
    Write-Host "  Failed: $failureCount functions" -ForegroundColor Red
}

if ($successCount -eq $functions.Count) {
    Write-Host "`n✓ All Lambda functions updated successfully!" -ForegroundColor Green
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Test the API endpoints" -ForegroundColor White
    Write-Host "  2. Monitor CloudWatch logs for any errors" -ForegroundColor White
    Write-Host "  3. Visit: https://d3qiqro0ukto58.cloudfront.net" -ForegroundColor Yellow
} else {
    Write-Host "`n⚠ Some functions failed to update. Please check the errors above." -ForegroundColor Yellow
}