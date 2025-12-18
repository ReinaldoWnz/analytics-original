import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(page_title="Dashboard GoTo Analytics", layout="wide")

st.title("📞 Análise de Chamadas - GoTo Analytics")

# --- 1. CARREGAMENTO E TRATAMENTO DE DADOS ---
@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    
    # Converter colunas de data (usando a coluna com fuso horário local se disponível)
    # O CSV tem "Date [America/Sao_Paulo]", vamos usar essa preferencialmente
    date_col = 'Date [America/Sao_Paulo]' if 'Date [America/Sao_Paulo]' in df.columns else 'Date'
    df['Data_Hora'] = pd.to_datetime(df[date_col])
    
    # Criar colunas auxiliares
    df['Data'] = df['Data_Hora'].dt.date
    df['Hora'] = df['Data_Hora'].dt.hour
    df['Dia_Semana'] = df['Data_Hora'].dt.day_name()
    
    # Converter Duração de Milissegundos para Minutos
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000
    
    # Limpeza da coluna 'Participants' ou 'From' para pegar o nome do Agente
    # Assumindo que queremos analisar quem originou ou atendeu. 
    # Ajuste essa lógica conforme sua necessidade específica de "Quem é o agente"
    df['Agente'] = df['From'].fillna('Desconhecido') 
    
    return df

# Upload do Arquivo
uploaded_file = st.file_uploader("Faça upload do CSV do GoTo", type=['csv'])

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    # --- 2. FILTROS LATERAIS (SIDEBAR) ---
    st.sidebar.header("Filtros")
    
    # Filtro de Data
    min_date = df['Data'].min()
    max_date = df['Data'].max()
    date_range = st.sidebar.date_input("Período", [min_date, max_date])
    
    # Filtro de Direção (Inbound/Outbound)
    direcoes = st.sidebar.multiselect(
        "Direção da Chamada", 
        options=df['Direction'].unique(),
        default=df['Direction'].unique()
    )
    
    # Filtro de Resultado (Missed, Ended successfully)
    resultados = st.sidebar.multiselect(
        "Resultado da Chamada",
        options=df['Call Result'].unique(),
        default=df['Call Result'].unique()
    )
    
    # Filtro de Agente (Opcional, pois pode haver muitos)
    agentes = st.sidebar.multiselect(
        "Agentes / Origem",
        options=df['Agente'].unique(),
        default=[] # Começa vazio para não poluir, se vazio considera todos
    )

    # APLICAR FILTROS
    df_filtered = df[
        (df['Data'] >= date_range[0]) & 
        (df['Data'] <= date_range[1]) &
        (df['Direction'].isin(direcoes)) &
        (df['Call Result'].isin(resultados))
    ]
    
    if agentes:
        df_filtered = df_filtered[df_filtered['Agente'].isin(agentes)]

    # --- 3. KPI CARDS (VISÃO GERAL) ---
    st.markdown("### 📊 Indicadores Principais")
    col1, col2, col3, col4 = st.columns(4)
    
    total_calls = len(df_filtered)
    total_duration = df_filtered['Duracao_Minutos'].sum()
    avg_duration = df_filtered['Duracao_Minutos'].mean()
    
    # Cálculo de Taxa de Perda (Considerando "Missed Call" como string no CSV)
    missed_calls = len(df_filtered[df_filtered['Call Result'] == 'Missed Call'])
    missed_rate = (missed_calls / total_calls * 100) if total_calls > 0 else 0

    col1.metric("Total de Chamadas", f"{total_calls}")
    col2.metric("Duração Total (h)", f"{total_duration/60:.1f}h")
    col3.metric("Tempo Médio (min)", f"{avg_duration:.2f} min")
    col4.metric("Taxa de Perda", f"{missed_rate:.1f}%", delta_color="inverse")

    st.divider()

    # --- 4. GRÁFICOS E VISUALIZAÇÕES ---
    
    # Linha 1: Evolução Temporal e Distribuição
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.subheader("Volume de Chamadas por Dia")
        calls_per_day = df_filtered.groupby('Data').size().reset_index(name='Contagem')
        fig_timeline = px.line(calls_per_day, x='Data', y='Contagem', markers=True, template="plotly_dark")
        st.plotly_chart(fig_timeline, use_container_width=True)
        
    with col_g2:
        st.subheader("Status das Chamadas")
        fig_pie = px.donut(df_filtered, names='Call Result', hole=0.4, template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)

    # Linha 2: Análise de Agentes e Horários
    col_g3, col_g4 = st.columns(2)
    
    with col_g3:
        st.subheader("Top Agentes por Volume")
        # Top 10 agentes
        top_agents = df_filtered['Agente'].value_counts().head(10).reset_index()
        top_agents.columns = ['Agente', 'Chamadas']
        fig_bar = px.bar(top_agents, x='Chamadas', y='Agente', orientation='h', template="plotly_dark")
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_g4:
        st.subheader("Pico de Horário (Heatmap)")
        # Agrupamento para Heatmap
        heatmap_data = df_filtered.groupby(['Dia_Semana', 'Hora']).size().reset_index(name='Chamadas')
        # Ordenar dias da semana
        dias_ordem = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        fig_heat = px.density_heatmap(
            heatmap_data, 
            x='Hora', 
            y='Dia_Semana', 
            z='Chamadas', 
            nbinsx=24,
            category_orders={"Dia_Semana": dias_ordem},
            color_continuous_scale='Viridis',
            template="plotly_dark"
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # --- 5. TABELA DETALHADA ---
    st.subheader("Dados Detalhados")
    st.dataframe(df_filtered[['Data_Hora', 'Direction', 'From', 'Participants', 'Call Result', 'Duracao_Minutos']].sort_values('Data_Hora', ascending=False))

else:
    st.info("Por favor, faça o upload do arquivo CSV do GoTo Analytics para começar.")
