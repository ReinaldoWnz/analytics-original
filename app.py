import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="GoTo Analytics", layout="wide")

st.title("📞 Dashboard de Chamadas")
st.markdown("Visão geral simplificada e limpa.")

# --- 2. TRATAMENTO DE DADOS (O mesmo que já funcionava) ---
@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    
    # Identificar coluna de data
    col_date = 'Date [America/Sao_Paulo]' if 'Date [America/Sao_Paulo]' in df.columns else 'Date'
    
    # Converter datas (com tratamento de erro)
    df['Data_Hora'] = pd.to_datetime(df[col_date], errors='coerce', utc=True)
    df = df.dropna(subset=['Data_Hora'])
    df['Data_Hora'] = df['Data_Hora'].dt.tz_convert('America/Sao_Paulo')
    
    # Colunas auxiliares
    df['Data'] = df['Data_Hora'].dt.date
    df['Hora'] = df['Data_Hora'].dt.hour
    df['Dia_Semana'] = df['Data_Hora'].dt.day_name() # Em inglês para o mapa de calor funcionar bem
    
    # Tratamento de Duração
    df['Duration [Milliseconds]'] = pd.to_numeric(df['Duration [Milliseconds]'], errors='coerce').fillna(0)
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000
    
    # Limpeza de Nomes (Remove códigos como '067: ')
    df['Agente'] = df['From'].astype(str).str.replace(r'^\d+:\s*', '', regex=True)
    df['Agente'] = df['Agente'].replace({'nan': 'Desconhecido', 'Wait in queue': 'Fila de Espera'})
    
    return df

# Função para formatar tempo (ex: 2.5 min -> 2m 30s)
def format_time(mins):
    if pd.isna(mins): return "0m"
    h = int(mins // 60)
    m = int(mins % 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m"

# --- 3. INTERFACE PRINCIPAL ---

uploaded_file = st.file_uploader("Arraste o CSV aqui", type=['csv'])

if uploaded_file:
    df = load_data(uploaded_file)
    
    # --- FILTROS (BARRA LATERAL) ---
    with st.sidebar:
        st.header("Filtros")
        
        # Filtro de Data
        min_d, max_d = df['Data'].min(), df['Data'].max()
        dates = st.date_input("Período", [min_d, max_d])
        
        # Outros Filtros
        agentes = st.multiselect("Agentes", sorted(df['Agente'].unique()))
        resultados = st.multiselect("Status", df['Call Result'].unique())
        direcao = st.multiselect("Direção", df['Direction'].unique())

        # Lógica de Filtragem
        mask = (df['Data'] >= dates[0]) & (df['Data'] <= dates[1]) if isinstance(dates, list) and len(dates) == 2 else (df['Data'] == dates)
        
        df_f = df[mask]
        if agentes: df_f = df_f[df_f['Agente'].isin(agentes)]
        if resultados: df_f = df_f[df_f['Call Result'].isin(resultados)]
        if direcao: df_f = df_f[df_f['Direction'].isin(direcao)]

    # --- KPIS (CARTÕES NO TOPO) ---
    # Usando st.container(border=True) para criar o efeito de "Card" nativo
    
    total = len(df_f)
    missed = len(df_f[df_f['Call Result'].str.contains('Missed|Voicemail', case=False, na=False)])
    missed_rate = (missed / total * 100) if total > 0 else 0
    tma = format_time(df_f['Duracao_Minutos'].mean())
    total_time = format_time(df_f['Duracao_Minutos'].sum())
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        with st.container(border=True): # Borda nativa bonita
            st.metric("Total Chamadas", total)
    with col2:
        with st.container(border=True):
            st.metric("Tempo Total", total_time)
    with col3:
        with st.container(border=True):
            st.metric("Tempo Médio (TMA)", tma)
    with col4:
        with st.container(border=True):
            st.metric("Taxa de Perda", f"{missed_rate:.1f}%", f"{missed} perdidas", delta_color="inverse")

    # --- GRÁFICOS ---
    
    # Linha 1: Evolução Temporal + Pizza
    c1, c2 = st.columns([2, 1])
    
    with c1:
        with st.container(border=True):
            st.subheader("Volume Diário")
            daily = df_f.groupby('Data').size().reset_index(name='Qtd')
            # Gráfico de Área limpo
            fig_area = px.area(daily, x='Data', y='Qtd')
            st.plotly_chart(fig_area, use_container_width=True)
            
    with c2:
        with st.container(border=True):
            st.subheader("Status")
            # CORREÇÃO DO ERRO: Usar px.pie com hole=0.5 para fazer o Donut
            fig_donut = px.pie(df_f, names='Call Result', hole=0.5)
            fig_donut.update_traces(textinfo='percent+label')
            fig_donut.update_layout(showlegend=False)
            st.plotly_chart(fig_donut, use_container_width=True)

    # Linha 2: Ranking Agentes
    with st.container(border=True):
        st.subheader("Ranking de Agentes")
        top_agents = df_f['Agente'].value_counts().head(10).reset_index()
        top_agents.columns = ['Agente', 'Chamadas']
        
        fig_bar = px.bar(top_agents, x='Chamadas', y='Agente', orientation='h', text='Chamadas')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- TABELA DE DADOS ---
    with st.expander("Ver dados detalhados"):
        st.dataframe(
            df_f[['Data_Hora', 'Direction', 'Agente', 'Call Result', 'Duracao_Minutos']]
            .sort_values('Data_Hora', ascending=False),
            use_container_width=True
        )

else:
    st.info("Por favor, faça upload do arquivo CSV.")
