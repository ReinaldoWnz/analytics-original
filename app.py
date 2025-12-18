import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="GoTo Analytics Dashboard",
    page_icon="📞",
    layout="wide"
)

# --- FUNÇÕES AUXILIARES DE FORMATAÇÃO ---
def formatar_duracao_humanizada(minutos_totais):
    """Converte minutos float (ex: 125.5) para string '2h 05m' ou '05m 30s'"""
    if pd.isna(minutos_totais):
        return "0m"
    
    segundos_totais = int(minutos_totais * 60)
    
    horas = segundos_totais // 3600
    minutos_restantes = (segundos_totais % 3600) // 60
    segundos = segundos_totais % 60
    
    if horas > 0:
        return f"{horas}h {minutos_restantes}m"
    else:
        return f"{minutos_restantes}m {segundos}s"

# --- CARREGAMENTO E LIMPEZA DE DADOS ---
@st.cache_data
def load_data(file):
    # Lê o CSV
    df = pd.read_csv(file)
    
    # 1. TRATAMENTO DE DATA (Evitar erros de formato)
    # Tenta usar a coluna com fuso horário local se existir, senão usa a padrão
    if 'Date [America/Sao_Paulo]' in df.columns:
        date_col = 'Date [America/Sao_Paulo]'
    else:
        date_col = 'Date'

    # Converte para datetime forçando erros a virarem NaT (Not a Time)
    # utc=True ajuda a interpretar formatos ISO complexos
    df['Data_Hora'] = pd.to_datetime(df[date_col], errors='coerce', utc=True)
    
    # Remove linhas que não tenham data válida (ex: rodapés ou linhas vazias)
    df = df.dropna(subset=['Data_Hora'])
    
    # Converte para o fuso horário de SP
    df['Data_Hora'] = df['Data_Hora'].dt.tz_convert('America/Sao_Paulo')
    
    # Cria colunas derivadas para filtros e gráficos
    df['Data'] = df['Data_Hora'].dt.date
    df['Hora'] = df['Data_Hora'].dt.hour
    df['Dia_Semana'] = df['Data_Hora'].dt.day_name()
    
    # 2. TRATAMENTO DE DURAÇÃO
    # Garante que é número e preenche vazios com 0
    df['Duration [Milliseconds]'] = pd.to_numeric(df['Duration [Milliseconds]'], errors='coerce').fillna(0)
    # Converte para minutos para facilitar cálculos
    df['Duracao_Minutos'] = df['Duration [Milliseconds]'] / 60000
    
    # 3. LIMPEZA DE NOMES DE AGENTES
    # Remove prefixos numéricos como '067: ' ou '031: ' da coluna 'From'
    df['Agente'] = df['From'].astype(str).str.replace(r'^\d+:\s*', '', regex=True)
    df['Agente'] = df['Agente'].replace({'nan': 'Desconhecido', 'Wait in queue': 'Fila de Espera'})
    
    # Tradução simples de dias da semana para ordenação no gráfico
    dias_traducao = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_Semana_PT'] = df['Dia_Semana'].map(dias_traducao)

    return df

# --- INTERFACE PRINCIPAL ---

st.title("📞 Dashboard GoTo Analytics")
st.markdown("Visão estratégica de chamadas, performance de agentes e horários de pico.")

# UPLOAD
uploaded_file = st.file_uploader("Arraste seu arquivo CSV (Relatório GoTo) aqui", type=['csv'])

if uploaded_file is not None:
    # Carregar dados
    df = load_data(uploaded_file)
    
    # --- BARRA LATERAL (FILTROS) ---
    st.sidebar.header("🔍 Filtros")
    
    # 1. Filtro de Data
    min_date = df['Data'].min()
    max_date = df['Data'].max()
    date_range = st.sidebar.date_input("Período de Análise", [min_date, max_date])

    # Se o usuário selecionar apenas uma data, o streamlit retorna só um objeto data, não uma lista
    if isinstance(date_range, list) and len(date_range) == 2:
        start_date, end_date = date_range
        mask_date = (df['Data'] >= start_date) & (df['Data'] <= end_date)
    else:
        mask_date = (df['Data'] == date_range[0]) if isinstance(date_range, list) else (df['Data'] == date_range)
    
    # 2. Filtro de Direção
    all_directions = df['Direction'].unique()
    directions = st.sidebar.multiselect("Direção", all_directions, default=all_directions)
    
    # 3. Filtro de Resultado (Ex: Missed, Ended)
    all_results = df['Call Result'].unique()
    results = st.sidebar.multiselect("Resultado", all_results, default=all_results)
    
    # 4. Filtro de Agente
    all_agents = sorted(df['Agente'].unique())
    selected_agents = st.sidebar.multiselect("Agentes", all_agents, default=[])

    # APLICAR FILTROS
    df_filtered = df[mask_date & df['Direction'].isin(directions) & df['Call Result'].isin(results)]
    
    if selected_agents:
        df_filtered = df_filtered[df_filtered['Agente'].isin(selected_agents)]

    if df_filtered.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
    else:
        # --- BLOCO DE KPIs (ESTILO GOTO) ---
        st.markdown("### Indicadores Chave")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Cálculos
        total_calls = len(df_filtered)
        
        total_duration_mins = df_filtered['Duracao_Minutos'].sum()
        total_duration_fmt = formatar_duracao_humanizada(total_duration_mins)
        
        avg_duration_mins = df_filtered['Duracao_Minutos'].mean()
        avg_duration_fmt = formatar_duracao_humanizada(avg_duration_mins)
        
        # Missed Calls (Lógica: Contém 'Missed' ou 'Voicemail')
        missed_count = len(df_filtered[df_filtered['Call Result'].str.contains('Missed|Voicemail', case=False, na=False)])
        missed_rate = (missed_count / total_calls * 100) if total_calls > 0 else 0
        
        # Exibição
        col1.metric("Volume de Chamadas", total_calls)
        col2.metric("Duração Total", total_duration_fmt)
        col3.metric("Tempo Médio (TMA)", avg_duration_fmt)
        col4.metric("Taxa de Perda", f"{missed_rate:.1f}%", f"{missed_count} perdidas", delta_color="inverse")
        
        st.divider()

        # --- GRÁFICOS ---
        
        # LINHA 1
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("Evolução de Chamadas")
            # Agrupa por dia
            daily_counts = df_filtered.groupby('Data').size().reset_index(name='Chamadas')
            fig_line = px.line(daily_counts, x='Data', y='Chamadas', markers=True, template='plotly_white')
            fig_line.update_layout(xaxis_title=None)
            st.plotly_chart(fig_line, use_container_width=True)
            
        with c2:
            st.subheader("Status das Chamadas")
            fig_pie = px.donut(df_filtered, names='Call Result', hole=0.4, template='plotly_white')
            fig_pie.update_layout(showlegend=False) # Legenda oculta para limpar visual se preferir
            st.plotly_chart(fig_pie, use_container_width=True)

        # LINHA 2
        c3, c4 = st.columns(2)
        
        with c3:
            st.subheader("Top Agentes (Volume)")
            # Top 10 Agentes
            top_agents = df_filtered['Agente'].value_counts().head(10).reset_index()
            top_agents.columns = ['Agente', 'Volume']
            fig_bar = px.bar(top_agents, x='Volume', y='Agente', orientation='h', text='Volume', template='plotly_white')
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with c4:
            st.subheader("Mapa de Calor (Horário x Dia)")
            # Heatmap
            heatmap_data = df_filtered.groupby(['Dia_Semana_PT', 'Hora']).size().reset_index(name='Chamadas')
            
            dias_ordem = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
            
            fig_heat = px.density_heatmap(
                heatmap_data, 
                x='Hora', 
                y='Dia_Semana_PT', 
                z='Chamadas', 
                nbinsx=24,
                category_orders={"Dia_Semana_PT": dias_ordem},
                color_continuous_scale='Tealgrn',
                template='plotly_white'
            )
            fig_heat.update_layout(xaxis_title="Hora do Dia", yaxis_title=None)
            st.plotly_chart(fig_heat, use_container_width=True)

        # --- DADOS BRUTOS (EXPANDER) ---
        with st.expander("Ver Dados Detalhados"):
            st.dataframe(
                df_filtered[['Data_Hora', 'Direction', 'Agente', 'Call Result', 'Duracao_Formatada']]
                .rename(columns={'Duracao_Formatada': 'Duração'})
                .sort_values('Data_Hora', ascending=False),
                use_container_width=True
            )
            
else:
    # Tela Inicial (Placeholder)
    st.info("👆 Faça o upload do arquivo CSV na barra lateral ou acima para começar a análise.")
