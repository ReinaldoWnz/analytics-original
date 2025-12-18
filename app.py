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
    
    # 1. Datas
    if 'Date [America/Sao_Paulo]' in df.columns:
        date_col = 'Date [America/Sao_Paulo]'
    else:
        date_col = 'Date'
        
    df['Data_Hora'] = pd.to_datetime(df[date_col], errors='coerce', utc=True)
    df = df.dropna(subset=['Data_Hora'])
    df['Data_Hora'] = df['Data_Hora'].dt.tz_convert('America/Sao_Paulo')
    
    df['Data'] = df['Data_Hora'].dt.date
    df['Hora'] = df['Data_Hora'].dt.hour
    
    # 2. Dias da Semana
    df['Dia_Semana_Raw'] = df['Data_Hora'].dt.day_name()
    map_dias = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_Semana'] = df['Dia_Semana_Raw'].map(map_dias).fillna(df['Dia_Semana_Raw'])

    # 3. Duração
    df['Duration [Milliseconds]'] = pd.to_numeric(df['Duration [Milliseconds]'], errors='coerce').fillna(0)
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000
    
    # 4. Mapeamento Específico Solicitado
    # Agente = From
    df['Agente'] = df['From'].fillna('Desconhecido').astype(str).str.strip()
    
    # Participantes (para busca de número)
    df['Participantes'] = df['Participants'].fillna('').astype(str).str.strip()

    # 5. Traduções (Status e Direção)
    df['Call Result'] = df['Call Result'].astype(str).str.strip()
    df['Direction'] = df['Direction'].astype(str).str.strip()

    map_resultados = {
        'Missed Call': 'Perdida',
        'Ended successfully': 'Atendida',
        'Voicemail': 'Correio de Voz',
        'Rejected': 'Rejeitada',
        'Internal': 'Interna',
        'Busy': 'Ocupado',
        'Failed': 'Falha',
        'Hung up (on hold)': 'Desligou na Espera',
        'Sent to voicemail': 'Enviado p/ Correio de Voz',
        'Hung up (in queue)': 'Desligou na Fila'
    }
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
    df = load_data(uploaded_file)
    
    # --- 2. FILTROS LATERAIS (SIDEBAR) ---
    st.sidebar.header("Filtros")
    
    # Data
    min_date = df['Data'].min()
    max_date = df['Data'].max()
    date_range = st.sidebar.date_input("Período", value=[min_date, max_date], format="DD/MM/YYYY")
    
    # Direção
    direcoes = st.sidebar.multiselect(
        "Direção", 
        options=df['Direcao_Traduzida'].unique(),
        default=df['Direcao_Traduzida'].unique()
    )
    
    # Resultado
    resultados = st.sidebar.multiselect(
        "Status / Resultado",
        options=df['Resultado_Traduzido'].unique(),
        default=df['Resultado_Traduzido'].unique()
    )
    
    # --- NOVOS FILTROS PEDIDOS ---
    
    # Filtro 1: Agente (Baseado no 'From')
    # Dica: Ordenamos a lista para ficar fácil de achar
    lista_agentes = sorted(df['Agente'].unique())
    agentes_selecionados = st.sidebar.multiselect(
        "Filtrar por Agente (From)",
        options=lista_agentes,
        default=[] # Vazio = Todos
    )

    # Filtro 2: Participante/Cliente (Busca por Texto)
    st.sidebar.markdown("---")
    st.sidebar.subheader("Buscar Cliente")
    busca_numero = st.sidebar.text_input(
        "Digite o número ou parte dele:",
        placeholder="Ex: 119985..."
    )
    st.sidebar.caption("Busca na coluna 'Participants'")

    # --- APLICAR LÓGICA DE FILTRAGEM ---
    
    # Tratamento de Data (evitar erro de dia único)
    if isinstance(date_range, list) and len(date_range) == 2:
        start_date, end_date = date_range
    elif isinstance(date_range, list) and len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        start_date = end_date = date_range

    mask = (
        (df['Data'] >= start_date) & 
        (df['Data'] <= end_date) &
        (df['Direcao_Traduzida'].isin(direcoes)) &
        (df['Resultado_Traduzido'].isin(resultados))
    )
    df_filtered = df[mask]
    
    # Filtro Específico de Agente
    if agentes_selecionados:
        df_filtered = df_filtered[df_filtered['Agente'].isin(agentes_selecionados)]
        
    # Filtro de Busca de Número (Participants)
    if busca_numero:
        # Filtra se o texto digitado estiver contido na coluna Participantes
        df_filtered = df_filtered[df_filtered['Participantes'].str.contains(busca_numero, case=False, na=False)]

    # --- 3. DASHBOARD ---
    
    st.markdown("### 📊 Visão Geral")
    
    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    total = len(df_filtered)
    duracao_total = df_filtered['Duracao_Minutos'].sum()
    media_total = df_filtered['Duracao_Minutos'].mean() if total > 0 else 0
    
    # Taxa de Perda Inteligente
    termos_perda = ['Perdida', 'Missed', 'Rejeitada', 'Desligou', 'Falha', 'Busy']
    perdas = len(df_filtered[df_filtered['Resultado_Traduzido'].astype(str).str.contains('|'.join(termos_perda), case=False)])
    taxa_perda = (perdas / total * 100) if total > 0 else 0

    c1.metric("Chamadas Filtradas", total)
    c2.metric("Tempo Total", f"{duracao_total/60:.1f}h")
    c3.metric("Tempo Médio", f"{media_total:.1f} min")
    c4.metric("Taxa de Insucesso", f"{taxa_perda:.1f}%", delta_color="inverse")
    
    st.divider()

    # Gráficos
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.subheader("Linha do Tempo")
        if total > 0:
            daily = df_filtered.groupby('Data').size().reset_index(name='Qtd')
            fig = px.line(daily, x='Data', y='Qtd', markers=True, template="plotly_dark")
            fig.update_xaxes(tickformat="%d/%m/%Y")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Sem dados para exibir no gráfico.")

    with col_g2:
        st.subheader("Distribuição")
        if total > 0:
            fig_pie = px.donut(df_filtered, names='Resultado_Traduzido', hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

    # --- 4. TABELA DE DADOS ---
    st.subheader("Detalhes das Chamadas")
    
    # Preparar colunas para exibir
    df_show = df_filtered.copy()
    df_show['Data Formatada'] = df_show['Data_Hora'].dt.strftime('%d/%m/%Y %H:%M')
    
    cols_order = [
        'Data Formatada', 
        'Agente',             # Coluna FROM
        'Participantes',      # Coluna PARTICIPANTS (O número do cliente está aqui)
        'Direcao_Traduzida', 
        'Resultado_Traduzido', 
        'Duracao_Minutos'
    ]
    
    # Renomear para ficar bonito na tela
    rename_map = {
        'Agente': 'Agente (From)',
        'Participantes': 'Detalhes / Número (Participants)',
        'Direcao_Traduzida': 'Direção',
        'Resultado_Traduzido': 'Status',
        'Duracao_Minutos': 'Duração (min)'
    }
    
    st.dataframe(
        df_show[cols_order].rename(columns=rename_map),
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("Aguardando upload...")
