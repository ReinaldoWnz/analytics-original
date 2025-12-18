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
    
    # 1. Identificar a coluna de data correta
    if 'Date [America/Sao_Paulo]' in df.columns:
        date_col = 'Date [America/Sao_Paulo]'
    else:
        date_col = 'Date'
        
    # 2. Conversão Robusta de Data
    df['Data_Hora'] = pd.to_datetime(df[date_col], errors='coerce', utc=True)
    df = df.dropna(subset=['Data_Hora'])
    df['Data_Hora'] = df['Data_Hora'].dt.tz_convert('America/Sao_Paulo')
    
    # 3. Criar colunas auxiliares
    df['Data'] = df['Data_Hora'].dt.date
    df['Hora'] = df['Data_Hora'].dt.hour
    df['Dia_Semana'] = df['Data_Hora'].dt.day_name()
    
    # --- TRADUÇÃO DOS DIAS DA SEMANA ---
    map_dias = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_Semana'] = df['Dia_Semana'].map(map_dias)

    # 4. Tratar Duração
    df['Duration [Milliseconds]'] = pd.to_numeric(df['Duration [Milliseconds]'], errors='coerce').fillna(0)
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000
    
    # 5. Limpeza de Agente
    df['Agente'] = df['From'].fillna('Desconhecido').astype(str)

    # --- TRADUÇÃO DE VALORES (Call Result e Direction) ---
    map_resultados = {
        'Missed Call': 'Perdida',
        'Ended successfully': 'Atendida',
        'Voicemail': 'Correio de Voz',
        'Rejected': 'Rejeitada',
        'Internal': 'Interna' # Às vezes aparece no status
    }
    # O replace funciona bem mesmo se aparecer algum termo novo (ele mantem o original)
    df['Call Result'] = df['Call Result'].replace(map_resultados)

    map_direcao = {
        'Inbound': 'Recebida',
        'Outbound': 'Realizada',
        'Internal': 'Interna'
    }
    df['Direction'] = df['Direction'].replace(map_direcao)

    return df

# Upload do Arquivo
uploaded_file = st.file_uploader("Faça upload do CSV do GoTo", type=['csv'])

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    # --- 2. FILTROS LATERAIS (SIDEBAR) ---
    st.sidebar.header("Filtros")
    
    # Filtro de Data (Formato BR)
    min_date = df['Data'].min()
    max_date = df['Data'].max()
    
    date_range = st.sidebar.date_input(
        "Período", 
        value=[min_date, max_date],
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY"  # <--- DATA EM FORMATO BR
    )
    
    # Filtro de Direção
    direcoes = st.sidebar.multiselect(
        "Direção da Chamada", 
        options=df['Direction'].unique(),
        default=df['Direction'].unique()
    )
    
    # Filtro de Resultado
    resultados = st.sidebar.multiselect(
        "Resultado da Chamada",
        options=df['Call Result'].unique(),
        default=df['Call Result'].unique()
    )
    
    # Filtro de Agente
    agentes = st.sidebar.multiselect(
        "Agentes / Origem",
        options=df['Agente'].unique(),
        default=[]
    )

    # APLICAR FILTROS (Lógica de datas corrigida para pegar range completo)
    start_date = date_range[0]
    end_date = date_range[1] if len(date_range) > 1 else date_range[0] # Garante que não quebre se selecionar só um dia

    df_filtered = df[
        (df['Data'] >= start_date) & 
        (df['Data'] <= end_date) &
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
    
    # Cálculo de Taxa de Perda (Usando o termo traduzido "Perdida")
    missed_calls = len(df_filtered[df_filtered['Call Result'] == 'Perdida'])
    missed_rate = (missed_calls / total_calls * 100) if total_calls > 0 else 0

    col1.metric("Total de Chamadas", f"{total_calls}")
    col2.metric("Duração Total (h)", f"{total_duration/60:.1f}h")
    col3.metric("Tempo Médio (min)", f"{avg_duration:.2f} min")
    col4.metric("Taxa de Perda", f"{missed_rate:.1f}%", delta_color="inverse")

    st.divider()

    # --- 4. GRÁFICOS E VISUALIZAÇÕES ---
    
    # Linha 1
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.subheader("Volume de Chamadas por Dia")
        calls_per_day = df_filtered.groupby('Data').size().reset_index(name='Contagem')
        fig_timeline = px.line(calls_per_day, x='Data', y='Contagem', markers=True, template="plotly_dark")
        # Força o formato de data no eixo X do gráfico também
        fig_timeline.update_xaxes(tickformat="%d/%m/%Y")
        st.plotly_chart(fig_timeline, use_container_width=True)
        
    with col_g2:
        st.subheader("Status das Chamadas")
        fig_pie = px.donut(df_filtered, names='Call Result', hole=0.4, template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)

    # Linha 2
    col_g3, col_g4 = st.columns(2)
    
    with col_g3:
        st.subheader("Top Agentes (Volume)")
        top_agents = df_filtered['Agente'].value_counts().head(10).reset_index()
        top_agents.columns = ['Agente', 'Chamadas']
        fig_bar = px.bar(top_agents, x='Chamadas', y='Agente', orientation='h', template="plotly_dark")
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_g4:
        st.subheader("Mapa de Calor (Horário de Pico)")
        heatmap_data = df_filtered.groupby(['Dia_Semana', 'Hora']).size().reset_index(name='Chamadas')
        
        # Ordenar dias da semana em PT-BR
        dias_ordem = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        
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
    
    # Selecionar e Renomear colunas para exibição
    df_display = df_filtered[['Data_Hora', 'Direction', 'Agente', 'Call Result', 'Duracao_Minutos']].copy()
    df_display.columns = ['Data/Hora', 'Direção', 'Agente/Origem', 'Resultado', 'Duração (min)']
    
    # Formatar a data na tabela para ficar bonita (String formatada)
    df_display['Data/Hora'] = df_display['Data/Hora'].dt.strftime('%d/%m/%Y %H:%M')
    
    st.dataframe(df_display, use_container_width=True)

else:
    st.info("Por favor, faça o upload do arquivo CSV do GoTo Analytics para começar.")
