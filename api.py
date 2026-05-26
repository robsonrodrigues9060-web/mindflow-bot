import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
import uvicorn
from google import genai
from db_config import HEADERS, URL_SUPABASE, buscar_ultima_orientacao, salvar_tarefa

# --- CONFIGURAÇÕES ---
GEMINI_KEY = "AIzaSyDJg_DSyJc6Gr2720ur5Ih800Zk9Lwn5VI"
client = genai.Client(api_key=GEMINI_KEY)

app = FastAPI()

# Modelo para receber as mensagens direto do site
class MensagemWeb(BaseModel):
    texto: str

# 🌐 1ª ROTA: O Chat Visual Lindo para conversar direto pelo navegador
@app.get("/", response_class=HTMLResponse)
async def pagina_inicial():
    html_content = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MindFlow Chat</title>
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
            }
            .chat-container {
                background: rgba(255, 255, 255, 0.1);
                padding: 20px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                max-width: 500px;
                width: 90%;
                height: 70vh;
                display: flex;
                flex-direction: column;
            }
            h1 {
                font-size: 1.8rem;
                margin: 0 0 15px 0;
                text-align: center;
                letter-spacing: 1px;
            }
            .chat-box {
                flex: 1;
                background: rgba(0, 0, 0, 0.2);
                border-radius: 10px;
                padding: 15px;
                overflow-y: auto;
                margin-bottom: 15px;
                display: flex;
                flex-direction: column;
                gap: 10px;
                text-align: left;
            }
            .message {
                padding: 10px 15px;
                border-radius: 15px;
                max-width: 80%;
                line-height: 1.4;
            }
            .user-msg {
                background-color: #0076ff;
                align-self: flex-end;
            }
            .bot-msg {
                background-color: #34c759;
                align-self: flex-start;
            }
            .input-area {
                display: flex;
                gap: 10px;
            }
            input {
                flex: 1;
                padding: 12px;
                border: none;
                border-radius: 25px;
                outline: none;
                font-size: 1rem;
            }
            button {
                background-color: #0076ff;
                color: white;
                border: none;
                padding: 0 20px;
                border-radius: 25px;
                font-weight: bold;
                cursor: pointer;
                transition: background 0.2s;
            }
            button:hover {
                background-color: #0056b3;
            }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <h1>🧠 MindFlow Chat</h1>
            <div class="chat-box" id="chatBox">
                <div class="message bot-msg">Olá! Sou o MindFlow. Me conte o que está te travando hoje para organizarmos seus passos?</div>
            </div>
            <div class="input-area">
                <input type="text" id="userInput" placeholder="Digite seu desabafo aqui..." onkeypress="verificarEnter(event)">
                <button onclick="enviarMensagem()">Enviar</button>
            </div>
        </div>

        <script>
            function verificarEnter(event) {
                if (event.key === 'Enter') enviarMensagem();
            }

            async function enviarMensagem() {
                const input = document.getElementById('userInput');
                const texto = input.value.trim();
                if (!texto) return;

                const chatBox = document.getElementById('chatBox');
                
                // Mostrar mensagem do usuário na tela
                chatBox.innerHTML += `<div class="message user-msg">${texto}</div>`;
                input.value = '';
                chatBox.scrollTop = chatBox.scrollHeight;

                // Mostrar balão de "Pensando..."
                const pensandoId = 'pensando_' + Date.now();
                chatBox.innerHTML += `<div class="message bot-msg" id="${pensandoId}">🧠 Pensando...</div>`;
                chatBox.scrollTop = chatBox.scrollHeight;

                try {
                    // Envia direto para o nosso servidor no Render
                    const response = await fetch('/conversar-web', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ texto: texto })
                    });
                    const dados = await response.json();
                    
                    // Substitui o "Pensando..." pela resposta real da IA
                    document.getElementById(pensandoId).innerText = dados.resposta;
                } catch (error) {
                    document.getElementById(pensandoId).innerText = "Ops, deu um erro ao conectar.";
                }
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


def chamar_gemini_com_memoria(desabafo, ultima_orientacao):
    instrucoes_tdah = """
    Você é o assistente do MindFlow para pessoas com TDAH que estão travadas.
    Identifique a ÚNICA tarefa principal que ele deve focar agora e dê até 3 micro-passos simples.
    Responda em português de forma curta e acolhedora.
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


# 🚀 2ª ROTA: O motor que processa as mensagens vindas DIRETO do site
@app.post("/conversar-web")
async def conversar_web(dados: MensagemWeb):
    try:
        mensagem = dados.texto
        
        # 1. Busca a memória do passado no Supabase
        ultima_orientacao = buscar_ultima_orientacao()

        # 2. Salva a nova mensagem que chegou no banco
        salvar_tarefa(titulo=mensagem, status="pendente")

        # Pegamos o ID mais recente criado para atualizar depois
        url_id = f"{URL_SUPABASE}/rest/v1/tarefas?order=id.desc&limit=1"
        res_id = httpx.get(url_id, headers=HEADERS).json()
        id_real = res_id[0]["id"]

        # 3. Chama o Gemini usando a memória
        resposta_da_ia = chamar_gemini_com_memoria(mensagem, ultima_orientacao)

        # 4. Atualiza o banco com a resposta final da IA
        url_patch = f"{URL_SUPABASE}/rest/v1/tarefas?id=eq.{id_real}"
        httpx.patch(
            url_patch,
            headers=HEADERS,
            json={"titulo": resposta_da_ia, "status": "resolvido"},
        )

        return {"resposta": resposta_da_ia}

    except Exception as e:
        return {"resposta": f"Erro ao processar: {str(e)}"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
