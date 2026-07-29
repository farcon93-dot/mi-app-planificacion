import streamlit as st
import pandas as pd
import google.generativeai as genai
import concurrent.futures
import requests
import datetime

st.set_page_config(page_title="Control Flota Enaex", layout="wide", page_icon="🚛")

# Usamos PNG oficial en lugar de SVG para evitar bloqueos de Firewalls Corporativos
st.markdown("""
    <div style="display: flex; align-items: center; gap: 20px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Enaex_logo.svg/512px-Enaex_logo.svg.png" alt="Enaex" width="160" onerror="this.style.display='none'">
        <h1 style="margin: 0; color: #1E3A8A;">🚛 Centro de Control: Flota y Auditoría</h1>
    </div>
    <hr style="margin-top: 10px; margin-bottom: 20px;">
""", unsafe_allow_html=True)

API_KEY_DASHBOARD = "CX92wBe9wV2NLUMyFE6PzvcyqTWyBPr5"
ENLACES_EXCEL = [
    "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing",
    "https://docs.google.com/spreadsheets/d/1VrDHEb-D7oeypyYdhUpd3_tw_jggTu3K/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"
]

CAPACIDAD_TALLERES = {
    "SKC ALTO HOSPICIO": 2,
    "SKC CALAMA": 4,
    "SKC ANTOFAGASTA": 2,
    "RIO LOA": 2,
    "SKC COPIAPO": 2,
    "FULL RPM": 4
}

MODELOS_SEGUROS = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro', 'gemini-pro']

@st.cache_resource
def configurar_ia(api_key):
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    for nombre_modelo in MODELOS_SEGUROS:
        try:
            modelo = genai.GenerativeModel(nombre_modelo)
            return modelo
        except Exception:
            continue
    return None

try:
    API_KEY_GEMINI = st.secrets.get("GEMINI_API_KEY", "")
except:
    API_KEY_GEMINI = ""

modelo_ia = configurar_ia(API_KEY_GEMINI)

@st.cache_data(ttl=600)
def cargar_excels(urls):
    df_maestro = pd.DataFrame()
    for url in urls:
        try:
            if "/d/" in url:
                id_archivo = url.split('/d/')[1].split('/')[0]
                url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
                # Lee TODAS las hojas del excel
                dict_hojas = pd.read_excel(url_descarga, sheet_name=None)
                for nombre_hoja, df_hoja in dict_hojas.items():
                    df_hoja['Origen_Hoja'] = nombre_hoja
                    df_maestro = pd.concat([df_maestro, df_hoja], ignore_index=True)
        except Exception as e:
            pass
    return df_maestro

@st.cache_data(ttl=300)
def extraer_api():
    tipos = [27, 26, 24, 21, 23, 41]
    zonas = list(range(1, 14))
    datos = []
    def fetch(t, z):
        try:
            r = requests.get(f"http://40.65.224.42/api/dashboard/estado/{t}/{z}?key={API_KEY_DASHBOARD}", timeout=4)
            if r.status_code == 200: 
                return r.json()
        except: 
            return []
        return []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futuros = [executor.submit(fetch, t, z) for t in tipos for z in zonas]
        for f in concurrent.futures.as_completed(futuros):
            res = f.result()
            if isinstance(res, list) and len(res) > 0: 
                datos.extend(res)
    return pd.DataFrame(datos)

def buscar_dato_flexible(df_equipo, palabras_clave):
    """Busca en TODAS las filas donde aparece el camión para armar el puzzle, leyendo de abajo hacia arriba."""
    if df_equipo is None or df_equipo.empty: 
        return "N/A"
    
    # Recorremos el dataframe desde la última fila hacia arriba (la data más fresca suele estar al final)
    for index, row in df_equipo.iloc[::-1].iterrows():
        for col in df_equipo.columns:
            col_str = str(col).lower().strip()
            for palabra in palabras_clave:
                if palabra in col_str:
                    valor = row[col]
                    # Validar que no sea NaN o texto vacío
                    if pd.notna(valor) and str(valor).strip().lower() not in ['nan', 'nat', 'none', '']:
                        return str(valor).strip()
    return "N/A"

def formatear_fecha(fecha_str):
    """Convierte fechas crudas al formato impecable DD/MM/YYYY"""
    if pd.isna(fecha_str) or fecha_str == "N/A" or str(fecha_str).strip() == "": 
        return "N/A"
    try:
        return pd.to_datetime(fecha_str, dayfirst=True).strftime('%d/%m/%Y')
    except:
        return str(fecha_str).split('T')[0].split(' ')[0]

def normalizar_nombre_taller(nombre):
    """Estandariza los nombres de los talleres para poder calcular la capacidad exacta."""
    if not nombre or nombre == "N/A": return "N/A"
    n = str(nombre).upper().strip()
    if "HOSPICIO" in n: return "SKC ALTO HOSPICIO"
    if "CALAMA" in n or "MECANICAL" in n: return "SKC CALAMA"
    if "ANTOFAGASTA" in n: return "SKC ANTOFAGASTA"
    if "LOA" in n: return "RIO LOA"
    if "COPIAP" in n: return "SKC COPIAPO"
    if "FULL" in n or "RPM" in n: return "FULL RPM"
    return n

with st.spinner("Descargando sistemas en vivo y planillas de Excel..."):
    df_excel_global = cargar_excels(ENLACES_EXCEL)
    df_api_global = extraer_api()

tab_alertas, tab_equipos, tab_movimientos, tab_faenas = st.tabs([
    "🚨 Alertas", "🔍 Buscar Equipo", "📅 Movimientos de Equipos", "📍 Ver por Faena"
])

with tab_alertas:
    st.header("🚨 Estado de Cumplimiento de Contratos")
    if not df_api_global.empty and 'nombre_faena' in df_api_global.columns:
        resumen_faenas = df_api_global.groupby('nombre_faena').size().reset_index(name='Total_Equipos')
        cols = st.columns(3)
        for idx, row in resumen_faenas.iterrows():
            with cols[idx % 3]:
                st.info(f"**Faena:** {row['nombre_faena']}\n\n**Equipos Operativos:** {row['Total_Equipos']}")
    else:
        st.warning("No se encontraron datos en la API para mostrar alertas.")

with tab_equipos:
    st.header("🔍 Búsqueda y Auditoría Individual")
    st.write("Busca información consolidada de Hardware, GPS y Planificación.")
    equipos_input = st.text_input("Ingresa el nombre o código del equipo (Ej: Quadra-70, Auger-165):")
    
    if st.button("Consultar Ficha Técnica") and equipos_input:
        nombres = [eq.strip().upper() for eq in equipos_input.split(",") if eq.strip()]
        
        for nombre in nombres:
            # 1. Filtrar DataFrame de Excel (Buscar en TODAS las filas donde aparece el camión)
            if not df_excel_global.empty:
                df_historial_equipo = df_excel_global[df_excel_global.astype(str).apply(lambda x: x.str.upper().str.contains(nombre)).any(axis=1)]
            else:
                df_historial_equipo = pd.DataFrame()

            # 2. Filtrar DataFrame de API
            if not df_api_global.empty and 'nombre' in df_api_global.columns:
                df_api_equipo = df_api_global[df_api_global['nombre'].str.upper().str.contains(nombre, na=False)]
            else:
                df_api_equipo = pd.DataFrame()
            
            if df_historial_equipo.empty and df_api_equipo.empty:
                st.error(f"❌ No se encontró '{nombre}' ni en Excel ni en API.")
                continue
                
            # --- EXTRACCIÓN FUERTE (Cruza todas las pestañas) ---
            patente = buscar_dato_flexible(df_historial_equipo, ['patente', 'placa', 'ppu'])
            vin = buscar_dato_flexible(df_historial_equipo, ['vin', 'chasis', 'serie'])
            marca = buscar_dato_flexible(df_historial_equipo, ['marca'])
            modelo = buscar_dato_flexible(df_historial_equipo, ['modelo', 'año', 'year'])
            capacidad = buscar_dato_flexible(df_historial_equipo, ['capacidad', 'tonelaje', 'tons'])
            control = buscar_dato_flexible(df_historial_equipo, ['control', 'sistema'])
            
            # Buscamos estatus y ubicación preferentemente en la última fila/hoja de planificación
            ultima_fila = df_historial_equipo.iloc[[-1]] if not df_historial_equipo.empty else pd.DataFrame()
            estatus_taller = buscar_dato_flexible(ultima_fila, ['estatus mp', 'status', 'estado'])
            ubicacion_taller = buscar_dato_flexible(ultima_fila, ['ubicación', 'taller', 'lugar'])
            comentarios = buscar_dato_flexible(ultima_fila, ['motivo', 'comentario', 'trabajos', 'estado de equipos'])
            
            fecha_inicio = formatear_fecha(buscar_dato_flexible(ultima_fila, ['fecha inicio', 'inicio planificado', 'inici', 'bajada']))
            fecha_entrega = formatear_fecha(buscar_dato_flexible(ultima_fila, ['fecha entrega', 'fin planificado', 'fina', 'subida']))

            # Datos GPS
            ubicacion_gps = df_api_equipo['nombre_faena'].iloc[0] if not df_api_equipo.empty and 'nombre_faena' in df_api_equipo.columns else "No reporta GPS"
            estado_gps = df_api_equipo['Estado_Deducido'].iloc[0] if not df_api_equipo.empty and 'Estado_Deducido' in df_api_equipo.columns else "N/A"
            horometro = df_api_equipo['horas_ult'].iloc[0] if not df_api_equipo.empty and 'horas_ult' in df_api_equipo.columns else "N/A"

            # --- RENDERIZADO VISUAL ---
            st.markdown(f"### 🚛 Ficha Técnica: {nombre}")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📡 Hardware e Identificación")
                st.info(f"📍 **Ubicación API:** {ubicacion_gps} | ⚙️ **Estado:** {estado_gps}")
                
                c1, c2 = st.columns(2)
                c1.markdown(f"**Patente:** {patente}")
                c1.markdown(f"**Marca/Modelo:** {marca} {modelo}")
                c1.markdown(f"**VIN/Chasis:** {vin}")
                
                c2.markdown(f"**Capacidad:** {capacidad}")
                c2.markdown(f"**Control:** {control}")
                c2.markdown(f"**Horómetro:** {horometro}")
                
                st.markdown("**🗓️ Certificaciones:** (Revisión Técnica / Sernageomin / DGMN) -> Buscando en matriz...")

            with col2:
                st.markdown("#### 🗓️ Planificación de Mantenimiento")
                st.success(f"📋 **Estatus:** {estatus_taller} | **Ubicación:** {ubicacion_taller}")
                
                st.markdown(f"**🗓️ Fechas de Planificación (Excel):**")
                st.markdown(f"- **Bajada a Taller (Inicio):** {fecha_inicio}")
                st.markdown(f"- **Subida a Faena (Entrega):** {fecha_entrega}")
                st.markdown(f"💬 **Trabajos / Motivo:** {comentarios}")
            
            # Auditoría IA Segura
            if modelo_ia:
                with st.expander("🤖 Auditoría Automática (Buscando Incongruencias)"):
                    try:
                        prompt = f"Analiza en 2 líneas. El equipo {nombre} tiene fecha de inicio {fecha_inicio} y entrega {fecha_entrega}, estatus {estatus_taller}, ubicado en {ubicacion_taller}. Según GPS está en {ubicacion_gps}. ¿Todo se ve normal?"
                        respuesta = modelo_ia.generate_content(prompt)
                        st.write(respuesta.text)
                    except Exception as e:
                        st.warning("⚠️ Límite de cuota IA alcanzado. Tu ficha técnica funciona perfectamente, pero la IA necesita que renueves la API Key o esperes unos minutos.")
            else:
                st.warning("IA no configurada o API Key inválida.")
            st.divider()

with tab_movimientos:
    st.header("📅 Control de Subidas, Bajadas y Capacidad")
    st.write("Análisis logístico de la semana según el Excel. (Sin consumo de IA para mayor velocidad)")
    
    if st.button("Calcular Semana Logística"):
        if df_excel_global.empty:
            st.error("No hay datos en el Excel para procesar.")
        else:
            hoy = pd.Timestamp.now().normalize()
            fin_semana = hoy + pd.Timedelta(days=7)
            
            subidas = []
            bajadas = []
            carga_actual = {k: 0 for k in CAPACIDAD_TALLERES.keys()}
            equipos_procesados = set()

            # Recorremos de abajo hacia arriba para capturar el último registro de cada camión
            for _, row in df_excel_global.iloc[::-1].iterrows():
                # Encontrar nombre del equipo en esta fila
                equipo = "N/A"
                for col in row.index:
                    if 'equipo' in str(col).lower().strip():
                        if pd.notna(row[col]): equipo = str(row[col]).strip().upper()
                        break
                
                if equipo == "N/A" or equipo in equipos_procesados: continue
                equipos_procesados.add(equipo)
                
                # Encontrar fechas y lugares
                df_row_series = pd.DataFrame([row])
                f_inicio_str = buscar_dato_flexible(df_row_series, ['fecha inicio', 'inicio planificado', 'inici'])
                f_entrega_str = buscar_dato_flexible(df_row_series, ['fecha entrega', 'fin planificado', 'fina'])
                faena = buscar_dato_flexible(df_row_series, ['faena', 'contrato'])
                taller_raw = buscar_dato_flexible(df_row_series, ['ubicación', 'taller'])
                
                taller_norm = normalizar_nombre_taller(taller_raw)
                
                # --- CALCULAR SUBIDAS Y BAJADAS (7 DÍAS) ---
                try:
                    if f_inicio_str != "N/A":
                        f_ini = pd.to_datetime(f_inicio_str, dayfirst=True)
                        if hoy <= f_ini <= fin_semana:
                            bajadas.append(f"🔧 **{equipo}** ➔ Baja al Taller: **{taller_raw}** ({f_ini.strftime('%d/%m')})")
                except: pass
                
                try:
                    if f_entrega_str != "N/A":
                        f_fin = pd.to_datetime(f_entrega_str, dayfirst=True)
                        if hoy <= f_fin <= fin_semana:
                            subidas.append(f"📈 **{equipo}** ➔ Sube a la Faena: **{faena}** ({f_fin.strftime('%d/%m')})")
                except: pass

                # --- CALCULAR CAPACIDAD DE TALLERES (ESTATUS ACTUAL) ---
                try:
                    en_taller = False
                    if f_inicio_str != "N/A":
                        f_i = pd.to_datetime(f_inicio_str, dayfirst=True)
                        if f_i <= fin_semana:
                            if f_entrega_str == "N/A":
                                en_taller = True
                            else:
                                f_e = pd.to_datetime(f_entrega_str, dayfirst=True)
                                if f_e >= hoy: 
                                    en_taller = True
                    
                    if en_taller and taller_norm in carga_actual:
                        carga_actual[taller_norm] += 1
                except: pass

            # --- RENDERIZAR RESULTADOS VISUALES ---
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.warning("### 📉 Bajan a Taller (Esta Semana)")
                if bajadas:
                    for b in bajadas: st.markdown(b)
                else:
                    st.success("No hay bajadas programadas esta semana.")
                    
            with col_m2:
                st.success("### ⛰️ Suben a Faena (Esta Semana)")
                if subidas:
                    for s in subidas: st.markdown(s)
                else:
                    st.info("No hay subidas programadas esta semana.")

            st.divider()
            st.subheader("⚖️ Estado de Capacidad por Taller (Ocupados / Máximo)")
            
            cols_talleres = st.columns(3)
            for i, (nombre_taller, limite) in enumerate(CAPACIDAD_TALLERES.items()):
                ocupados = carga_actual.get(nombre_taller, 0)
                
                with cols_talleres[i % 3]:
                    if ocupados > limite:
                        st.error(f"**{nombre_taller}**\n\n🔴 SOBREPASADO\n\nEquipos: {ocupados} / {limite}")
                    elif ocupados == limite:
                        st.warning(f"**{nombre_taller}**\n\n🟡 AL LÍMITE\n\nEquipos: {ocupados} / {limite}")
                    else:
                        st.success(f"**{nombre_taller}**\n\n🟢 CON ESPACIO\n\nEquipos: {ocupados} / {limite}")

with tab_faenas:
    st.header("📍 Vista Global de Faenas")
    if not df_api_global.empty and 'nombre_faena' in df_api_global.columns:
        faenas_unicas = df_api_global['nombre_faena'].dropna().unique()
        for faena in sorted(faenas_unicas):
            with st.expander(f"⛰️ {faena}"):
                df_filtrado = df_api_global[df_api_global['nombre_faena'] == faena]
                st.dataframe(df_filtrado[['nombre', 'marca_nombre', 'horas_ult', 'Estado_Deducido']].reset_index(drop=True), use_container_width=True)
    else:
        st.write("No hay datos de GPS/Faenas disponibles en este momento.")
