# CLAUDE.md - Guía de IA para el Proyecto ASPOR

## 🤖 Contexto para el Asistente de IA

Eres un asistente especializado en el mantenimiento y desarrollo de la **Plataforma ASPOR**, un sistema serverless de análisis documental legal que utiliza AWS Bedrock Claude para procesar escrituras públicas.

## 📋 Información del Proyecto

### Propósito
Sistema de extracción automática de información legal que procesa documentos PDF/DOCX y genera informes profesionales usando IA, específicamente para:
- **Modelo A**: Validar poderes notariales y capacidad de firma de contragarantías
- **Modelo B**: Generar informes societarios estructurados

### Stack Tecnológico
```yaml
Backend:
  - Runtime: Python 3.12
  - Framework: AWS Lambda
  - API: API Gateway HTTP
  - Database: DynamoDB
  - Storage: S3
  - AI: Amazon Bedrock Claude Opus 4.1
  - OCR: AWS Textract
  
Frontend:
  - HTML5 + JavaScript Vanilla
  - CDN: CloudFront
  - No frameworks (diseño simple y directo)

Infrastructure:
  - IaC: AWS SAM / CloudFormation
  - Region: us-east-1
  - Deployment: PowerShell scripts (Windows)
```

## 🗂️ Estructura del Proyecto

```
CH-Aspor/
├── 📄 CONTRAGARANTIAS.txt      # Prompt del Modelo A
├── 📄 INFORMES SOCIALES.txt    # Prompt del Modelo B
├── 📄 README.md                 # Documentación usuario
├── 📄 MASTER_PROMPT.md          # Documentación técnica
├── 📄 CLAUDE.md                 # Este archivo
└── aspor-extraction-platform/
    ├── 🏗️ template.yaml        # Infraestructura principal
    ├── 🔧 deploy-windows.ps1    # Script de despliegue
    ├── 📦 Lambda Functions:
    │   ├── lambda_code_fixed.py    # Handler principal con procesamiento
    │   ├── lambda_presign.py       # Genera URLs de carga
    │   ├── lambda_get_run.py       # Obtiene detalles de ejecución
    │   ├── lambda_list_runs.py     # Lista historial
    │   └── lambda_delete_run.py    # Elimina ejecuciones
    └── frontend/
        └── index.html           # Interfaz web completa
```

## 🎯 Tareas Comunes y Soluciones

### 1. Agregar nueva funcionalidad
```python
# Ejemplo: Agregar campo de email para notificaciones
# En lambda_code_fixed.py, agregar:
email = body.get('email')
if email:
    run_item['email'] = email
    # Aquí agregar lógica de SES para enviar email
```

### 2. Modificar prompts de IA
```python
# Los prompts están en los archivos .txt y también en lambda_process_run.py
# Para actualizar:
1. Editar CONTRAGARANTIAS.txt o INFORMES SOCIALES.txt
2. Actualizar las constantes en lambda_process_run.py:
   CONTRAGARANTIAS_PROMPT = """[nuevo prompt]"""
   INFORMES_SOCIALES_PROMPT = """[nuevo prompt]"""
```

### 3. Debugging de errores comunes

#### Error 500 en API
```bash
# Verificar permisos Lambda
aws iam get-role-policy --role-name [LAMBDA_ROLE] --policy-name AsporBedrockTextractPolicy

# Ver logs
aws logs tail /aws/lambda/aspor-create-run --follow
```

#### Run not found
```python
# El problema suele ser en lambda_get_run_simple.py
# La función usa query con filtro manual:
response = table.query(
    KeyConditionExpression=Key('pk').eq(f'USER#{user_id}') & Key('sk').begins_with('RUN#')
)
# Luego filtra en Python por runId
```

#### Descarga no funciona
```python
# En lambda_get_run_simple.py, verificar generación de URL:
download_url = s3_client.generate_presigned_url(
    'get_object',
    Params={
        'Bucket': bucket_name,
        'Key': s3_key,
        'ResponseContentDisposition': f'attachment; filename="reporte_{run_id[:8]}.{output_format}"'
    },
    ExpiresIn=3600
)
```

### 4. Actualizar Lambda Functions
```powershell
# Script para actualizar una función específica
$functionName = "aspor-create-run"
$sourceFile = "lambda_code_fixed.py"

# Crear zip con el nombre correcto
mkdir temp-deploy
cp $sourceFile temp-deploy/lambda_code.py
Compress-Archive -Path temp-deploy/lambda_code.py -DestinationPath function.zip -Force

# Actualizar función
aws lambda update-function-code `
    --function-name $functionName `
    --zip-file fileb://function.zip `
    --region us-east-1

# Limpiar
rm -r temp-deploy
rm function.zip
```

### 5. Agregar nuevo endpoint API
```yaml
# En template.yaml, agregar bajo Resources:
NewEndpointFunction:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: aspor-new-endpoint
    Handler: lambda_code.handler
    Events:
      ApiEvent:
        Type: HttpApi
        Properties:
          ApiId: !Ref AsporApi
          Path: /new-endpoint
          Method: POST
```

## 🔧 Configuraciones Importantes

### Variables de Entorno Lambda
```python
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'aspor-extractions')
DOCUMENTS_BUCKET = os.environ.get('DOCUMENTS_BUCKET', 'aspor-documents-520754296204')
BEDROCK_MODEL = 'anthropic.claude-opus-4-1-20250805-v1:0'  # Modelo actual
```

### Estructura DynamoDB
```python
# Clave primaria compuesta
{
    'pk': f'USER#{user_id}',           # Partition key
    'sk': f'RUN#{timestamp}#{run_id}', # Sort key
    'runId': str(uuid.uuid4()),
    'model': 'A' | 'B',
    'files': ['s3_key1', 's3_key2'],
    'fileNames': ['doc1.pdf', 'doc2.pdf'],
    'status': 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED',
    'output': {
        'docx': 's3_key_output',
        'downloadUrl': 'presigned_url'
    }
}
```

### Configuración Bedrock
```python
body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 8000,
    "messages": [
        {
            "role": "user",
            "content": prompt
        }
    ],
    "temperature": 0.3,
    "top_p": 0.95
}

response = bedrock_client.invoke_model(
    modelId="anthropic.claude-opus-4-1-20250805-v1:0",
    contentType="application/json",
    accept="application/json",
    body=json.dumps(body)
)
```

## 📝 Checklist de Mantenimiento

### Diario
- [ ] Verificar CloudWatch Logs para errores
- [ ] Revisar métricas de Lambda (duración, errores)
- [ ] Comprobar uso de DynamoDB

### Semanal
- [ ] Revisar costos de AWS
- [ ] Verificar espacio en S3
- [ ] Actualizar dependencias si hay parches de seguridad

### Mensual
- [ ] Auditar permisos IAM
- [ ] Revisar y optimizar prompts según feedback
- [ ] Limpiar archivos antiguos de S3 (si aplica)
- [ ] Generar reporte de uso para cliente

## 🚀 Comandos Útiles

```bash
# Desplegar todo
cd aspor-extraction-platform
./deploy-windows.ps1

# Ver logs en tiempo real
aws logs tail /aws/lambda/aspor-create-run --follow --region us-east-1

# Listar todas las ejecuciones
aws dynamodb scan --table-name aspor-extractions --region us-east-1

# Obtener URLs del sistema
aws cloudformation describe-stacks --stack-name aspor-platform \
    --query 'Stacks[0].Outputs' --region us-east-1

# Verificar estado de Bedrock
aws bedrock list-foundation-models --region us-east-1 \
    --query "modelSummaries[?contains(modelId, 'claude')]"

# Test rápido del API
curl -X POST https://[API_URL]/runs/presign \
    -H "Content-Type: application/json" \
    -d '{"file_count": 1}'
```

## 🐛 Solución Rápida de Problemas

### Problema: "Bedrock model not available"
```bash
# Solución: Habilitar el modelo en la consola AWS
# 1. Ir a Amazon Bedrock > Model access
# 2. Solicitar acceso a Claude Opus 4.1
# 3. Esperar aprobación (usualmente inmediata)
```

### Problema: "Lambda timeout"
```python
# Solución: En template.yaml, aumentar timeout
CreateRunFunction:
  Properties:
    Timeout: 900  # 15 minutos máximo
```

### Problema: "CORS error"
```yaml
# Solución: En template.yaml, verificar CORS en API Gateway
AsporApi:
  Properties:
    CorsConfiguration:
      AllowOrigins: ['*']
      AllowMethods: ['*']
      AllowHeaders: ['*']
```

## 🔐 Seguridad

### Credenciales
- **NUNCA** hardcodear credenciales AWS
- Usar IAM roles para permisos entre servicios
- Rotar access keys regularmente

### Datos Sensibles
- Los documentos se almacenan cifrados en S3
- URLs de descarga expiran en 1 hora
- DynamoDB no almacena contenido de documentos, solo metadata

### Permisos Mínimos
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::aspor-documents-*/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/aspor-extractions"
    }
  ]
}
```

## 📞 Información de Contacto

- **Desarrollador**: Diego Borra
- **Email**: dborra@cloudhesive.com
- **GitHub**: https://github.com/dborra-83/CH-Aspor
- **Cliente**: ASPOR
- **Ambiente Producción**: https://d3qiqro0ukto58.cloudfront.net

## 💡 Tips para Claude/IA

Cuando trabajes en este proyecto:

1. **Siempre verifica el estado actual** antes de hacer cambios
2. **Usa los scripts PowerShell** existentes para despliegues
3. **Mantén los prompts en español** (cliente hispanohablante)
4. **Genera reportes profesionales** con formato formal
5. **Prioriza la seguridad** en todo cambio
6. **Documenta cambios** en commits descriptivos
7. **Prueba localmente** cuando sea posible antes de desplegar
8. **Mantén compatibilidad** con Python 3.12 y AWS SAM
9. **Optimiza para costos** (arquitectura serverless)
10. **Respeta la estructura** existente del proyecto

---

**Última actualización**: Agosto 2025
**Versión**: 1.0.0
**Estado**: ✅ Producción