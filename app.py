import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timezone
import requests
import concurrent.futures

# ==========================================
# 1. CONFIGURACIÓN CORPORATIVA Y CLAVES
# ==========================================
st.set_page_config(page_title="Control Flota Enaex", layout="wide", page_icon="🚛")

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
except Exception:
    GEMINI_API_KEY = "PEGA_TU_KEY_DE_GEMINI_AQUI_SI_NO_USAS_SECRETS"

if GEMINI_API_KEY and GEMINI_API_KEY != "PEGA_TU_KEY_DE_GEMINI_AQUI_SI_NO_USAS_SECRETS":
    genai.configure(api_key=GEMINI_API_KEY)

API_KEY_DASHBOARD = "CX92wBe9wV2NLUMyFE6PzvcyqTWyBPr5"

ENLACES_EXCEL = [
    "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing",
    "https://docs.google.com/spreadsheets/d/1VrDHEb-D7oeypyYdhUpd3_tw_jggTu3K/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"
]

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
# 2. MOTOR DE IA BLINDADO Y DIAGNÓSTICO
# ==========================================
def invocar_ia_segura(instruccion, stream=False):
    """Invoca la IA manejando explícitamente los límites de cuota."""
    modelos_a_probar = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    ultimo_error = "No se configuró la API Key."
    
    if not GEMINI_API_KEY or "PEGA_TU_KEY" in GEMINI_API_KEY:
        raise Exception(ultimo_error)

    for nombre_modelo in modelos_a_probar:
        try:
            modelo = genai.GenerativeModel(nombre_modelo)
            if stream:
                return modelo.generate_content(instruccion, stream=True)
            else:
                return modelo.generate_content(instruccion)
        except Exception as e:
            error_str = str(e).lower()
            # Interceptamos el error de cuota inmediatamente
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                raise Exception("CUOTA_EXCEDIDA")
            ultimo_error = str(e)
            continue 
            
    raise Exception(f"Error Técnico: {ultimo_error}")

# ==========================================
# 3. EXTRACCIÓN FLEXIBLE Y FORMATO DE FECHAS
# ==========================================
def buscar_dato_flexible(df_busqueda, palabras_clave):
    """Busca aproximaciones de nombres de columnas (Fuzzy Search) iterando de la más nueva a la más vieja."""
    if df_busqueda is None or df_busqueda.empty:
        return "N/A"
    
    if not isinstance(df_busqueda, pd.DataFrame):
        df_busqueda = df_busqueda.to_frame().T

    for _, fila in df_busqueda.iloc[::-1].iterrows():
        for col in fila.index:
            col_str = str(col).lower().strip()
            for palabra in palabras_clave:
                if palabra in col_str:
                    val = fila[col]
                    if not pd.isna(val) and str(val).strip().lower() not in ['nan', 'nat', 'none', '']:
                        return str(val).strip()
    return "N/A"

def formatear_fecha_limpia(fecha_str):
    """Fuerza cualquier formato de fecha a DD/MM/YYYY limpio."""
    if pd.isna(fecha_str) or str(fecha_str).strip() in ['None', '', 'nan', 'NaT', 'N/A']: 
        return 'N/A'
    try:
        return pd.to_datetime(fecha_str, dayfirst=True).strftime('%d/%m/%Y')
    except:
        return str(fecha_str).split('T')[0].split(' ')[0]

def fusionar_datos(api_val, exc_val):
    if api_val not in ["N/A", "None", "", "nan"] and pd.notna(api_val): return api_val
    if exc_val not in ["N/A", "None", "", "nan"] and pd.notna(exc_val): return exc_val
    return "N/A"

# ==========================================
# 4. CARGA DE DATOS MULTIHILO
# ==========================================
@st.cache_data(ttl=600) 
def cargar_multiples_excel(lista_urls):
    df_maestro = pd.DataFrame()
    total_hojas = 0
    for url in lista_urls:
        if not url or "PEGA_AQUI" in url: continue
        try:
            if "/d/" in url:
                id_archivo = url.split('/d/')[1].split('/')[0]
                url_descarga = f"https://drive.google.com/uc?export=download&id={id_archivo}"
                diccionario_hojas = pd.read_excel(url_descarga, sheet_name=None)
                total_hojas += len(diccionario_hojas)
                for nombre_hoja, df_hoja in diccionario_hojas.items():
                    df_hoja['Origen_Datos'] = f"Hoja: {nombre_hoja}"
                    df_maestro = pd.concat([df_maestro, df_hoja], ignore_index=True)
        except Exception:
            pass 
    return df_maestro.dropna(how='all'), total_hojas

def fetch_api(tipo, zona, api_key):
    url = f"http://40.65.224.42/api/dashboard/estado/{tipo}/{zona}?key={api_key}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
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
    return df_api

# ==========================================
# 5. INTERFAZ GRÁFICA PRINCIPAL
# ==========================================
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/e/e8/Enaex_logo.svg" 
             onerror="this.style.display='none';" 
             height="55" style="object-fit: contain;">
        <h1 style="margin: 0; padding: 0; font-size: 2.2rem; display: flex; align-items: center; gap: 10px;">
            🚛 Centro de Control: Flota y Auditoría
        </h1>
    </div>
    <hr>
    """, unsafe_allow_html=True
)

with st.spinner("Sincronizando Sistema Vivo y Bases de Excel..."):
    df_api_global = extraer_datos_api_paralelo()
    df_excel_global, cant_hojas = cargar_multiples_excel(ENLACES_EXCEL)

if not df_api_global.empty:
    cols_necesarias = ['rev_fecha_expiracion', 'ser_fecha_expiracion', 'dgmn_fecha_expiracion', 'nombre', 'nombre_faena', 'horas_ult', 'nombre_es', 'marca_nombre', 'ultimo_estado', 'ultimo_lugar', 'control', 'patente', 'vin', 'chasis', 'modelo']
    for col in cols_necesarias:
        if col not in df_api_global.columns: df_api_global[col] = None

    df_api_global['Estado_Deducido'] = df_api_global['nombre_es'].fillna(df_api_global['ultimo_estado']).fillna('OK')
    df_api_global['Lugar_Deducido'] = df_api_global['ultimo_lugar'].fillna('Faena')

tab_alertas, tab_equipos, tab_faenas = st.tabs(["🚨 Alertas del Sistema", "🔍 Buscar y Carta Gantt", "📍 Ver por Faena"])

# ---------------------------------------------------------
# PESTAÑA 1: ALERTAS DEL SISTEMA
# ---------------------------------------------------------
with tab_alertas:
    st.header("🚨 Panel de Alertas Tempranas y Contratos")
    if df_api_global.empty:
        st.warning("No se pudieron cargar los datos de la API.")
    else:
        st.subheader("⚖️ Estado de Cumplimiento de Contratos (Camiones Fábrica)")
        alertas_contrato_rojas = []
        alertas_contrato_amarillas = []
        alertas_correctivas = []
        
        for faena, info in CONTRATOS_FAENA.items():
            df_faena_alerta = df_api_global[df_api_global['nombre_faena'].astype(str).str.strip().str.lower() == faena.lower()]
            if df_faena_alerta.empty: continue
            df_fabrica = df_faena_alerta[df_faena_alerta['nombre'].astype(str).str.contains('AUGER|QUADRA', case=False, na=False)]
            mask_lugar_faena = df_fabrica['Lugar_Deducido'].str.lower() == 'faena'
            mask_correctivo = df_fabrica['Estado_Deducido'].str.lower().str.contains('correctivo', na=False)
            mask_catastrofico = df_fabrica['Estado_Deducido'].str.lower().str.contains('catastr', na=False)
            
            equipos_en_correctivo = df_fabrica[mask_lugar_faena & mask_correctivo]['nombre'].tolist()
            if equipos_en_correctivo: alertas_correctivas.append({'faena': faena, 'equipos': equipos_en_correctivo})
            
            mask_operativos = mask_lugar_faena & ~mask_catastrofico
            df_operativos = df_fabrica[mask_operativos]
            df_fuera = df_fabrica[~mask_operativos] 
            
            cant_operativos = len(df_operativos)
            requeridos = info['Contrato']
            
            if cant_operativos < requeridos:
                alertas_contrato_rojas.append({'faena': faena, 'operativos': cant_operativos, 'requeridos': requeridos, 'faltan': requeridos - cant_operativos, 'nombres_op': df_operativos['nombre'].tolist(), 'nombres_fuera': df_fuera['nombre'].tolist()})
            elif cant_operativos == requeridos:
                alertas_contrato_amarillas.append({'faena': faena, 'operativos': cant_operativos, 'requeridos': requeridos, 'nombres_op': df_operativos['nombre'].tolist(), 'nombres_fuera': df_fuera['nombre'].tolist()})
                
        if alertas_contrato_rojas or alertas_contrato_amarillas or alertas_correctivas:
            todas_alertas = []
            for a in alertas_contrato_rojas: todas_alertas.append({"tipo": "error", "faena": a['faena'], "faltan": a['faltan'], "op": a['operativos'], "req": a['requeridos'], "nombres_op": a['nombres_op'], "nombres_fuera": a['nombres_fuera']})
            for a in alertas_contrato_amarillas: todas_alertas.append({"tipo": "warning", "faena": a['faena'], "op": a['operativos'], "req": a['requeridos'], "nombres_op": a['nombres_op'], "nombres_fuera": a['nombres_fuera']})
            for a in alertas_correctivas: todas_alertas.append({"tipo": "info", "faena": a['faena'], "equipos": a['equipos']})
            
            columnas_grid = st.columns(6)
            for i, alerta in enumerate(todas_alertas):
                with columnas_grid[i % 6]:
                    if alerta["tipo"] == "error":
                        st.error(f"**{alerta['faena']}**\n\n🔴 Faltan: {alerta['faltan']}\n\n*{alerta['op']} de {alerta['req']}*")
                    elif alerta["tipo"] == "warning":
                        st.warning(f"**{alerta['faena']}**\n\n🟡 Al límite\n\n*{alerta['op']} de {alerta['req']}*")
                    elif alerta["tipo"] == "info":
                        st.info(f"**{alerta['faena']}**\n\n🔧 En Taller:\n\n*{len(alerta['equipos'])} eq.*")
        else:
            st.success("✅ Excelente. Todos los contratos tienen los equipos operativos requeridos.")

# ---------------------------------------------------------
# PESTAÑA 2: CARTA GANTT Y BÚSQUEDA DE EQUIPOS
# ---------------------------------------------------------
with tab_equipos:
    st.header("📅 Planificación de la Semana (Carta Gantt)")
    with st.expander("Ver Resumen de Subidas y Bajadas", expanded=False):
        st.write("Cálculo automático de movimientos basados en las fechas del Excel para los próximos 7 días.")
        if st.button("Generar Resumen Semanal"):
            hoy = pd.Timestamp.now().normalize()
            fin_semana = hoy + pd.Timedelta(days=7)
            bajadas = []
            subidas = []
            
            if not df_excel_global.empty:
                for _, row in df_excel_global.iterrows():
                    equipo = buscar_dato_flexible(row, ['equipo', 'nombre'])
                    if equipo == "N/A": continue
                    
                    f_ini_str = buscar_dato_flexible(row, ['inici', 'bajada', 'ingreso'])
                    f_fin_str = buscar_dato_flexible(row, ['fina', 'subida', 'entrega'])
                    
                    try:
                        if f_ini_str != "N/A":
                            f_ini = pd.to_datetime(f_ini_str, dayfirst=True)
                            if hoy <= f_ini <= fin_semana:
                                bajadas.append(f"{equipo} ({f_ini.strftime('%d/%m')})")
                    except: pass
                    
                    try:
                        if f_fin_str != "N/A":
                            f_fin = pd.to_datetime(f_fin_str, dayfirst=True)
                            if hoy <= f_fin <= fin_semana:
                                subidas.append(f"{equipo} ({f_fin.strftime('%d/%m')})")
                    except: pass
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.warning(f"📉 **Bajan a Taller (Próximos 7 días):**\n\n" + ("\n".join([f"- {x}" for x in set(bajadas)]) if bajadas else "Ninguno planificado."))
            with col_g2:
                st.success(f"📈 **Suben a Faena (Próximos 7 días):**\n\n" + ("\n".join([f"- {x}" for x in set(subidas)]) if subidas else "Ninguno planificado."))
                
            # Comentario IA (Si hay cuota)
            try:
                prompt_semana = f"Resumen logístico: Bajan a taller: {', '.join(set(bajadas))}. Suben a faena: {', '.join(set(subidas))}. Escribe un mensaje breve de ánimo al equipo de Enaex para esta semana."
                respuesta = invocar_ia_segura(prompt_semana, stream=False)
                st.info(f"🤖 **Comentario IA:** {respuesta.text}")
            except Exception as e:
                if "CUOTA_EXCEDIDA" in str(e):
                    st.caption("*(Nota: Comentario de IA omitido por límite de consultas gratuitas. El resumen de fechas superior es preciso).*")

    st.markdown("---")
    st.header("🔍 Búsqueda y Auditoría Individual")
    equipo_a_buscar = st.text_input("Ingresa uno o varios equipos (Ej: Quadra-1060, Auger-165):")

    if st.button("Consultar Estado"):
        if not equipo_a_buscar:
            st.warning("⚠️ Escribe al menos un equipo para buscar.")
        else:
            terminos = [t.strip().upper() for t in str(equipo_a_buscar).split(",") if t.strip()]
            fichas_generadas = [] 
            
            for termino in terminos:
                df_api_eq = pd.DataFrame()
                if not df_api_global.empty:
                    df_api_eq = df_api_global[df_api_global['nombre'].astype(str).str.upper().str.contains(termino, na=False)]
                
                df_excel_eq = pd.DataFrame()
                if not df_excel_global.empty:
                    # Filtramos todas las filas donde aparezca el equipo
                    df_excel_eq = df_excel_global[df_excel_global.astype(str).apply(lambda x: x.str.upper().str.contains(termino)).any(axis=1)]
                
                if df_api_eq.empty and df_excel_eq.empty:
                    st.error(f"❌ No se encontró coincidencia en API ni en Excel para: **{termino}**")
                    continue
                
                row_api = df_api_eq.iloc[0] if not df_api_eq.empty else None
                nombre_real = row_api.get('nombre', termino) if row_api is not None else termino
                ubi_api = str(row_api.get('Lugar_Deducido', 'N/A')) if row_api is not None else "N/A"
                faena_api = str(row_api.get('nombre_faena', 'N/A')) if row_api is not None else "N/A"
                estado_api = str(row_api.get('Estado_Deducido', 'N/A')) if row_api is not None else "N/A"
                hrs_api = str(row_api.get('horas_ult', 'N/A')) if row_api is not None else "N/A"
                
                rt_api = formatear_fecha_limpia(row_api.get('rev_fecha_expiracion')) if row_api is not None else "N/A"
                sngm_api = formatear_fecha_limpia(row_api.get('ser_fecha_expiracion')) if row_api is not None else "N/A"
                dgmn_api = formatear_fecha_limpia(row_api.get('dgmn_fecha_expiracion')) if row_api is not None else "N/A"
                
                # Extracción Inteligente en todas las filas del Excel
                ex_patente = buscar_dato_flexible(df_excel_eq, ['patente', 'placa', 'ppu'])
                ex_vin = buscar_dato_flexible(df_excel_eq, ['vin', 'chasis', 'serie'])
                ex_marca = buscar_dato_flexible(df_excel_eq, ['marca'])
                ex_modelo = buscar_dato_flexible(df_excel_eq, ['modelo', 'año', 'year'])
                ex_control = buscar_dato_flexible(df_excel_eq, ['control', 'sistema'])
                
                estatus = buscar_dato_flexible(df_excel_eq, ['estatus mp', 'estado', 'status'])
                ubicacion_plan = buscar_dato_flexible(df_excel_eq, ['ubicación', 'lugar', 'taller'])
                comentarios = buscar_dato_flexible(df_excel_eq, ['comentario', 'trabajos', 'motivo'])
                
                f_ini = formatear_fecha_limpia(buscar_dato_flexible(df_excel_eq, ['inici', 'bajada', 'inicio planificado']))
                f_fin = formatear_fecha_limpia(buscar_dato_flexible(df_excel_eq, ['fina', 'subida', 'fin planificado', 'fecha entrega']))
                
                patente = fusionar_datos(str(row_api.get('patente', 'N/A')) if row_api is not None else "N/A", ex_patente)
                vin = fusionar_datos(str(row_api.get('vin', 'N/A')) if row_api is not None else str(row_api.get('chasis', 'N/A')) if row_api is not None else "N/A", ex_vin)
                marca_modelo = fusionar_datos(str(row_api.get('marca_nombre', 'N/A')) if row_api is not None else "N/A", f"{ex_marca} {ex_modelo}".strip())
                control = fusionar_datos(str(row_api.get('control', 'N/A')) if row_api is not None else "N/A", ex_control)

                with st.container():
                    st.markdown(f"### 🚛 Ficha Técnica: {nombre_real}")
                    col_sis, col_plan = st.columns(2)
                    
                    with col_sis:
                        st.markdown("#### 📡 En Vivo (Hardware y Sistema)")
                        if row_api is not None:
                            st.info(f"📍 **Ubicación:** {ubi_api} ({faena_api}) | ⚙️ **Estado:** {estado_api}")
                        else:
                            st.warning("⚠️ Sin conexión GPS/Sistema en vivo para este equipo.")
                        
                        c1, c2 = st.columns(2)
                        c1.markdown(f"**Patente:** {patente}")
                        c1.markdown(f"**Marca/Modelo:** {marca_modelo}")
                        c1.markdown(f"**VIN/Chasis:** {vin}")
                        c2.markdown(f"**Horómetro:** {hrs_api} hrs")
                        c2.markdown(f"**Control:** {control}")
                        
                        st.markdown("**🗓️ Certificaciones (Plazos):**")
                        st.caption(f"Revisión Técnica: {rt_api} | Sernageomin: {sngm_api} | DGMN: {dgmn_api}")
                            
                    with col_plan:
                        st.markdown("#### 🗓️ Planificación (Último Registro)")
                        if not df_excel_eq.empty:
                            st.success(f"📋 **Estatus Taller:** {estatus} | **Ubicación:** {ubicacion_plan}")
                            st.markdown(f"**🗓️ Fechas de Planificación:**")
                            st.markdown(f"- **Bajada / Inicio:** {f_ini}")
                            st.markdown(f"- **Subida / Entrega:** {f_fin}")
                            st.markdown(f"💬 **Últimos Trabajos:** {comentarios}")
                        else:
                            st.warning("⚠️ No hay registros en los Excel de planificación.")
                            
                    st.divider()
                    
                    texto_auditoria = f"Equipo {nombre_real}. API: Ubicación {ubi_api}, Estado {estado_api}. Excel: Estatus {estatus}, Ubicación {ubicacion_plan}, Bajada {f_ini}, Subida {f_fin}, Trabajos {comentarios}."
                    fichas_generadas.append(texto_auditoria)

            if fichas_generadas:
                st.markdown("### 🤖 Auditoría Automática (Buscando Incongruencias)")
                st.caption("La IA cruza la información mostrada arriba para alertar sobre desvíos.")
                
                prompt_auditor = f"""
                Eres un auditor de mantenimiento. Revisa estos datos crudos.
                Busca incongruencias entre API y Excel (ej: API dice operando, pero Excel dice en taller).
                Si las fechas muestran atraso al día de hoy, menciónalo.
                Si todo cuadra, responde: "✅ Todo coincide correctamente."
                Sé directo, máximo 2 líneas por equipo.
                DATOS A AUDITAR: {chr(10).join(fichas_generadas)}
                """
                
                try:
                    respuesta_stream = invocar_ia_segura(prompt_auditor, stream=True)
                    st.write_stream((chunk.text for chunk in respuesta_stream if chunk.text))
                except Exception as e:
                    error_msg = str(e)
                    if "CUOTA_EXCEDIDA" in error_msg:
                        st.warning("⚠️ **Límite gratuito de IA alcanzado.** Por favor espera unos minutos antes de volver a consultar a la Inteligencia Artificial. ¡Tus fichas técnicas superiores siguen operativas!")
                    else:
                        st.error(f"❌ **Fallo de Conexión IA:** {error_msg}")

# ---------------------------------------------------------
# PESTAÑA 3: VISTA POR FAENA
# ---------------------------------------------------------
with tab_faenas:
    st.header("📍 Resumen Operativo por Faena")
    if df_api_global.empty:
        st.warning("No hay datos de API disponibles.")
    else:
        faenas_disponibles = sorted(df_api_global['nombre_faena'].dropna().unique().tolist())
        faena_seleccionada = st.selectbox("Seleccione una Faena:", ["--- Seleccionar Faena ---"] + faenas_disponibles)
        
        if faena_seleccionada != "--- Seleccionar Faena ---":
            df_faena = df_api_global[df_api_global['nombre_faena'] == faena_seleccionada].copy()
            st.success(f"🚛 {len(df_faena)} equipos reportados actualmente en **{faena_seleccionada}**")
            
            cols_vista = {
                'nombre': 'Equipo', 'marca_nombre': 'Marca', 'Lugar_Deducido': 'Lugar/Ubicación',
                'horas_ult': 'Horómetro', 'Estado_Deducido': 'Estado Actual'
            }
            
            cols_existentes = [c for c in cols_vista.keys() if c in df_faena.columns]
            df_mostrar = df_faena[cols_existentes].rename(columns=cols_vista).fillna("-")
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
