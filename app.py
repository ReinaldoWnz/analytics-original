import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="GoTo Analytics",
    page_icon="📞",
    layout="wide"
)

# Título Principal com Estilo
st.title("📞 Dashboard de Chamadas")
st.markdown("### Visão Estratégica e Performance")

# --- 2. FUNÇÕES DE TRATAMENTO (Robustas e com Traduções) ---

def formatar_tempo(minutos):
    """Transforma 125.5 minutos em '2h 05m'"""
    if pd.isna(minutos): return "0m"
    minutos = float(minutos)
    horas = int(minutos // 60)
    mins = int(minutos % 60)
    if horas > 0:
        return f"{horas}h {mins}m"
    else:
        return f"{mins}m"

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    
    # 1. TRATAMENTO DE DATAS (Seguro contra erros)
    col_date = 'Date [America/Sao_Paulo]' if 'Date [America/Sao_Paulo]' in df.columns else 'Date'
    
    # Converte forçando erros a virarem NaT e depois converte fuso
    df['Data_Hora'] = pd.to_datetime(df[col_date], errors='coerce', utc=True)
    df = df.dropna(subset=['Data_Hora'])
    df['Data_Hora'] = df['Data_Hora'].dt.tz_convert('America/Sao_Paulo')
    
    # Colunas Derivadas
    df['Data'] = df['Data_Hora'].dt.date
    df['Hora'] = df['Data_Hora'].dt.hour
    df['Dia_Semana_Ingles'] = df['Data_Hora'].dt.day_name()
    
    # 2. TRADUÇÃO DOS DIAS (Feature restaurada!)
    mapa_dias = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_Semana'] = df['Dia_Semana_Ingles'].map(mapa_dias)
    
    # 3. DURAÇÃO E AGENTES
    df['Duration [Milliseconds]'] = pd.to_numeric(df['Duration [Milliseconds]'], errors='coerce').fillna(0)
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000
    
    # Limpeza de Agente (Remove '067: ', etc)
    df['Agente'] = df['From'].astype(str).str.replace(r'^\d+:\s*', '', regex=True)
    df['Agente'] = df['Agente'].replace({'nan': 'Desconhecido', 'Wait in queue': 'Fila de Espera'})
    
    return df

# --- 3. INTERFACE E LÓGICA ---

uploaded_file = st.file_uploader("📂 Arraste o CSV do GoTo Analytics aqui", type=['csv'])

if uploaded_file:
    df = load_data(uploaded_file)
    
    # --- BARRA LATERAL (FILTROS) ---
    with st.sidebar:
        st.header("🔍 Filtros Avançados")
        
        # Data
        min_d, max_d = df['Data'].min(), df['Data'].max()
        dates = st.date_input("Período", [min_d, max_d])
        
        st.divider()
        
        # Filtros Multiselect
        agentes = st.multiselect("👤 Agentes", sorted(df['Agente'].unique()))
        status = st.multiselect("📊 Status", sorted(df['Call Result'].unique()))
        direcao = st.multiselect("arrows_left_right Direção", sorted(df['Direction'].unique()))

        # Aplicar Filtros
        mask = (df['Data'] >= dates[0]) & (df['Data'] <= dates[1]) if isinstance(dates, list) and len(dates) == 2 else (df['Data'] == dates)
        
        df_f = df[mask]
        if agentes: df_f = df_f[df_f['Agente'].isin(agentes)]
        if status: df_f = df_f[df_f['Call Result'].isin(status)]
        if direcao: df_f = df_f[df_f['Direction'].isin(direcao)]

    if df_f.empty:
        st.warning("Nenhum dado encontrado com os filtros atuais.")
        st.stop()

    # --- KPI CARDS (VISUAL BONITO) ---
    
    # Cálculos
    total = len(df_f)
    tma = formatar_tempo(df_f['Duracao_Minutos'].mean())
    tempo_total = formatar_tempo(df_f['Duracao_Minutos'].sum())
    
    # Taxa de Perda
    perdidas = len(df_f[df_f['Call Result'].str.contains('Missed|Voicemail', case=False, na=False)])
    taxa_perda = (perdidas / total * 100) if total > 0 else 0
    
    # Layout de Cartões (Container com Borda)
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        with st.container(border=True):
            st.metric("📞 Volume Total", total)
    with c2:
        with st.container(border=True):
            st.metric("⏱️ Tempo Total", tempo_total)
    with c3:
        with st.container(border=True):
            st.metric("⏳ Tempo Médio (TMA)", tma)
    with c4:
        with st.container(border=True):
            st.metric("🚫 Taxa de Perda", f"{taxa_perda:.1f}%", f"{perdidas} chamadas")

    st.markdown("---")

    # --- GRÁFICOS (RESTAURADOS E BONITOS) ---
    
    # Linha 1: Evolução + Pizza
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        with st.container(border=True):
            st.subheader("📈 Evolução de Chamadas")
            daily = df_f.groupby('Data').size().reset_index(name='Chamadas')
            # Gráfico de Área (Moderno)
            fig = px.area(daily, x='Data', y='Chamadas', template='plotly_white')
            fig.update_traces(line_color='#3b82f6', fillcolor='rgba(59, 130, 246, 0.1)')
            st.plotly_chart(fig, use_container_width=True)
            
    with col_g2:
        with st.container(border=True):
            st.subheader("🍩 Status")
            # Gráfico de Rosca (Donut)
            fig = px.pie(df_f, names='Call Result', hole=0.5, template='plotly_white')
            fig.update_traces(textposition='inside', textinfo='percent')
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Linha 2: Heatmap + Top Agentes
    col_g3, col_g4 = st.columns(2)
    
    with col_g3:
        with st.container(border=True):
            st.subheader("🔥 Mapa de Calor (Horário)")
            # Heatmap Restaurado!
            heatmap_data = df_f.groupby(['Dia_Semana', 'Hora']).size().reset_index(name='Qtd')
            dias_ordem = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
            
            fig = px.density_heatmap(
                heatmap_data, x='Hora', y='Dia_Semana', z='Qtd', 
                nbinsx=24, category_orders={"Dia_Semana": dias_ordem},
                color_continuous_scale='Teal', template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_g4:
        with st.container(border=True):
            st.subheader("🏆 Top Agentes")
            top = df_f['Agente'].value_counts().head(8).reset_index()
            top.columns = ['Agente', 'Chamadas']
            
            fig = px.bar(top, x='Chamadas', y='Agente', orientation='h', text='Chamadas', template='plotly_white')
            fig.update_traces(marker_color='#10b981')
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

    # --- TABELA DE DADOS ---
    with st.expander("📄 Ver Dados Detalhados"):
        st.dataframe(
            df_f[['Data_Hora', 'Direction', 'Agente', 'Call Result', 'Duracao_Minutos']]
            .sort_values('Data_Hora', ascending=False)
            .style.format({'Duracao_Minutos': '{:.2f} min'}),
            use_container_width=True
        )

else:
    # Tela de Boas-vindas
    st.info("👆 Por favor, faça o upload do arquivo CSV na barra acima.")
