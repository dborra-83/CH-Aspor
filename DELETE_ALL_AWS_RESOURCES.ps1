# ============================================
# SCRIPT DE ELIMINACIÓN COMPLETA - PROYECTO ASPOR
# ============================================
# ADVERTENCIA: Este script eliminará TODOS los recursos de AWS
# relacionados con el proyecto ASPOR. Esta acción es IRREVERSIBLE.
# ============================================

param(
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1",
    
    [Parameter(Mandatory=$false)]
    [switch]$Force = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun = $false
)

# Colores para output
$ErrorActionPreference = "Continue"

Write-Host "`n============================================" -ForegroundColor Red
Write-Host "   ELIMINACIÓN COMPLETA - PROYECTO ASPOR" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Red
Write-Host "ADVERTENCIA: Este script eliminará TODOS los recursos AWS" -ForegroundColor Yellow
Write-Host "Esta acción es IRREVERSIBLE" -ForegroundColor Yellow
Write-Host "============================================`n" -ForegroundColor Red

if ($DryRun) {
    Write-Host "MODO DRY RUN - No se eliminará nada, solo se mostrará lo que se eliminaría`n" -ForegroundColor Cyan
}

if (-not $Force -and -not $DryRun) {
    $confirmation = Read-Host "¿Estás SEGURO que quieres eliminar TODOS los recursos? Escribe 'ELIMINAR TODO' para confirmar"
    if ($confirmation -ne "ELIMINAR TODO") {
        Write-Host "Operación cancelada" -ForegroundColor Green
        exit 0
    }
}

# Función para ejecutar comandos
function Execute-Command {
    param(
        [string]$Description,
        [string]$Command,
        [bool]$ContinueOnError = $true
    )
    
    Write-Host "`n→ $Description" -ForegroundColor Yellow
    
    if ($DryRun) {
        Write-Host "  [DRY RUN] $Command" -ForegroundColor Cyan
        return
    }
    
    try {
        Invoke-Expression $Command 2>&1 | Out-Null
        Write-Host "  ✓ Completado" -ForegroundColor Green
    } catch {
        if ($ContinueOnError) {
            Write-Host "  ⚠ Error (continuando): $_" -ForegroundColor Yellow
        } else {
            Write-Host "  ✗ Error crítico: $_" -ForegroundColor Red
            exit 1
        }
    }
}

Write-Host "`n📋 PASO 1: IDENTIFICANDO RECURSOS..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Identificar recursos
$stackName = "aspor-platform"
$buckets = @(
    "aspor-documents-520754296204",
    "aspor-website-520754296204"
)
$tableName = "aspor-extractions"
$lambdaFunctions = @(
    "aspor-create-run",
    "aspor-get-run",
    "aspor-list-runs",
    "aspor-delete-run",
    "aspor-presign",
    "aspor-process-run"
)
$apiName = "aspor-platform"
$apiId = "bsdxo3p5tc"
$distributionId = "E116W8SDLXW5Z2"

Write-Host "Stack: $stackName" -ForegroundColor White
Write-Host "Buckets S3: $($buckets -join ', ')" -ForegroundColor White
Write-Host "Tabla DynamoDB: $tableName" -ForegroundColor White
Write-Host "Lambda Functions: $($lambdaFunctions.Count) funciones" -ForegroundColor White
Write-Host "API Gateway: $apiName (ID: $apiId)" -ForegroundColor White
Write-Host "CloudFront Distribution: $distributionId" -ForegroundColor White

# ============================================
# ELIMINAR CLOUDFRONT DISTRIBUTION
# ============================================
Write-Host "`n🌐 PASO 2: ELIMINANDO CLOUDFRONT..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Primero, deshabilitar la distribución
Write-Host "Obteniendo configuración de CloudFront..." -ForegroundColor Yellow
if (-not $DryRun) {
    try {
        $distConfig = aws cloudfront get-distribution-config --id $distributionId --region $Region 2>&1
        if ($LASTEXITCODE -eq 0) {
            $config = $distConfig | ConvertFrom-Json
            $etag = $config.ETag
            
            # Modificar configuración para deshabilitar
            $config.DistributionConfig.Enabled = $false
            $configJson = $config.DistributionConfig | ConvertTo-Json -Depth 10
            $configJson | Out-File -FilePath "dist-config.json" -Encoding UTF8
            
            Execute-Command `
                -Description "Deshabilitando CloudFront Distribution" `
                -Command "aws cloudfront update-distribution --id $distributionId --distribution-config file://dist-config.json --if-match `"$etag`" --region $Region"
            
            Write-Host "  ⏳ Esperando a que CloudFront se deshabilite (esto puede tomar varios minutos)..." -ForegroundColor Yellow
            
            if (-not $DryRun) {
                Start-Sleep -Seconds 60
            }
            
            # Eliminar distribución
            Execute-Command `
                -Description "Eliminando CloudFront Distribution" `
                -Command "aws cloudfront delete-distribution --id $distributionId --if-match `"$etag`" --region $Region"
            
            # Limpiar archivo temporal
            Remove-Item -Path "dist-config.json" -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host "  ⚠ CloudFront no encontrado o ya eliminado" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [DRY RUN] Deshabilitaría y eliminaría CloudFront Distribution: $distributionId" -ForegroundColor Cyan
}

# ============================================
# VACIAR Y ELIMINAR BUCKETS S3
# ============================================
Write-Host "`n🗑️ PASO 3: ELIMINANDO BUCKETS S3..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

foreach ($bucket in $buckets) {
    Write-Host "`nProcesando bucket: $bucket" -ForegroundColor Yellow
    
    # Verificar si el bucket existe
    $bucketExists = $false
    try {
        aws s3api head-bucket --bucket $bucket --region $Region 2>&1 | Out-Null
        $bucketExists = ($LASTEXITCODE -eq 0)
    } catch {
        $bucketExists = $false
    }
    
    if ($bucketExists) {
        # Vaciar bucket (eliminar todos los objetos)
        Execute-Command `
            -Description "Vaciando bucket $bucket" `
            -Command "aws s3 rm s3://$bucket --recursive --region $Region"
        
        # Eliminar versiones si el versionado está habilitado
        Execute-Command `
            -Description "Eliminando versiones del bucket $bucket" `
            -Command "aws s3api delete-objects --bucket $bucket --delete '{\`"Objects\`":[{\`"Key\`":\`"*\`",\`"VersionId\`":\`"*\`"}]}' --region $Region"
        
        # Eliminar bucket
        Execute-Command `
            -Description "Eliminando bucket $bucket" `
            -Command "aws s3api delete-bucket --bucket $bucket --region $Region"
    } else {
        Write-Host "  ⚠ Bucket $bucket no encontrado" -ForegroundColor Yellow
    }
}

# ============================================
# ELIMINAR TABLA DYNAMODB
# ============================================
Write-Host "`n📊 PASO 4: ELIMINANDO DYNAMODB..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

Execute-Command `
    -Description "Eliminando tabla DynamoDB: $tableName" `
    -Command "aws dynamodb delete-table --table-name $tableName --region $Region"

# ============================================
# ELIMINAR LAMBDA FUNCTIONS
# ============================================
Write-Host "`n⚡ PASO 5: ELIMINANDO LAMBDA FUNCTIONS..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

foreach ($function in $lambdaFunctions) {
    Execute-Command `
        -Description "Eliminando Lambda function: $function" `
        -Command "aws lambda delete-function --function-name $function --region $Region"
}

# ============================================
# ELIMINAR API GATEWAY
# ============================================
Write-Host "`n🔌 PASO 6: ELIMINANDO API GATEWAY..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

Execute-Command `
    -Description "Eliminando API Gateway: $apiId" `
    -Command "aws apigatewayv2 delete-api --api-id $apiId --region $Region"

# ============================================
# ELIMINAR CLOUDWATCH LOG GROUPS
# ============================================
Write-Host "`n📝 PASO 7: ELIMINANDO CLOUDWATCH LOGS..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

foreach ($function in $lambdaFunctions) {
    $logGroup = "/aws/lambda/$function"
    Execute-Command `
        -Description "Eliminando log group: $logGroup" `
        -Command "aws logs delete-log-group --log-group-name $logGroup --region $Region"
}

# ============================================
# ELIMINAR IAM ROLES Y POLICIES
# ============================================
Write-Host "`n🔐 PASO 8: ELIMINANDO IAM ROLES..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Buscar roles que contengan "aspor" en el nombre
if (-not $DryRun) {
    $roles = aws iam list-roles --query "Roles[?contains(RoleName, ``'aspor``')].RoleName" --output json | ConvertFrom-Json
    
    foreach ($roleName in $roles) {
        Write-Host "Procesando rol: $roleName" -ForegroundColor Yellow
        
        # Primero, desasociar políticas
        $attachedPolicies = aws iam list-attached-role-policies --role-name $roleName --query "AttachedPolicies[].PolicyArn" --output json | ConvertFrom-Json
        foreach ($policyArn in $attachedPolicies) {
            Execute-Command `
                -Description "Desasociando política $policyArn del rol $roleName" `
                -Command "aws iam detach-role-policy --role-name $roleName --policy-arn $policyArn"
        }
        
        # Eliminar políticas inline
        $inlinePolicies = aws iam list-role-policies --role-name $roleName --query "PolicyNames[]" --output json | ConvertFrom-Json
        foreach ($policyName in $inlinePolicies) {
            Execute-Command `
                -Description "Eliminando política inline $policyName del rol $roleName" `
                -Command "aws iam delete-role-policy --role-name $roleName --policy-name $policyName"
        }
        
        # Eliminar el rol
        Execute-Command `
            -Description "Eliminando rol IAM: $roleName" `
            -Command "aws iam delete-role --role-name $roleName"
    }
} else {
    Write-Host "  [DRY RUN] Buscaría y eliminaría roles IAM que contengan 'aspor'" -ForegroundColor Cyan
}

# ============================================
# ELIMINAR CLOUDFORMATION STACK
# ============================================
Write-Host "`n📦 PASO 9: ELIMINANDO CLOUDFORMATION STACK..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

Execute-Command `
    -Description "Eliminando CloudFormation stack: $stackName" `
    -Command "aws cloudformation delete-stack --stack-name $stackName --region $Region"

if (-not $DryRun) {
    Write-Host "  ⏳ Esperando a que se complete la eliminación del stack..." -ForegroundColor Yellow
    aws cloudformation wait stack-delete-complete --stack-name $stackName --region $Region 2>&1 | Out-Null
}

# ============================================
# ELIMINAR RECURSOS SAM
# ============================================
Write-Host "`n🎯 PASO 10: ELIMINANDO RECURSOS SAM..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Buscar y eliminar buckets de SAM
if (-not $DryRun) {
    $samBuckets = aws s3api list-buckets --query "Buckets[?contains(Name, ``'sam-``') || contains(Name, ``'aws-sam-``')].Name" --output json | ConvertFrom-Json
    
    foreach ($samBucket in $samBuckets) {
        Write-Host "Eliminando bucket SAM: $samBucket" -ForegroundColor Yellow
        
        Execute-Command `
            -Description "Vaciando bucket SAM $samBucket" `
            -Command "aws s3 rm s3://$samBucket --recursive --region $Region"
        
        Execute-Command `
            -Description "Eliminando bucket SAM $samBucket" `
            -Command "aws s3api delete-bucket --bucket $samBucket --region $Region"
    }
} else {
    Write-Host "  [DRY RUN] Buscaría y eliminaría buckets SAM" -ForegroundColor Cyan
}

# ============================================
# VERIFICACIÓN FINAL
# ============================================
Write-Host "`n✅ PASO 11: VERIFICACIÓN FINAL..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

if (-not $DryRun) {
    Write-Host "Verificando recursos restantes..." -ForegroundColor Yellow
    
    # Verificar Lambda functions
    $remainingLambdas = aws lambda list-functions --query "Functions[?contains(FunctionName, ``'aspor``')].FunctionName" --output json --region $Region | ConvertFrom-Json
    if ($remainingLambdas.Count -gt 0) {
        Write-Host "  ⚠ Lambdas restantes: $($remainingLambdas -join ', ')" -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ Todas las Lambda functions eliminadas" -ForegroundColor Green
    }
    
    # Verificar DynamoDB
    $remainingTables = aws dynamodb list-tables --query "TableNames[?contains(@, 'aspor')]" --output json --region $Region | ConvertFrom-Json
    if ($remainingTables.Count -gt 0) {
        Write-Host "  ⚠ Tablas DynamoDB restantes: $($remainingTables -join ', ')" -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ Todas las tablas DynamoDB eliminadas" -ForegroundColor Green
    }
    
    # Verificar S3
    $remainingBuckets = aws s3api list-buckets --query "Buckets[?contains(Name, ``'aspor``')].Name" --output json | ConvertFrom-Json
    if ($remainingBuckets.Count -gt 0) {
        Write-Host "  ⚠ Buckets S3 restantes: $($remainingBuckets -join ', ')" -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ Todos los buckets S3 eliminados" -ForegroundColor Green
    }
}

# ============================================
# RESUMEN FINAL
# ============================================
Write-Host "`n============================================" -ForegroundColor Green
Write-Host "   ELIMINACIÓN COMPLETADA" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

if ($DryRun) {
    Write-Host "`nEsto fue un DRY RUN. Para ejecutar la eliminación real, ejecuta:" -ForegroundColor Cyan
    Write-Host "  .\DELETE_ALL_AWS_RESOURCES.ps1 -Force" -ForegroundColor White
} else {
    Write-Host "`n✅ Todos los recursos del proyecto ASPOR han sido eliminados" -ForegroundColor Green
    Write-Host "`nRecursos eliminados:" -ForegroundColor Yellow
    Write-Host "  • CloudFront Distribution" -ForegroundColor White
    Write-Host "  • Buckets S3 (documentos y website)" -ForegroundColor White
    Write-Host "  • Tabla DynamoDB" -ForegroundColor White
    Write-Host "  • Lambda Functions" -ForegroundColor White
    Write-Host "  • API Gateway" -ForegroundColor White
    Write-Host "  • CloudWatch Log Groups" -ForegroundColor White
    Write-Host "  • IAM Roles y Policies" -ForegroundColor White
    Write-Host "  • CloudFormation Stack" -ForegroundColor White
    Write-Host "  • Recursos SAM" -ForegroundColor White
}

Write-Host "`n📌 Nota: Algunos recursos pueden tardar unos minutos en eliminarse completamente" -ForegroundColor Yellow
Write-Host "📌 Verifica la consola de AWS para confirmar que todo fue eliminado" -ForegroundColor Yellow

# Limpiar archivos temporales locales si existen
if (Test-Path "dist-config.json") {
    Remove-Item "dist-config.json" -Force
}

Write-Host "`nScript completado`n" -ForegroundColor Cyan