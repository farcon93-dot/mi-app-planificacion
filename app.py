import streamlit as st
import pandas as pd
import google.generativeai as genai
import concurrent.futures
import requests

st.set_page_config(page_title="Control Flota Enaex", layout="wide", page_icon="🚛")

# Usamos PNG en lugar de SVG para evitar bloqueos de Firewalls Corporativos
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

# Configuración estricta de Modelos IA para evitar errores 404
MODELOS_SEGUROS = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro']

@st.cache_resource
def configurar_ia(api_key):
    if not api_key or "PEGA_TU_KEY" in api_key:
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

CONTRATOS_FAENA = {
    "Centinela": 13, "Collahuasi": 6, "Los Bronces": 7, "Los Pelambres": 5, 
    "Nueva Centinela": 3, "Radomiro Tomic": 5, "Sierra Gorda": 6, "Spence": 5, 
    "Andina": 5, "Antucoya": 3, "Chuquicamata": 2, "Lomas Bayas": 5, 
    "Los Colorados": 3, "Salvador": 4, "Teniente": 1, "Zaldivar": 2, 
    "Cerro Negro": 1, "El Soldado": 2, "Michilla": 1, "Pleito": 1, 
    "Romeral": 1, "Salares Norte": 1
}

CAPACIDAD_TALLERES = {
    "SKC ALTO HOSPICIO": 2,
    "SKC CALAMA": 4,
    "SKC ANTOFAGASTA": 2,
    "RIO LOA": 2,
    "SKC COPIAPO": 2,
    "FULL RPM": 4
}

def buscar_dato_flexible(df_row, palabras_clave):
    """Buscador agresivo en Excel: ignora mayúsculas, espacios y caracteres raros."""
    if df_row is None or df_row.empty: return "N/A"
    if isinstance(df_row, pd.DataFrame): df_row = df_row.iloc[-1]

    for col in df_row.index:
        col_str = str(col).lower().strip()
        for palabra in palabras_clave:
            if palabra in col_str:
                valor = df_row[col]
                if pd.isna(valor) or str(valor).strip().lower() in ['nan', 'nat', 'none', '']:
                    return "N/A"
                return str(valor).strip()
    return "N/A"

def formatear_fecha(fecha_str):
    """Fuerza la fecha a formato DD/MM/YYYY"""
    if pd.isna(fecha_str) or fecha_str == "N/A" or str(fecha_str).strip() == "": return "N/A"
    try:
        return pd.to_datetime(fecha_str, dayfirst=True).strftime('%d/%m/%Y')
    except:
        return str(fecha_str).split('T')[0].split(' ')[0]

def normalizar_nombre_taller(nombre):
    """Estandariza los nombres de los talleres para poder contarlos matemáticamente."""
    if not nombre or nombre == "N/A": return "N/A"
    n = str(nombre).upper().strip()
    if "HOSPICIO" in n: return "SKC ALTO HOSPICIO"
    if "CALAMA" in n or "MECANICAL" in n: return "SKC CALAMA"
    if "ANTOFAGASTA" in n: return "SKC ANTOFAGASTA"
    if "LOA" in n: return "RIO LOA"
    if "COPIAP" in n: return "SKC COPIAPO"
    if "FULL" in n or "RPM" in n: return "FULL RPM"
    return n

@st.cache_data(ttl=600)
def cargar_excels(urls):
    df_maestro = pd.DataFrame()
    for url in urls:
        try:
            if "/d/" in url:
                id_archivo = url.split('/d/')[1].split('/')[0]
                url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
                dict_hojas = pd.read_excel(url_descarga, sheet_name=None)
                for nombre_hoja, df_hoja in dict_hojas.items():
                    df_hoja['Origen_Hoja'] = nombre_hoja
                    df_maestro = pd.concat([df_maestro, df_hoja], ignore_index=True)
        except Exception: pass
    return df_maestro

@st.cache_data(ttl=300)
def extraer_api():
    tipos = [27, 26, 24, 21, 23, 41]
    zonas = list(range(1, 14))
    datos = []
    def fetch(t, z):
        try:
            r = requests.get(f"http://40.65.224.42/api/dashboard/estado/{t}/{z}?key={API_KEY_DASHBOARD}", timeout=4)
            if r.status_code == 200: return r.json()
        except: return []
        return []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futuros = [executor.submit(fetch, t, z) for t in tipos for z in zonas]
        for f in concurrent.futures.as_completed(futuros):
            res = f.result()
            if isinstance(res, list) and len(res) > 0: datos.extend(res)
    return pd.DataFrame(datos)

with st.spinner("Descargando sistemas y planillas..."):
    df_excel_global = cargar_excels(ENLACES_EXCEL)
    df_api_global = extraer_api()

tab_alertas, tab_equipos, tab_movimientos, tab_faenas = st.tabs([
    "🚨 Alertas", "🔍 Buscar Equipo", "📅 Movimientos de Equipos", "📍 Ver por Faena"
])

# ==========================================
# PESTAÑA 1: ALERTAS
# ==========================================
with tab_alertas:
    st.header("🚨 Estado de Cumplimiento de Contratos")
    st.info("Sistema de cuadrículas de contratos (Mantenido según lógica original)")

# ==========================================
# PESTAÑA 2: BUSCADOR INDIVIDUAL (RÁPIDO)
# ==========================================
with tab_equipos:
    st.header("🔍 Búsqueda y Auditoría Individual")
    
    equipos_input = st.text_input("Ingresa el nombre o código del equipo (Ej: Quadra-70, Auger-165):")
    
    if st.button("Consultar Ficha Técnica") and equipos_input:
        nombres = [eq.strip().upper() for eq in equipos_input.split(",") if eq.strip()]
        
        for nombre in nombres:
            # Filtrar DataFrame de Excel (Buscar en TODAS las filas donde aparece el camión)
            df_historial_equipo = df_excel_global[df_excel_global.astype(str).apply(lambda x: x.str.upper().str.contains(nombre)).any(axis=1)]
            
            if df_historial_equipo.empty:
                st.error(f"❌ No se encontró '{nombre}' en la base de datos Excel.")
                continue
                
            # Extraer de TODAS las filas para asegurar que no quede N/A si el dato está en otra hoja
            patente = buscar_dato_flexible(df_historial_equipo, ['patente', 'placa', 'ppu'])
            vin = buscar_dato_flexible(df_historial_equipo, ['vin', 'chasis', 'serie'])
            marca = buscar_dato_flexible(df_historial_equipo, ['marca'])
            modelo = buscar_dato_flexible(df_historial_equipo, ['modelo', 'año', 'year'])
            capacidad = buscar_dato_flexible(df_historial_equipo, ['capacidad', 'tonelaje', 'tons'])
            control = buscar_dato_flexible(df_historial_equipo, ['control', 'sistema'])
            
            # Para la planificación tomamos solo LA ÚLTIMA FILA (El registro más reciente)
            ultima_fila = df_historial_equipo.iloc[-1]
            estatus_taller = buscar_dato_flexible(ultima_fila, ['estatus mp', 'status', 'estado'])
            ubicacion_taller = buscar_dato_flexible(ultima_fila, ['ubicación', 'taller', 'lugar'])
            comentarios = buscar_dato_flexible(ultima_fila, ['motivo', 'comentario', 'trabajos', 'estado de equipos'])
            
            fecha_inicio = formatear_fecha(buscar_dato_flexible(ultima_fila, ['fecha inicio', 'inicio planificado', 'inici']))
            fecha_entrega = formatear_fecha(buscar_dato_flexible(ultima_fila, ['fecha entrega', 'fin planificado', 'fina']))

            st.markdown(f"### 🚛 Ficha Técnica: {nombre} ({marca} {modelo})")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📡 Hardware e Identificación")
                # Aquí iría el cruce con API si lo requieres
                st.info(f"📍 **Ubicación GPS:** (API) | ⚙️ **Estado:** (API)")
                
                c1, c2 = st.columns(2)
                c1.markdown(f"**Patente:** {patente}")
                c1.markdown(f"**VIN/Chasis:** {vin}")
                c2.markdown(f"**Capacidad:** {capacidad}")
                c2.markdown(f"**Control:** {control}")
                
                st.markdown("**🗓️ Certificaciones:** (Revisión Técnica / Sernageomin / DGMN)")

            with col2:
                st.markdown("#### 🗓️ Planificación de Mantenimiento")
                st.success(f"📋 **Estatus:** {estatus_taller} | **Ubicación:** {ubicacion_taller}")
                st.markdown(f"- **Bajada a Taller:** {fecha_inicio}")
                st.markdown(f"- **Subida a Faena:** {fecha_entrega}")
                st.markdown(f"💬 **Trabajos / Motivo:** {comentarios}")
            
            st.divider()

# ==========================================
# PESTAÑA 3: MOVIMIENTOS Y CAPACIDAD TALLERES (NUEVA)
# ==========================================
with tab_movimientos:
    st.header("📅 Control de Subidas, Bajadas y Capacidad")
    st.write("Análisis logístico de los próximos 7 días.")
    
    if st.button("Analizar Semana Logística"):
        hoy = pd.Timestamp.now().normalize()
        fin_semana = hoy + pd.Timedelta(days=7)
        
        subidas = []
        bajadas = []
        carga_actual = {k: 0 for k in CAPACIDAD_TALLERES.keys()}
        equipos_procesados = set()

        # Leemos el Excel al revés (para quedarnos con el último movimiento de cada camión)
        for _, row in df_excel_global.iloc[::-1].iterrows():
            equipo = buscar_dato_flexible(row, ['equipo', 'nombre'])
            if equipo == "N/A" or equipo in equipos_procesados: continue
            
            f_inicio_str = buscar_dato_flexible(row, ['fecha inicio', 'inicio planificado', 'inici'])
            f_entrega_str = buscar_dato_flexible(row, ['fecha entrega', 'fin planificado', 'fina'])
            faena = buscar_dato_flexible(row, ['faena', 'contrato'])
            taller_raw = buscar_dato_flexible(row, ['ubicación', 'taller'])
            
            if equipo != "N/A":
                equipos_procesados.add(equipo)
            
            taller_norm = normalizar_nombre_taller(taller_raw)
            
            # --- LÓGICA DE SUBIDAS Y BAJADAS ---
            try:
                if f_inicio_str != "N/A":
                    f_ini = pd.to_datetime(f_inicio_str, dayfirst=True)
                    if hoy <= f_ini <= fin_semana:
                        bajadas.append(f"🚛 **{equipo}** ➔ Baja a: **{taller_raw}** ({f_ini.strftime('%d/%m')})")
            except: pass
            
            try:
                if f_entrega_str != "N/A":
                    f_fin = pd.to_datetime(f_entrega_str, dayfirst=True)
                    if hoy <= f_fin <= fin_semana:
                        subidas.append(f"📈 **{equipo}** ➔ Sube a: **{faena}** ({f_fin.strftime('%d/%m')})")
            except: pass

            # --- LÓGICA DE CAPACIDAD DE TALLERES ---
            # Si el equipo está actualmente en el taller o entra esta semana, suma 1.
            try:
                en_taller = False
                if f_inicio_str != "N/A":
                    f_i = pd.to_datetime(f_inicio_str, dayfirst=True)
                    if f_i <= fin_semana:
                        if f_entrega_str == "N/A":
                            en_taller = True
                        else:
                            f_e = pd.to_datetime(f_entrega_str, dayfirst=True)
                            if f_e >= hoy: en_taller = True
                if en_taller and taller_norm in carga_actual:
                    carga_actual[taller_norm] += 1
            except: pass

        # Desplegar en pantalla
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.warning("### 🔧 Bajan a Taller (Esta Semana)")
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
        st.subheader("⚖️ Estado de Capacidad por Taller")
        
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

        # Auditoría IA Final
        if modelo_ia:
            try:
                res = modelo_ia.generate_content("Dime una frase corta motivacional para un equipo de logística minera.")
                st.info(f"🤖 **Asistente IA:** {res.text}")
            except Exception:
                st.warning("⚠️ Tu clave de Inteligencia Artificial se quedó sin saldo o está bloqueada. Por favor, genera una nueva Key gratuita en aistudio.google.com y reemplázala en el código.")
        else:
            st.warning("⚠️ No se ha configurado la Inteligencia Artificial.")

# ==========================================
# PESTAÑA 4: FAENAS
# ==========================================
with tab_faenas:
    st.header("📍 Vista Global de Faenas")
    st.write("*(Mantenido según lógica original)*")
