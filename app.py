import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timezone
import requests
import concurrent.futures

# ==========================================
# 1. CONFIGURACIÓN DE TUS ENLACES Y CLAVES
# ==========================================
st.set_page_config(page_title="Copiloto de Equipos", layout="wide", page_icon="🚜")

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
except Exception:
    GEMINI_API_KEY = "PEGA_TU_KEY_DE_GEMINI_AQUI_SI_NO_USAS_SECRETS"

API_KEY_DASHBOARD = "CX92wBe9wV2NLUMyFE6PzvcyqTWyBPr5"

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
# 2. FUNCIONES INTELIGENTES Y MOTORES
# ==========================================
@st.cache_resource
def obtener_lista_modelos():
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        modelos_seguros = [m for m in modelos if 'vision' not in m]
        return [m for m in modelos_seguros if 'flash' in m] + ["models/gemini-1.5-flash"]
    except Exception:
        return ["models/gemini-1.5-flash"]

lista_modelos_seguros = obtener_lista_modelos()

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

def filtrar_por_equipo(df, nombre_equipo):
    if df.empty: return df
    termino = str(nombre_equipo).strip().lower()
    mask = df.astype(str).apply(lambda x: x.str.lower().str.contains(termino, na=False)).any(axis=1)
    return df[mask]

# ==========================================
# 3. INTERFAZ Y PRECARGA DE DATOS
# ==========================================
st.title("🚜 Centro de Control: Flota y Auditoría")

with st.spinner("Sincronizando Sistema Vivo y Bases de Excel... (Esto toma unos segundos la primera vez)"):
    df_api_global = extraer_datos_api_paralelo()
    df_excel_global, cant_hojas, cant_archivos = cargar_multiples_excel(ENLACES_EXCEL)

# Limpieza y deducción global para que aplique a TODA la app
if not df_api_global.empty:
    cols_necesarias = [
        'rev_fecha_expiracion', 'ser_fecha_expiracion', 'dgmn_fecha_expiracion', 
        'nombre', 'nombre_faena', 'nombre_zona', 'horas_ult', 'nombre_es', 
        'marca_nombre', 'ultimo_estado', 'ultimo_lugar', 'control'
    ]
    for col in cols_necesarias:
        if col not in df_api_global.columns:
            df_api_global[col] = None

    # Lógica de Deducción (Si viene nulo, el camión está en "Faena" y estado "OK")
    df_api_global['Estado_Deducido'] = df_api_global['nombre_es'].fillna(df_api_global['ultimo_estado']).fillna('OK')
    df_api_global['Estado_Deducido'] = df_api_global['Estado_Deducido'].replace(['', 'None', 'nan'], 'OK')
    
    df_api_global['Lugar_Deducido'] = df_api_global['ultimo_lugar'].fillna('Faena')
    df_api_global['Lugar_Deducido'] = df_api_global['Lugar_Deducido'].replace(['', 'None', 'nan'], 'Faena')

tab_alertas, tab_equipos, tab_faenas = st.tabs([
    "🚨 Alertas del Sistema", 
    "🔍 Buscar Equipo", 
    "📍 Ver por Faena"
])

# ---------------------------------------------------------
# PESTAÑA 1: ALERTAS DEL SISTEMA
# ---------------------------------------------------------
with tab_alertas:
    st.header("🚨 Panel de Alertas Tempranas y Contratos")
    
    if df_api_global.empty:
        st.warning("No se pudieron cargar los datos de la API para generar las alertas.")
    else:
        st.subheader("⚖️ Estado de Cumplimiento de Contratos (Camiones Fábrica)")
        alertas_contrato_rojas = []
        alertas_contrato_amarillas = []
        alertas_correctivas = []
        
        for faena, info in CONTRATOS_FAENA.items():
            df_faena_alerta = df_api_global[df_api_global['nombre_faena'].astype(str).str.strip().str.lower() == faena.lower()]
            if df_faena_alerta.empty:
                continue
                
            # Filtrar solo Auger y Quadra
            df_fabrica = df_faena_alerta[df_faena_alerta['nombre'].astype(str).str.contains('AUGER|QUADRA', case=False, na=False)]
            
            # Evaluar operativos: Lugar debe ser 'Faena' y NO debe estar en 'Catastrofico'
            mask_lugar = df_fabrica['Lugar_Deducido'].str.lower() == 'faena'
            mask_catastrofico = df_fabrica['Estado_Deducido'].str.lower().str.contains('catastr', na=False)
            mask_operativos = mask_lugar & ~mask_catastrofico
            
            # Clasificamos qué equipos están OK y cuáles están Fuera (para los detalles)
            df_operativos = df_fabrica[mask_operativos]
            df_fuera = df_fabrica[~mask_operativos]
            
            nombres_operativos = df_operativos['nombre'].tolist()
            nombres_fuera = df_fuera['nombre'].tolist()
            
            cant_operativos = len(df_operativos)
            requeridos = info['Contrato']
            
            # Detectar equipos en 'Correctivo' en Faena para la alerta de atención
            mask_correctivo = mask_lugar & df_fabrica['Estado_Deducido'].str.lower().str.contains('correctivo', na=False)
            equipos_en_correctivo = df_fabrica[mask_correctivo]['nombre'].tolist()
            if equipos_en_correctivo:
                alertas_correctivas.append({
                    'faena': faena, 'equipos': equipos_en_correctivo
                })
            
            if cant_operativos < requeridos:
                alertas_contrato_rojas.append({
                    'faena': faena, 'operativos': cant_operativos, 'requeridos': requeridos, 'faltan': requeridos - cant_operativos,
                    'nombres_op': nombres_operativos, 'nombres_fuera': nombres_fuera
                })
            elif cant_operativos == requeridos:
                alertas_contrato_amarillas.append({
                    'faena': faena, 'operativos': cant_operativos, 'requeridos': requeridos,
                    'nombres_op': nombres_operativos, 'nombres_fuera': nombres_fuera
                })
                
        if alertas_contrato_rojas or alertas_contrato_amarillas or alertas_correctivas:
            todas_alertas = []
            for a in alertas_contrato_rojas:
                todas_alertas.append({"tipo": "error", "faena": a['faena'], "faltan": a['faltan'], "op": a['operativos'], "req": a['requeridos'], "nombres_op": a['nombres_op'], "nombres_fuera": a['nombres_fuera']})
            for a in alertas_contrato_amarillas:
                todas_alertas.append({"tipo": "warning", "faena": a['faena'], "op": a['operativos'], "req": a['requeridos'], "nombres_op": a['nombres_op'], "nombres_fuera": a['nombres_fuera']})
            for a in alertas_correctivas:
                todas_alertas.append({"tipo": "info", "faena": a['faena'], "equipos": a['equipos']})
            
            # Crear cuadrícula de 6 columnas (Para hacerlos más pequeños y tipo dashboard)
            columnas_grid = st.columns(6)
            for i, alerta in enumerate(todas_alertas):
                with columnas_grid[i % 6]:
                    if alerta["tipo"] == "error":
                        st.error(f"**{alerta['faena']}**\n\n🔴 Faltan: {alerta['faltan']}\n\n*{alerta['op']}/{alerta['req']} Op.*")
                        with st.expander("Ver detalle"):
                            st.markdown("✅ **OK:**")
                            st.caption(", ".join(alerta['nombres_op']) if alerta['nombres_op'] else "Ninguno")
                            st.markdown("❌ **Fuera:**")
                            st.caption(", ".join(alerta['nombres_fuera']) if alerta['nombres_fuera'] else "Ninguno")
                            
                    elif alerta["tipo"] == "warning":
                        st.warning(f"**{alerta['faena']}**\n\n🟡 Al límite\n\n*{alerta['op']}/{alerta['req']} Op.*")
                        with st.expander("Ver detalle"):
                            st.markdown("✅ **OK:**")
                            st.caption(", ".join(alerta['nombres_op']) if alerta['nombres_op'] else "Ninguno")
                            st.markdown("⚠️ **Fuera/Taller:**")
                            st.caption(", ".join(alerta['nombres_fuera']) if alerta['nombres_fuera'] else "Ninguno")
                            
                    elif alerta["tipo"] == "info":
                        st.info(f"**{alerta['faena']}**\n\n🔧 En Taller:\n\n*Avisos: {len(alerta['equipos'])}*")
                        with st.expander("Ver detalle"):
                            st.markdown("🔧 **Correctivo(s):**")
                            for eq in alerta['equipos']:
                                st.caption(f"- {eq}")
        else:
            st.success("✅ Excelente. Todos los contratos tienen los equipos operativos requeridos y no hay equipos en correctivo.")
            
        st.divider()

        st.subheader("📅 Certificaciones por Vencer (Próximos 30 días)")
        hoy = pd.Timestamp.utcnow().normalize()
        
        dias_rt = (pd.to_datetime(df_api_global['rev_fecha_expiracion'], errors='coerce', utc=True).dt.normalize() - hoy).dt.days
        dias_sngm = (pd.to_datetime(df_api_global['ser_fecha_expiracion'], errors='coerce', utc=True).dt.normalize() - hoy).dt.days
        dias_dgmn = (pd.to_datetime(df_api_global['dgmn_fecha_expiracion'], errors='coerce', utc=True).dt.normalize() - hoy).dt.days
        
        alertas_rt = df_api_global[dias_rt <= 30][['nombre', 'nombre_faena']].copy()
        alertas_rt['Dias'] = dias_rt[dias_rt <= 30]
        
        alertas_sngm = df_api_global[dias_sngm <= 30][['nombre', 'nombre_faena']].copy()
        alertas_sngm['Dias'] = dias_sngm[dias_sngm <= 30]
        
        alertas_dgmn = df_api_global[dias_dgmn <= 30][['nombre', 'nombre_faena']].copy()
        alertas_dgmn['Dias'] = dias_dgmn[dias_dgmn <= 30]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.error(f"📄 Revisión Técnica ({len(alertas_rt)})")
            for _, row in alertas_rt.sort_values(by="Dias").iterrows():
                estado = "🔥 VENCIDO" if row['Dias'] < 0 else f"Quedan {int(row['Dias'])} días"
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{estado}*")
        with c2:
            st.warning(f"⛏️ Sernageomin ({len(alertas_sngm)})")
            for _, row in alertas_sngm.sort_values(by="Dias").iterrows():
                estado = "🔥 VENCIDO" if row['Dias'] < 0 else f"Quedan {int(row['Dias'])} días"
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{estado}*")
        with c3:
            st.info(f"💣 DGMN ({len(alertas_dgmn)})")
            for _, row in alertas_dgmn.sort_values(by="Dias").iterrows():
                estado = "🔥 VENCIDO" if row['Dias'] < 0 else f"Quedan {int(row['Dias'])} días"
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{estado}*")

# ---------------------------------------------------------
# PESTAÑA 2: BÚSQUEDA Y AUDITORÍA DE EQUIPOS
# ---------------------------------------------------------
with tab_equipos:
    st.header("🔍 Búsqueda y Auditoría Individual")
    equipo_a_buscar = st.text_input("Ingresa el nombre o código del equipo (Ej: Quadra-1049, Auger-165):")

    if st.button("Consultar y Auditar Equipo"):
        if not equipo_a_buscar:
            st.warning("⚠️ Por favor, escribe un equipo para buscar.")
        else:
            with st.spinner(f'Analizando historial con IA para {equipo_a_buscar}...'):
                datos_excel = filtrar_por_equipo(df_excel_global, equipo_a_buscar)
                datos_api = pd.DataFrame()
                
                if not df_api_global.empty and 'nombre' in df_api_global.columns:
                    mask_api = df_api_global['nombre'].astype(str).str.lower().str.contains(equipo_a_buscar.lower(), na=False)
                    datos_api = df_api_global[mask_api]

                if datos_excel.empty and datos_api.empty:
                    st.error(f"No se encontró ninguna coincidencia exacta para: {equipo_a_buscar}")
                else:
                    st.success(f"✅ Conexión Exitosa. Se cruzaron datos históricos con el GPS/Sistema en vivo.")
                    fecha_actual = datetime.now().strftime("%d de %B de %Y")
                    contexto = f"--- DATOS EXCEL ---\n{datos_excel.to_string()}\n\n--- DATOS API ---\n{datos_api.to_string()}\n"
                    
                    instruccion = f"""
                    Eres un auditor estricto de bases de datos de equipos pesados. Hoy es {fecha_actual}.
                    Tu función es leer los DATOS EXCEL y los DATOS API del equipo '{equipo_a_buscar}' y rellenar estrictamente esta plantilla.
                    
                    🚜 1. Datos Básicos del Equipo:
                    - Marca y Modelo: [Extraer]
                    - PPU: [Extraer]
                    - Año / VIN: [Extraer]
                    - Sistema de Control: [Extraer 'control' de la API o Excel]
                    - Capacidades: [Extraer toneladas/litros si aparece detallado en Excel]
                    
                    🛠️ 2. Actualización de Taller y Planificación (Reunión Diaria):
                    - Analiza los registros del Excel. Presta extrema atención a la columna "estatus MP" y "estado de equipos" (o similares).
                    - Estatus Taller: [Si en estatus MP dice "En proceso", indica que está 'En Taller'. Si dice "Listo", indica que ya fue 'Entregado a Faena'].
                    - Trabajos / Comentarios ("Estado de equipos"): [Copia los últimos comentarios o trabajos realizados exactamente como aparecen en la columna 'estado de equipos'. Si dice Listo, menciona qué fue lo último que se le hizo.]
                    - ⏱️ Análisis de Desviación de Fechas: [Busca y compara las fechas planificadas con las fechas de entrega reales en el Excel. Si la fecha real es posterior a la planificada, escribe "⚠️ DESVIACIÓN DETECTADA: Se planificó para el [Fecha] pero se entregó/entregará el [Fecha]". Si va a tiempo, escribe "✅ Entregado/Avanzando según lo planificado". Si no hay fechas comparables, omite este punto o pon N/A.]
                    
                    📍 3. Ubicación y Auditoría de Congruencia:
                    - Ubicación según Excel (Manual): [Extraer Faena/Ubicación]
                    - Ubicación según Sistema Vivo (API/GPS): [Extraer 'Lugar_Deducido' o 'nombre_faena' de la API]
                    - ⚠️ Alerta de Congruencia: [Compara ambas ubicaciones. Si coinciden o tienen sentido, escribe "✅ Sistemas congruentes". Si son diferentes escribe "❌ INCONGRUENCIA DETECTADA: El sistema vivo indica una ubicación distinta al registro manual."]
                    
                    🛡️ 4. Cumplimiento y Horómetro (En Vivo):
                    - Estado Actual: [Extraer de 'Estado_Deducido' de la API]
                    - Horómetro Actual: [Extraer 'horas_ult' de API] hrs
                    - Vencimiento RT: [Extraer 'rev_fecha_expiracion' de API, limpiar hora]
                    - Vencimiento Sernageomin: [Extraer 'ser_fecha_expiracion' de API, limpiar hora]
                    - Vencimiento DGMN: [Extraer 'dgmn_fecha_expiracion' de API, limpiar hora]
                    
                    DATOS A ANALIZAR:
                    {contexto}
                    """
                    
                    try:
                        respuesta, modelo_exitoso = None, ""
                        for nombre_modelo in lista_modelos_seguros:
                            try:
                                respuesta = genai.GenerativeModel(nombre_modelo).generate_content(instruccion, generation_config={"temperature": 0.0})
                                modelo_exitoso = nombre_modelo
                                break 
                            except Exception: continue 
                        
                        if respuesta:
                            st.markdown(respuesta.text)
                            st.caption(f"✨ Análisis generado por IA (Modelo: {modelo_exitoso})")
                        else:
                            st.error("Servidores de IA ocupados. Intenta de nuevo.")
                    except Exception as e:
                        st.error(f"Error IA: {e}")

# ---------------------------------------------------------
# PESTAÑA 3: VISTA POR FAENA
# ---------------------------------------------------------
with tab_faenas:
    st.header("📍 Resumen Operativo por Faena")
    
    if df_api_global.empty:
        st.warning("No hay datos de API disponibles.")
    else:
        faenas_disponibles = sorted(df_api_global['nombre_faena'].dropna().unique().tolist())
        faena_seleccionada = st.selectbox(
            "Seleccione una Faena para ver los equipos presentes (Datos en vivo desde el Sistema):",
            ["--- Seleccionar Faena ---"] + faenas_disponibles
        )
        
        if faena_seleccionada != "--- Seleccionar Faena ---":
            
            # --- PANEL DE CONTRATO (MÉTRICAS) ---
            info_contrato = None
            for nombre_planta, datos in CONTRATOS_FAENA.items():
                if nombre_planta.lower() == faena_seleccionada.lower():
                    info_contrato = datos
                    break
            
            if info_contrato:
                st.info(f"📋 **Condiciones de Contrato: {faena_seleccionada}**")
                col1, col2, col3 = st.columns(3)
                col1.metric("Segmento de la Faena", f"Segmento {info_contrato['Segmento']}")
                col2.metric("Camiones Fábrica (Contrato)", info_contrato['Contrato'])
                col3.metric("Equipos Back Up Requeridos", info_contrato['Back Up'])
                st.divider()
            # ------------------------------------

            df_faena = df_api_global[df_api_global['nombre_faena'] == faena_seleccionada].copy()
            st.success(f"🚜 {len(df_faena)} equipos reportados actualmente en **{faena_seleccionada}**")
            
            # Limpiar y seleccionar columnas útiles para mostrar
            cols_vista = {
                'nombre': 'Equipo',
                'marca_nombre': 'Marca',
                'Lugar_Deducido': 'Lugar/Ubicación',
                'horas_ult': 'Horómetro (hrs)',
                'Estado_Deducido': 'Estado Actual',
                'rev_fecha_expiracion': 'Venc. RT',
                'ser_fecha_expiracion': 'Venc. SNGM',
                'dgmn_fecha_expiracion': 'Venc. DGMN'
            }
            
            cols_existentes = [c for c in cols_vista.keys() if c in df_faena.columns]
            df_mostrar = df_faena[cols_existentes].rename(columns=cols_vista)
            
            # Formatear fechas a DD/MM/AAAA
            columnas_fechas = ['Venc. RT', 'Venc. SNGM', 'Venc. DGMN']
            for col in columnas_fechas:
                if col in df_mostrar.columns:
                    df_mostrar[col] = pd.to_datetime(df_mostrar[col], errors='coerce').dt.strftime('%d/%m/%Y')
            
            df_mostrar = df_mostrar.fillna("-")
            
            # ==========================================
            # FORMATO VISUAL: Configuración de Columnas Nativa
            # ==========================================
            st.dataframe(
                df_mostrar,
                use_container_width=False,  # Para que se ajuste al texto
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
