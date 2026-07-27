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
def obtener_lista_modelos():
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Eliminamos versiones inestables
        modelos_seguros = [m for m in modelos if '2.5' not in m and 'vision' not in m]
        
        # TRUCO DE VELOCIDAD: Forzamos a que pruebe primero los modelos "flash" (ultra rápidos)
        flash_models = [m for m in modelos_seguros if 'flash' in m]
        pro_models = [m for m in modelos_seguros if 'flash' not in m]
        
        return flash_models + pro_models + ["models/gemini-1.5-flash"]
    except Exception:
        return ["models/gemini-1.5-flash", "models/gemini-pro"]

lista_modelos_seguros = obtener_lista_modelos()

@st.cache_data(ttl=600)
def cargar_excel(url):
    if not url or "AQUÍ" in url:
        return pd.DataFrame(), 0
        
    try:
        if "/d/" in url:
            id_archivo = url.split('/d/')[1].split('/')[0]
            url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
            
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
# 4. INTERFAZ DE LA APLICACIÓN
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
                st.success("🤖 Analizando historial y datos maestros con Inteligencia Artificial...")
                
                contexto = f"DATOS ENCONTRADOS:\n{datos_equipo.to_string()}\n"
                
                # INSTRUCCIÓN TIPO MÁQUINA (Cero libertad creativa)
                instruccion = f"""
                ESTA ES UNA TAREA DE EXTRACCIÓN AUTOMÁTICA DE DATOS.
                REGLAS ESTRICTAS:
                1. NO expliques tu razonamiento. NO pienses en voz alta. NO uses inglés.
                2. Copia EXACTAMENTE la plantilla de abajo y solo reemplaza los corchetes con la información del equipo '{equipo_a_buscar}'.
                3. Si imprimes algo fuera de la plantilla, el sistema fallará.

                🚜 1. Datos Básicos del Equipo:
                - Marca y Modelo: [Extraer]
                - PPU: [Extraer]
                - Año: [Extraer]
                - VIN: [Extraer]
                
                📅 2. Estado de Planificación y OT:
                - Actividad: [Actividad con fecha más reciente o futura]
                - Fecha Proyectada: [Extraer]
                - Estatus de OT: [Extraer]
                
                📍 3. Ubicación y Faena:
                - Faena actual reportada: [Extraer]
                
                TABLA DE DATOS:
                {contexto}
                """
                
                try:
                    respuesta = None
                    modelo_exitoso = ""
                    ultimo_error = ""
                    
                    for nombre_modelo in lista_modelos_seguros:
                        try:
                            modelo_prueba = genai.GenerativeModel(nombre_modelo)
                            # TEMPERATURA 0: Convierte a la IA en un robot directo y sin imaginación
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
                        st.error("Todos los modelos fallaron.")
                        st.caption(f"🔧 Último error: {ultimo_error}")
                        
                except Exception as e:
                    st.error(f"Hubo un error inesperado. Detalle técnico: {e}")

st.divider()
st.caption("Los datos se sincronizan automáticamente con SharePoint. (Próximamente: Integración con API)")
