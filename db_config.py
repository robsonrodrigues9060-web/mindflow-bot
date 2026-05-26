import httpx

# Suas credenciais do Supabase
URL_SUPABASE = "https://abtkbdqhwvspkrzxgdbm.supabase.co"
CHAVE_SUPABASE = "sb_publishable_p40B8cvVJrXPv8O2Lx8TRQ_Wxi7bDtN"

# Cabeçalhos padrão para o Supabase aceitar nossos dados
HEADERS = {
    "apikey": CHAVE_SUPABASE,
    "Authorization": f"Bearer {CHAVE_SUPABASE}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def salvar_tarefa(titulo, status="pendente"):
    """Função que envia a tarefa direto para a nuvem do Supabase"""
    url_tabela = f"{URL_SUPABASE}/rest/v1/tarefas"
    dados = {
        "titulo": titulo,
        "status": status
    }
    
    try:
        # Envia os dados pela internet para o seu banco
        resposta = httpx.post(url_tabela, headers=HEADERS, json=dados)
        if resposta.status_code == 201:
            print("🎉 SUCESSO! Tarefa salva no Supabase!")
            print("Dados:", resposta.json())
            return True
        else:
            print(f"❌ Erro do Supabase ({resposta.status_code}):", resposta.text)
            return False
    except Exception as e:
        print("❌ Erro ao conectar com a internet:", e)
        return False

def buscar_ultima_orientacao():
    """Busca a última resposta que a IA deu para usar como memória"""
    # Filtra pelas tarefas resolvidas e ordena para pegar a mais recente
    url_tabela = f"{URL_SUPABASE}/rest/v1/tarefas?status=eq.resolvido&order=id.desc&limit=1"
    
    try:
        resposta = httpx.get(url_tabela, headers=HEADERS)
        if resposta.status_code == 200 and resposta.json():
            # Retorna o texto da última orientação da IA
            return resposta.json()[0]["titulo"]
        return None
    except Exception:
        return None