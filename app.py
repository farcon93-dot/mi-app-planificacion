import streamlit as st
import pandas as pd
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACIÓN DE TUS ENLACES Y CLAVES
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 

# Ahora solo usamos UN link principal, el tuyo.
LINK_EXCEL = "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing"

# ==========================================
# 2. CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(page_title="Copiloto de Equipos", layout="centered", page_icon="🚜")
genai.configure(api_key=GEMINI_API_KEY)
modelo = genai.GenerativeModel('gemini-pro')

# ==========================================
# 3. FUNCIONES INTELIGENTES (El Motor)
# ==========================================
@st.cache_data(ttl=600) # Guarda en memoria por 10 minutos para ser rapidísimo
def cargar_excel(url):
    if not url or "AQUÍ" in url:
        return pd.DataFrame(), 0
        
    try:
        if "/d/" in url:
            id_archivo = url.split('/d/')[1].split('/')[0]
            url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
            
            # EL SÚPER PODER: sheet_name=None obliga a leer TODAS las pestañas
            diccionario_hojas = pd.read_excel(url_descarga, sheet_name=None)
            
            df_combinado = pd.DataFrame()
            
            # Unimos todas las pestañas en una sola gran tabla
            for nombre_hoja, df_hoja in diccionario_hojas.items():
                df_hoja['Pestaña_Origen'] = nombre_hoja # Marca de agua para saber de dónde viene
                df_combinado = pd.concat([df_combinado, df_hoja], ignore_index=True)
                
            # Limpiamos los datos para que el buscador no falle por espacios invisibles
            df_combinado = df_combinado.dropna(how='all') 
            
            return df_combinado, len(diccionario_hojas)
        else:
            return pd.DataFrame(), 0
    except Exception as e:
        st.error(f"❌ Error leyendo el Excel. Detalle: {e}")
        return pd.DataFrame(), 0

def filtrar_por_equipo(df, nombre_equipo):
    if df.empty: return df
    
    # Busca ignorando mayúsculas, minúsculas y espacios extra
    termino = str(nombre_equipo).strip().lower()
    
    # Busca en todas las columnas
    mask = df.astype(str).apply(lambda x: x.str.lower().str.contains(termino, na=False)).any(axis=1)
    return df[mask]

# ==========================================
# 4. INTERFAZ DE LA APLICACIÓN (Tu celular)
# ==========================================
st.title("🚜 Copiloto de Equipos")
st.markdown("Consulta el estado, ubicación y datos básicos de tus equipos.")

# Buscador principal
equipo_a_buscar = st.text_input("🔍 Ingresa el nombre o código del equipo (Ej: Quadra-1049, Auger-165):")

if st.button("Consultar Estado Actual"):
    if not equipo_a_buscar:
        st.warning("⚠️ Por favor, escribe un equipo para buscar.")
    else:
        with st.spinner(f'Analizando todas las pestañas del Excel buscando a {equipo_a_buscar}...'):
            
            # 1. Cargamos el Excel completo (Todas las hojas)
            df_total, cant_hojas = cargar_excel(LINK_EXCEL)
            
            if df_total.empty:
                st.stop() # Se detiene si hubo un error al cargar
                
            # 2. Filtramos solo lo que importa de ese equipo
            datos_equipo = filtrar_por_equipo(df_total, equipo_a_buscar)
            
            # Radiografía del filtro
            st.success(f"✅ Conectado a Drive. Se revisaron {cant_hojas} pestañas y {len(df_total)} filas en total.")
            st.info(f"🔍 Se encontraron {len(datos_equipo)} registros para el equipo '{equipo_a_buscar}'.")
            
            if len(datos_equipo) == 0:
                st.error(f"No se encontró ninguna coincidencia exacta para: {equipo_a_buscar}")
                st.caption("Tip: Intenta buscar solo el número (Ej: 1049 en vez de Quadra-1049)")
            else:
                # 3. Le pasamos la info a la IA
                st.success("🤖 Analizando historial y datos maestros con Inteligencia Artificial...")
                
                contexto = f"DATOS ENCONTRADOS:\n{datos_equipo.to_string()}\n"
                
                instruccion = f"""
                Eres un analista experto en mantenimiento y planificación de equipos pesados en la minería.
                El usuario preguntó por el equipo: '{equipo_a_buscar}'.
                
                Aquí tienes TODAS las filas donde aparece ese equipo cruzando distintas pestañas del Excel.
                La columna 'Pestaña_Origen' te dice de qué hoja viene la información (Ej: Base de Datos, Planificación, Historial).
                
                Concéntrate en deducir y resumir esto:
                1. Datos Básicos del Equipo (Si hay información de la base de datos).
                2. ¿Cuál es su estado más actual de planificación y estatus de OT?
                3. ¿Cuál es su ubicación actual o faena reportada?
                
                Ignora información vieja irrelevante. Responde de forma muy directa, clara, profesional y en viñetas para que sea fácil de leer en un celular.
                
                DATOS DE RESPALDO:
                {contexto}
                """
                
                try:
                    respuesta = modelo.generate_content(instruccion)
                    st.info(respuesta.text)
                    
                    # Mostrar la tabla cruda abajo por si el usuario quiere verificar
                    with st.expander("Ver tabla original extraída del Excel"):
                        st.dataframe(datos_equipo)
                        
                except Exception as e:
                    st.error(f"Hubo un error al conectar con Gemini (IA). Detalle técnico: {e}")

st.divider()
st.caption("Los datos se sincronizan automáticamente con SharePoint. (Próximamente: Integración con API)")
