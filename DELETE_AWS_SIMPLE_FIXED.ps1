# ============================================
# SCRIPT SIMPLIFICADO DE ELIMINACIÓN - PROYECTO ASPOR
# ============================================
# ADVERTENCIA: Este script eliminará TODOS los recursos de AWS
# ============================================

param(
    [switch]$Force = $false
)

Write-Host ""
Write-Host "============================================" -ForegroundColor Red
Write-Host "   ELIMINACIÓN DE RECURSOS AWS - ASPOR" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Red
Write-Host ""

if (-not $Force) {
    $confirmation = Read-Host "Escribe 'ELIMINAR' para confirmar"
    if ($confirmation -ne "ELIMINAR") {
        Write-Host "Cancelado" -ForegroundColor Green
        exit 0
    }
}

$Region = "us-east-1"

# Configuración de recursos
$buckets = @(
    "aspor-documents-520754296204",
    "aspor-website-520754296204"
)

$functions = @(
    "aspor-create-run",
    "aspor-get-run",
    "aspor-list-runs",
    "aspor-delete-run",
    "aspor-presign",
    "aspor-process-run"
)

Write-Host "PASO 1: Eliminando CloudFront" -ForegroundColor Yellow
Write-Host "==============================" -ForegroundColor Yellow
try {
    # Primero obtener el ETag
    $dist = aws cloudfront get-distribution --id E116W8SDLXW5Z2 --region $Region 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "CloudFront encontrado, deshabilitando..." -ForegroundColor White
        # Por ahora solo informamos, la eliminación requiere deshabilitarlo primero
        Write-Host "NOTA: CloudFront debe deshabilitarse manualmente desde la consola" -ForegroundColor Yellow
    }
} catch {
    Write-Host "CloudFront no encontrado o ya eliminado" -ForegroundColor Green
}

Write-Host ""
Write-Host "PASO 2: Vaciando y eliminando buckets S3" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Yellow
foreach ($bucket in $buckets) {
    Write-Host "Procesando: $bucket" -ForegroundColor White
    
    # Vaciar bucket
    aws s3 rm s3://$bucket --recursive --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  - Vaciado OK" -ForegroundColor Green
    }
    
    # Eliminar versiones si está habilitado el versionado
    aws s3api delete-bucket-versioning --bucket $bucket --region $Region 2>&1 | Out-Null
    
    # Eliminar bucket
    aws s3api delete-bucket --bucket $bucket --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  - Eliminado OK" -ForegroundColor Green
    } else {
        Write-Host "  - No se pudo eliminar o no existe" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "PASO 3: Eliminando tabla DynamoDB" -ForegroundColor Yellow
Write-Host "==================================" -ForegroundColor Yellow
aws dynamodb delete-table --table-name aspor-extractions --region $Region 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Tabla aspor-extractions eliminada" -ForegroundColor Green
} else {
    Write-Host "Tabla no encontrada o ya eliminada" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "PASO 4: Eliminando Lambda functions" -ForegroundColor Yellow
Write-Host "====================================" -ForegroundColor Yellow
foreach ($func in $functions) {
    Write-Host "Eliminando: $func" -ForegroundColor White
    aws lambda delete-function --function-name $func --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  - OK" -ForegroundColor Green
    } else {
        Write-Host "  - No encontrada" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "PASO 5: Eliminando API Gateway" -ForegroundColor Yellow
Write-Host "===============================" -ForegroundColor Yellow
aws apigatewayv2 delete-api --api-id bsdxo3p5tc --region $Region 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "API Gateway eliminado" -ForegroundColor Green
} else {
    Write-Host "API Gateway no encontrado" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "PASO 6: Eliminando CloudWatch Log Groups" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Yellow
foreach ($func in $functions) {
    $logGroup = "/aws/lambda/$func"
    aws logs delete-log-group --log-group-name $logGroup --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Log group $func eliminado" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "PASO 7: Eliminando CloudFormation Stack" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
aws cloudformation delete-stack --stack-name aspor-platform --region $Region 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Stack aspor-platform eliminado (puede tardar unos minutos)" -ForegroundColor Green
} else {
    Write-Host "Stack no encontrado" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   PROCESO COMPLETADO" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Recursos eliminados:" -ForegroundColor White
Write-Host "- Buckets S3" -ForegroundColor White
Write-Host "- Tabla DynamoDB" -ForegroundColor White  
Write-Host "- Lambda Functions" -ForegroundColor White
Write-Host "- API Gateway" -ForegroundColor White
Write-Host "- CloudWatch Logs" -ForegroundColor White
Write-Host "- CloudFormation Stack" -ForegroundColor White
Write-Host ""
Write-Host "NOTA: CloudFront debe eliminarse manualmente desde la consola" -ForegroundColor Yellow
Write-Host "NOTA: Algunos recursos pueden tardar minutos en eliminarse" -ForegroundColor Yellow
Write-Host ""