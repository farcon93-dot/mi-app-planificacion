import streamlit as st
import pandas as pd
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACIÓN DE TUS ENLACES Y CLAVES
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
LINK_EXCEL = "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing"

# ==========================================
# 2. CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(page_title="Copiloto de Equipos", layout="centered", page_icon="🚜")

# ==========================================
# 3. FUNCIONES INTELIGENTES (El Motor)
# ==========================================
@st.cache_resource
def obtener_modelo_ia():
    genai.configure(api_key=GEMINI_API_KEY)
    modelo_elegido = 'gemini-1.5-flash' # Modelo por defecto
    try:
        # Le preguntamos a Google qué modelos existen para esta clave
        modelos_disponibles = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Buscamos el mejor disponible en orden de prioridad
        if "models/gemini-1.5-flash" in modelos_disponibles:
            modelo_elegido = "models/gemini-1.5-flash"
        elif "models/gemini-1.5-pro" in modelos_disponibles:
            modelo_elegido = "models/gemini-1.5-pro"
        elif "models/gemini-1.0-pro" in modelos_disponibles:
            modelo_elegido = "models/gemini-1.0-pro"
        elif len(modelos_disponibles) > 0:
            modelo_elegido = modelos_disponibles[0] # Usar el primero que funcione
            
        return genai.GenerativeModel(modelo_elegido), modelo_elegido
    except Exception:
        return genai.GenerativeModel(modelo_elegido), modelo_elegido

# Obtenemos la IA lista para usar
modelo, nombre_modelo_usado = obtener_modelo_ia()

@st.cache_data(ttl=600)
def cargar_excel(url):
    if not url or "AQUÍ" in url:
        return pd.DataFrame(), 0
        
    try:
        if "/d/" in url:
            id_archivo = url.split('/d/')[1].split('/')[0]
            url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
            
            # Extraemos todas las pestañas de una vez
            diccionario_hojas = pd.read_excel(url_descarga, sheet_name=None)
            df_combinado = pd.DataFrame()
            
            for nombre_hoja, df_hoja in diccionario_hojas.items():
                df_hoja['Pestaña_Origen'] = nombre_hoja
                df_combinado = pd.concat([df_combinado, df_hoja], ignore_index=True)
                
            df_combinado = df_combinado.dropna(how='all') 
            return df_combinado, len(diccionario_hojas)
        else:
            return pd.DataFrame(), 0
    except Exception as e:
        st.error(f"❌ Error leyendo el Excel. Detalle: {e}")
        return pd.DataFrame(), 0

def filtrar_por_equipo(df, nombre_equipo):
    if df.empty: return df
    termino = str(nombre_equipo).strip().lower()
    mask = df.astype(str).apply(lambda x: x.str.lower().str.contains(termino, na=False)).any(axis=1)
    return df[mask]

# ==========================================
# 4. INTERFAZ DE LA APLICACIÓN (Tu celular)
# ==========================================
st.title("🚜 Copiloto de Equipos")
st.markdown("Consulta el estado, ubicación y datos básicos de tus equipos.")

equipo_a_buscar = st.text_input("🔍 Ingresa el nombre o código del equipo (Ej: Quadra-1049, Auger-165):")

if st.button("Consultar Estado Actual"):
    if not equipo_a_buscar:
        st.warning("⚠️ Por favor, escribe un equipo para buscar.")
    else:
        with st.spinner(f'Analizando todas las pestañas del Excel buscando a {equipo_a_buscar}...'):
            df_total, cant_hojas = cargar_excel(LINK_EXCEL)
            
            if df_total.empty:
                st.stop()
                
            datos_equipo = filtrar_por_equipo(df_total, equipo_a_buscar)
            
            st.success(f"✅ Conectado a Drive. Se revisaron {cant_hojas} pestañas y {len(df_total)} filas en total.")
            st.info(f"🔍 Se encontraron {len(datos_equipo)} registros para el equipo '{equipo_a_buscar}'.")
            
            if len(datos_equipo) == 0:
                st.error(f"No se encontró ninguna coincidencia exacta para: {equipo_a_buscar}")
            else:
                st.success("🤖 Analizando historial y datos maestros con Inteligencia Artificial...")
                
                contexto = f"DATOS ENCONTRADOS:\n{datos_equipo.to_string()}\n"
                instruccion = f"""
                Eres un analista experto en mantenimiento y planificación de equipos pesados en la minería.
                El usuario preguntó por el equipo: '{equipo_a_buscar}'.
                
                Aquí tienes TODAS las filas donde aparece ese equipo cruzando distintas pestañas del Excel.
                La columna 'Pestaña_Origen' te dice de qué hoja viene la información.
                
                Concéntrate en deducir y resumir esto:
                1. Datos Básicos del Equipo.
                2. ¿Cuál es su estado más actual de planificación y estatus de OT?
                3. ¿Cuál es su ubicación actual o faena reportada?
                
                Ignora información vieja irrelevante. Responde de forma muy directa, clara, profesional y en viñetas.
                
                DATOS DE RESPALDO:
                {contexto}
                """
                
                try:
                    respuesta = modelo.generate_content(instruccion)
                    st.info(respuesta.text)
                    
                    with st.expander("Ver tabla original extraída del Excel"):
                        st.dataframe(datos_equipo)
                        
                except Exception as e:
                    st.error(f"Hubo un error al conectar con Gemini (IA). Detalle técnico: {e}")
                    st.caption(f"🔧 Diagnóstico del sistema: La aplicación intentó usar el modelo '{nombre_modelo_usado}'.")

st.divider()
st.caption("Los datos se sincronizan automáticamente con SharePoint.")
