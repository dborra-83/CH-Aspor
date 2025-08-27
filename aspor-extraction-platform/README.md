# ASPOR Extraction Platform v1.1 - Technical Documentation

Sistema serverless en AWS para extracción y análisis de documentos legales usando Amazon Bedrock Claude Opus 4.1.

## Características

- **Procesamiento de Documentos**: Soporta archivos PDF y DOCX (hasta 3 archivos por procesamiento)
- **Dos Modelos de Extracción**:
  - **Modelo A - Contragarantías/ASPOR**: Análisis de poderes y validación de facultades para contragarantías
  - **Modelo B - Informes Sociales**: Generación de informes societarios profesionales
- **Formatos de Salida**: DOCX y PDF
- **Historial**: Almacenamiento y consulta de ejecuciones previas
- **Arquitectura Serverless**: 100% serverless usando AWS Lambda, API Gateway, DynamoDB y S3

## Arquitectura

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend  │────▶│ API Gateway  │────▶│   Lambda    │
│  (S3/CF)    │     │              │     │  Functions  │
└─────────────┘     └──────────────┘     └─────────────┘
                                                 │
                            ┌────────────────────┼────────────────────┐
                            │                    │                    │
                      ┌─────▼─────┐      ┌──────▼──────┐     ┌───────▼───────┐
                      │    S3     │      │  DynamoDB   │     │   Bedrock     │
                      │ (Storage) │      │  (Metadata) │     │  (Claude 4)   │
                      └───────────┘      └─────────────┘     └───────────────┘
```

## Prerequisitos

1. **Cuenta AWS** con acceso a los siguientes servicios:
   - Lambda
   - API Gateway
   - S3
   - DynamoDB
   - Bedrock (con modelo Claude habilitado)
   - CloudFormation
   - SSM Parameter Store

2. **Herramientas locales**:
   - AWS CLI configurado
   - SAM CLI
   - Python 3.12
   - Git

3. **Permisos IAM** necesarios para desplegar recursos

## Instalación Rápida

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd aspor-extraction-platform
```

### 2. Configurar AWS CLI
```bash
aws configure
# Ingrese sus credenciales AWS
```

### 3. Habilitar modelo Claude en Bedrock
1. Ir a la consola AWS → Bedrock
2. Navegar a "Model access"
3. Habilitar "Claude 3 Opus" o el modelo deseado
4. Esperar aprobación (puede tomar unos minutos)

### 4. Desplegar la aplicación
```bash
chmod +x deploy.sh
./deploy.sh aspor-platform us-east-1
```

El script realizará:
- Build de la aplicación SAM
- Despliegue de la infraestructura
- Carga de los prompts a SSM Parameter Store
- Configuración del frontend con la URL del API
- Upload del frontend a S3

### 5. Verificar el despliegue
Al finalizar, el script mostrará:
```
API Endpoint: https://xxxxx.execute-api.us-east-1.amazonaws.com/prod
Website URL: https://xxxxx.cloudfront.net
```

## Uso de la Plataforma

### Interfaz Web
1. Acceder a la URL del sitio web proporcionada
2. Subir 1-3 archivos PDF o DOCX
3. Seleccionar el modelo de extracción:
   - Modelo A para análisis de poderes y contragarantías
   - Modelo B para informes societarios
4. Elegir formato de salida (DOCX o PDF)
5. Procesar y descargar el reporte generado

### API REST

#### Obtener URLs para carga de archivos
```bash
curl -X POST https://api-url/prod/runs/presign \
  -H "Content-Type: application/json" \
  -d '{"file_count": 2}'
```

#### Crear nueva ejecución
```bash
curl -X POST https://api-url/prod/runs \
  -H "Content-Type: application/json" \
  -d '{
    "model": "A",
    "files": ["uploads/file1.pdf", "uploads/file2.docx"],
    "outputFormat": "docx"
  }'
```

#### Consultar estado de ejecución
```bash
curl https://api-url/prod/runs/{runId}
```

#### Listar historial
```bash
curl https://api-url/prod/runs?limit=10
```

## Estructura del Proyecto

```
aspor-extraction-platform/
├── template.yaml              # Plantilla SAM - Infraestructura
├── requirements.txt           # Dependencias Python
├── deploy.sh                 # Script de despliegue
├── src/
│   ├── handlers/            # Lambda handlers
│   │   ├── presign.py       # Generar URLs presignadas
│   │   ├── create_run.py    # Crear y procesar ejecución
│   │   ├── get_run.py       # Obtener detalles de ejecución
│   │   ├── list_runs.py     # Listar historial
│   │   └── delete_run.py    # Eliminar ejecución
│   ├── processors/          # Procesamiento de documentos
│   │   ├── document_processor.py  # Extracción de texto
│   │   └── bedrock_agent.py      # Integración con Bedrock
│   └── generators/          # Generación de reportes
│       └── report_generator.py    # DOCX/PDF generation
├── frontend/
│   └── index.html          # Interfaz web
└── tests/                  # Tests unitarios
```

## Configuración

### Variables de Entorno
Las siguientes variables se configuran automáticamente en el template:

- `BEDROCK_MODEL_ID`: ID del modelo Claude en Bedrock
- `DOCUMENTS_BUCKET`: Bucket S3 para documentos
- `DYNAMODB_TABLE`: Tabla para metadata
- `AGENT_A_PROMPT_PARAM`: Parámetro SSM para prompt A
- `AGENT_B_PROMPT_PARAM`: Parámetro SSM para prompt B
- `MAX_FILES`: Máximo de archivos por ejecución (3)
- `MAX_FILE_SIZE_MB`: Tamaño máximo por archivo (25MB)

### Personalización de Prompts

Los prompts se almacenan en SSM Parameter Store y se pueden actualizar sin redesplegar:

```bash
# Actualizar prompt del Modelo A
aws ssm put-parameter \
  --name "/aspor/prompts/agent-a-contragarantias" \
  --value "Nuevo prompt..." \
  --overwrite

# Actualizar prompt del Modelo B
aws ssm put-parameter \
  --name "/aspor/prompts/agent-b-informes" \
  --value "Nuevo prompt..." \
  --overwrite
```

## Monitoreo y Logs

### CloudWatch Logs
Cada función Lambda genera logs en CloudWatch:
- `/aws/lambda/aspor-presign`
- `/aws/lambda/aspor-create-run`
- `/aws/lambda/aspor-get-run`
- `/aws/lambda/aspor-list-runs`
- `/aws/lambda/aspor-delete-run`

### Métricas
Las métricas se almacenan en DynamoDB para cada ejecución:
- `tokensIn`: Tokens de entrada a Bedrock
- `tokensOut`: Tokens de salida de Bedrock
- `latencyMs`: Latencia del procesamiento

## Costos Estimados

- **Lambda**: ~$0.0000166667 por GB-segundo
- **API Gateway**: $1.00 por millón de requests
- **DynamoDB**: Pay-per-request (~$0.25 por millón de lecturas)
- **S3**: $0.023 por GB almacenado
- **Bedrock Claude**: Variable según el modelo (~$0.015 por 1K tokens)
- **CloudFront**: $0.085 por GB transferido

**Estimado mensual para uso moderado (100 documentos/mes)**: ~$15-25 USD

## Troubleshooting

### Error: "Model not found in Bedrock"
- Verificar que el modelo Claude esté habilitado en Bedrock
- Confirmar el ID del modelo en los parámetros

### Error: "Access Denied"
- Verificar permisos IAM de Lambda
- Confirmar que los buckets S3 existen

### Archivos PDF no se procesan correctamente
- Para PDFs escaneados, Textract debe estar disponible en la región
- Verificar límites de tamaño de archivo

### Timeout en procesamiento
- Aumentar timeout de Lambda en template.yaml
- Considerar implementar procesamiento asíncrono con SQS

## Seguridad

- **API Key**: Implementación básica para demo. En producción usar Cognito
- **Presigned URLs**: Expiran en 1 hora
- **IAM Roles**: Principio de menor privilegio
- **Encriptación**: S3 y DynamoDB encriptados por defecto
- **CORS**: Configurado para desarrollo. Restringir en producción

## Mantenimiento

### Actualizar la aplicación
```bash
sam build
sam deploy --no-fail-on-empty-changeset
```

### Limpiar recursos antiguos
```bash
# Eliminar archivos antiguos (>90 días se eliminan automáticamente)
aws s3 rm s3://bucket-name/uploads/ --recursive --exclude "*" --include "*.pdf" --older-than 30
```

### Backup de DynamoDB
```bash
aws dynamodb create-backup \
  --table-name aspor-extractions \
  --backup-name backup-$(date +%Y%m%d)
```

## Soporte

Para problemas o preguntas:
1. Revisar logs en CloudWatch
2. Verificar configuración en Systems Manager
3. Confirmar permisos IAM
4. Revisar límites de servicio en AWS

## Licencia

Propietario para uso interno de ASPOR.