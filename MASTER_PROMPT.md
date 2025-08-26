# MASTER PROMPT - Sistema de Extracción ASPOR

## Descripción del Sistema

Este documento contiene el prompt maestro para replicar y mantener el sistema de extracción de información legal ASPOR usando AWS Bedrock Claude 4.0.

---

## PROMPT PARA REPLICACIÓN DEL SISTEMA

```
Eres un arquitecto/desarrollador experto en AWS que debe crear una plataforma serverless de extracción de información legal. El sistema debe:

### REQUISITOS FUNCIONALES:

1. **Procesamiento de Documentos**
   - Aceptar 1-3 archivos PDF o DOCX por procesamiento
   - Extraer texto usando PyPDF2/python-docx
   - OCR con AWS Textract para PDFs escaneados
   - Límite de 25MB por archivo

2. **Modelos de Extracción con Bedrock Claude 4.0**
   
   MODELO A - CONTRAGARANTÍAS/ASPOR:
   - Análisis de escrituras públicas de poderes
   - Validación de facultades para contragarantías
   - Identificación de apoderados por clases (A, B, C)
   - Análisis de grupos de actuación conjunta
   - Detección de vencimientos y limitaciones
   - Trazabilidad notarial completa
   
   MODELO B - INFORMES SOCIALES:
   - Extracción de información societaria
   - Transcripción literal del objeto social
   - Capital social (autorizado/suscrito/pagado)
   - Tabla de socios con participaciones
   - Estructura administrativa y directorio
   - Antecedentes legales y notariales

3. **Salidas del Sistema**
   - Generación de reportes en DOCX y PDF
   - Estructura profesional con secciones definidas
   - Citas textuales y referencias notariales
   - Alertas y recomendaciones específicas

4. **Gestión de Datos**
   - Historial persistente de ejecuciones
   - Metadatos: fecha, modelo, archivos, estado
   - Enlaces de descarga con expiración
   - Opción de reprocesar con otro modelo

### ARQUITECTURA TÉCNICA AWS:

#### Componentes Core:
- **API Gateway**: REST API con CORS habilitado
- **Lambda Functions** (Python 3.12):
  - presign: Generar URLs para uploads
  - create_run: Procesar documentos con Bedrock
  - get_run: Consultar estado de ejecución
  - list_runs: Listar historial
  - delete_run: Eliminar ejecución
  
- **Almacenamiento**:
  - S3: Archivos fuente y reportes generados
  - DynamoDB: Metadata y estado de ejecuciones
  - SSM Parameter Store: Prompts de los modelos

- **Procesamiento IA**:
  - Amazon Bedrock con Claude 4.0
  - Contexto máximo: 50,000 caracteres por documento
  - Temperature: 0.1 para consistencia

- **Frontend**:
  - HTML/JS estático en S3
  - CloudFront para distribución global
  - Interfaz responsive con upload drag&drop

#### Flujo de Procesamiento:
1. Usuario sube archivos vía presigned URLs
2. Lambda extrae texto de documentos
3. Bedrock Claude procesa con prompt específico
4. Generación de reporte DOCX/PDF
5. Almacenamiento en S3 con URL temporal
6. Actualización de estado en DynamoDB

### ESTRUCTURA DE PROMPTS POR MODELO:

#### Prompt Base Modelo A - Contragarantías:
- Identificar sociedad (razón social, RUT, tipo)
- Extraer fechas críticas y notarías
- Buscar facultades cambiarias específicas
- Clasificar apoderados por clases
- Determinar grupos de actuación válidos
- Generar matriz de validación
- Alertar vencimientos y restricciones

#### Prompt Base Modelo B - Informes Sociales:
- Extraer antecedentes del cliente
- Transcribir objeto social literalmente
- Detallar capital social
- Crear tabla de socios/accionistas
- Describir estructura administrativa
- Compilar antecedentes legales
- Listar apoderados con facultades

### CONFIGURACIÓN Y DESPLIEGUE:

Variables de Entorno:
- BEDROCK_MODEL_ID: anthropic.claude-3-opus-20240229
- MAX_FILES: 3
- MAX_FILE_SIZE_MB: 25
- Timeouts: 300s para Lambda, 900s para procesamiento

Seguridad:
- IAM roles con least privilege
- Presigned URLs con 1 hora de expiración
- Encriptación en reposo para S3 y DynamoDB
- API key temporal (migrable a Cognito)

Costos Estimados:
- Lambda: ~$0.50/mes base
- S3: ~$2/mes para 10GB
- DynamoDB: ~$1/mes on-demand
- Bedrock: ~$15/1M tokens
- Total: ~$20-30/mes para 100 docs

### VALIDACIONES Y REGLAS DE NEGOCIO:

Para Contragarantías:
- ✅ Facultades requeridas: girar, aceptar, suscribir pagarés
- ✅ Otorgar mandatos generales/especiales
- ✅ Contratar seguros y pólizas
- ⚠️ Restricciones por tipo societario
- ❌ Rechazar si poderes vencidos

Para Informes Sociales:
- Transcripción literal obligatoria
- Citas textuales con comillas
- "INFORMACIÓN NO ENCONTRADA" si falta dato
- Formato profesional de estudio jurídico
- Referencias notariales completas

### OUTPUTS ESPERADOS:

Reporte DOCX/PDF debe contener:
1. Portada con modelo y fecha
2. Archivos procesados
3. Resumen ejecutivo
4. Secciones específicas del modelo
5. Alertas y limitaciones
6. Recomendaciones y acciones

Metadata en DynamoDB:
{
  "runId": "uuid",
  "model": "A|B",
  "status": "COMPLETED",
  "files": ["s3://..."],
  "output": {"docx": "s3://..."},
  "metrics": {
    "tokensIn": 5000,
    "tokensOut": 2000,
    "latencyMs": 8500
  }
}

### MANTENIMIENTO Y MONITOREO:

- CloudWatch Logs para cada Lambda
- Métricas de tokens y latencia
- Lifecycle S3: eliminar >90 días
- Backup DynamoDB mensual
- Actualización de prompts vía SSM
```

---

## INSTRUCCIONES DE USO

### Para Desarrolladores:

1. **Clonar y Configurar:**
```bash
git clone https://github.com/dborra-83/CH-Aspor.git
cd CH-Aspor/aspor-extraction-platform
aws configure  # Configurar credenciales AWS
```

2. **Personalizar Prompts:**
   - Editar `CONTRAGARANTIAS.txt` para Modelo A
   - Editar `INFORMES SOCIALES.txt` para Modelo B
   - Los prompts se cargan automáticamente al desplegar

3. **Desplegar:**
```bash
chmod +x deploy.sh
./deploy.sh
```

4. **Verificar:**
   - Acceder a la URL de CloudFront proporcionada
   - Importar `postman_collection.json` para probar APIs
   - Revisar logs en CloudWatch

### Para Mantenimiento:

1. **Actualizar Prompts sin Redesplegar:**
```bash
python upload_prompts.py --region us-east-1
```

2. **Monitorear Costos:**
```bash
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics "BlendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE
```

3. **Limpiar Recursos Antiguos:**
```bash
make clean  # Limpia archivos locales
# Para S3, configurar lifecycle rules
```

### Para Usuarios Finales:

1. **Acceder a la Plataforma:**
   - Navegar a la URL proporcionada
   - No requiere autenticación (versión demo)

2. **Procesar Documentos:**
   - Seleccionar máximo 3 archivos PDF/DOCX
   - Elegir Modelo A (Contragarantías) o B (Informes)
   - Seleccionar formato de salida (DOCX/PDF)
   - Hacer clic en "Procesar"

3. **Descargar Resultados:**
   - Esperar procesamiento (~30 segundos)
   - Descargar reporte generado
   - Consultar historial para re-descargas

---

## TROUBLESHOOTING COMÚN

### Error: "Model not found"
- Verificar que Claude esté habilitado en Bedrock
- Confirmar región correcta (us-east-1 recomendado)

### Error: "Access Denied"
- Revisar permisos IAM del rol de Lambda
- Verificar políticas de bucket S3

### Procesamiento Lento
- Aumentar memoria de Lambda a 3008MB
- Verificar tamaño de documentos (<25MB)
- Considerar procesamiento asíncrono con SQS

### Costos Elevados
- Revisar métricas de tokens en DynamoDB
- Implementar caché para documentos repetidos
- Ajustar temperature de Bedrock a 0

---

## MEJORAS FUTURAS RECOMENDADAS

1. **Seguridad:**
   - Implementar AWS Cognito para autenticación
   - VPC endpoints para servicios AWS
   - WAF en API Gateway

2. **Funcionalidad:**
   - Procesamiento batch de >3 archivos
   - API webhook para integraciones
   - Versionado de reportes

3. **Performance:**
   - ElastiCache para resultados frecuentes
   - Lambda@Edge para optimización
   - Step Functions para flujos complejos

4. **Analítica:**
   - QuickSight dashboards
   - Exportación a Excel
   - Métricas de precisión del modelo

---

## CONTACTO Y SOPORTE

- **Repositorio**: https://github.com/dborra-83/CH-Aspor
- **Issues**: Reportar en GitHub Issues
- **Documentación AWS**: https://docs.aws.amazon.com/bedrock/

---

*Este prompt maestro permite replicar completamente el sistema ASPOR con cualquier LLM que soporte generación de código y comprensión de arquitecturas cloud.*