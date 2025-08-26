# PowerShell script to deploy all updates

Write-Host "Deploying all updates..." -ForegroundColor Yellow

# Update Lambda functions
$functions = @(
    @{Name="aspor-create-run"; File="lambda_code.py"},
    @{Name="aspor-get-run"; File="lambda_get_run.py"},
    @{Name="aspor-list-runs"; File="lambda_list_runs.py"},
    @{Name="aspor-delete-run"; File="lambda_delete_run.py"},
    @{Name="aspor-presign"; File="lambda_presign.py"}
)

Write-Host "Updating Lambda functions..." -ForegroundColor Cyan
foreach ($func in $functions) {
    $tempDir = "temp-$($func.Name)"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    Copy-Item $func.File "$tempDir\lambda_code.py" -Force
    Compress-Archive -Path "$tempDir\lambda_code.py" -DestinationPath "$($func.Name).zip" -Force
    aws lambda update-function-code --function-name $func.Name --zip-file "fileb://$($func.Name).zip" --region us-east-1 | Out-Null
    Write-Host "  Updated $($func.Name)" -ForegroundColor Green
    Remove-Item $tempDir -Recurse -Force
    Remove-Item "$($func.Name).zip" -Force
}

# Update frontend
Write-Host "Updating frontend..." -ForegroundColor Cyan
aws s3 cp frontend/index.html s3://aspor-website-520754296204/index.html --region us-east-1
Write-Host "  Frontend updated" -ForegroundColor Green

# Invalidate CloudFront cache
Write-Host "Invalidating CloudFront cache..." -ForegroundColor Cyan
$distributionId = aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='aspor-platform Distribution'].Id" --output text --region us-east-1
if ($distributionId) {
    aws cloudfront create-invalidation --distribution-id $distributionId --paths "/*" --region us-east-1 | Out-Null
    Write-Host "  Cache invalidated" -ForegroundColor Green
} else {
    Write-Host "  CloudFront distribution not found" -ForegroundColor Yellow
}

Write-Host "All updates deployed successfully!" -ForegroundColor Green
Write-Host "Test the application at: https://d3qiqro0ukto58.cloudfront.net" -ForegroundColor Yellow