import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import httpx
import uvicorn
from google import genai
from db_config import HEADERS, URL_SUPABASE, buscar_ultima_orientacao, salvar_tarefa

# --- CONFIGURAÇÕES ---
GEMINI_KEY = "AIzaSyDJg_DSyJc6Gr2720ur5Ih800Zk9Lwn5VI"
client = genai.Client(api_key=GEMINI_KEY)

# Configurações da Z-API com as suas chaves reais
ZAPI_INSTANCE = "3F3B4D01F9F3D259DE86DE142E885538"
ZAPI_TOKEN = "A2AE9A86694FAB83B34DD6C9"

app = FastAPI()


# 🌐 1ª ROTA: A página visual bonita para quem ler o QR Code
@app.get("/", response_class=HTMLResponse)
async def pagina_inicial():
    html_content = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MindFlow Bot</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
                text-align: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                max-width: 500px;
                width: 90%;
            }
            h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                letter-spacing: 2px;
            }
            p {
                font-size: 1.2rem;
                opacity: 0.9;
                margin-bottom: 30px;
                line-height: 1.5;
            }
            .btn-whatsapp {
                background-color: #25D366;
                color: white;
                text-decoration: none;
                padding: 15px 30px;
                border-radius: 50px;
                font-weight: bold;
                font-size: 1.1rem;
                display: inline-flex;
                align-items: center;
                gap: 10px;
                transition: transform 0.2s, background-color 0.2s;
                box-shadow: 0 4px 15px rgba(37, 211, 102, 0.4);
            }
            .btn-whatsapp:hover {
                transform: scale(1.05);
                background-color: #20ba5a;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧠 MindFlow</h1>
            <p>Bem-vindo ao futuro do atendimento inteligente. Meu assistente virtual integrado ao Gemini IA está pronto para apoiar e destravar o seu foco!</p>
            
            <a href="https://wa.me/5511999999999" target="_blank" class="btn-whatsapp">
                💬 Fale Comigo no WhatsApp
            </a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


def chamar_gemini_com_memoria(desabafo, ultima_orientacao):
    instrucoes_tdah = """
    Você é o assistente do MindFlow para pessoas com TDAH que estão travadas.
    Identifique a ÚNICA tarefa principal que ele deve focar agora e dê até 3 micro-passos simples.
    Responda em português de forma curta e acolhedora, perfeita para ler no WhatsApp.
    """
    contexto = f"{instrucoes_tdah}\n"
    if ultima_orientacao:
        contexto += f"Conversa anterior:\n\"\"\"{ultima_orientacao}\"\"\"\n\n"
    contexto += f"Nova mensagem do usuário: {desabafo}"

    for tentativa in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=contexto
            )
            return response.text
        except Exception:
            time.sleep(2)
    return "Ops, o servidor do Google balançou. Tente enviar novamente!"


# --- 2ª ROTA: CONEXÃO COM A Z-API ---
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
        httpx.patch(
            url_patch,
            headers=HEADERS,
            json={"titulo": resposta_da_ia, "status": "resolvido"},
        )

        # 6. ENVIAR A RESPOSTA DE VOLTA PARA O WHATSAPP DO USUÁRIO
        url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        payload_zapi = {"phone": chat_id, "message": resposta_da_ia}
        httpx.post(url_zapi, json=payload_zapi)
        print("🧠 RESPOSTA DO GEMINI ENVIADA PRO CELULAR!")

        return {"status": "Sucesso"}

    except Exception as e:
        print(f"❌ Erro ao processar: {e}")
        return {"status": "Erro", "detalhe": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
