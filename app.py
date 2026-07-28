import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timezone
import requests
import concurrent.futures

# ==========================================
# 1. CONFIGURACIÓN CORPORATIVA Y CLAVES
# ==========================================
st.set_page_config(page_title="Copiloto Flota Enaex", layout="wide", page_icon="🚛")

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
except Exception:
    GEMINI_API_KEY = "PEGA_TU_KEY_DE_GEMINI_AQUI_SI_NO_USAS_SECRETS"

genai.configure(api_key=GEMINI_API_KEY)

# API del Sistema de Planificación
API_KEY_DASHBOARD = "CX92wBe9wV2NLUMyFE6PzvcyqTWyBPr5"

# Tus Excels
ENLACES_EXCEL = [
    "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing",
    "https://docs.google.com/spreadsheets/d/1VrDHEb-D7oeypyYdhUpd3_tw_jggTu3K/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"
]

# Diccionario Global de Contratos
CONTRATOS_FAENA = {
    "Centinela": {"Segmento": 1, "Contrato": 13, "Back Up": 3},
    "Collahuasi": {"Segmento": 1, "Contrato": 6, "Back Up": 2},
    "Los Bronces": {"Segmento": 1, "Contrato": 7, "Back Up": 1},
    "Los Pelambres": {"Segmento": 1, "Contrato": 5, "Back Up": 2},
    "Nueva Centinela": {"Segmento": 1, "Contrato": 3, "Back Up": 1},
    "Radomiro Tomic": {"Segmento": 1, "Contrato": 5, "Back Up": 2},
    "Sierra Gorda": {"Segmento": 1, "Contrato": 6, "Back Up": 2},
    "Spence": {"Segmento": 1, "Contrato": 5, "Back Up": 1},
    "Andina": {"Segmento": 2, "Contrato": 5, "Back Up": 4},
    "Antucoya": {"Segmento": 2, "Contrato": 3, "Back Up": 1},
    "Chuquicamata": {"Segmento": 2, "Contrato": 2, "Back Up": 1},
    "Lomas Bayas": {"Segmento": 2, "Contrato": 5, "Back Up": 1},
    "Los Colorados": {"Segmento": 2, "Contrato": 3, "Back Up": 1},
    "Salvador": {"Segmento": 2, "Contrato": 4, "Back Up": 2},
    "Teniente": {"Segmento": 2, "Contrato": 1, "Back Up": 1},
    "Zaldivar": {"Segmento": 2, "Contrato": 2, "Back Up": 1},
    "Cerro Negro": {"Segmento": 3, "Contrato": 1, "Back Up": 1},
    "El Soldado": {"Segmento": 3, "Contrato": 2, "Back Up": 1},
    "Michilla": {"Segmento": 3, "Contrato": 1, "Back Up": 1},
    "Pleito": {"Segmento": 3, "Contrato": 1, "Back Up": 1},
    "Romeral": {"Segmento": 3, "Contrato": 1, "Back Up": 1},
    "Salares Norte": {"Segmento": 3, "Contrato": 1, "Back Up": 2}
}

# ==========================================
# 2. MOTOR DE IA OPTIMIZADO (FIJO)
# ==========================================
def invocar_ia_segura(instruccion, stream=False):
    """Invoca la IA usando un modelo fijo para evitar gastos de cuota buscando modelos."""
    try:
        modelo_elegido = "gemini-1.5-flash"
        modelo = genai.GenerativeModel(modelo_elegido)
        
        if stream:
            return modelo.generate_content(instruccion, stream=True), modelo_elegido
        else:
            return modelo.generate_content(instruccion), modelo_elegido
            
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str:
            raise Exception("429_QUOTA")
        raise e

# ==========================================
# 3. FUNCIONES DE EXTRACCIÓN Y FILTRADO
# ==========================================
@st.cache_data(ttl=600) 
def cargar_multiples_excel(lista_urls):
    df_maestro = pd.DataFrame()
    total_hojas = 0
    archivos_leidos = 0
    
    for url in lista_urls:
        if not url or "PEGA_AQUI" in url: continue
        try:
            if "/d/" in url:
                id_archivo = url.split('/d/')[1].split('/')[0]
                url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
                diccionario_hojas = pd.read_excel(url_descarga, sheet_name=None)
                archivos_leidos += 1
                total_hojas += len(diccionario_hojas)
                for nombre_hoja, df_hoja in diccionario_hojas.items():
                    df_hoja['Origen_Datos'] = f"Excel {archivos_leidos} ({nombre_hoja})"
                    df_maestro = pd.concat([df_maestro, df_hoja], ignore_index=True)
        except Exception:
            pass 
    return df_maestro.dropna(how='all'), total_hojas, archivos_leidos

def fetch_api(tipo, zona, api_key):
    url = f"http://40.65.224.42/api/dashboard/estado/{tipo}/{zona}?key={api_key}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return []
    return []

@st.cache_data(ttl=300)
def extraer_datos_api_paralelo():
    tipos = [27, 26, 24, 21, 23, 41] 
    zonas = list(range(1, 14)) 
    tareas = []
    datos_totales = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        for t in tipos:
            for z in zonas:
                tareas.append(executor.submit(fetch_api, t, z, API_KEY_DASHBOARD))
        for futuro in concurrent.futures.as_completed(tareas):
            resultado = futuro.result()
            if isinstance(resultado, list) and len(resultado) > 0:
                datos_totales.extend(resultado)
                
    df_api = pd.DataFrame(datos_totales)
    if not df_api.empty:
        df_api['Origen_Datos'] = "API Sistema en Tiempo Real"
    return df_api

def filtrar_por_multiples_equipos(df, texto_busqueda):
    if df.empty or not str(texto_busqueda).strip(): return df
    
    # Separar por comas y limpiar espacios
    terminos = [t.strip().lower() for t in str(texto_busqueda).split(",") if t.strip()]
    if not terminos: return pd.DataFrame()
    
    mask = pd.Series(False, index=df.index)
    for termino in terminos:
        mask = mask | df.astype(str).apply(lambda x: x.str.lower().str.contains(termino, na=False)).any(axis=1)
    
    return df[mask]

@st.cache_data(ttl=3600)
def analizar_movimientos_semana(df_excel, fecha_str):
    if df_excel.empty: return "No hay datos de planificación disponibles."
    
    mask = df_excel['Origen_Datos'].astype(str).str.contains('proceso|mov. equipos', case=False, na=False)
    df_subset = df_excel[mask].dropna(how='all', axis=1).dropna(how='all', axis=0)
    
    cols_vitales = [c for c in df_subset.columns if str(c).lower().strip() in ['equipo', 'faena', 'ubicación', 'ubicacion', 'motivo', 'status mp', 'fecha inici', 'fecha fina']]
    df_reducido = df_subset[cols_vitales] if cols_vitales else df_subset
    
    # Limitar fuertemente caracteres para cuidar la cuota gratuita
    csv_data = df_reducido.to_csv(index=False)[:4000] 
    
    instruccion = f"""
    Eres el Planificador. Hoy es {fecha_str}.
    Ignora la carta Gantt. Basa tu análisis SOLO en:
    1. 'Fecha Inici': Si cae dentro de los próximos 7 días, el camión BAJA A TALLER.
    2. 'Fecha Fina': Si cae dentro de los próximos 7 días, el camión SUBE A FAENA.
    
    Formato:
    ### 🟢 Equipos que SUBEN a Faena
    * **[Nombre]**
    ### 🔴 Equipos que BAJAN a Taller
    * **[Nombre]**
    
    DATOS:
    {csv_data}
    """
    try:
        respuesta, _ = invocar_ia_segura(instruccion, stream=False)
        return respuesta.text
    except Exception as e:
        if str(e) == "429_QUOTA": return "⚠️ **Límite de cuota IA alcanzado.** Revisa tus tablas directamente."
        return f"⚠️ IA no disponible. Error: {e}"

# ==========================================
# 4. INTERFAZ GRÁFICA PRINCIPAL
# ==========================================
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="https://www.enaex.com/wp-content/uploads/2021/04/Enaex_Logo_RGB.png" width="180" style="object-fit: contain;">
        <h1 style="margin: 0; padding: 0; font-size: 2.2rem;">🚛 Centro de Control: Flota y Auditoría</h1>
    </div>
    """, unsafe_allow_html=True
)

with st.spinner("Sincronizando Sistema Vivo y Bases de Excel..."):
    df_api_global = extraer_datos_api_paralelo()
    df_excel_global, cant_hojas, cant_archivos = cargar_multiples_excel(ENLACES_EXCEL)

if not df_api_global.empty:
    cols_necesarias = [
        'rev_fecha_expiracion', 'ser_fecha_expiracion', 'dgmn_fecha_expiracion', 
        'nombre', 'nombre_faena', 'horas_ult', 'nombre_es', 
        'marca_nombre', 'ultimo_estado', 'ultimo_lugar', 'control'
    ]
    for col in cols_necesarias:
        if col not in df_api_global.columns:
            df_api_global[col] = None

    df_api_global['Estado_Deducido'] = df_api_global['nombre_es'].fillna(df_api_global['ultimo_estado']).fillna('OK')
    df_api_global['Estado_Deducido'] = df_api_global['Estado_Deducido'].replace(['', 'None', 'nan'], 'OK')
    
    df_api_global['Lugar_Deducido'] = df_api_global['ultimo_lugar'].fillna('Faena')
    df_api_global['Lugar_Deducido'] = df_api_global['Lugar_Deducido'].replace(['', 'None', 'nan'], 'Faena')

tab_alertas, tab_equipos, tab_faenas = st.tabs([
    "🚨 Alertas del Sistema", 
    "🔍 Buscar Equipos", 
    "📍 Ver por Faena"
])

# ---------------------------------------------------------
# PESTAÑA 1: ALERTAS DEL SISTEMA
# ---------------------------------------------------------
with tab_alertas:
    st.header("🚨 Panel de Alertas Tempranas y Contratos")
    
    if df_api_global.empty:
        st.warning("No se pudieron cargar los datos de la API.")
    else:
        st.subheader("⚖️ Estado de Cumplimiento de Contratos (Camiones Fábrica)")
        alertas_contrato_rojas = []
        alertas_contrato_amarillas = []
        alertas_correctivas = []
        
        for faena, info in CONTRATOS_FAENA.items():
            df_faena_alerta = df_api_global[df_api_global['nombre_faena'].astype(str).str.strip().str.lower() == faena.lower()]
            if df_faena_alerta.empty: continue
                
            df_fabrica = df_faena_alerta[df_faena_alerta['nombre'].astype(str).str.contains('AUGER|QUADRA', case=False, na=False)]
            mask_lugar_faena = df_fabrica['Lugar_Deducido'].str.lower() == 'faena'
            mask_correctivo = df_fabrica['Estado_Deducido'].str.lower().str.contains('correctivo', na=False)
            mask_catastrofico = df_fabrica['Estado_Deducido'].str.lower().str.contains('catastr', na=False)
            
            equipos_en_correctivo = df_fabrica[mask_lugar_faena & mask_correctivo]['nombre'].tolist()
            if equipos_en_correctivo:
                alertas_correctivas.append({'faena': faena, 'equipos': equipos_en_correctivo})
            
            mask_operativos = mask_lugar_faena & ~mask_catastrofico
            df_operativos = df_fabrica[mask_operativos]
            df_fuera = df_fabrica[~mask_operativos] 
            
            cant_operativos = len(df_operativos)
            requeridos = info['Contrato']
            
            if cant_operativos < requeridos:
                alertas_contrato_rojas.append({'faena': faena, 'operativos': cant_operativos, 'requeridos': requeridos, 'faltan': requeridos - cant_operativos, 'nombres_op': df_operativos['nombre'].tolist(), 'nombres_fuera': df_fuera['nombre'].tolist()})
            elif cant_operativos == requeridos:
                alertas_contrato_amarillas.append({'faena': faena, 'operativos': cant_operativos, 'requeridos': requeridos, 'nombres_op': df_operativos['nombre'].tolist(), 'nombres_fuera': df_fuera['nombre'].tolist()})
                
        if alertas_contrato_rojas or alertas_contrato_amarillas or alertas_correctivas:
            todas_alertas = []
            for a in alertas_contrato_rojas: todas_alertas.append({"tipo": "error", "faena": a['faena'], "faltan": a['faltan'], "op": a['operativos'], "req": a['requeridos'], "nombres_op": a['nombres_op'], "nombres_fuera": a['nombres_fuera']})
            for a in alertas_contrato_amarillas: todas_alertas.append({"tipo": "warning", "faena": a['faena'], "op": a['operativos'], "req": a['requeridos'], "nombres_op": a['nombres_op'], "nombres_fuera": a['nombres_fuera']})
            for a in alertas_correctivas: todas_alertas.append({"tipo": "info", "faena": a['faena'], "equipos": a['equipos']})
            
            columnas_grid = st.columns(6)
            for i, alerta in enumerate(todas_alertas):
                with columnas_grid[i % 6]:
                    if alerta["tipo"] == "error":
                        st.error(f"**{alerta['faena']}**\n\n🔴 Faltan: {alerta['faltan']}\n\n*{alerta['op']} de {alerta['req']}*")
                        with st.expander("Ver detalle"):
                            st.caption("**OK:** " + (", ".join(alerta['nombres_op']) if alerta['nombres_op'] else "Ninguno"))
                            st.caption("**Falta:** " + (", ".join(alerta['nombres_fuera']) if alerta['nombres_fuera'] else "Ninguno"))
                    elif alerta["tipo"] == "warning":
                        st.warning(f"**{alerta['faena']}**\n\n🟡 Al límite\n\n*{alerta['op']} de {alerta['req']}*")
                        with st.expander("Ver detalle"):
                            st.caption("**OK:** " + (", ".join(alerta['nombres_op']) if alerta['nombres_op'] else "Ninguno"))
                            st.caption("**Falta:** " + (", ".join(alerta['nombres_fuera']) if alerta['nombres_fuera'] else "Ninguno"))
                    elif alerta["tipo"] == "info":
                        st.info(f"**{alerta['faena']}**\n\n🔧 En Taller:\n\n*{len(alerta['equipos'])} equipo(s)*")
                        with st.expander("Ver detalle"):
                            for eq in alerta['equipos']: st.caption(f"- {eq}")
        else:
            st.success("✅ Excelente. Todos los contratos tienen los equipos operativos requeridos.")
            
        st.divider()
        st.subheader("📅 Certificaciones por Vencer (Próximos 30 días)")
        hoy = pd.Timestamp(datetime.now(timezone.utc))
        dias_rt = (pd.to_datetime(df_api_global['rev_fecha_expiracion'], errors='coerce', utc=True) - hoy).dt.days
        dias_sngm = (pd.to_datetime(df_api_global['ser_fecha_expiracion'], errors='coerce', utc=True) - hoy).dt.days
        dias_dgmn = (pd.to_datetime(df_api_global['dgmn_fecha_expiracion'], errors='coerce', utc=True) - hoy).dt.days
        
        c1, c2, c3 = st.columns(3)
        with c1:
            alertas_rt = df_api_global[dias_rt <= 30][['nombre', 'nombre_faena']].copy()
            alertas_rt['Dias'] = dias_rt[dias_rt <= 30]
            st.error(f"📄 Revisión Técnica ({len(alertas_rt)})")
            for _, row in alertas_rt.sort_values(by="Dias").iterrows():
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{'🔥 VENCIDO' if row['Dias'] < 0 else f'Quedan {int(row['Dias'])} días'}*")
        with c2:
            alertas_sngm = df_api_global[dias_sngm <= 30][['nombre', 'nombre_faena']].copy()
            alertas_sngm['Dias'] = dias_sngm[dias_sngm <= 30]
            st.warning(f"⛏️ Sernageomin ({len(alertas_sngm)})")
            for _, row in alertas_sngm.sort_values(by="Dias").iterrows():
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{'🔥 VENCIDO' if row['Dias'] < 0 else f'Quedan {int(row['Dias'])} días'}*")
        with c3:
            alertas_dgmn = df_api_global[dias_dgmn <= 30][['nombre', 'nombre_faena']].copy()
            alertas_dgmn['Dias'] = dias_dgmn[dias_dgmn <= 30]
            st.info(f"💣 DGMN ({len(alertas_dgmn)})")
            for _, row in alertas_dgmn.sort_values(by="Dias").iterrows():
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{'🔥 VENCIDO' if row['Dias'] < 0 else f'Quedan {int(row['Dias'])} días'}*")

# ---------------------------------------------------------
# PESTAÑA 2: BÚSQUEDA Y AUDITORÍA DE EQUIPOS
# ---------------------------------------------------------
with tab_equipos:
    with st.expander("Ver Resumen de Subidas y Bajadas (Carta Gantt)"):
        st.info("💡 Haz clic en el botón para leer la planificación de esta semana. Así evitamos saturar la IA.")
        if st.button("🤖 Analizar Semana con IA"):
            with st.spinner("Analizando fechas..."):
                st.markdown(analizar_movimientos_semana(df_excel_global, datetime.now().strftime("%d de %B de %Y")))
            
    st.divider()
    
    st.header("🔍 Búsqueda Múltiple de Equipos")
    equipo_a_buscar = st.text_input("Ingresa uno o varios equipos separados por coma (Ej: Quadra-1049, Auger-165, Quadra-1030):")

    if st.button("Consultar Base de Datos y Auditar"):
        if not equipo_a_buscar:
            st.warning("⚠️ Escribe al menos un equipo para buscar.")
        else:
            # 1. FILTRADO DE DATOS (MÚLTIPLES EQUIPOS)
            datos_excel = filtrar_por_multiples_equipos(df_excel_global, equipo_a_buscar)
            
            datos_api = pd.DataFrame()
            if not df_api_global.empty and 'nombre' in df_api_global.columns:
                datos_api = filtrar_por_multiples_equipos(df_api_global, equipo_a_buscar)

            if datos_excel.empty and datos_api.empty:
                st.error(f"No se encontró ninguna coincidencia para: {equipo_a_buscar}")
            else:
                # 2. REDUCCIÓN DE COLUMNAS
                cols_excel = [c for c in datos_excel.columns if any(p in str(c).lower() for p in ['equipo', 'estatus', 'status mp', 'estado', 'fecha', 'faena', 'ubicación', 'comentario', 'planificada', 'real', 'entrega', 'inici', 'fina'])]
                datos_excel_reducido = datos_excel[cols_excel] if cols_excel else datos_excel
                cols_api = [c for c in datos_api.columns if c in ['nombre', 'marca_nombre', 'Lugar_Deducido', 'nombre_faena', 'Estado_Deducido', 'horas_ult']]
                datos_api_reducido = datos_api[cols_api] if not datos_api.empty else datos_api

                # 3. MOSTRAR DATOS CRUDOS SIEMPRE (SEGURO CONTRA FALLAS DE IA)
                st.markdown("### 📑 Datos Crudos Obtenidos")
                st.caption("Esta información se extrae directamente de los sistemas sin importar si la IA está disponible.")
                
                col_api, col_excel = st.columns(2)
                with col_api:
                    st.success("📡 Datos del Sistema (API Vivo)")
                    if not datos_api_reducido.empty:
                        st.dataframe(datos_api_reducido, hide_index=True)
                    else:
                        st.write("No hay datos en el sistema para este equipo.")
                
                with col_excel:
                    st.info("📊 Datos de Planificación (Excel)")
                    if not datos_excel_reducido.empty:
                        st.dataframe(datos_excel_reducido, hide_index=True)
                    else:
                        st.write("No hay datos de planificación para este equipo.")
                        
                st.divider()

                # 4. INTENTO DE ANÁLISIS CON IA
                texto_excel = datos_excel_reducido.to_string()[:2000] # Super reducido para cuidar cuota
                texto_api = datos_api_reducido.to_string()[:1000]
                
                instruccion = f"""
                Eres un auditor experto. Analiza estos equipos: '{equipo_a_buscar}'.
                Compara los datos del Excel vs API. Resalta discrepancias de ubicación, atrasos en fechas de entrega, y comenta los trabajos recientes del taller. Se breve y directo.
                
                EXCEL: {texto_excel}
                API: {texto_api}
                """
                
                st.markdown("### 🤖 Análisis de Inteligencia Artificial")
                try:
                    respuesta_stream, modelo = invocar_ia_segura(instruccion, stream=True)
                    st.write_stream((chunk.text for chunk in respuesta_stream if chunk.text))
                except Exception as e:
                    if str(e) == "429_QUOTA":
                        st.warning("⚠️ **Límite Diario/Minuto de IA alcanzado (Cuota Gratuita de Google).** Pero no te preocupes, puedes seguir utilizando las tablas de datos crudos de arriba para hacer tu gestión manual.")
                    else:
                        st.error(f"Error en IA: {e}. Revisa las tablas crudas superiores.")

# ---------------------------------------------------------
# PESTAÑA 3: VISTA POR FAENA
# ---------------------------------------------------------
with tab_faenas:
    st.header("📍 Resumen Operativo por Faena")
    
    if df_api_global.empty:
        st.warning("No hay datos de API disponibles.")
    else:
        faenas_disponibles = sorted(df_api_global['nombre_faena'].dropna().unique().tolist())
        faena_seleccionada = st.selectbox("Seleccione una Faena:", ["--- Seleccionar Faena ---"] + faenas_disponibles)
        
        if faena_seleccionada != "--- Seleccionar Faena ---":
            info_contrato = next((datos for nombre, datos in CONTRATOS_FAENA.items() if nombre.lower() == faena_seleccionada.lower()), None)
            
            if info_contrato:
                st.info(f"📋 **Condiciones de Contrato: {faena_seleccionada}**")
                col1, col2, col3 = st.columns(3)
                col1.metric("Segmento de la Faena", f"Segmento {info_contrato['Segmento']}")
                col2.metric("Camiones Fábrica (Contrato)", info_contrato['Contrato'])
                col3.metric("Equipos Back Up Requeridos", info_contrato['Back Up'])
                st.divider()

            df_faena = df_api_global[df_api_global['nombre_faena'] == faena_seleccionada].copy()
            st.success(f"🚛 {len(df_faena)} equipos reportados actualmente en **{faena_seleccionada}**")
            
            cols_vista = {
                'nombre': 'Equipo', 'marca_nombre': 'Marca', 'Lugar_Deducido': 'Lugar/Ubicación',
                'horas_ult': 'Horómetro (hrs)', 'Estado_Deducido': 'Estado Actual',
                'rev_fecha_expiracion': 'Venc. RT', 'ser_fecha_expiracion': 'Venc. SNGM', 'dgmn_fecha_expiracion': 'Venc. DGMN'
            }
            
            cols_existentes = [c for c in cols_vista.keys() if c in df_faena.columns]
            df_mostrar = df_faena[cols_existentes].rename(columns=cols_vista)
            
            for col in ['Venc. RT', 'Venc. SNGM', 'Venc. DGMN']:
                if col in df_mostrar.columns:
                    df_mostrar[col] = pd.to_datetime(df_mostrar[col], errors='coerce').dt.strftime('%d/%m/%Y')
            
            df_mostrar = df_mostrar.fillna("-")
            
            st.dataframe(
                df_mostrar,
                use_container_width=False, 
                hide_index=True,
                column_config={
                    "Equipo": st.column_config.TextColumn("Equipo", alignment="left"),
                    "Marca": st.column_config.TextColumn("Marca", alignment="center"),
                    "Lugar/Ubicación": st.column_config.TextColumn("Lugar/Ubicación", alignment="center"),
                    "Horómetro (hrs)": st.column_config.NumberColumn("Horómetro (hrs)", alignment="center"),
                    "Estado Actual": st.column_config.TextColumn("Estado Actual", alignment="center"),
                    "Venc. RT": st.column_config.TextColumn("Venc. RT", alignment="center"),
                    "Venc. SNGM": st.column_config.TextColumn("Venc. SNGM", alignment="center"),
                    "Venc. DGMN": st.column_config.TextColumn("Venc. DGMN", alignment="center"),
                }
            )
