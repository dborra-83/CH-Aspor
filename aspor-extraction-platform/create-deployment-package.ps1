# PowerShell script to create deployment packages with common library
Write-Host "Creating deployment packages for ASPOR Lambda functions..." -ForegroundColor Cyan

# Clean up previous packages
Remove-Item -Path "*.zip" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "temp-deploy" -Recurse -Force -ErrorAction SilentlyContinue

# Create temporary deployment directory
New-Item -ItemType Directory -Force -Path "temp-deploy" | Out-Null
New-Item -ItemType Directory -Force -Path "temp-deploy/common" | Out-Null

# Copy common library
Write-Host "Copying common library..." -ForegroundColor Yellow
Copy-Item -Path "common/*.py" -Destination "temp-deploy/common/" -Force

# Function to create deployment package
function Create-Package {
    param(
        [string]$SourceFile,
        [string]$TargetName,
        [string]$OutputZip
    )
    
    Write-Host "Creating package for $TargetName..." -ForegroundColor Yellow
    
    # Copy the Lambda function
    Copy-Item -Path $SourceFile -Destination "temp-deploy/$TargetName" -Force
    
    # Create ZIP
    Compress-Archive -Path "temp-deploy/*" -DestinationPath $OutputZip -Force
    
    # Remove the Lambda file for next iteration
    Remove-Item -Path "temp-deploy/$TargetName" -Force
    
    Write-Host "  Created: $OutputZip" -ForegroundColor Green
}

# Create main Lambda package
Create-Package -SourceFile "lambda_code.py" -TargetName "lambda_code.py" -OutputZip "lambda-create-run.zip"

# Create other Lambda packages (these don't need common library but we'll include it for consistency)
$lambdaFunctions = @(
    @{Source="lambda_presign.py"; Target="lambda_code.py"; Output="lambda-presign.zip"},
    @{Source="lambda_get_run.py"; Target="lambda_code.py"; Output="lambda-get-run.zip"},
    @{Source="lambda_list_runs.py"; Target="lambda_code.py"; Output="lambda-list-runs.zip"},
    @{Source="lambda_delete_run.py"; Target="lambda_code.py"; Output="lambda-delete-run.zip"}
)

foreach ($lambda in $lambdaFunctions) {
    if (Test-Path $lambda.Source) {
        Create-Package -SourceFile $lambda.Source -TargetName $lambda.Target -OutputZip $lambda.Output
    }
}

# Clean up
Remove-Item -Path "temp-deploy" -Recurse -Force

Write-Host "`nDeployment packages created successfully!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run: .\update-lambdas.ps1" -ForegroundColor White
Write-Host "  2. Test the API endpoints" -ForegroundColor White