# PowerShell script to deploy all fixes

Write-Host "Deploying fixes for download issues..." -ForegroundColor Yellow

# Update get-run Lambda
Write-Host "Updating get-run Lambda..." -ForegroundColor Cyan
$tempDir = "temp-fixes"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

Copy-Item lambda_get_run.py "$tempDir\lambda_code.py" -Force
Compress-Archive -Path "$tempDir\lambda_code.py" -DestinationPath "get-run-fix.zip" -Force
aws lambda update-function-code --function-name aspor-get-run --zip-file fileb://get-run-fix.zip --region us-east-1 | Out-Null
Write-Host "  Get-run updated" -ForegroundColor Green

# Clean up
Remove-Item $tempDir -Recurse -Force
Remove-Item "get-run-fix.zip" -Force

Write-Host "`nAll fixes deployed!" -ForegroundColor Green
Write-Host "Download links should now work correctly for:" -ForegroundColor Yellow
Write-Host "  - Model A (Contragarantias)" -ForegroundColor Cyan
Write-Host "  - Model B (Informes Sociales)" -ForegroundColor Cyan  
Write-Host "  - Historical runs in the history section" -ForegroundColor Cyan

Write-Host "`nTest at: https://d3qiqro0ukto58.cloudfront.net" -ForegroundColor Yellow