from fastapi import FastAPI, Request
import uvicorn
from google import genai
import time
from db_config import salvar_tarefa, buscar_ultima_orientacao, URL_SUPABASE, HEADERS
import httpx

# --- CONFIGURAÇÕES ---
GEMINI_KEY = "AIzaSyDJg_DSyJc6Gr2720ur5Ih800Zk9Lwn5VI"
client = genai.Client(api_key=GEMINI_KEY)

# Configurações da Z-API com as suas chaves reais
ZAPI_INSTANCE = "3F3B4D01F9F3D259DE86DE142E885538"
ZAPI_TOKEN = "A2AE9A86694FAB83B34DD6C9"

app = FastAPI()

def chamar_gemini_com_memoria(desabafo, ultima_orientacao):
    instrucoes_tdah = """
    Você é o assistente do MindFlow para pessoas com TDAH que estão travadas.
    Identifique a ÚNICA tarefa principal que ele deve focar agora e dê até 3 micro-passos simples.
    Responda em português de forma corta e acolhedora, perfeita para ler no WhatsApp.
    """
    contexto = f"{instrucoes_tdah}\n"
    if ultima_orientacao:
        contexto += f"Conversa anterior:\n\"\"\"{ultima_orientacao}\"\"\"\n\n"
    contexto += f"Nova mensagem do usuário: {desabafo}"
    
    for tentativa in range(3):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=contexto)
            return response.text
        except Exception:
            time.sleep(2)
    return "Ops, o servidor do Google balançou. Tente enviar novamente!"

# --- ROTA QUE CONECTA COM A Z-API ---
@app.post("/whatsapp")
async def receber_mensagem_whatsapp(request: Request):
    try:
        # 1. Recebendo o JSON enviado pela Z-API
        dados = await request.json()
        
        # Extraindo o texto da mensagem e o número de quem enviou
        mensagem = dados.get("text", {}).get("message", "")
        chat_id = dados.get("phone", "")
        
        if not mensagem.strip():
            return {"status": "Mensagem vazia ignorada"}
            
        print(f"\n📱 MENSAGEM RECEBIDA: '{mensagem}' do número {chat_id}")
        
        # 2. Busca a memória do passado no Supabase
        ultima_orientacao = buscar_ultima_orientacao()
        
        # 3. Salva a nova mensagem que chegou no banco
        salvar_tarefa(titulo=mensagem, status="pendente")
        
        # Pegamos o ID mais recente criado para atualizar depois
        url_id = f"{URL_SUPABASE}/rest/v1/tarefas?order=id.desc&limit=1"
        res_id = httpx.get(url_id, headers=HEADERS).json()
        id_real = res_id[0]["id"]
        
        # 4. Chama o Gemini usando a memória
        resposta_da_ia = chamar_gemini_com_memoria(mensagem, ultima_orientacao)
        
        # 5. Atualiza o banco com a resposta final da IA
        url_patch = f"{URL_SUPABASE}/rest/v1/tarefas?id=eq.{id_real}"
        httpx.patch(url_patch, headers=HEADERS, json={"titulo": resposta_da_ia, "status": "resolvido"})
        
        # 6. ENVIAR A RESPOSTA DE VOLTA PARA O WHATSAPP DO USUÁRIO
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        payload_zapi = {
            "phone": chat_id,
            "message": resposta_da_ia
        }
        httpx.post(url_zapi, json=payload_zapi)
        print(f"🧠 RESPOSTA DO GEMINI ENVIADA PRO CELULAR!")
        
        return {"status": "Sucesso"}

    except Exception as e:
        print(f"❌ Erro ao processar: {e}")
        return {"status": "Erro", "detalhe": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)