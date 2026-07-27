import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN DE TUS ENLACES Y CLAVES
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
LINK_EXCEL = "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing"

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
        # Filtramos para usar versiones estables
        modelos_seguros = [m for m in modelos if 'vision' not in m]
        
        # Prioridad absoluta a la velocidad: Modelos Flash primero
        flash_models = [m for m in modelos_seguros if 'flash' in m]
        pro_models = [m for m in modelos_seguros if 'flash' not in m]
        
        return flash_models + pro_models + ["models/gemini-1.5-flash", "models/gemini-pro"]
    except Exception:
        return ["models/gemini-1.5-flash", "models/gemini-pro"]

lista_modelos_seguros = obtener_lista_modelos()

@st.cache_data(ttl=600) 
def cargar_excel(url):
    """Descarga el Excel de Drive y lee TODAS las pestañas combinándolas"""
    if not url or "AQUÍ" in url:
        return pd.DataFrame(), 0
        
    try:
        if "/d/" in url:
            id_archivo = url.split('/d/')[1].split('/')[0]
            url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
            
            # sheet_name=None obliga a Pandas a leer el libro entero
            diccionario_hojas = pd.read_excel(url_descarga, sheet_name=None)
            df_combinado = pd.DataFrame()
            
            # Combinamos las hojas dejando una "marca de agua" de su origen
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
    """Busca el equipo en cualquier columna, ignorando mayúsculas y espacios"""
    if df.empty: return df
    termino = str(nombre_equipo).strip().lower()
    mask = df.astype(str).apply(lambda x: x.str.lower().str.contains(termino, na=False)).any(axis=1)
    return df[mask]

# ==========================================
# 3. INTERFAZ DE LA APLICACIÓN (UI)
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
                st.caption("Tip: Intenta buscar solo el número (Ej: 1049 en vez de Quadra-1049)")
            else:
                st.success("🤖 Analizando historial y cruzando datos maestros...")
                
                # Inyectamos la fecha actual para que la IA sepa qué es pasado y qué es futuro
                fecha_actual = datetime.now().strftime("%d de %B de %Y")
                contexto = f"DATOS ENCONTRADOS (Pestañas combinadas):\n{datos_equipo.to_string()}\n"
                
                instruccion = f"""
                Eres un analista experto en planificación de equipos pesados. Hoy es {fecha_actual}.
                
                Tu misión es CRUZAR la información de las diferentes pestañas del Excel (Base de datos, Planificación, Histórico) para deducir el estado REAL del equipo '{equipo_a_buscar}'.
                
                ANÁLISIS MENTAL (Aplica esta lógica pero NO la escribas en tu respuesta):
                1. Compara las fechas de las OT con la fecha de hoy ({fecha_actual}).
                2. Si una fecha de mantenimiento preventivo ya pasó, asume lógicamente que se ejecutó y el equipo volvió a operación en su faena, a menos que haya un registro correctivo posterior.
                3. Busca cuál es la verdadera "Próxima" actividad hacia el futuro.
                
                REGLA ESTRICTA DE SALIDA:
                NO expliques tu razonamiento. NO saludes. NO uses bloques de código. Entrega ÚNICAMENTE esta plantilla exacta completada con tus deducciones finales:

                🚜 1. Datos Básicos del Equipo:
                - Marca y Modelo: [Extraer de Base de Datos]
                - PPU: [Extraer]
                - Año: [Extraer]
                - VIN: [Extraer]
                
                📅 2. Estado Actual y Próxima Planificación (Cruce Inteligente):
                - Situación real hoy ({fecha_actual}): [Deducción: Ej. Operativo en faena, En taller, etc.]
                - Próxima Actividad Programada: [Actividad con fecha FUTURA más cercana, Fecha y Estatus]
                
                📍 3. Ubicación y Faena:
                - Ubicación Actual Deducida: [Basado en el análisis cronológico]
                
                TABLA DE DATOS PARA ANALIZAR:
                {contexto}
                """
                
                try:
                    respuesta = None
                    modelo_exitoso = ""
                    ultimo_error = ""
                    
                    # Intentamos con el modelo más rápido primero (Cascada)
                    for nombre_modelo in lista_modelos_seguros:
                        try:
                            modelo_prueba = genai.GenerativeModel(nombre_modelo)
                            # Temperature 0.0 evita que la IA alucine o sea habladora
                            respuesta = modelo_prueba.generate_content(
                                instruccion,
                                generation_config={"temperature": 0.0}
                            )
                            modelo_exitoso = nombre_modelo
                            break 
                        except Exception as error_modelo:
                            ultimo_error = str(error_modelo)
                            continue 
                    
                    if respuesta:
                        st.info(respuesta.text)
                        st.caption(f"✨ Análisis generado exitosamente usando: {modelo_exitoso} (Modo Rápido)")
                        
                        with st.expander("Ver tabla original extraída del Excel"):
                            st.dataframe(datos_equipo)
                    else:
                        st.error("Todos los modelos fallaron al intentar conectar.")
                        st.caption(f"🔧 Último error: {ultimo_error}")
                        
                except Exception as e:
                    st.error(f"Hubo un error inesperado al conectar con Gemini (IA). Detalle técnico: {e}")

st.divider()
st.caption("Los datos se sincronizan automáticamente con SharePoint. (Integración API activada para análisis cronológico)")
