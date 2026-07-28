import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timezone
import requests
import concurrent.futures

# ==========================================
# 1. CONFIGURACIÓN CORPORATIVA Y CLAVES
# ==========================================
st.set_page_config(page_title="Copiloto Flota Enaex", layout="wide", page_icon="🚛")

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"] 
except Exception:
    GEMINI_API_KEY = "PEGA_TU_KEY_DE_GEMINI_AQUI_SI_NO_USAS_SECRETS"

genai.configure(api_key=GEMINI_API_KEY)

# API del Sistema de Planificación
API_KEY_DASHBOARD = "CX92wBe9wV2NLUMyFE6PzvcyqTWyBPr5"

# Tus Excels
ENLACES_EXCEL = [
    "https://docs.google.com/spreadsheets/d/1PUlnTUm_CpkvrpVoKJN_3nyD9khxITDV/edit?usp=sharing",
    "https://docs.google.com/spreadsheets/d/1VrDHEb-D7oeypyYdhUpd3_tw_jggTu3K/edit?usp=drive_link&ouid=112672268024787990541&rtpof=true&sd=true"
]

# Diccionario Global de Contratos
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
# 2. MOTOR DE IA Y EXTRACCIÓN DE DATOS
# ==========================================
def invocar_ia_segura(instruccion, stream=False):
    """Invoca la IA usando exclusivamente el modelo más estable y rápido."""
    try:
        # Forzamos el uso de la versión estable 1.5 flash para evitar errores 404 de modelos experimentales.
        modelo = genai.GenerativeModel("gemini-1.5-flash")
        
        if stream:
            return modelo.generate_content(instruccion, stream=True)
        else:
            return modelo.generate_content(instruccion)
            
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str:
            raise Exception("429_QUOTA")
        raise e

@st.cache_data(ttl=600) 
def cargar_multiples_excel(lista_urls):
    df_maestro = pd.DataFrame()
    total_hojas = 0
    archivos_leidos = 0
    
    for url in lista_urls:
        if not url or "PEGA_AQUI" in url: continue
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
    return df_maestro.dropna(how='all'), total_hojas, archivos_leidos

def fetch_api(tipo, zona, api_key):
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
    if not df_api.empty:
        df_api['Origen_Datos'] = "API Sistema en Tiempo Real"
    return df_api

def filtrar_por_multiples_equipos(df, texto_busqueda):
    if df.empty or not str(texto_busqueda).strip(): return df
    
    # Separar por comas y limpiar espacios
    terminos = [t.strip().lower() for t in str(texto_busqueda).split(",") if t.strip()]
    if not terminos: return pd.DataFrame()
    
    mask = pd.Series(False, index=df.index)
    for termino in terminos:
        mask = mask | df.astype(str).apply(lambda x: x.str.lower().str.contains(termino, na=False)).any(axis=1)
    
    return df[mask]

def obtener_dato_seguro(row, posibles_columnas, default="-"):
    """Busca un dato en el Excel probando varios nombres de columna posibles."""
    for col in posibles_columnas:
        if col in row.index and pd.notna(row[col]) and str(row[col]).strip() != "":
            # Si es fecha, intentar formatearla limpiamente
            val = str(row[col]).strip()
            if "00:00:00" in val:
                val = val.split(" ")[0]
            return val
    return default

@st.cache_data(ttl=3600)
def analizar_movimientos_semana(df_excel, fecha_str):
    if df_excel.empty: return "No hay datos de planificación disponibles."
    
    # Filtrar solo hojas relevantes y quitar columnas basura
    mask = df_excel['Origen_Datos'].astype(str).str.contains('proceso|mov. equipos', case=False, na=False)
    df_subset = df_excel[mask].dropna(how='all', axis=1).dropna(how='all', axis=0)
    
    cols_vitales = [c for c in df_subset.columns if str(c).lower().strip() in ['equipo', 'faena', 'ubicación', 'ubicacion', 'motivo', 'status mp', 'fecha inici', 'fecha fina']]
    df_reducido = df_subset[cols_vitales] if cols_vitales else df_subset
    
    csv_data = df_reducido.to_csv(index=False)[:3500] 
    
    instruccion = f"""
    Eres el Planificador. Hoy es {fecha_str}.
    Ignora los colores o columnas de la carta Gantt. Basa tu análisis SOLO en estas dos columnas:
    1. 'Fecha Inici': Si cae dentro de los próximos 7 días, el camión BAJA A TALLER.
    2. 'Fecha Fina': Si cae dentro de los próximos 7 días, el camión SUBE A FAENA.
    
    Formato:
    ### 🟢 Equipos que SUBEN a Faena
    * **[Nombre]** (Motivo: ...)
    ### 🔴 Equipos que BAJAN a Taller
    * **[Nombre]** (Motivo: ...)
    
    DATOS:
    {csv_data}
    """
    try:
        respuesta = invocar_ia_segura(instruccion, stream=False)
        return respuesta.text
    except Exception as e:
        if str(e) == "429_QUOTA": return "⚠️ **Límite de IA alcanzado.** Revisa las fechas directamente en tu Excel."
        return f"⚠️ Error procesando la semana: {e}"

# ==========================================
# 3. INTERFAZ GRÁFICA PRINCIPAL
# ==========================================
# Solución definitiva al logo: Usamos un PNG público de alta compatibilidad. 
# Si la red lo bloquea, el onerror lo oculta para no mostrar el icono de imagen rota.
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Enaex_logo.svg/512px-Enaex_logo.svg.png" 
             onerror="this.style.display='none';" 
             height="55" style="object-fit: contain;">
        <h1 style="margin: 0; padding: 0; font-size: 2.2rem; display: flex; align-items: center; gap: 10px;">
            🚛 Centro de Control: Flota y Auditoría
        </h1>
    </div>
    """, unsafe_allow_html=True
)

with st.spinner("Sincronizando Sistema Vivo y Bases de Excel..."):
    df_api_global = extraer_datos_api_paralelo()
    df_excel_global, cant_hojas, cant_archivos = cargar_multiples_excel(ENLACES_EXCEL)

if not df_api_global.empty:
    cols_necesarias = [
        'rev_fecha_expiracion', 'ser_fecha_expiracion', 'dgmn_fecha_expiracion', 
        'nombre', 'nombre_faena', 'horas_ult', 'nombre_es', 
        'marca_nombre', 'ultimo_estado', 'ultimo_lugar', 'control',
        'patente', 'vin', 'chasis', 'modelo'
    ]
    for col in cols_necesarias:
        if col not in df_api_global.columns:
            df_api_global[col] = None

    df_api_global['Estado_Deducido'] = df_api_global['nombre_es'].fillna(df_api_global['ultimo_estado']).fillna('OK')
    df_api_global['Estado_Deducido'] = df_api_global['Estado_Deducido'].replace(['', 'None', 'nan'], 'OK')
    
    df_api_global['Lugar_Deducido'] = df_api_global['ultimo_lugar'].fillna('Faena')
    df_api_global['Lugar_Deducido'] = df_api_global['Lugar_Deducido'].replace(['', 'None', 'nan'], 'Faena')

tab_alertas, tab_equipos, tab_faenas = st.tabs([
    "🚨 Alertas del Sistema", 
    "🔍 Buscar Equipos", 
    "📍 Ver por Faena"
])

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
            if equipos_en_correctivo:
                alertas_correctivas.append({'faena': faena, 'equipos': equipos_en_correctivo})
            
            # Correctivos en faena SÍ suman como operativos, solo catastróficos restan.
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
                        with st.expander("Ver detalle"):
                            st.caption("**OK:** " + (", ".join(alerta['nombres_op']) if alerta['nombres_op'] else "Ninguno"))
                            st.caption("**Falta:** " + (", ".join(alerta['nombres_fuera']) if alerta['nombres_fuera'] else "Ninguno"))
                    elif alerta["tipo"] == "warning":
                        st.warning(f"**{alerta['faena']}**\n\n🟡 Al límite\n\n*{alerta['op']} de {alerta['req']}*")
                        with st.expander("Ver detalle"):
                            st.caption("**OK:** " + (", ".join(alerta['nombres_op']) if alerta['nombres_op'] else "Ninguno"))
                            st.caption("**Falta:** " + (", ".join(alerta['nombres_fuera']) if alerta['nombres_fuera'] else "Ninguno"))
                    elif alerta["tipo"] == "info":
                        st.info(f"**{alerta['faena']}**\n\n🔧 En Taller:\n\n*{len(alerta['equipos'])} eq.*")
                        with st.expander("Ver detalle"):
                            for eq in alerta['equipos']: st.caption(f"- {eq}")
        else:
            st.success("✅ Excelente. Todos los contratos tienen los equipos operativos requeridos.")
            
        st.divider()
        st.subheader("📅 Certificaciones por Vencer (Próximos 30 días)")
        hoy = pd.Timestamp(datetime.now(timezone.utc))
        dias_rt = (pd.to_datetime(df_api_global['rev_fecha_expiracion'], errors='coerce', utc=True) - hoy).dt.days
        dias_sngm = (pd.to_datetime(df_api_global['ser_fecha_expiracion'], errors='coerce', utc=True) - hoy).dt.days
        dias_dgmn = (pd.to_datetime(df_api_global['dgmn_fecha_expiracion'], errors='coerce', utc=True) - hoy).dt.days
        
        c1, c2, c3 = st.columns(3)
        with c1:
            alertas_rt = df_api_global[dias_rt <= 30][['nombre', 'nombre_faena']].copy()
            alertas_rt['Dias'] = dias_rt[dias_rt <= 30]
            st.error(f"📄 Revisión Técnica ({len(alertas_rt)})")
            for _, row in alertas_rt.sort_values(by="Dias").iterrows():
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{'🔥 VENCIDO' if row['Dias'] < 0 else f'Quedan {int(row['Dias'])} días'}*")
        with c2:
            alertas_sngm = df_api_global[dias_sngm <= 30][['nombre', 'nombre_faena']].copy()
            alertas_sngm['Dias'] = dias_sngm[dias_sngm <= 30]
            st.warning(f"⛏️ Sernageomin ({len(alertas_sngm)})")
            for _, row in alertas_sngm.sort_values(by="Dias").iterrows():
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{'🔥 VENCIDO' if row['Dias'] < 0 else f'Quedan {int(row['Dias'])} días'}*")
        with c3:
            alertas_dgmn = df_api_global[dias_dgmn <= 30][['nombre', 'nombre_faena']].copy()
            alertas_dgmn['Dias'] = dias_dgmn[dias_dgmn <= 30]
            st.info(f"💣 DGMN ({len(alertas_dgmn)})")
            for _, row in alertas_dgmn.sort_values(by="Dias").iterrows():
                st.markdown(f"**{row['nombre']}** ({row['nombre_faena']}) - *{'🔥 VENCIDO' if row['Dias'] < 0 else f'Quedan {int(row['Dias'])} días'}*")

# ---------------------------------------------------------
# PESTAÑA 2: BÚSQUEDA Y AUDITORÍA DE EQUIPOS
# ---------------------------------------------------------
with tab_equipos:
    with st.expander("Ver Resumen de Subidas y Bajadas (Carta Gantt)"):
        st.info("💡 Haz clic en el botón para que el sistema analice las subidas y bajadas de la semana.")
        if st.button("🤖 Analizar Semana"):
            with st.spinner("Leyendo planificación..."):
                st.markdown(analizar_movimientos_semana(df_excel_global, datetime.now().strftime("%d de %B de %Y")))
            
    st.divider()
    
    st.header("🔍 Búsqueda y Estado de Equipos")
    st.caption("Ingresa uno o varios equipos separados por coma (Ej: Quadra-1049, Auger-165, Quadra-91):")
    equipo_a_buscar = st.text_input("Buscar:", label_visibility="collapsed")

    if st.button("Consultar Estado"):
        if not equipo_a_buscar:
            st.warning("⚠️ Escribe al menos un equipo para buscar.")
        else:
            # Separar y limpiar términos buscados
            terminos = [t.strip().upper() for t in str(equipo_a_buscar).split(",") if t.strip()]
            
            fichas_generadas = [] # Guardaremos texto aquí para dárselo a la IA al final
            
            for termino in terminos:
                # Filtrar data cruda
                df_api_eq = pd.DataFrame()
                if not df_api_global.empty:
                    df_api_eq = df_api_global[df_api_global['nombre'].astype(str).str.upper().str.contains(termino, na=False)]
                
                df_excel_eq = pd.DataFrame()
                if not df_excel_global.empty:
                    df_excel_eq = df_excel_global[df_excel_global.astype(str).apply(lambda x: x.str.upper().str.contains(termino)).any(axis=1)]
                
                if df_api_eq.empty and df_excel_eq.empty:
                    st.error(f"❌ No se encontró ninguna coincidencia para: **{termino}**")
                    continue
                
                # --- CONSTRUIR LA FICHA TÉCNICA VISUAL ---
                with st.container():
                    # Encontrar el nombre real del equipo
                    nombre_real = termino
                    marca_real = ""
                    if not df_api_eq.empty:
                        nombre_real = df_api_eq.iloc[0].get('nombre', termino)
                        marca_real = df_api_eq.iloc[0].get('marca_nombre', '')
                    
                    st.markdown(f"### 🚛 Ficha Técnica: {nombre_real} {f'({marca_real})' if marca_real and marca_real != '-' else ''}")
                    
                    col_sis, col_plan = st.columns(2)
                    
                    texto_auditoria = f"Equipo: {nombre_real}\n"
                    
                    # Funciones auxiliares para extracción y limpieza
                    row_api = df_api_eq.iloc[0] if not df_api_eq.empty else pd.Series()
                    row_excel = df_excel_eq.iloc[0] if not df_excel_eq.empty else pd.Series()

                    def get_dato_fusionado(campo_api, campos_excel, default="N/A"):
                        """Si el API no tiene el dato, lo busca en el Excel para evitar mostrar 'None'"""
                        val = str(row_api.get(campo_api, default)).strip()
                        if val in ['None', 'nan', '', default, 'N/A'] and not row_excel.empty:
                            val = obtener_dato_seguro(row_excel, campos_excel, default)
                        return val if val not in ['None', 'nan', ''] else default

                    def clean_date(d):
                        """Formatea cualquier fecha al formato chileno DD/MM/YYYY"""
                        if pd.isna(d) or str(d).strip() in ['None', '', 'nan', 'NaT']: return 'N/A'
                        try:
                            return pd.to_datetime(d).strftime('%d/%m/%Y')
                        except:
                            return str(d).split('T')[0].split(' ')[0]

                    # Columna 1: SISTEMA EN VIVO (Cruzado con Excel)
                    with col_sis:
                        st.markdown("#### 📡 En Vivo (GPS/Sistema)")
                        if not row_api.empty:
                            ubi = row_api.get('Lugar_Deducido', 'N/A')
                            faena = row_api.get('nombre_faena', 'N/A')
                            estado = row_api.get('Estado_Deducido', 'N/A')
                            
                            # Extracción de Hardware inteligente
                            patente = get_dato_fusionado('patente', ['Patente', 'Placa', 'PPU'])
                            modelo = get_dato_fusionado('modelo', ['Modelo', 'Marca/Modelo', 'Tipo'])
                            vin = get_dato_fusionado('vin', ['VIN', 'Chasis', 'N° Chasis', 'Serie'])
                            if vin == "N/A": vin = get_dato_fusionado('chasis', ['VIN', 'Chasis', 'N° Chasis', 'Serie'])
                            hrs = get_dato_fusionado('horas_ult', ['Horómetro', 'Horometro', 'Horas', 'Hrs'])
                            control = get_dato_fusionado('control', ['Control', 'Sistema Control', 'Sistema'])
                            
                            rt = clean_date(row_api.get('rev_fecha_expiracion'))
                            sngm = clean_date(row_api.get('ser_fecha_expiracion'))
                            dgmn = clean_date(row_api.get('dgmn_fecha_expiracion'))
                            
                            st.info(f"📍 **Ubicación:** {ubi} ({faena}) | ⚙️ **Estado:** {estado}")
                            
                            c1, c2 = st.columns(2)
                            c1.markdown(f"**Patente:** {patente}\n\n**Modelo:** {modelo}\n\n**VIN/Chasis:** {vin}")
                            c2.markdown(f"**Horómetro:** {hrs} hrs\n\n**Control:** {control}")
                            
                            st.markdown("**📅 Certificaciones (Plazos):**")
                            st.caption(f"**Revisión Técnica:** {rt} | **Sernageomin:** {sngm} | **DGMN:** {dgmn}")
                            
                            texto_auditoria += f"GPS dice: Ubicación {ubi}, Estado {estado}.\n"
                        else:
                            st.warning("No hay conexión en vivo para este equipo.")
                            texto_auditoria += "GPS: Sin conexión.\n"
                            
                    # Columna 2: PLANIFICACIÓN EXCEL (Solo el último registro)
                    with col_plan:
                        st.markdown("#### 📅 Planificación (Último Registro)")
                        if not row_excel.empty:
                            estatus = obtener_dato_seguro(row_excel, ['Status MP', 'Estatus MP', 'Estado'])
                            ubicacion_plan = obtener_dato_seguro(row_excel, ['Ubicación', 'Ubicacion', 'Lugar', 'Faena'])
                            f_ini = clean_date(obtener_dato_seguro(row_excel, ['Fecha Inici', 'Fecha Inicial']))
                            f_fin = clean_date(obtener_dato_seguro(row_excel, ['Fecha Fina', 'Fecha Final', 'Termino']))
                            comentarios = obtener_dato_seguro(row_excel, ['Estado de equipos', 'Comentarios', 'Comentario', 'Motivo'])
                            
                            st.success(f"📋 **Estatus Taller:** {estatus} | **Ubicación:** {ubicacion_plan}")
                            st.markdown(f"**🗓️ Fechas:** {f_ini} al {f_fin}\n\n**💬 Últimos Trabajos / Comentarios:**\n{comentarios}")
                            
                            texto_auditoria += f"Excel dice: Estatus {estatus}, Ubicación {ubicacion_plan}, Fechas {f_ini} a {f_fin}, Detalle: {comentarios}\n"
                        else:
                            st.warning("No hay registros en la planificación.")
                            texto_auditoria += "Excel: Sin registros recientes.\n"
                            
                    st.divider()
                    fichas_generadas.append(texto_auditoria)

            # --- AUDITORÍA IA ---
            if fichas_generadas:
                st.markdown("### 🤖 Auditoría Automática (Buscando Incongruencias)")
                st.caption("La IA cruza la información mostrada arriba para alertar sobre desvíos.")
                
                prompt_auditor = f"""
                Eres un auditor de mantenimiento. Revisa estos datos crudos.
                Tu ÚNICO trabajo es encontrar incongruencias entre lo que dice el "GPS" y lo que dice el "Excel".
                Por ejemplo: Si el GPS dice que está en Faena operando, pero el Excel dice que está en Taller, ALERTA de eso.
                Si las fechas del Excel muestran atraso al día de hoy ({datetime.now().strftime('%d/%m/%Y')}), menciónalo brevemente.
                Si todo cuadra perfectamente, responde SOLO: "✅ Todo coincide correctamente. Sin incongruencias detectadas."
                Sé muy directo y breve.
                
                DATOS A AUDITAR:
                {chr(10).join(fichas_generadas)}
                """
                
                try:
                    respuesta_stream = invocar_ia_segura(prompt_auditor, stream=True)
                    st.write_stream((chunk.text for chunk in respuesta_stream if chunk.text))
                except Exception as e:
                    if str(e) == "429_QUOTA":
                        st.warning("⚠️ **Límite de IA temporalmente alcanzado.** Pero no te preocupes, tienes toda la información de las fichas arriba para hacer tu propia gestión visual.")
                    else:
                        st.error("La IA no está disponible en este momento. Utiliza las fichas técnicas superiores.")

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
            info_contrato = next((datos for nombre, datos in CONTRATOS_FAENA.items() if nombre.lower() == faena_seleccionada.lower()), None)
            
            if info_contrato:
                st.info(f"📋 **Condiciones de Contrato: {faena_seleccionada}**")
                col1, col2, col3 = st.columns(3)
                col1.metric("Segmento de la Faena", f"Segmento {info_contrato['Segmento']}")
                col2.metric("Camiones Fábrica (Contrato)", info_contrato['Contrato'])
                col3.metric("Equipos Back Up Requeridos", info_contrato['Back Up'])
                st.divider()

            df_faena = df_api_global[df_api_global['nombre_faena'] == faena_seleccionada].copy()
            st.success(f"🚛 {len(df_faena)} equipos reportados actualmente en **{faena_seleccionada}**")
            
            cols_vista = {
                'nombre': 'Equipo', 'marca_nombre': 'Marca', 'Lugar_Deducido': 'Lugar/Ubicación',
                'horas_ult': 'Horómetro (hrs)', 'Estado_Deducido': 'Estado Actual',
                'rev_fecha_expiracion': 'Venc. RT', 'ser_fecha_expiracion': 'Venc. SNGM', 'dgmn_fecha_expiracion': 'Venc. DGMN'
            }
            
            cols_existentes = [c for c in cols_vista.keys() if c in df_faena.columns]
            df_mostrar = df_faena[cols_existentes].rename(columns=cols_vista)
            
            for col in ['Venc. RT', 'Venc. SNGM', 'Venc. DGMN']:
                if col in df_mostrar.columns:
                    df_mostrar[col] = pd.to_datetime(df_mostrar[col], errors='coerce').dt.strftime('%d/%m/%Y')
            
            df_mostrar = df_mostrar.fillna("-")
            
            # Centrado absoluto de datos gracias a la API nativa de column_config de Streamlit
            st.dataframe(
                df_mostrar,
                use_container_width=False, 
                hide_index=True,
                column_config={
                    "Equipo": st.column_config.TextColumn("Equipo", alignment="left"),
                    "Marca": st.column_config.TextColumn("Marca", alignment="center"),
                    "Lugar/Ubicación": st.column_config.TextColumn("Lugar/Ubicación", alignment="center"),
                    "Horómetro (hrs)": st.column_config.NumberColumn("Horómetro (hrs)", alignment="center"),
                    "Estado Actual": st.column_config.TextColumn("Estado Actual", alignment="center"),
                    "Venc. RT": st.column_config.TextColumn("Venc. RT", alignment="center"),
                    "Venc. SNGM": st.column_config.TextColumn("Venc. SNGM", alignment="center"),
                    "Venc. DGMN": st.column_config.TextColumn("Venc. DGMN", alignment="center"),
                }
            )
