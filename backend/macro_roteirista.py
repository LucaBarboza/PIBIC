import os
import json
from google import genai
from google.genai import types
from prompts import PROMPT_MACRO_ROTEIRISTA
from client_factory import get_genai_client
from pydantic import BaseModel, Field

class AulaCronograma(BaseModel):
    numero_aula: int = Field(description="Número sequencial da aula no cronograma.")
    titulo: str = Field(description="Título formal e descritivo da aula.")
    objetivo_principal: str = Field(description="Objetivo pedagógico central da aula.")
    topicos_abordados: list[str] = Field(description="Lista de tópicos/subtópicos abordados nesta aula.")
    aula_complementar: bool = Field(default=False, description="Indica se é aula de aprofundamento complementar.")

class CronogramaCompleto(BaseModel):
    aulas: list[AulaCronograma] = Field(description="Lista completa e ordenada de aulas do cronograma.")

class MacroRoteirista:
    def __init__(self):
        self.client = get_genai_client()
        self.system_instruction = PROMPT_MACRO_ROTEIRISTA

    def gerar_cronograma(self, ementa_texto: str, instrucoes_personalizadas: str = None, tipo_carga_horaria: str = "padrao_30", permitir_aprofundamento: bool = False, max_aulas: int = 30) -> list:
        
        instrucao_carga = ""
        if tipo_carga_horaria == "padrao_30" or tipo_carga_horaria == "manual":
            instrucao_carga = f"O curso DEVE TER EXATAMENTE {max_aulas} aulas no total. Não gere mais nem menos aulas. Aloque todo o conteúdo de forma balanceada nesse espaço."
        elif tipo_carga_horaria == "auto_ementa":
            instrucao_carga = "O curso deve ter a quantidade de aulas calculada matematicamente a partir da ementa oficial. Leia a ementa, ache a Carga Horária. Se a carga horária for quebrada ou antiga (ex: 72h, 54h), ARREDONDE para a grade universitária oficial mais próxima (30, 45, 60 ou 90 horas). Depois, divida essa carga oficial por ~2.5 horas (150 minutos) para obter a quantidade total de aulas da matéria. Use EXATAMENTE essa quantidade de aulas para estruturar o cronograma."
        elif tipo_carga_horaria == "auto_ia":
            instrucao_carga = "Você deve analisar todo o material e decidir a quantidade ideal de aulas para abordá-lo de forma profunda e bem cadenciada. O número total de aulas geradas DEVE OBRIGATORIAMENTE ser entre MÍNIMO 20 aulas e MÁXIMO 40 aulas."
            
        instrucao_aprofundamento = ""
        if permitir_aprofundamento:
            instrucao_aprofundamento = "VOCÊ TEM PERMISSÃO PARA APROFUNDAR: Você pode criar até 5 aulas ADICIONAIS no final do cronograma contendo temas da fronteira do conhecimento que façam muito sentido com a matéria, mesmo que não estejam na ementa. Marque o campo 'aula_complementar': true em todas elas."
        else:
            instrucao_aprofundamento = "É ESTRITAMENTE PROIBIDO adicionar conteúdos ou aulas sobre tópicos que não constam na ementa. O campo 'aula_complementar' deve ser sempre false."

        prompt = f"""
Por favor, analise a ementa abaixo e crie um cronograma balanceado.

Ementa Oficial:
\"\"\"{ementa_texto}\"\"\"

Instruções Personalizadas do Professor:
\"\"\"{instrucoes_personalizadas or 'Nenhuma.'}\"\"\"

DIRETRIZ DE CARGA HORÁRIA (MANDATÓRIO):
{instrucao_carga}

DIRETRIZ DE APROFUNDAMENTO (MANDATÓRIO):
{instrucao_aprofundamento}
"""
        print(f"[MacroRoteirista] Pensando e fatiando a ementa via Structured Output. (Carga={tipo_carga_horaria}, Aprofundamento={permitir_aprofundamento})...")
        
        try:
            from gemini_retry import executar_chamada_com_retry

            def chamar_macro():
                return self.client.models.generate_content(
                    model="gemini-pro-latest",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        response_mime_type="application/json",
                        response_schema=CronogramaCompleto
                    )
                )

            response = executar_chamada_com_retry(
                chamar_macro,
                max_retries=5,
                nome_agente="MacroRoteirista",
                descricao="fatiamento da ementa em cronograma"
            )
            cronograma = CronogramaCompleto.model_validate_json(response.text)
            return [aula.model_dump() for aula in cronograma.aulas]
        except Exception as e:
            print(f"[Erro no MacroRoteirista JSON] {e}")
            return []
