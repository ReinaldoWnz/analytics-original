import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da Página
st.set_page_config(page_title="Dashboard GoTo Analytics", layout="wide")

st.title("📞 Análise de Chamadas - GoTo Analytics")

# --- 1. CARREGAMENTO E TRATAMENTO DE DADOS ---
@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    
    # 1. Identificar a coluna de data correta e converter
    if 'Date [America/Sao_Paulo]' in df.columns:
        date_col = 'Date [America/Sao_Paulo]'
    else:
        date_col = 'Date'
        
    df['Data_Hora'] = pd.to_datetime(df[date_col], errors='coerce', utc=True)
    df = df.dropna(subset=['Data_Hora'])
    df['Data_Hora'] = df['Data_Hora'].dt.tz_convert('America/Sao_Paulo')
    
    # Colunas auxiliares
    df['Data'] = df['Data_Hora'].dt.date
    df['Hora'] = df['Data_Hora'].dt.hour
    
    # --- TRADUÇÃO DOS DIAS (Garantindo que venha em inglês para traduzir certo) ---
    df['Dia_Semana_Raw'] = df['Data_Hora'].dt.day_name()
    map_dias = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_Semana'] = df['Dia_Semana_Raw'].map(map_dias).fillna(df['Dia_Semana_Raw'])

    # Tratar Duração
    df['Duration [Milliseconds]'] = pd.to_numeric(df['Duration [Milliseconds]'], errors='coerce').fillna(0)
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000
    
    # Limpeza de Agente
    df['Agente'] = df['From'].fillna('Desconhecido').astype(str)

    # --- TRADUÇÃO DE RESULTADOS E DIREÇÃO (Blindagem) ---
    # Primeiro, converte para string e remove espaços extras do começo/fim
    df['Call Result'] = df['Call Result'].astype(str).str.strip()
    df['Direction'] = df['Direction'].astype(str).str.strip()

    map_resultados = {
        'Missed Call': 'Perdida',
        'Ended successfully': 'Atendida',
        'Voicemail': 'Correio de Voz',
        'Rejected': 'Rejeitada',
        'Internal': 'Interna',
        'Busy': 'Ocupado',
        'Failed': 'Falha'
    }
    # Se não encontrar no dicionário, mantém o original
    df['Resultado_Traduzido'] = df['Call Result'].map(map_resultados).fillna(df['Call Result'])

    map_direcao = {
        'Inbound': 'Recebida',
        'Outbound': 'Realizada',
        'Internal': 'Interna'
    }
    df['Direcao_Traduzida'] = df['Direction'].map(map_direcao).fillna(df['Direction'])

    return df

# Upload do Arquivo
uploaded_file = st.file_uploader("Faça upload do CSV do GoTo", type=['csv'])

if uploaded_file is not None:
    # Limpar cache antigo para garantir que a nova lógica rode
    # st.cache_data.clear() # Descomente essa linha se continuar dando erro, rode uma vez e comente de novo
    
    df = load_data(uploaded_file)
    
    # --- 2. FILTROS LATERAIS (SIDEBAR) ---
    st.sidebar.header("Filtros")
    
    # Filtro de Data (Formato BR Visual)
    min_date = df['Data'].min()
    max_date = df['Data'].max()
    
    date_range = st.sidebar.date_input(
        "Período", 
        value=[min_date, max_date],
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY" 
    )
    
    # Filtro de Direção (Usando a coluna traduzida)
    direcoes = st.sidebar.multiselect(
        "Direção da Chamada", 
        options=df['Direcao_Traduzida'].unique(),
        default=df['Direcao_Traduzida'].unique()
    )
    
    # Filtro de Resultado (Usando a coluna traduzida)
    resultados = st.sidebar.multiselect(
        "Resultado da Chamada",
        options=df['Resultado_Traduzido'].unique(),
        default=df['Resultado_Traduzido'].unique()
    )
    
    # Filtro de Agente
    agentes = st.sidebar.multiselect(
        "Agentes / Origem",
        options=df['Agente'].unique(),
        default=[]
    )

    # APLICAR FILTROS
    start_date = date_range[0]
    end_date = date_range[1] if len(date_range) > 1 else date_range[0]

    df_filtered = df[
        (df['Data'] >= start_date) & 
        (df['Data'] <= end_date) &
        (df['Direcao_Traduzida'].isin(direcoes)) &
        (df['Resultado_Traduzido'].isin(resultados))
    ]
    
    if agentes:
        df_filtered = df_filtered[df_filtered['Agente'].isin(agentes)]

    # --- 3. KPI CARDS ---
    st.markdown("### 📊 Indicadores Principais")
    col1, col2, col3, col4 = st.columns(4)
    
    total_calls = len(df_filtered)
    total_duration = df_filtered['Duracao_Minutos'].sum()
    avg_duration = df_filtered['Duracao_Minutos'].mean() if total_calls > 0 else 0
    
    # Taxa de Perda (Procura por 'Perdida' ou 'Missed' caso a tradução tenha falhado por algum motivo extremo)
    missed_calls = len(df_filtered[df_filtered['Resultado_Traduzido'].str.contains('Perdida|Missed|Rejeitada', case=False)])
    missed_rate = (missed_calls / total_calls * 100) if total_calls > 0 else 0

    col1.metric("Total de Chamadas", f"{total_calls}")
    col2.metric("Duração Total (h)", f"{total_duration/60:.1f}h")
    col3.metric("Tempo Médio (min)", f"{avg_duration:.2f} min")
    col4.metric("Taxa de Perda", f"{missed_rate:.1f}%", delta_color="inverse")

    st.divider()

    # --- 4. GRÁFICOS ---
    
    # Linha 1
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.subheader("Volume Diário")
        calls_per_day = df_filtered.groupby('Data').size().reset_index(name='Contagem')
        fig_timeline = px.line(calls_per_day, x='Data', y='Contagem', markers=True, template="plotly_dark")
        fig_timeline.update_xaxes(tickformat="%d/%m/%Y") # Formato BR no Gráfico
        st.plotly_chart(fig_timeline, use_container_width=True)
        
    with col_g2:
        st.subheader("Status")
        fig_pie = px.donut(df_filtered, names='Resultado_Traduzido', hole=0.4, template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)

    # Linha 2
    col_g3, col_g4 = st.columns(2)
    
    with col_g3:
        st.subheader("Top Agentes")
        top_agents = df_filtered['Agente'].value_counts().head(10).reset_index()
        top_agents.columns = ['Agente', 'Chamadas']
        fig_bar = px.bar(top_agents, x='Chamadas', y='Agente', orientation='h', template="plotly_dark")
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_g4:
        st.subheader("Mapa de Calor (Horário)")
        heatmap_data = df_filtered.groupby(['Dia_Semana', 'Hora']).size().reset_index(name='Chamadas')
        dias_ordem = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        
        fig_heat = px.density_heatmap(
            heatmap_data, x='Hora', y='Dia_Semana', z='Chamadas', 
            nbinsx=24, category_orders={"Dia_Semana": dias_ordem},
            color_continuous_scale='Viridis', template="plotly_dark"
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # --- 5. TABELA DETALHADA ---
    st.subheader("Dados Detalhados")
    
    # Criar tabela de exibição limpa
    df_display = df_filtered.copy()
    
    # Formatar Data explicitamente para String BR
    df_display['Data_Formatada'] = df_display['Data_Hora'].dt.strftime('%d/%m/%Y %H:%M')
    
    # Selecionar colunas finais
    colunas_finais = {
        'Data_Formatada': 'Data/Hora',
        'Direcao_Traduzida': 'Direção',
        'Agente': 'Agente/Origem',
        'Resultado_Traduzido': 'Resultado',
        'Duracao_Minutos': 'Duração (min)'
    }
    
    df_show = df_display[list(colunas_finais.keys())].rename(columns=colunas_finais)
    
    st.dataframe(df_show, use_container_width=True, hide_index=True)

else:
    st.info("Aguardando upload do CSV...")
