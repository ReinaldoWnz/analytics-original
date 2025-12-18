import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="GoTo Analytics",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PERSONALIZADO (A MÁGICA VISUAL) ---
st.markdown("""
<style>
    /* Fundo geral da aplicação (Cinza suave estilo SaaS) */
    .stApp {
        background-color: #f0f2f6;
    }
    
    /* Estilo dos Cards (Caixas brancas com sombra) */
    .css-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
    }
    
    /* Títulos dos Cards */
    .card-title {
        font-size: 16px;
        font-weight: 600;
        color: #555;
        margin-bottom: 10px;
    }
    
    /* Números Grandes (KPIs) */
    .kpi-value {
        font-size: 32px;
        font-weight: 700;
        color: #1f2937;
        margin: 0;
    }
    
    /* Legendas dos KPIs */
    .kpi-label {
        font-size: 14px;
        color: #6b7280;
        margin-top: 4px;
    }
    
    /* Destaque para cores específicas */
    .text-green { color: #10b981; }
    .text-red { color: #ef4444; }
    .text-blue { color: #3b82f6; }
    
    /* Remove padding excessivo do topo */
    .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE CARGA E TRATAMENTO (Mesma lógica robusta) ---
@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    
    # Datas
    if 'Date [America/Sao_Paulo]' in df.columns:
        date_col = 'Date [America/Sao_Paulo]'
    else:
        date_col = 'Date'

    df['Data_Hora'] = pd.to_datetime(df[date_col], errors='coerce', utc=True)
    df = df.dropna(subset=['Data_Hora'])
    df['Data_Hora'] = df['Data_Hora'].dt.tz_convert('America/Sao_Paulo')
    
    df['Data'] = df['Data_Hora'].dt.date
    df['Hora'] = df['Data_Hora'].dt.hour
    df['Dia_Semana'] = df['Data_Hora'].dt.day_name()
    
    # Duração
    df['Duration [Milliseconds]'] = pd.to_numeric(df['Duration [Milliseconds]'], errors='coerce').fillna(0)
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000
    
    # Limpeza de Nomes
    df['Agente'] = df['From'].astype(str).str.replace(r'^\d+:\s*', '', regex=True)
    df['Agente'] = df['Agente'].replace({'nan': 'Desconhecido', 'Wait in queue': 'Fila de Espera'})
    
    # Tradução Dias
    dias_map = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'}
    df['Dia_Semana_PT'] = df['Dia_Semana'].map(dias_map)

    return df

def format_time(mins):
    if pd.isna(mins): return "0m"
    h = int(mins // 60)
    m = int(mins % 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m"

# --- APP PRINCIPAL ---

st.markdown("### 📞 Dashboard de Chamadas")

uploaded_file = st.file_uploader("", type=['csv'], label_visibility="collapsed")
if not uploaded_file:
    st.info("👆 Carregue o CSV do GoTo Analytics para ver o dashboard.")
    st.stop()

df = load_data(uploaded_file)

# --- SIDEBAR (Filtros Limpos) ---
with st.sidebar:
    st.header("Filtros")
    
    # Filtro Data
    min_d, max_d = df['Data'].min(), df['Data'].max()
    dates = st.date_input("Período", [min_d, max_d])
    
    # Filtros Multiplos
    direction = st.multiselect("Direção", df['Direction'].unique(), default=df['Direction'].unique())
    results = st.multiselect("Status", df['Call Result'].unique(), default=df['Call Result'].unique())
    agents = st.multiselect("Agentes", sorted(df['Agente'].unique()))

    # Lógica de Filtro
    if isinstance(dates, list) and len(dates) == 2:
        mask = (df['Data'] >= dates[0]) & (df['Data'] <= dates[1])
    else:
        mask = (df['Data'] == dates[0]) if isinstance(dates, list) else (df['Data'] == dates)
        
    df_f = df[mask & df['Direction'].isin(direction) & df['Call Result'].isin(results)]
    if agents: df_f = df_f[df_f['Agente'].isin(agents)]

# --- CÁLCULOS KPI ---
total = len(df_f)
dur_total = format_time(df_f['Duracao_Minutos'].sum())
dur_media = format_time(df_f['Duracao_Minutos'].mean())
missed = len(df_f[df_f['Call Result'].str.contains('Missed|Voicemail', case=False, na=False)])
missed_rate = (missed / total * 100) if total > 0 else 0

# --- LAYOUT DE CARDS (HTML PURO PARA BELEZA) ---
col1, col2, col3, col4 = st.columns(4)

def kpi_card(title, value, subtext="", color_class=""):
    return f"""
    <div class="css-card">
        <div class="card-title">{title}</div>
        <div class="kpi-value {color_class}">{value}</div>
        <div class="kpi-label">{subtext}</div>
    </div>
    """

with col1:
    st.markdown(kpi_card("Total Chamadas", total, "Volume no período"), unsafe_allow_html=True)
with col2:
    st.markdown(kpi_card("Duração Total", dur_total, "Tempo falado"), unsafe_allow_html=True)
with col3:
    st.markdown(kpi_card("TMA", dur_media, "Tempo médio ated."), unsafe_allow_html=True)
with col4:
    color = "text-red" if missed_rate > 15 else "text-green"
    st.markdown(kpi_card("Taxa de Perda", f"{missed_rate:.1f}%", f"{missed} não atendidas", color), unsafe_allow_html=True)

# --- GRÁFICOS (EM CONTAINER BRANCO) ---

# Linha 1: Evolução
with st.container():
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Fluxo de Chamadas por Dia</div>', unsafe_allow_html=True)
    
    daily = df_f.groupby('Data').size().reset_index(name='Chamadas')
    fig = px.area(daily, x='Data', y='Chamadas', template='plotly_white')
    fig.update_traces(line_color='#3b82f6', fillcolor='rgba(59, 130, 246, 0.1)')
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=10, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Linha 2: Duas Colunas
c1, c2 = st.columns(2)

with c1:
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Top Agentes</div>', unsafe_allow_html=True)
    top = df_f['Agente'].value_counts().head(8).reset_index()
    top.columns = ['Agente', 'Qtd']
    fig = px.bar(top, x='Qtd', y='Agente', orientation='h', text='Qtd', template='plotly_white')
    fig.update_traces(marker_color='#10b981', textposition='outside')
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Status da Chamada</div>', unsafe_allow_html=True)
    fig = px.donut(df_f, names='Call Result', hole=0.6, template='plotly_white')
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=20), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Tabela
st.markdown('<div class="css-card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">Detalhamento</div>', unsafe_allow_html=True)
st.dataframe(df_f[['Data_Hora', 'Direction', 'Agente', 'Call Result', 'Duracao_Minutos']].sort_values('Data_Hora', ascending=False), use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)
