import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime
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

# Tus enlaces maestros de Excel en Google Drive
ENLACES_EXCEL = [
    "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing",
    "https://docs.google.com/spreadsheets/d/1VrDHEb-D7oeypyYdhUpd3_tw_jggTu3K/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"
]

# ==========================================
# 2. FUNCIONES INTELIGENTES Y MOTORES
# ==========================================
@st.cache_resource
def obtener_lista_modelos():
    """Busca qué modelos están disponibles y prioriza los Flash (ultra rápidos)"""
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        modelos_seguros = [m for m in modelos if 'vision' not in m]
        flash_models = [m for m in modelos_seguros if 'flash' in m]
        return flash_models + ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest"]
    except Exception:
        return ["models/gemini-1.5-flash"]

lista_modelos_seguros = obtener_lista_modelos()

@st.cache_data(ttl=600) 
def cargar_multiples_excel(lista_urls):
    """Descarga múltiples Excel de Drive y lee TODAS las pestañas combinándolas"""
    df_maestro = pd.DataFrame()
    total_hojas = 0
    archivos_leidos = 0
    
    for url in lista_urls:
        if not url or "PEGA_AQUI" in url:
            continue
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
            
    df_maestro = df_maestro.dropna(how='all') 
    return df_maestro, total_hojas, archivos_leidos

def fetch_api(tipo, zona, api_key):
    """Llamada individual a la API para un tipo y zona específica"""
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
    """Descarga datos de la API escaneando múltiples zonas al mismo tiempo"""
    tipos = [27, 26, 24, 21, 23, 41] # CF, PMO, TP, Gravillero, Nodriza, Tolva
    zonas = list(range(1, 14)) 
    
    tareas = []
    datos_totales = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
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

with st.spinner("Sincronizando Sistema Vivo y Bases de Excel... (Esto puede tomar unos segundos la primera vez)"):
    df_api_global = extraer_datos_api_paralelo()
    df_excel_global, cant_hojas, cant_archivos = cargar_multiples_excel(ENLACES_EXCEL)

if not df_api_global.empty:
    cols_necesarias = [
        'rev_fecha_expiracion', 'ser_fecha_expiracion', 'dgmn_fecha_expiracion', 
        'nombre', 'nombre_faena', 'nombre_zona', 'horas_ult', 'nombre_es', 
        'marca_nombre', 'ultimo_estado', 'ultimo_lugar', 'control'
    ]
    for col in cols_necesarias:
        if col not in df_api_global.columns:
            df_api_global[col] = None

    df_api_global['ultimo_estado'] = df_api_global['nombre_es'].fillna(df_api_global['ultimo_estado']).fillna('OK')
    df_api_global['ultimo_estado'] = df_api_global['ultimo_estado'].replace(['', 'None', 'nan'], 'OK')
    
    df_api_global['ultimo_lugar'] = df_api_global['ultimo_lugar'].fillna('Faena')
    df_api_global['ultimo_lugar'] = df_api_global['ultimo_lugar'].replace(['', 'None', 'nan'], 'Faena')

tab_alertas, tab_equipos, tab_faenas = st.tabs([
    "🚨 Alertas del Sistema", 
    "🔍 Buscar Equipo", 
    "📍 Ver por Faena"
])

# ---------------------------------------------------------
# PESTAÑA 1: ALERTAS DEL SISTEMA
# ---------------------------------------------------------
with tab_alertas:
    st.header("🚨 Panel de Alertas Tempranas (Próximos 30 días)")
    
    if df_api_global.empty:
        st.warning("No se pudieron cargar los datos de la API para generar las alertas.")
    else:
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
            st.error(f"📄 Revisión Técnica ({len(alertas_rt)} equipos)")
            for _, row in alertas_rt.sort_values(by="Dias").iterrows():
                estado = "🔥 VENCIDO" if row['Dias'] < 0 else f"Quedan {int(row['Dias'])} días"
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']})  \n*{estado}*")
                
        with c2:
            st.warning(f"⛏️ Sernageomin ({len(alertas_sngm)} equipos)")
            for _, row in alertas_sngm.sort_values(by="Dias").iterrows():
                estado = "🔥 VENCIDO" if row['Dias'] < 0 else f"Quedan {int(row['Dias'])} días"
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']})  \n*{estado}*")
                
        with c3:
            st.info(f"💣 DGMN ({len(alertas_dgmn)} equipos)")
            for _, row in alertas_dgmn.sort_values(by="Dias").iterrows():
                estado = "🔥 VENCIDO" if row['Dias'] < 0 else f"Quedan {int(row['Dias'])} días"
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']})  \n*{estado}*")

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
                    st.caption("Tip: Intenta buscar solo el número (Ej: 1049 en vez de Quadra-1049)")
                else:
                    st.success(f"✅ Conexión Exitosa. Se cruzaron datos de {cant_archivos} Excels con el sistema en tiempo real.")
                    
                    fecha_actual = datetime.now().strftime("%d de %B de %Y")
                    contexto = f"--- DATOS EXCEL ---\n{datos_excel.to_string()}\n\n"
                    contexto += f"--- DATOS API (SISTEMA VIVO) ---\n{datos_api.to_string()}\n"
                    
                    instruccion = f"""
                    Eres un auditor estricto de bases de datos de equipos pesados. Hoy es {fecha_actual}.
                    Tu función es leer los DATOS EXCEL y los DATOS API del equipo '{equipo_a_buscar}' y rellenar estrictamente esta plantilla.
                    
                    REGLAS ABSOLUTAS: 
                    1. Tu respuesta debe ser ÚNICAMENTE el texto de la plantilla completada. NO expliques tu razonamiento.
                    2. Si un dato no existe, escribe 'No registrado'.
                    3. CRUZA Y COMPARA la ubicación del Excel contra la de la API para la auditoría.
                    
                    🚜 1. Datos Básicos del Equipo:
                    - Marca y Modelo: [Extraer]
                    - PPU: [Extraer]
                    - Año / VIN: [Extraer]
                    - Sistema de Control: [Extraer de la columna 'control' en la API o del Excel]
                    - Capacidades: [Extraer si aparece detallado en la base de datos Excel]
                    
                    📅 2. Estado de Planificación y OT:
                    - Situación real a hoy ({fecha_actual}): [Deducir si está en faena o en taller basado en fechas]
                    - Última / Próxima Actividad Programada: [Actividad, Fecha y Estatus]
                    
                    📍 3. Ubicación y Auditoría de Congruencia:
                    - Ubicación según Excel (Manual): [Extraer Faena/Ubicación de los Excels]
                    - Ubicación según Sistema (API/GPS): [Extraer 'ultimo_lugar' o 'nombre_faena' de la API]
                    - ⚠️ Alerta de Congruencia: [Compara ambas ubicaciones. Si coinciden o tienen sentido, escribe "✅ Sistemas congruentes". Si son diferentes (ej. Excel dice Chuquicamata y API dice Pelambres), escribe "❌ INCONGRUENCIA DETECTADA: El sistema vivo indica una ubicación distinta al registro manual. Recomendación: Actualizar Excel."]
                    
                    🛡️ 4. Cumplimiento y Horómetro (Datos en Vivo API):
                    - Estado Actual del Camión: [Extraer de 'ultimo_estado' de la API]
                    - Horómetro Actual: [Extraer 'horas_ult' de API] hrs
                    - Vencimiento Revisión Técnica (RT): [Extraer 'rev_fecha_expiracion' de API, limpiar formato de hora si es posible]
                    - Vencimiento Sernageomin: [Extraer 'ser_fecha_expiracion' de API, limpiar formato de hora]
                    - Vencimiento DGMN: [Extraer 'dgmn_fecha_expiracion' de API, limpiar formato de hora]
                    
                    DATOS A ANALIZAR:
                    {contexto}
                    """
                    
                    try:
                        respuesta = None
                        modelo_exitoso = ""
                        
                        for nombre_modelo in lista_modelos_seguros:
                            try:
                                modelo_prueba = genai.GenerativeModel(nombre_modelo)
                                respuesta = modelo_prueba.generate_content(
                                    instruccion,
                                    generation_config={"temperature": 0.0} 
                                )
                                modelo_exitoso = nombre_modelo
                                break 
                            except Exception:
                                continue 
                        
                        if respuesta:
                            st.markdown(respuesta.text)
                            st.caption(f"✨ Análisis generado instantáneamente por IA (Modelo: {modelo_exitoso})")
                        else:
                            st.error("Los modelos de IA están saturados. Intenta de nuevo en unos segundos.")
                            
                    except Exception as e:
                        st.error(f"Hubo un error con la IA: {e}")

# ---------------------------------------------------------
# PESTAÑA 3: VISTA POR FAENA
# ---------------------------------------------------------
with tab_faenas:
    st.header("📍 Resumen Operativo por Faena")
    
    # Diccionario de Contratos
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

    if df_api_global.empty:
        st.warning("No hay datos de API disponibles para mostrar las faenas.")
    else:
        faenas_disponibles = sorted(df_api_global['nombre_faena'].dropna().unique().tolist())
        
        faena_seleccionada = st.selectbox(
            "Seleccione una Faena para ver los equipos presentes (Datos en vivo desde el Sistema):",
            ["--- Seleccionar Faena ---"] + faenas_disponibles
        )
        
        if faena_seleccionada != "--- Seleccionar Faena ---":
            
            # --- MOSTRAR INFORMACIÓN DEL CONTRATO ---
            info_contrato = None
            for nombre_planta, datos in CONTRATOS_FAENA.items():
                if nombre_planta.lower() in faena_seleccionada.lower():
                    info_contrato = datos
                    break
            
            if info_contrato:
                st.info(f"📋 **Condiciones de Contrato: {faena_seleccionada}**")
                col1, col2, col3 = st.columns(3)
                col1.metric("Segmento de la Faena", f"Segmento {info_contrato['Segmento']}")
                col2.metric("Camiones Fábrica (Contrato)", info_contrato['Contrato'])
                col3.metric("Equipos Back Up Requeridos", info_contrato['Back Up'])
                st.divider()
            
            # --- MOSTRAR TABLA DE EQUIPOS ---
            df_faena = df_api_global[df_api_global['nombre_faena'] == faena_seleccionada].copy()
            
            st.success(f"🚜 {len(df_faena)} equipos totales reportados actualmente en **{faena_seleccionada}**")
            
            # Lógica Deductiva de Estado y Lugar
            df_faena['Estado_Deducido'] = df_faena['nombre_es'].fillna(df_faena['ultimo_estado']).fillna('OK')
            df_faena['Estado_Deducido'] = df_faena['Estado_Deducido'].replace(['', 'None', 'nan'], 'OK')
            
            df_faena['Lugar_Deducido'] = df_faena['ultimo_lugar'].fillna('Faena')
            df_faena['Lugar_Deducido'] = df_faena['Lugar_Deducido'].replace(['', 'None', 'nan'], 'Faena')
            
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
            
            # Formatear fechas a DD/MM/AAAA usando zona horaria limpia
            columnas_fechas = ['Venc. RT', 'Venc. SNGM', 'Venc. DGMN']
            for col in columnas_fechas:
                if col in df_mostrar.columns:
                    df_mostrar[col] = pd.to_datetime(df_mostrar[col], errors='coerce', utc=True).dt.strftime('%d/%m/%Y')
            
            df_mostrar = df_mostrar.fillna("-")
            
            # Dibujar la tabla finalmente
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
