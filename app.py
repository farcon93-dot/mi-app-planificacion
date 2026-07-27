import streamlit as st
import pandas as pd
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACIÓN DE TUS ENLACES Y CLAVES
# ==========================================

# En lugar de pegar la clave aquí, le decimos que la busque en la "Caja Fuerte" de Streamlit
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 

# Pega aquí los links de "Cualquier persona con el enlace" de tus 3 Excel en Google Drive
# Si por ahora solo tienes 1, pega el mismo link en los 3 para que no de error.
LINK_EXCEL_1 = "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"
LINK_EXCEL_2 = "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"
LINK_EXCEL_3 = "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"

# ==========================================
# 2. CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(page_title="Copiloto de Equipos", layout="centered", page_icon="🚜")
genai.configure(api_key=GEMINI_API_KEY)
modelo = genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# 3. FUNCIONES INTELIGENTES (El Motor)
# ==========================================
# Le quitamos la memoria caché temporalmente y le agregamos "Rayos X"
def cargar_excel(url, nombre):
    if not url or "AQUÍ" in url:
        return pd.DataFrame()
        
    try:
        # Truco para que Python descargue el Excel directo de Drive
        if "/d/" in url:
            id_archivo = url.split('/d/')[1].split('/')[0]
            url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
            df = pd.read_excel(url_descarga)
            st.success(f"✅ {nombre} conectado. Se leyeron {len(df)} filas.")
            return df
        else:
            st.warning(f"⚠️ El enlace de {nombre} no es válido: {url}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error interno leyendo {nombre}. Detalle: {e}")
        return pd.DataFrame()

def filtrar_por_equipo(df, nombre_equipo):
    if df.empty: return df
    # Busca el nombre del equipo en CUALQUIER columna del Excel
    mask = df.astype(str).apply(lambda x: x.str.contains(nombre_equipo, case=False, na=False)).any(axis=1)
    return df[mask]

# ==========================================
# 4. INTERFAZ DE LA APLICACIÓN (Tu celular)
# ==========================================
st.title("🚜 Copiloto de Equipos")
st.markdown("Consulta el estado y ubicación más reciente de tus equipos.")

# Buscador principal
equipo_a_buscar = st.text_input("🔍 Ingresa el nombre o código del equipo (Ej: Camión 12, CA-101):")

if st.button("Consultar Estado Actual"):
    if not equipo_a_buscar:
        st.warning("⚠️ Por favor, escribe un equipo para buscar.")
    else:
        with st.spinner(f'Buscando a {equipo_a_buscar} en los registros...'):
            # 1. Cargamos los 3 Excels con la función de Rayos X
            df1 = cargar_excel(LINK_EXCEL_1, "Excel 1")
            df2 = cargar_excel(LINK_EXCEL_2, "Excel 2")
            df3 = cargar_excel(LINK_EXCEL_3, "Excel 3")
            
            # 2. Filtramos solo lo que importa de ese equipo
            filtro1 = filtrar_por_equipo(df1, equipo_a_buscar)
            filtro2 = filtrar_por_equipo(df2, equipo_a_buscar)
            filtro3 = filtrar_por_equipo(df3, equipo_a_buscar)
            
            total_filas = len(filtro1) + len(filtro2) + len(filtro3)
            
            # Radiografía del filtro
            st.info(f"🔍 Rayos X: El buscador encontró {len(filtro1)} coincidencias en Excel 1, {len(filtro2)} en Excel 2, y {len(filtro3)} en Excel 3.")
            
            if total_filas == 0:
                st.error(f"No se encontró información reciente para el equipo: {equipo_a_buscar}")
            else:
                # 3. Le pasamos la info filtrada a la IA
                st.success(f"✅ Se encontraron registros. Analizando el estado más reciente...")
                
                contexto = f"""
                DATOS EXCEL 1:\n{filtro1.to_string()}\n
                DATOS EXCEL 2:\n{filtro2.to_string()}\n
                DATOS EXCEL 3:\n{filtro3.to_string()}
                """
                
                instruccion = f"""
                Eres un analista de mantenimiento y planificación de equipos pesados.
                El usuario preguntó por el equipo: '{equipo_a_buscar}'.
                
                Aquí tienes todas las filas donde aparece ese equipo en nuestros registros de Excel.
                IMPORTANTE: Ignora el historial antiguo (como mantenciones del año pasado). 
                Concéntrate en deducir:
                1. ¿Cuál es su estado más actual (Operativo, En Taller, Detenido, etc.)?
                2. ¿Cuál es su ubicación actual reportada?
                3. ¿Hay algún comentario o alerta reciente que debamos saber?
                
                Responde de forma muy directa, clara y en viñetas para que sea fácil de leer en un celular.
                
                DATOS DE RESPALDO:
                {contexto}
                """
                
                try:
                    respuesta = modelo.generate_content(instruccion)
                    st.info(respuesta.text)
                except Exception as e:
                    st.error("Hubo un error al conectar con la Inteligencia Artificial.")

st.divider()
st.caption("Los datos se sincronizan automáticamente con SharePoint. (Próximamente: Integración con API)")
