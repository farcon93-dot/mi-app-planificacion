import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import requests
import concurrent.futures

# ==========================================
# 1. CONFIGURACIÓN DE TUS ENLACES Y CLAVES
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
API_KEY_DASHBOARD = "CX92wBe9wV2NLUMyFE6PzvcyqTWyBPr5"

# TUS LINKS DE GOOGLE DRIVE (Añade más aquí si lo necesitas en el futuro)
ENLACES_EXCEL = [
    "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing",
    "https://docs.google.com/spreadsheets/d/1VrDHEb-D7oeypyYdhUpd3_tw_jggTu3K/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"
]

st.set_page_config(page_title="Copiloto de Equipos", layout="centered", page_icon="🚜")

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
        # Forzar el uso de modelos Flash para velocidad
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
    
    for i, url in enumerate(lista_urls):
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
            pass # Ignoramos errores silenciosamente para no interrumpir
            
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

@st.cache_data(ttl=120) # Se actualiza cada 2 minutos
def extraer_datos_api_paralelo():
    """Descarga datos de la API escaneando múltiples zonas al mismo tiempo"""
    tipos = [27, 26, 24, 21, 23, 41] # Tipos comunes según doc: CF, PMO, TP, Gravillero, Nodriza, Tolva
    zonas = list(range(1, 14)) # Zonas 1 a 13 según documentación
    
    tareas = []
    datos_totales = []
    
    # Usamos ThreadPoolExecutor para hacer decenas de consultas en 1 segundo
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
# 3. INTERFAZ DE LA APLICACIÓN (UI)
# ==========================================
st.title("🚜 Copiloto de Equipos")
st.markdown("Consulta el estado, ubicación, historial y **certificaciones en tiempo real**.")

equipo_a_buscar = st.text_input("🔍 Ingresa el nombre o código del equipo (Ej: Quadra-1049, Auger-165):")

if st.button("Consultar Estado Actual"):
    if not equipo_a_buscar:
        st.warning("⚠️ Por favor, escribe un equipo para buscar.")
    else:
        with st.spinner(f'Consultando Excel de Drive y API en tiempo real buscando a {equipo_a_buscar}...'):
            
            # 1. Leer Excels
            df_excel, cant_hojas, cant_archivos = cargar_multiples_excel(ENLACES_EXCEL)
            datos_excel = filtrar_por_equipo(df_excel, equipo_a_buscar)
            
            # 2. Leer API
            df_api = extraer_datos_api_paralelo()
            datos_api = pd.DataFrame()
            if not df_api.empty and 'nombre' in df_api.columns:
                # Buscamos coincidencias en la API
                mask_api = df_api['nombre'].astype(str).str.lower().str.contains(equipo_a_buscar.lower(), na=False)
                datos_api = df_api[mask_api]

            # Unir resultados
            if datos_excel.empty and datos_api.empty:
                st.error(f"No se encontró ninguna coincidencia exacta para: {equipo_a_buscar}")
                st.caption("Tip: Intenta buscar solo el número (Ej: 1049 en vez de Quadra-1049)")
                st.stop()

            st.success(f"✅ Conexión Exitosa. Excels analizados: {cant_archivos}. Datos en vivo desde la API capturados.")
            st.info(f"🔍 Registros encontrados: {len(datos_excel)} en Historial (Excel) y {len(datos_api)} en Sistema Vivo (API).")
            
            fecha_actual = datetime.now().strftime("%d de %B de %Y")
            
            # Preparamos el contexto enviando las dos tablas juntas
            contexto = f"--- DATOS EXCEL (Histórico y Planificación) ---\n{datos_excel.to_string()}\n\n"
            contexto += f"--- DATOS API (Tiempo Real) ---\n{datos_api.to_string()}\n"
            
            instruccion = f"""
            Eres un sistema automático que genera reportes directos de auditoría de maquinaria. Hoy es {fecha_actual}.
            Tu función es leer los DATOS EXCEL y DATOS API del equipo '{equipo_a_buscar}' y rellenar estrictamente esta plantilla.
            
            REGLA ABSOLUTA: Tu respuesta debe ser ÚNICAMENTE el texto de la plantilla completada. NO expliques tu razonamiento. NO saludes. Empieza desde el icono del tractor.
            Usa los datos de la API para la sección de certificaciones (rev_fecha_expiracion, dgmn_fecha_expiracion, ser_fecha_expiracion, horas_ult). Si un dato no existe, escribe 'No registrado'.
            
            🚜 1. Datos Básicos del Equipo:
            - Marca y Modelo: [Extraer]
            - PPU (Patente): [Extraer]
            - Año: [Extraer]
            
            📅 2. Estado de Mantenimiento y OT (Cruce Histórico):
            - Situación real a hoy ({fecha_actual}): [Deducir si está operativo o en taller según fechas]
            - Última/Próxima Actividad Programada: [Actividad, Fecha y Estatus]
            
            📍 3. Ubicación:
            - Faena / Zona Actual: [Extraer de 'nombre_faena' o 'ultimo_lugar' de la API]
            
            🛡️ 4. Cumplimiento y Horómetro (Datos en Tiempo Real API):
            - Estado Sistema Vivo: [Extraer de 'nombre_es' o 'ultimo_estado' en la API]
            - Horómetro / Kms Actual: [Extraer de 'horas_ult' o 'incremento_diario' en la API]
            - Vencimiento Revisión Técnica (RT): [Extraer de 'rev_fecha_expiracion' en la API]
            - Vencimiento Sernageomin: [Extraer de 'ser_fecha_expiracion' en la API]
            - Vencimiento DGMN: [Extraer de 'dgmn_fecha_expiracion' en la API]
            
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
                            generation_config={"temperature": 0.0} # Temperatura 0 para formato estricto
                        )
                        modelo_exitoso = nombre_modelo
                        break 
                    except Exception:
                        continue 
                
                if respuesta:
                    st.success("🤖 Reporte generado con Inteligencia Artificial:")
                    st.markdown(respuesta.text)
                    st.caption(f"✨ Análisis generado usando: {modelo_exitoso} | Datos API y Excel integrados.")
                    
                    with st.expander("Ver tablas crudas originales (Para Depuración)"):
                        st.write("Datos API (Tiempo Real):")
                        st.dataframe(datos_api)
                        st.write("Datos Excel (Histórico):")
                        st.dataframe(datos_excel)
                else:
                    st.error("Los modelos de IA están saturados. Intenta de nuevo en unos segundos.")
                    
            except Exception as e:
                st.error(f"Hubo un error con la IA: {e}")

st.divider()
st.caption("Los datos se obtienen en tiempo real fusionando Excel en Cloud y la API del Dashboard (v1.0)")
