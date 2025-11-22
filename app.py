import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import os
import json
# --- Configurações da Página ---
st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="wide")

# --- CONFIGURAÇÃO GOOGLE SHEETS ---
# Nome EXATO da planilha que você criou no Google Drive
NOME_PLANILHA_GOOGLE = "Controle Financeiro App"
ARQUIVO_CREDENCIAIS = "credentials.json"

# --- CONFIGURAÇÃO DE LOGIN ---
CREDENCIAIS = {
    "angebergui@gmail.com": "123456",
    "jaimecardozo.junior@gmail.com": "123456"
}

# --- FUNÇÕES DE CONEXÃO (CORRIGIDA) ---
@st.cache_resource
def conectar_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. TENTA LER DOS SEGREDOS (Modo Cloud)
    if "gcp_service_account" in st.secrets:
        try:
            # Converte a chave TOML para dicionário JSON
            creds_dict = dict(st.secrets["gcp_service_account"])
            
            # CORREÇÃO CRÍTICA: Garante que a private_key use quebras de linha corretas
            # Este é o ponto que costuma falhar se a chave for copiada errada para os Secrets
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client.open(NOME_PLANILHA_GOOGLE)
        except Exception as e:
            st.error(f"Erro ao conectar na Nuvem (Secrets): Verifique o formato do TOML. Erro: {e}")
            st.stop()

    # 2. TENTA LER DO ARQUIVO LOCAL (Modo Desenvolvimento)
    elif os.path.exists("credentials.json"):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            client = gspread.authorize(creds)
            return client.open(NOME_PLANILHA_GOOGLE)
        except Exception as e:
            st.error(f"Erro ao conectar Localmente: {e}")
            st.stop()

    else:
        st.error("ERRO: Nenhuma credencial encontrada. Configure o arquivo 'secrets' na Nuvem.")
        st.stop()

def carregar_dados_sheets(aba_nome):
    """Lê os dados de uma aba específica e retorna um DataFrame."""
    try:
        sh = conectar_google_sheets()
        worksheet = sh.worksheet(aba_nome)
        dados = worksheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        st.error(f"Erro ao carregar dados do Google Sheets: {e}")
        return pd.DataFrame()

def salvar_dados_sheets(df, aba_nome):
    """Limpa a aba e reescreve os dados atualizados."""
    try:
        sh = conectar_google_sheets()
        worksheet = sh.worksheet(aba_nome)
        
        # Converte datas para string antes de enviar, para evitar erro de JSON
        df_export = df.copy()
        if "Data" in df_export.columns:
            df_export["Data"] = df_export["Data"].astype(str)
            
        # Limpa tudo e reescreve
        worksheet.clear()
        # Adiciona cabeçalho e dados
        worksheet.update([df_export.columns.values.tolist()] + df_export.values.tolist())
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no Google Sheets: {e}")
        return False

# --- LOGIN ---
def verificar_login(email, senha):
    """Verifica se o email e a senha (limpos de espaços) correspondem."""
    
    email_limpo = email.strip() # Remove espaços do email que o usuário digitou
    senha_limpa = senha.strip() # Remove espaços da senha que o usuário digitou
    
    # 1. Checa se o e-mail (limpo) existe no dicionário
    if email_limpo in CREDENCIAIS:
        
        # 2. Pega a senha do Secret, converte para string e remove espaços invisíveis
        senha_secreta_limpa = str(CREDENCIAIS[email_limpo]).strip() 
        
        # 3. Compara as senhas limpas
        if senha_secreta_limpa == senha_limpa:
            return True
            
    return False

def tela_login():
    st.title("🔒 Acesso Restrito")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            email_input = st.text_input("E-mail")
            senha_input = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if verificar_login(email_input.strip(), senha_input.strip()):
                    st.session_state["logado"] = True
                    st.session_state["usuario_atual"] = email_input
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    tela_login()
    st.stop()

# ========================================================
# SISTEMA FINANCEIRO (CONECTADO AO SHEETS)
# ========================================================

# --- Funções de Dados Adaptadas ---
def obter_despesas():
    df = carregar_dados_sheets("Despesas")
    if df.empty:
        return pd.DataFrame(columns=["Data", "Categoria", "Descrição", "Valor"])
    
    # Converter tipos
    df["Data"] = pd.to_datetime(df["Data"]).dt.date
    # Tentar converter valor, lidando com possíveis strings de moeda
    df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0.0)
    return df

def obter_categorias():
    df = carregar_dados_sheets("Categorias")
    if df.empty:
        # Se vazio, cria padrão e salva lá
        padrao = ["Alimentação", "Transporte", "Moradia", "Lazer", "Educação", "Saúde", "Outros"]
        df_padrao = pd.DataFrame(padrao, columns=["Categoria"])
        salvar_dados_sheets(df_padrao, "Categorias")
        return padrao
    return df["Categoria"].tolist()

# --- Interface ---
st.sidebar.success(f"👤 {st.session_state['usuario_atual']}")
if st.sidebar.button("Sair"):
    st.session_state["logado"] = False
    st.rerun()

st.title("💰 Controle de despesas")

# Carregamento inicial
df_despesas = obter_despesas()
lista_categorias = obter_categorias()

# --- Adicionar Nova Categoria ---
with st.sidebar.expander("➕ Categorias"):
    nova_cat = st.text_input("Nova Categoria")
    if st.button("Adicionar"):
        nova_cat = nova_cat.strip().title()
        if nova_cat and nova_cat not in lista_categorias:
            lista_categorias.append(nova_cat)
            salvar_dados_sheets(pd.DataFrame(lista_categorias, columns=["Categoria"]), "Categorias")
            st.success("Categoria Salva na Nuvem!")
            st.rerun()
        else:
            st.warning("Categoria inválida ou já existente.")

st.sidebar.divider()

# --- Adicionar Nova Despesa ---
st.sidebar.header("📝 Nova Despesa")
with st.sidebar.form("form_despesa"):
    data_in = st.date_input("Data", date.today())
    cat_in = st.selectbox("Categoria", lista_categorias)
    desc_in = st.text_input("Descrição")
    val_in = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
    
    if st.form_submit_button("Salvar na Nuvem"):
        if val_in > 0:
            nova_linha = {
                "Data": data_in,
                "Categoria": cat_in,
                "Descrição": desc_in,
                "Valor": val_in
            }
            # Adiciona e salva
            novo_df = pd.DataFrame([nova_linha])
            df_despesas = pd.concat([df_despesas, novo_df], ignore_index=True)
            
            with st.spinner('Salvando no Google Sheets...'):
                salvar_dados_sheets(df_despesas, "Despesas")
            
            st.success("Salvo com sucesso!")
            st.rerun()
        else:
            st.error("Valor inválido.")

# --- Visualização e Edição ---
if not df_despesas.empty:
    # Métricas
    col1, col2 = st.columns(2)
    total = df_despesas["Valor"].sum()
    # Filtro mês atual
    df_calc = df_despesas.copy()
    df_calc["Data"] = pd.to_datetime(df_calc["Data"])
    mes_atual = date.today().strftime("%Y-%m")
    total_mes = df_calc[df_calc["Data"].dt.strftime('%Y-%m') == mes_atual]["Valor"].sum()
    
    col1.metric("Total Geral", f"R$ {total:,.2f}")
    col2.metric("Neste Mês", f"R$ {total_mes:,.2f}")

    st.divider()

    # Tabela Editável
    st.subheader("📋 Editar Planilha (Sincronizado)")
    
    config_colunas = {
        "Categoria": st.column_config.SelectboxColumn(options=lista_categorias, required=True),
        "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
        "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
    }

    df_editado = st.data_editor(
        df_despesas.sort_values("Data", ascending=False),
        column_config=config_colunas,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_sheets",
        hide_index=True
    )

    if st.button("💾 Salvar Alterações no Google Sheets"):
        with st.spinner('Atualizando planilha online...'):
            salvar_dados_sheets(df_editado, "Despesas")
        st.success("Planilha atualizada!")
        st.rerun()

    # Gráficos
    st.divider()
    c1, c2 = st.columns(2)
    c1.bar_chart(df_despesas.groupby("Categoria")["Valor"].sum())
    c2.line_chart(df_despesas.groupby("Data")["Valor"].sum())

else:
    st.info("A planilha 'Despesas' está vazia no Google Sheets.")