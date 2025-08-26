import boto3
import json
import os
from typing import List, Dict, Any
from datetime import datetime

class BedrockAgent:
    """Handle Bedrock Claude 4.0 interactions for document processing"""
    
    def __init__(self):
        self.bedrock_client = boto3.client('bedrock-runtime')
        self.ssm_client = boto3.client('ssm')
        self.model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-opus-20240229')
        
        # Load prompts from SSM Parameter Store
        self.agent_a_prompt = self._load_prompt(os.environ['AGENT_A_PROMPT_PARAM'])
        self.agent_b_prompt = self._load_prompt(os.environ['AGENT_B_PROMPT_PARAM'])
    
    def _load_prompt(self, param_name: str) -> str:
        """Load prompt from SSM Parameter Store"""
        try:
            response = self.ssm_client.get_parameter(
                Name=param_name,
                WithDecryption=False
            )
            return response['Parameter']['Value']
        except Exception as e:
            print(f"Error loading prompt from {param_name}: {str(e)}")
            # Fallback to a basic prompt if SSM fails
            return "Analyze the provided documents and extract relevant information."
    
    def process_contragarantias(self, documents: List[Dict[str, str]]) -> Dict[str, Any]:
        """Process documents using Agent A - Contragarantías/ASPOR"""
        
        # Combine all document texts
        combined_text = self._combine_documents(documents)
        
        # Build the complete prompt
        system_prompt = self.agent_a_prompt
        
        user_prompt = f"""
        Analiza los siguientes documentos de poderes y escrituras públicas para validar la capacidad de firma de contragarantías según los criterios de ASPOR.
        
        DOCUMENTOS A ANALIZAR:
        {combined_text}
        
        Por favor, genera un informe completo siguiendo exactamente la estructura especificada, identificando:
        1. Información societaria completa
        2. Fechas legales críticas y trazabilidad notarial
        3. Validación de contragarantías (simple y avalada)
        4. Apoderados por clases y sus facultades específicas
        5. Grupos de actuación válidos
        6. Alertas, limitaciones y recomendaciones
        
        IMPORTANTE: Extrae citas textuales de las facultades encontradas y marca "INFORMACIÓN NO ENCONTRADA" cuando falten datos críticos.
        """
        
        return self._invoke_bedrock(system_prompt, user_prompt, "contragarantias")
    
    def process_informes_sociales(self, documents: List[Dict[str, str]]) -> Dict[str, Any]:
        """Process documents using Agent B - Informes Sociales"""
        
        # Combine all document texts
        combined_text = self._combine_documents(documents)
        
        # Build the complete prompt
        system_prompt = self.agent_b_prompt
        
        user_prompt = f"""
        Genera un INFORME DE SOCIEDAD profesional a partir de las siguientes escrituras de constitución.
        
        DOCUMENTOS A ANALIZAR:
        {combined_text}
        
        Por favor, extrae y presenta la información siguiendo exactamente la estructura profesional especificada:
        1. Antecedentes del cliente (RUT, razón social, calidad jurídica)
        2. Objeto social (transcripción LITERAL y COMPLETA)
        3. Capital social (total, suscrito, pagado)
        4. Socios/accionistas con tabla de participación
        5. Administración y directorio
        6. Antecedentes legales (repertorio, notaría, inscripciones)
        7. Apoderados y sus facultades
        
        IMPORTANTE: 
        - Transcribe el objeto social de forma LITERAL sin resumir
        - Incluye todas las referencias notariales completas
        - Marca "INFORMACIÓN NO ENCONTRADA" cuando falten datos
        """
        
        return self._invoke_bedrock(system_prompt, user_prompt, "informes_sociales")
    
    def _combine_documents(self, documents: List[Dict[str, str]]) -> str:
        """Combine multiple document texts"""
        combined = ""
        for idx, doc in enumerate(documents, 1):
            combined += f"\n\n{'='*60}\n"
            combined += f"DOCUMENTO {idx}: {doc['file']}\n"
            combined += f"{'='*60}\n\n"
            combined += doc['text'][:50000]  # Limit text per document to manage context
        return combined
    
    def _invoke_bedrock(self, system_prompt: str, user_prompt: str, agent_type: str) -> Dict[str, Any]:
        """Invoke Bedrock Claude model"""
        try:
            start_time = datetime.utcnow()
            
            # Prepare the request
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 8000,
                "temperature": 0.1,
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            }
            
            # Invoke the model
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            content = response_body.get('content', [{}])[0].get('text', '')
            
            # Calculate metrics
            end_time = datetime.utcnow()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Parse the structured content
            result = self._parse_agent_response(content, agent_type)
            
            # Add metrics
            result['metrics'] = {
                'tokensIn': response_body.get('usage', {}).get('input_tokens', 0),
                'tokensOut': response_body.get('usage', {}).get('output_tokens', 0),
                'latencyMs': latency_ms,
                'modelId': self.model_id
            }
            
            return result
            
        except Exception as e:
            print(f"Error invoking Bedrock: {str(e)}")
            raise
    
    def _parse_agent_response(self, content: str, agent_type: str) -> Dict[str, Any]:
        """Parse the agent response into structured format"""
        
        result = {
            'agentType': agent_type,
            'timestamp': datetime.utcnow().isoformat(),
            'rawContent': content,
            'structuredData': {}
        }
        
        if agent_type == "contragarantias":
            # Parse contragarantías specific sections
            result['structuredData'] = {
                'informacionSocietaria': self._extract_section(content, 'INFORMACIÓN SOCIETARIA'),
                'fechasLegales': self._extract_section(content, 'FECHAS LEGALES'),
                'validacionContragarantias': self._extract_section(content, 'VALIDACIÓN CONTRAGARANTÍAS'),
                'apoderados': self._extract_section(content, 'APODERADOS'),
                'gruposActuacion': self._extract_section(content, 'GRUPOS DE ACTUACIÓN'),
                'alertas': self._extract_section(content, 'ALERTAS'),
                'recomendaciones': self._extract_section(content, 'RECOMENDACIONES')
            }
        else:
            # Parse informes sociales specific sections
            result['structuredData'] = {
                'antecedentesCliente': self._extract_section(content, 'ANTECEDENTES DEL CLIENTE'),
                'objetoSocial': self._extract_section(content, 'OBJETO SOCIAL'),
                'capitalSocial': self._extract_section(content, 'CAPITAL'),
                'socios': self._extract_section(content, 'SOCIOS'),
                'administracion': self._extract_section(content, 'ADMINISTRACIÓN'),
                'directorio': self._extract_section(content, 'DIRECTORIO'),
                'antecedentesLegales': self._extract_section(content, 'ANTECEDENTES LEGALES'),
                'apoderados': self._extract_section(content, 'APODERADOS')
            }
        
        return result
    
    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract a specific section from the response"""
        import re
        
        # Try to find the section
        pattern = rf'{section_name}.*?(?=\n#|\n##|$)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(0).strip()
        return "SECCIÓN NO ENCONTRADA"