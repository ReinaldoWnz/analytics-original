import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da Página
st.set_page_config(page_title="Dashboard GoTo Analytics", layout="wide")

st.title("📞 Análise de Chamadas")

# --- FUNÇÃO DE FORMATAÇÃO DE TEMPO ---
def formatar_tempo(ms):
    if pd.isna(ms) or ms == 0:
        return "00:00"
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    hours = int((ms / (1000 * 60 * 60)))
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

# --- 1. CARREGAMENTO E TRATAMENTO DE DADOS (Back-end) ---
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
    
    # 2. Duração (Cálculos internos)
    df['Duration [Milliseconds]'] = pd.to_numeric(df['Duration [Milliseconds]'], errors='coerce').fillna(0)
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000 
    
    # Coluna Visual (para a tabela)
    df['Duracao_Visual'] = df['Duration [Milliseconds]'].apply(formatar_tempo)
    
    # 3. Limpeza de Strings
    df['Agente'] = df['From'].fillna('Desconhecido').astype(str).str.strip()
    df['Participantes'] = df['Participants'].fillna('').astype(str).str.strip()

    # 4. Traduções Internas
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
    # Variável interna (o usuário não vai ver esse nome feio)
    df['Status_Calc'] = df['Call Result'].map(map_resultados).fillna(df['Call Result'])

    map_direcao = {
        'Inbound': 'Recebida',
        'Outbound': 'Realizada',
        'Internal': 'Interna'
    }
    df['Direcao_Calc'] = df['Direction'].map(map_direcao).fillna(df['Direction'])

    return df

# Upload do Arquivo
uploaded_file = st.file_uploader("Faça upload do CSV do GoTo", type=['csv'])

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    # --- 2. FILTROS (Visual Limpo) ---
    st.sidebar.header("Filtros")
    
    # Data
    min_date = df['Data'].min()
    max_date = df['Data'].max()
    date_range = st.sidebar.date_input("Período", value=[min_date, max_date], format="DD/MM/YYYY")
    
    # Direção
    direcoes = st.sidebar.multiselect(
        "Direção", 
        options=df['Direcao_Calc'].unique(),
        default=df['Direcao_Calc'].unique()
    )
    
    # Resultado
    resultados = st.sidebar.multiselect(
        "Status",
        options=df['Status_Calc'].unique(),
        default=df['Status_Calc'].unique()
    )
    
    # Agente
    lista_agentes = sorted(df['Agente'].unique())
    agentes_selecionados = st.sidebar.multiselect(
        "Agente",
        options=lista_agentes,
        default=[] 
    )

    # Busca Cliente
    st.sidebar.markdown("---")
    st.sidebar.subheader("Buscar Cliente")
    busca_numero = st.sidebar.text_input(
        "Digite o telefone:",
        placeholder="Ex: 1199..."
    )

    # --- LÓGICA DE FILTRAGEM ---
    if isinstance(date_range, (list, tuple)):
        if len(date_range) == 2:
            start_date, end_date = date_range
        elif len(date_range) == 1:
            start_date = end_date = date_range[0]
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date = end_date = date_range

    mask = (
        (df['Data'] >= start_date) & 
        (df['Data'] <= end_date) &
        (df['Direcao_Calc'].isin(direcoes)) &
        (df['Status_Calc'].isin(resultados))
    )
    df_filtered = df[mask]
    
    if agentes_selecionados:
        df_filtered = df_filtered[df_filtered['Agente'].isin(agentes_selecionados)]
        
    if busca_numero:
        df_filtered = df_filtered[df_filtered['Participantes'].str.contains(busca_numero, case=False, na=False)]

    # --- 3. DASHBOARD ---
    
    st.markdown("### 📊 Visão Geral")
    
    c1, c2, c3, c4 = st.columns(4)
    total = len(df_filtered)
    duracao_total_min = df_filtered['Duracao_Minutos'].sum()
    media_total_min = df_filtered['Duracao_Minutos'].mean() if total > 0 else 0
    
    termos_perda = ['Perdida', 'Missed', 'Rejeitada', 'Desligou', 'Falha', 'Busy']
    perdas = len(df_filtered[df_filtered['Status_Calc'].astype(str).str.contains('|'.join(termos_perda), case=False)])
    taxa_perda = (perdas / total * 100) if total > 0 else 0

    c1.metric("Total de Chamadas", total)
    c2.metric("Tempo Total", f"{duracao_total_min/60:.1f}h")
    c3.metric("Tempo Médio", f"{media_total_min:.1f} min")
    c4.metric("Taxa de Perda", f"{taxa_perda:.1f}%", delta_color="inverse")
    
    st.divider()

    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.subheader("Volume por Dia")
        if total > 0:
            daily = df_filtered.groupby('Data').size().reset_index(name='Quantidade')
            # labels={} renomeia a legenda automática do gráfico
            fig = px.line(
                daily, x='Data', y='Quantidade', markers=True, 
                template="plotly_dark",
                labels={'Data': 'Data', 'Quantidade': 'Chamadas'}
            )
            fig.update_xaxes(tickformat="%d/%m/%Y")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Sem dados.")

    with col_g2:
        st.subheader("Status")
        if total > 0:
            # labels={} garante que no gráfico apareça 'Status' e não 'Status_Calc'
            fig_pie = px.pie(
                df_filtered, 
                names='Status_Calc', 
                hole=0.4, 
                template="plotly_dark",
                labels={'Status_Calc': 'Status'} 
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    # --- 4. TABELA DE DADOS (Visual Clean) ---
    st.subheader("Extrato das Chamadas")
    
    df_show = df_filtered.copy()
    
    # Formatação Visual da Data
    df_show['Data_Visual'] = df_show['Data_Hora'].dt.strftime('%d/%m/%Y %H:%M')
    
    # Formatação Visual do Cliente (Pega só o primeiro número)
    df_show['Cliente_Visual'] = df_show['Participantes'].str.split(';').str[0]
    
    # Seleção e Renomeação Final (O pulo do gato para ficar limpo)
    cols_order = [
        'Data_Visual', 
        'Agente',             
        'Cliente_Visual',      
        'Direcao_Calc', 
        'Status_Calc', 
        'Duracao_Visual'
    ]
    
    # Dicionário de nomes amigáveis
    rename_map = {
        'Data_Visual': 'Data/Hora',
        'Agente': 'Agente',
        'Cliente_Visual': 'Cliente / Telefone',
        'Direcao_Calc': 'Direção',
        'Status_Calc': 'Status',
        'Duracao_Visual': 'Duração'
    }
    
    st.dataframe(
        df_show[cols_order].rename(columns=rename_map),
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("Aguardando upload do arquivo CSV...")
