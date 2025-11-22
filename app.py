import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import os
import json
from streamlit_cookies import CookieManager # NOVO IMPORT

# --- Configurações da Página ---
st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="wide")

# --- CONFIGURAÇÕES CRÍTICAS ---
NOME_PLANILHA_GOOGLE = "Controle Financeiro App" 
ARQUIVO_CREDENCIAIS = "credentials.json"
COOKIE_USER_KEY = "finance_app_user" # Chave do cookie para armazenar o email

# Inicializa o gerenciador de cookies
cookie_manager = CookieManager()


# ========================================================
# FUNÇÕES DE CONEXÃO E SECRETS
# ========================================================

@st.cache_resource
def conectar_google_sheets():
    """Conecta ao Google Sheets, priorizando Secrets (Cloud) e fallback para JSON (Local)."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. TENTA LER DOS SEGREDOS (Modo Cloud)
    if "gcp_service_account" in st.secrets:
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client.open(NOME_PLANILHA_GOOGLE)
        except Exception as e:
            st.error(f"Erro ao conectar na Nuvem (Secrets): Verifique o formato do TOML. Erro: {e}")
            st.stop()

    # 2. TENTA LER DO ARQUIVO LOCAL (Modo Desenvolvimento)
    elif os.path.exists(ARQUIVO_CREDENCIAIS):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(ARQUIVO_CREDENCIAIS, scope)
            client = gspread.authorize(creds)
            return client.open(NOME_PLANILHA_GOOGLE)
        except Exception as e:
            st.error(f"Erro ao conectar Localmente (JSON Inválido ou Planilha Inacessível): {e}")
            st.stop()

    else:
        st.error("ERRO: Nenhuma credencial encontrada. Configure o arquivo 'secrets' na Nuvem ou 'credentials.json' localmente.")
        st.stop()

def carregar_dados_sheets(aba_nome):
    """Lê os dados de uma aba específica e retorna um DataFrame."""
    try:
        sh = conectar_google_sheets()
        worksheet = sh.worksheet(aba_nome)
        dados = worksheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        st.error(f"Erro ao carregar dados do Google Sheets da aba '{aba_nome}': {e}")
        return pd.DataFrame()

def salvar_dados_sheets(df, aba_nome):
    """Limpa a aba e reescreve os dados atualizados."""
    try:
        sh = conectar_google_sheets()
        worksheet = sh.worksheet(aba_nome)
        
        df_export = df.copy()
        if "Data" in df_export.columns:
            df_export["Data"] = df_export["Data"].astype(str)
            
        worksheet.clear()
        worksheet.update([df_export.columns.values.tolist()] + df_export.values.tolist())
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no Google Sheets: {e}")
        return False


# --- CONFIGURAÇÃO DE LOGIN (LENDO DOS SECRETS) ---
try:
    CREDENCIAIS = st.secrets.login_credentials
except AttributeError:
    st.error("ERRO DE CONFIGURAÇÃO: O app não encontrou a seção [login_credentials] no Secrets.")
    CREDENCIAIS = {}

def verificar_login(email, senha):
    """Verifica se o email e a senha (limpos de espaços) correspondem."""
    email_limpo = email.strip()
    senha_limpa = senha.strip()
    
    if email_limpo in CREDENCIAIS:
        senha_secreta_limpa = str(CREDENCIAIS[email_limpo]).strip() 
        
        if senha_secreta_limpa == senha_limpa:
            return True
            
    return False

# ========================================================
# TELA DE LOGIN, ESTADO E LÓGICA DE COOKIES (NOVO)
# ========================================================

def tela_login():
    st.title("🔒 Acesso Restrito")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            email_input = st.text_input("E-mail")
            senha_input = st.text_input("Senha", type="password")
            
            # NOVO: Checkbox "Lembrar-me"
            lembrar_me = st.checkbox("Lembrar-me por 30 dias")
            
            if st.form_submit_button("Entrar"):
                if verificar_login(email_input, senha_input):
                    st.session_state["logado"] = True
                    st.session_state["usuario_atual"] = email_input.strip()
                    
                    # NOVO: Se marcou "Lembrar-me", salva o email no cookie
                    if lembrar_me:
                        # Expira em 30 dias
                        cookie_manager.set(COOKIE_USER_KEY, email_input.strip(), expires_at=date.today().day + 30)
                        
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

# --- Lógica de Inicialização de Sessão ---

# 1. Tenta carregar o estado do cookie
user_cookie = cookie_manager.get(COOKIE_USER_KEY)

if "logado" not in st.session_state:
    st.session_state["logado"] = False
    
# 2. Se a sessão não está logada E achamos um cookie:
if not st.session_state["logado"] and user_cookie:
    # Verifica se o email do cookie ainda é um usuário válido nos Secrets
    if user_cookie.strip() in CREDENCIAIS:
        st.session_state["logado"] = True
        st.session_state["usuario_atual"] = user_cookie.strip()
        st.success(f"Bem-vindo(a) de volta, {user_cookie}!")
        st.rerun() # Recarrega para pular o login

# 3. Se não está logado (e não tem cookie), mostra a tela de login
if not st.session_state["logado"]:
    tela_login()
    st.stop()


# ========================================================
# SISTEMA FINANCEIRO CORE
# ========================================================

# --- Interface ---
st.sidebar.success(f"👤 {st.session_state['usuario_atual']}")

# NOVO: Botão Sair também deleta o cookie
if st.sidebar.button("Sair"):
    st.session_state["logado"] = False
    st.session_state["usuario_atual"] = ""
    # Deleta o cookie
    cookie_manager.delete(COOKIE_USER_KEY)
    st.rerun()

st.title("💰 Finanças no Google Sheets")

# Carregamento inicial (restante do app)
df_despesas = obter_despesas()
lista_categorias = obter_categorias()

# ... (O restante da sua lógica de gerenciamento de categorias, despesas, gráficos e edição) ...
# O restante do código abaixo é o mesmo que você já tem, garantindo que tudo funcione

# --- Adicionar Nova Categoria ---
with st.sidebar.expander("➕ Gerenciar Categorias"):
    col_cat1, col_cat2 = st.columns(2)
    nova_cat = col_cat1.text_input("Nova Categoria", key="input_nova_cat")
    
    if col_cat2.button("Adicionar", key="btn_add_cat"):
        nova_cat = nova_cat.strip().title()
        if nova_cat and nova_cat not in lista_categorias:
            lista_categorias.append(nova_cat)
            salvar_dados_sheets(pd.DataFrame(lista_categorias, columns=["Categoria"]), "Categorias")
            st.success("Categoria Salva na Nuvem!")
            st.rerun()
        else:
            st.warning("Categoria inválida ou já existente.")
            
    st.markdown("---")
    st.info("Categorias Atuais:")
    st.write(lista_categorias)


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
    
    # --- Métricas ---
    col1, col2 = st.columns(2)
    total = df_despesas["Valor"].sum()
    
    df_calc = df_despesas.copy()
    df_calc["Data"] = pd.to_datetime(df_calc["Data"], errors='coerce')
    mes_atual = date.today().strftime("%Y-%m")
    total_mes = df_calc[df_calc["Data"].dt.strftime('%Y-%m') == mes_atual]["Valor"].sum()
    
    col1.metric("Total Geral Gasto", f"R$ {total:,.2f}")
    col2.metric("Total Gasto Neste Mês", f"R$ {total_mes:,.2f}")

    st.divider()

    # --- Tabela Editável ---
    st.subheader("📋 Editar / Deletar Lançamentos (Sincronizado)")
    
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
        
        df_editado = df_editado.dropna(subset=['Data', 'Valor'])
        df_editado = df_editado[df_editado['Valor'] > 0] 
        
        with st.spinner('Atualizando planilha online...'):
            salvar_dados_sheets(df_editado, "Despesas")
        st.success("Planilha atualizada na Nuvem!")
        st.rerun()

    # --- Gráficos ---
    st.divider()
    st.subheader("📊 Análise Gráfica")
    c1, c2 = st.columns(2)
    
    df_agrupado_cat = df_despesas.groupby("Categoria")["Valor"].sum().reset_index()
    c1.bar_chart(df_agrupado_cat, x="Categoria", y="Valor")
    
    df_agrupado_data = df_despesas.groupby("Data")["Valor"].sum().reset_index()
    c2.line_chart(df_agrupado_data, x="Data", y="Valor")


else:
    st.info("A planilha 'Despesas' está vazia no Google Sheets. Adicione o primeiro lançamento na barra lateral.")