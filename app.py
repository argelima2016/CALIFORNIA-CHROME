import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader
from streamlit_autorefresh import st_autorefresh

# Configuración de la página web en modo responsivo avanzado (anchura total fluida)
st.set_page_config(page_title="Sistema de Remates Responsivo", layout="wide", page_icon="🏇")

# --- AUTOREFRESH OPTIMIZADO (3 SEGUNDOS) ---
st_autorefresh(interval=3000, key="datarefresh_en_vivo")

# --- HORA LOCAL DE VENEZUELA (ESTRICTA 12 HORAS) ---
def obtener_hora_venezuela_local():
    try:
        zona_venezuela = ZoneInfo("America/Caracas")
        return datetime.now(zona_venezuela).replace(tzinfo=None)
    except Exception:
        pass
    
    tz_venezuela = timezone(timedelta(hours=-4))
    return datetime.now(tz_venezuela).replace(tzinfo=None)

# --- ESCALA OFICIAL DE PUJAS CONDICIONADAS ---
ESCALA_PUJAS = [
    50, 100, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 900, 1000,
    1200, 1400, 1600, 1800, 2000, 2500, 3000, 3500, 4000, 4500, 5000,
    5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000
] + list(range(11000, 1000001, 1000))

def obtener_siguientes_montos(monto_actual):
    siguientes = [m for m in ESCALA_PUJAS if m > monto_actual]
    if not siguientes:
        ultimo = ESCALA_PUJAS[-1] if ESCALA_PUJAS else max(monto_actual, 10000)
        siguientes = [ultimo + i * 1000 for i in range(1, 50)]
    return siguientes

# --- ESTILOS CSS MULTIPLATAFORMA (ADAPTABLE A MÓVILES Y COMPUTADORAS) ---
st.markdown("""
    <style>
    :root {
        --bg-main: #0e1117;
        --bg-card: #161b22;
        --border-color: #30363d;
        --text-primary: #f0f6fc;
        --accent-gold: #f1e05a;
        --accent-red: #ff4757;
        --accent-cyan: #00d2d3;
    }

    .stApp {
        background-color: var(--bg-main);
        color: var(--text-primary);
    }
    
    .subasta-header {
        font-size: clamp(18px, 4vw, 26px);
        font-weight: 800;
        color: var(--accent-gold);
        margin-bottom: 12px;
        border-bottom: 2px solid var(--accent-gold);
        padding-bottom: 6px;
    }
    
    .timer-box {
        background-color: var(--bg-card);
        border: 2px solid var(--accent-red);
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        font-size: clamp(16px, 3.5vw, 22px);
        font-weight: bold;
        color: var(--accent-red);
        margin-bottom: 12px;
    }
    
    .cierre-info-box {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 10px;
        border-radius: 6px;
        text-align: center;
        font-size: clamp(14px, 2vw, 16px);
        color: var(--text-primary);
        margin-bottom: 12px;
    }

    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
    }

    div[data-testid="stMetricValue"] {
        color: var(--accent-gold) !important;
        font-size: clamp(18px, 3vw, 24px) !important;
        font-weight: 700;
    }

    /* Adaptabilidad total del contenedor principal para evitar desbordes en celulares */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 100% !important;
    }
    
    /* Botones táctiles amplios para pantallas táctiles de Android e iOS */
    .stButton button {
        width: 100% !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        padding: 0.6rem !important;
        min-height: 42px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- CARGA INICIAL DE JUGADORES ---
@st.cache_data
def cargar_jugadores_base():
    try:
        df_excel = pd.read_excel('TOTAL DE REMATES.xlsx', sheet_name='Hoja1')
        jugadores = df_excel.iloc[5:, 1].dropna().tolist()
        jugadores = [str(j).strip().upper() for j in jugadores if str(j).strip() != '']
        return list(sorted(set(jugadores)))
    except Exception:
        return ["CASA", "SOMBI", "LUIS", "CARLOS", "RAMON", "ALDEA", "ANGEL", "ALFONSO", "MACANO", "MIGUEL", "TOCAYO", "EL GOCHO", "PAPIRO", "CHAYO", "ALEXIS"]

# --- ESTADO GLOBAL DE LA SESIÓN ---
if 'lista_jugadores' not in st.session_state:
    st.session_state.lista_jugadores = cargar_jugadores_base()

if 'banco_caballos_por_carrera' not in st.session_state:
    st.session_state.banco_caballos_por_carrera = {}

if 'remates' not in st.session_state:
    st.session_state.remates = {}

if 'historial_ganadores' not in st.session_state:
    st.session_state.historial_ganadores = {}

if 'carreras_cerradas_remate' not in st.session_state:
    st.session_state.carreras_cerradas_remate = {}

if 'remates_cargados_en_cuentas' not in st.session_state:
    st.session_state.remates_cargados_en_cuentas = {}

if 'horas_cierre_remate' not in st.session_state:
    st.session_state.horas_cierre_remate = {}

if 'estado_conteo_carrera' not in st.session_state:
    st.session_state.estado_conteo_carrera = {}

if 'tiempo_inicio_conteo' not in st.session_state:
    st.session_state.tiempo_inicio_conteo = {}

if 'cuentas' not in st.session_state:
    st.session_state.cuentas = {j: {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0} for j in st.session_state.lista_jugadores}

if 'ganancia_casa' not in st.session_state:
    st.session_state.ganancia_casa = 0.0

if 'historial_transacciones' not in st.session_state:
    st.session_state.historial_transacciones = []

if 'dupletas_tickets' not in st.session_state:
    st.session_state.dupletas_tickets = []

if 'carreras_habilitadas_dupleta' not in st.session_state:
    st.session_state.carreras_habilitadas_dupleta = []

if 'dupleta_bloqueada' not in st.session_state:
    st.session_state.dupleta_bloqueada = False

def formatear_bs(monto):
    return f"Bs. {monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# ⚙️ BARRA LATERAL RESPONSIVA
# ==========================================
st.sidebar.header("⚙️ Menú de Control")

ahora_dt = obtener_hora_venezuela_local()
st.sidebar.markdown(f"🕒 **Hora:** `{ahora_dt.strftime('%I:%M:%S %p')}`")

def procesar_programa_pdf(archivo_pdf):
    try:
        lector_pdf = PdfReader(archivo_pdf)
        texto_extraido = ""
        for pagina in lector_pdf.pages:
            t_pag = pagina.extract_text()
            if t_pag:
                texto_extraido += t_pag + "\n"
        
        lineas = texto_extraido.split('\n')
        carrera_actual_detectada = None
        banco_temporal = {}
        
        patron_carrera = re.compile(r'(?:carrera|primera|segunda|tercera|cuarta|quinta|sexta|septima|octava|novena|decima|\d+)\s*(?:ª|º|\.)?\s*carrera', re.IGNORECASE)
        
        for linea in lineas:
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue
                
            match_carr = patron_carrera.search(linea_limpia)
            if match_carr or "carrera" in linea_limpia.lower() and len(linea_limpia) < 30:
                for c_n in range(1, 15):
                    if str(c_n) in linea_limpia or f"carrera {c_n}" in linea_limpia.lower():
                        carrera_actual_detectada = f"Carrera {c_n}"
                        if carrera_actual_detectada not in banco_temporal:
                            banco_temporal[carrera_actual_detectada] = []
                        break
            
            if carrera_actual_detectada:
                match_ejemplar = re.match(r'^(\d{1,2})[\s\-\.\)]+(.*)', linea_limpia)
                if match_ejemplar:
                    num_ej = match_ejemplar.group(1)
                    nom_ej = match_ejemplar.group(2).strip()
                    if len(nom_ej) > 2 and not any(palabra in nom_ej.lower() for palabra in ['retirado', 'jinete', 'entrenador', 'distancia', 'pista']):
                        formato_ej = f"{num_ej} - {nom_ej.title()}"
                        if formato_ej not in banco_temporal[carrera_actual_detectada]:
                            banco_temporal[carrera_actual_detectada].append(formato_ej)

        if not banco_temporal:
            match_simple_carr = re.findall(r'(\d+)\s*[-]?\s*([A-ZÁÉÍÓÚÑa-zñ\s]{3,})', texto_extraido)
            if match_simple_carr:
                carrera_generica = "Carrera 1"
                banco_temporal[carrera_generica] = []
                for num, nom in match_simple_carr[:15]:
                    b_item = f"{num.strip()} - {nom.strip().title()}"
                    if b_item not in banco_temporal[carrera_generica]:
                        banco_temporal[carrera_generica].append(b_item)

        if banco_temporal:
            st.session_state.banco_caballos_por_carrera = banco_temporal
            for c_key, c_vals in banco_temporal.items():
                if c_key not in st.session_state.remates:
                    st.session_state.remates[c_key] = {}
                for ev in c_vals[:17]:
                    if ev not in st.session_state.remates[c_key]:
                        st.session_state.remates[c_key][ev] = {"jugador": "Sin Postor", "monto": 0.0}
            return True
    except Exception as e:
        st.sidebar.error(f"Error procesando PDF: {e}")
    return False

def cargar_programa_automatico():
    archivo_fijo = "programa_del_dia.xlsx" 
    if os.path.exists(archivo_fijo):
        try:
            df_prog = pd.read_excel(archivo_fijo)
            if "Carrera" in df_prog.columns and "Caballo" in df_prog.columns:
                carreras_detectadas = sorted(df_prog["Carrera"].unique(), key=lambda x: int(''.join(filter(str.isdigit, str(x))) or 0))
                banco_temp = {}
                for carr in carreras_detectadas:
                    carr_name = str(carr) if "Carrera" in str(carr) else f"Carrera {carr}"
                    banco_temp[carr_name] = []
                    caballos_carrera = df_prog[df_prog["Carrera"] == carr]["Caballo"].tolist()
                    for idx, cab in enumerate(caballos_carrera[:17], start=1):
                        nombre_limpio = str(cab).strip()
                        nombre_limpio = re.sub(r'^\d+[\s\-\.\)]*', '', nombre_limpio).strip().title()
                        formato_llave = f"{idx} - {nombre_limpio}"
                        if formato_llave not in banco_temp[carr_name]:
                            banco_temp[carr_name].append(formato_llave)
                            
                st.session_state.banco_caballos_por_carrera = banco_temp
                for c_k, c_v in banco_temp.items():
                    if c_k not in st.session_state.remates:
                        st.session_state.remates[c_k] = {}
                    for ev in c_v:
                        if ev not in st.session_state.remates[c_k]:
                            st.session_state.remates[c_k][ev] = {"jugador": "Sin Postor", "monto": 0.0}
                return True
        except Exception:
            pass
    return False

if not st.session_state.remates:
    exito_carga = cargar_programa_automatico()
    if not exito_carga:
        for i in range(1, 11):
            carr_nombre = f"Carrera {i}"
            st.session_state.banco_caballos_por_carrera[carr_nombre] = [f"{j} - Ejemplar {j}" for j in range(1, 11)]
            st.session_state.remates[carr_nombre] = {f"{j} - Ejemplar {j}": {"jugador": "Sin Postor", "monto": 0.0} for j in range(1, 11)}

lista_carreras_disponibles = list(st.session_state.remates.keys())

if not st.session_state.carreras_habilitadas_dupleta and lista_carreras_disponibles:
    st.session_state.carreras_habilitadas_dupleta = list(lista_carreras_disponibles)

carrera_actual = st.sidebar.selectbox("Carrera Activa", lista_carreras_disponibles, key="selector_carrera_sidebar")

with st.sidebar.expander("🏠 Retención de la Casa", expanded=False):
    porcentaje_casa = st.slider("Retención (%)", 0, 50, 30, key="slider_retencion_casa")

if carrera_actual not in st.session_state.remates or not st.session_state.remates[carrera_actual]:
    st.session_state.remates[carrera_actual] = {f"{i} - Caballo": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 11)}

with st.sidebar.expander("⏰ Hora de Cierre Estricta", expanded=False):
    hora_guardada_actual = st.session_state.horas_cierre_remate.get(carrera_actual)
    periodo_opciones = ["AM", "PM"]
    periodo_actual = "PM" if hora_guardada_actual and hora_guardada_actual.hour >= 12 else "AM"
    
    periodo_sel = st.radio("Periodo", periodo_opciones, index=0 if periodo_actual == "AM" else 1, key=f"radio_periodo_{carrera_actual}", horizontal=True)
    
    hora_def_12 = 1
    min_def = 0
    if hora_guardada_actual:
        h_24 = hora_guardada_actual.hour
        hora_def_12 = 12 if h_24 == 0 else (h_24 - 12 if h_24 > 12 else h_24)
        min_def = hora_guardada_actual.minute
    else:
        h_24_act = ahora_dt.hour
        m_act = min(59, ahora_dt.minute + 5)
        hora_def_12 = 12 if h_24_act == 0 else (h_24_act - 12 if h_24_act > 12 else h_24_act)
        min_def = m_act

    hora_12 = st.selectbox("Hora", list(range(1, 13)), index=int(hora_def_12) - 1, key=f"sel_h12_{carrera_actual}")
    minuto_sel = st.selectbox("Minutos", list(range(0, 60)), index=int(min_def), key=f"sel_m12_{carrera_actual}")
    
    h_24_conv = int(hora_12)
    if periodo_sel == "PM" and h_24_conv < 12:
        h_24_conv += 12
    elif periodo_sel == "AM" and h_24_conv == 12:
        h_24_conv = 0
        
    hora_seleccionada = time(h_24_conv, int(minuto_sel))
    
    col_bh1, col_bh2 = st.sidebar.columns(2)
    with col_bh1:
        if st.button("💾 Guardar", key=f"btn_save_h_{carrera_actual}"):
            st.session_state.horas_cierre_remate[carrera_actual] = hora_seleccionada
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            st.toast("✅ Hora guardada")
            st.rerun()
    with col_bh2:
        if st.button("🗑️ Borrar", key=f"btn_clear_h_{carrera_actual}"):
            if carrera_actual in st.session_state.horas_cierre_remate:
                del st.session_state.horas_cierre_remate[carrera_actual]
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            st.toast("🗑️ Hora removida")
            st.rerun()

with st.sidebar.expander("🔒 Estado Dupletas", expanded=False):
    if st.session_state.dupleta_bloqueada:
        st.markdown("<p style='color: #ff4757; font-weight: bold;'>🔴 Dupletas BLOQUEADAS</p>", unsafe_allow_html=True)
        if st.button("🔓 Desbloquear", key="btn_desbloq_resp"):
            st.session_state.dupleta_bloqueada = False
            st.rerun()
    else:
        st.markdown("<p style='color: #00d2d3; font-weight: bold;'>🟢 Dupletas ABIERTAS</p>", unsafe_allow_html=True)
        if st.button("🔒 Bloquear", key="btn_bloq_resp"):
            st.session_state.dupleta_bloqueada = True
            st.rerun()

if st.sidebar.button("🗑️ Reiniciar Jornada", use_container_width=True):
    for key in list(st.session_state.keys()):
        if key != 'banco_caballos_por_carrera':
            del st.session_state[key]
    st.toast("🚨 Jornada reiniciada.")
    st.rerun()

# --- INTERFAZ DE PESTAÑAS (ADAPTABLES A PANTALLAS TÁCTILES Y ESCRITORIO) ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏇 Remate", 
    "✍️ Banco", 
    "🎟️ Dupletas", 
    "🏁 Cierre", 
    "📊 Cuentas", 
    "🧾 Hist.", 
    "📄 PDF"
])

# ==========================================
# PESTAÑA 1: REMATE (MODO MULTIPLATAFORMA)
# ==========================================
with tab1:
    st.markdown(f"<div class='subasta-header'>🎯 {carrera_actual}</div>", unsafe_allow_html=True)
    
    hora_limite = st.session_state.horas_cierre_remate.get(carrera_actual)
    carrera_cerrada = st.session_state.carreras_cerradas_remate.get(carrera_actual, False)
    estado_conteo = st.session_state.estado_conteo_carrera.get(carrera_actual, "INACTIVO")
    
    if hora_limite:
        dt_limite_dummy = datetime.combine(ahora_dt.date(), hora_limite)
        st.markdown(f"<div class='cierre-info-box'>⏰ Cierre: <b>{dt_limite_dummy.strftime('%I:%M %p')}</b></div>", unsafe_allow_html=True)

    if hora_limite and not carrera_cerrada:
        dt_limite = datetime.combine(ahora_dt.date(), hora_limite)
        diferencia_segundos = (dt_limite - ahora_dt).total_seconds()
        
        if estado_conteo == "INACTIVO":
            if 0 < diferencia_segundos <= 10:
                st.session_state.estado_conteo_carrera[carrera_actual] = "CONTEO_10S"
                st.session_state.tiempo_inicio_conteo[carrera_actual] = ahora_dt
                st.rerun()
            elif diferencia_segundos <= 0:
                st.session_state.carreras_cerradas_remate[carrera_actual] = True
                st.session_state.estado_conteo_carrera[carrera_actual] = "CERRADO"
                st.rerun()
                
        elif estado_conteo == "CONTEO_10S":
            tiempo_inicio = st.session_state.tiempo_inicio_conteo.get(carrera_actual, ahora_dt)
            restantes_10s = max(0, 10 - int((ahora_dt - tiempo_inicio).total_seconds()))
            if restantes_10s > 0:
                st.markdown(f"<div class='timer-box'>⚠️ CIERRE EN: <b>{restantes_10s}s</b></div>", unsafe_allow_html=True)
            else:
                st.session_state.estado_conteo_carrera[carrera_actual] = "ESPERA_POST_PUJA"
                st.session_state.tiempo_inicio_conteo[carrera_actual] = ahora_dt
                st.rerun()

    # Diseño responsivo en dos columnas de ancho flexible (en móviles se apilan automáticamente gracias a Streamlit Layout)
    col_izq_puja, col_der_tabla = st.columns([1.1, 1.9], gap="medium")

    with col_izq_puja:
        with st.container(border=True):
            st.markdown("⚡ **Registro Rápido de Puja**")
            lista_caballos_activos = list(st.session_state.remates[carrera_actual].keys())
            
            if not lista_caballos_activos:
                st.warning("Sin ejemplares. Agrégalos en la pestaña Banco o sube un PDF.")
            else:
                if f"caballo_seleccionado_click_{carrera_actual}" not in st.session_state or st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] not in lista_caballos_activos:
                    st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] = lista_caballos_activos[0]
                    
                cols_botones = st.columns(4) # Cuadrícula táctil ideal para celulares Android/iOS y PC
                for idx, cab_item in enumerate(lista_caballos_activos):
                    num_parte = cab_item.split(" - ")[0]
                    with cols_botones[idx % 4]:
                        if st.button(f"#{num_parte}", key=f"btn_r_cab_{carrera_actual}_{idx}", use_container_width=True):
                            st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] = cab_item
                
                caballo_seleccionado = st.session_state[f"caballo_seleccionado_click_{carrera_actual}"]
                st.markdown(f"Seleccionado: **{caballo_seleccionado}**")

                jugador = st.selectbox("Jugador", st.session_state.lista_jugadores, key=f"sel_jug_{carrera_actual}")
                puja_actual = st.session_state.remates[carrera_actual][caballo_seleccionado]['monto']
                
                opciones_escala = obtener_siguientes_montos(puja_actual)
                monto_puja = st.selectbox("Monto", opciones_escala, format_func=lambda x: formatear_bs(x), key=f"sel_esc_{carrera_actual}_{caballo_seleccionado}")
                
                if carrera_cerrada:
                    st.button("🔨 Confirmar Puja", key=f"btn_p_{carrera_actual}", use_container_width=True, type="primary", disabled=True)
                else:
                    if st.button("🔨 Confirmar Puja", key=f"btn_p_{carrera_actual}", use_container_width=True, type="primary"):
                        if monto_puja <= puja_actual:
                            st.error("Debe ser mayor")
                        else:
                            st.session_state.remates[carrera_actual][caballo_seleccionado] = {"jugador": jugador, "monto": monto_puja}
                            st.rerun()

    with col_der_tabla:
        st.subheader("📋 Estado Actual")
        datos_tabla = []
        total_pote = 0.0
        for cab, info in st.session_state.remates[carrera_actual].items():
            datos_tabla.append({"Ejemplar": cab, "Comprador": info['jugador'], "Monto": formatear_bs(info['monto'])})
            total_pote += info['monto']
        
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True)
        
        monto_casa = total_pote * (porcentaje_casa / 100)
        pote_neto_base = total_pote - monto_casa

        c_m1, c_m2 = st.columns(2)
        c_m1.metric("💰 Pote", formatear_bs(total_pote))
        pote_incentivo_extra = c_m2.number_input("🎁 Extra", min_value=0.0, value=0.0, step=50.0, key=f"pote_inc_{carrera_actual}")
        premio_total_calculado = pote_neto_base + pote_incentivo_extra
        st.metric("🏆 Premio Total", formatear_bs(premio_total_calculado))

# ==========================================
# PESTAÑA 2: BANCO DE CABALLOS POR CARRERA
# ==========================================
with tab2:
    st.markdown("<div class='subasta-header'>✍️ Banco de Caballos por Carrera</div>", unsafe_allow_html=True)
    st.markdown("Gestiona el banco de ejemplares de forma manual o impórtalos automáticamente desde el PDF en la última pestaña.")
    
    carr_banco_sel = st.selectbox("Seleccionar Carrera para Banco", lista_carreras_disponibles, key="sel_carrera_banco_gestion")
    
    if carr_banco_sel not in st.session_state.banco_caballos_por_carrera:
        st.session_state.banco_caballos_por_carrera[carr_banco_sel] = []
        
    with st.container(border=True):
        st.markdown(f"**Agregar Ejemplar a {carr_banco_sel}**")
        nuevo_nom_banco = st.text_input("Nombre del Ejemplar", placeholder="Ej: Rey David", key=f"input_banco_nom_{carr_banco_sel}")
        if st.button("💾 Agregar al Banco y Jornada", use_container_width=True, type="primary"):
            nom_limp = nuevo_nom_banco.strip().title()
            if nom_limp:
                nums = [int(re.match(r'^(\d+)', e).group(1)) for e in st.session_state.banco_caballos_por_carrera[carr_banco_sel] if re.match(r'^(\d+)', e)]
                sig_num = 1
                while sig_num in nums and sig_num <= 17:
                    sig_num += 1
                formato_nuevo = f"{sig_num} - {nom_limp}"
                
                if formato_nuevo not in st.session_state.banco_caballos_por_carrera[carr_banco_sel]:
                    st.session_state.banco_caballos_por_carrera[carr_banco_sel].append(formato_nuevo)
                if carr_banco_sel not in st.session_state.remates:
                    st.session_state.remates[carr_banco_sel] = {}
                if formato_nuevo not in st.session_state.remates[carr_banco_sel]:
                    st.session_state.remates[carr_banco_sel][formato_nuevo] = {"jugador": "Sin Postor", "monto": 0.0}
                st.toast(f"✅ ¡{nom_limp} agregado a {carr_banco_sel}!")
                st.rerun()

    st.markdown("---")
    st.subheader(f"📋 Ejemplares Registrados en {carr_banco_sel}")
    ejemplares_actuales = st.session_state.banco_caballos_por_carrera[carr_banco_sel]
    
    if not ejemplares_actuales:
        st.info("No hay ejemplares en este banco de carrera.")
    else:
        for idx_b, ej_item in enumerate(ejemplares_actuales):
            col_ib1, col_ib2 = st.columns([5, 1])
            with col_ib1:
                st.text(ej_item)
            with col_ib2:
                if st.button("🗑️", key=f"del_banco_{carr_banco_sel}_{idx_b}", use_container_width=True):
                    st.session_state.banco_caballos_por_carrera[carr_banco_sel].pop(idx_b)
                    if carr_banco_sel in st.session_state.remates and ej_item in st.session_state.remates[carr_banco_sel]:
                        del st.session_state.remates[carr_banco_sel][ej_item]
                    st.toast("Ejemplar eliminado del banco.")
                    st.rerun()

# ==========================================
# PESTAÑA 3: MÓDULO DE DUPLETA PRO
# ==========================================
with tab3:
    st.markdown("<div class='subasta-header'>🎟️ Módulo de Dupletas</div>", unsafe_allow_html=True)

    if st.session_state.dupleta_bloqueada:
        st.error("🔒 **BLOQUEADO:** Emisión cerrada.")

    pote_total_dupletas = sum([t['monto'] for t in st.session_state.dupletas_tickets])

    st.metric("💰 Pote Acumulado Dupletas", formatear_bs(pote_total_dupletas))

    col_d1, col_d2 = st.columns(2, gap="medium")
    with col_d1:
        with st.container(border=True):
            jugador_dupleta = st.selectbox("👤 Jugador", st.session_state.lista_jugadores, key="sel_jug_dup_resp")
            monto_dupleta = st.number_input("💰 Monto (Bs.)", min_value=50.0, value=500.0, step=50.0, key="input_m_dup_resp")
            num_legs = st.radio("Cantidad de Selecciones:", [2, 3, 4, 5, 6], horizontal=True, key="radio_legs_resp")

    with col_d2:
        with st.container(border=True):
            st.markdown("**Selecciones por Carrera**")
            seleccion_legs = []
            carreras_usadas_en_ticket = set()
            valido_legs = True
            
            carreras_habilitadas = st.session_state.carreras_habilitadas_dupleta
            for i in range(num_legs):
                c_leg, cb_leg_col = st.columns(2)
                with c_leg:
                    carr_leg = st.selectbox(f"Carrera {i+1}", carreras_habilitadas, key=f"sel_c_resp_{i}")
                with cb_leg_col:
                    caballos_en_carr = list(st.session_state.remates.get(carr_leg, {}).keys())
                    cab_leg = st.selectbox(f"Ejemplar {i+1}", caballos_en_carr if caballos_en_carr else ["Sin Caballos"], key=f"sel_cb_resp_{i}")
                
                if carr_leg in carreras_usadas_en_ticket:
                    st.error(f"⚠️ Carrera repetida: {carr_leg}")
                    valido_legs = False
                carreras_usadas_en_ticket.add(carr_leg)
                seleccion_legs.append({"carrera": carr_leg, "ejemplar": cab_leg})

    if not st.session_state.dupleta_bloqueada:
        if st.button("🚀 Emitir Ticket de Dupleta", use_container_width=True, type="primary"):
            if not valido_legs:
                st.error("⚠️ Corrige carreras repetidas.")
            else:
                ticket_id = f"DUP-{len(st.session_state.dupletas_tickets) + 1:04d}"
                nuevo_ticket = {
                    "id": ticket_id, "jugador": jugador_dupleta, "monto": monto_dupleta,
                    "legs": seleccion_legs, "estado": "Pendiente", "fecha": ahora_dt.strftime('%d/%m %I:%M %p')
                }
                st.session_state.dupletas_tickets.append(nuevo_ticket)
                
                if jugador_dupleta not in st.session_state.cuentas:
                    st.session_state.cuentas[jugador_dupleta] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                st.session_state.cuentas[jugador_dupleta]['Pujas'] += monto_dupleta
                
                st.session_state.historial_transacciones.append({
                    "Carrera": "Múltiple", "Jugador": jugador_dupleta,
                    "Tipo": "Cargo (Dupleta)", "Detalle": f"Ticket {ticket_id}", "Monto (Bs.)": -monto_dupleta
                })
                st.success(f"✅ Ticket {ticket_id} emitido")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Gestión de Tickets")
    if not st.session_state.dupletas_tickets:
        st.info("Sin tickets emitidos.")
    else:
        for idx_t, tick in enumerate(st.session_state.dupletas_tickets):
            with st.container(border=True):
                col_ti1, col_ti2, col_ti3, col_ti4 = st.columns([1.5, 2, 1, 1.5])
                with col_ti1:
                    st.markdown(f"**ID:** `{tick['id']}`")
                with col_ti2:
                    st.markdown(f"**Jugador:** {tick['jugador']} <br> Monto: {formatear_bs(tick['monto'])}", unsafe_allow_html=True)
                with col_ti3:
                    st.markdown(f"**{tick.get('estado', 'Pendiente')}**")
                with col_ti4:
                    c_g, c_p, c_d = st.columns(3)
                    with c_g:
                        if st.button("✅", key=f"bg_resp_{idx_t}", use_container_width=True):
                            tick['estado'] = "Ganador"
                            st.session_state.cuentas[tick['jugador']]['Premios'] += pote_total_dupletas
                            st.rerun()
                    with c_p:
                        if st.button("❌", key=f"bp_resp_{idx_t}", use_container_width=True):
                            tick['estado'] = "Perdedor"
                            st.rerun()
                    with c_d:
                        if st.button("🗑️", key=f"bd_resp_{idx_t}", use_container_width=True):
                            st.session_state.dupletas_tickets.pop(idx_t)
                            st.rerun()

# ==========================================
# PESTAÑA 4: CIERRE Y LIQUIDACIÓN
# ==========================================
with tab4:
    st.markdown("<div class='subasta-header'>🏁 Cierre y Liquidación</div>", unsafe_allow_html=True)
    
    datos_resumen_jornada = []
    for carr_item in lista_carreras_disponibles:
        c_cerrada = st.session_state.carreras_cerradas_remate.get(carr_item, False)
        info_liq = st.session_state.historial_ganadores.get(carr_item, None)
        pote_carr = sum([info['monto'] for info in st.session_state.remates.get(carr_item, {}).values()])
        
        estatus_txt = "🏆 Liquidada" if info_liq else ("🔒 Cerrado" if c_cerrada else "🟢 Abierto")
        datos_resumen_jornada.append({"Carrera": carr_item, "Estatus": estatus_txt, "Pote": formatear_bs(pote_carr)})

    st.dataframe(pd.DataFrame(datos_resumen_jornada), use_container_width=True, hide_index=True)

    st.markdown("---")
    carr_seleccionada_liq = st.selectbox("Gestionar Carrera", lista_carreras_disponibles, key="sel_c_liq_resp")

    with st.container(border=True):
        st.markdown(f"**Gestión: {carr_seleccionada_liq}**")
        c_cerrada_actual = st.session_state.carreras_cerradas_remate.get(carr_seleccionada_liq, False)
        
        col_la, col_lb = st.columns(2)
        with col_la:
            if not c_cerrada_actual:
                if st.button(f"🔒 Cerrar Remate", key=f"btn_qc_{carr_seleccionada_liq}", use_container_width=True):
                    st.session_state.carreras_cerradas_remate[carr_seleccionada_liq] = True
                    st.session_state.estado_conteo_carrera[carr_seleccionada_liq] = "CERRADO"
                    
                    if not st.session_state.remates_cargados_en_cuentas.get(carr_seleccionada_liq, False):
                        for cab, info in st.session_state.remates[carr_seleccionada_liq].items():
                            if info['jugador'] != "Sin Postor" and info['monto'] > 0:
                                if info['jugador'] not in st.session_state.cuentas:
                                    st.session_state.cuentas[info['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                                st.session_state.cuentas[info['jugador']]['Pujas'] += info['monto']
                        st.session_state.remates_cargados_en_cuentas[carr_seleccionada_liq] = True
                    st.rerun()
            else:
                if st.button(f"🔓 Reabrir Remate", key=f"btn_qr_{carr_seleccionada_liq}", use_container_width=True):
                    st.session_state.carreras_cerradas_remate[carr_seleccionada_liq] = False
                    st.session_state.remates_cargados_en_cuentas[carr_seleccionada_liq] = False
                    st.rerun()

        st.markdown("---")
        if carr_seleccionada_liq in st.session_state.historial_ganadores:
            st.success("✅ Esta carrera ya se encuentra liquidada.")
        else:
            pote_carr_total = sum([info['monto'] for info in st.session_state.remates[carr_seleccionada_liq].values()])
            monto_casa_calc = pote_carr_total * (porcentaje_casa / 100)
            premio_final_liq = pote_carr_total - monto_casa_calc + st.session_state.get(f"pote_inc_{carr_seleccionada_liq}", 0.0)
            
            caballo_ganador_elegido = st.selectbox("Seleccionar Ejemplar Ganador", list(st.session_state.remates[carr_seleccionada_liq].keys()), key=f"sel_g_resp_{carr_seleccionada_liq}")
            
            if st.button("🎯 Liquidar Premio de la Carrera", key=f"btn_liq_{carr_seleccionada_liq}", use_container_width=True, type="primary"):
                info_g = st.session_state.remates[carr_seleccionada_liq][caballo_ganador_elegido]
                if info_g['jugador'] != "Sin Postor":
                    if info_g['jugador'] not in st.session_state.cuentas:
                        st.session_state.cuentas[info_g['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                    st.session_state.cuentas[info_g['jugador']]['Premios'] += premio_final_liq
                st.session_state.ganancia_casa += monto_casa_calc
                st.session_state.historial_ganadores[carr_seleccionada_liq] = {
                    "Ganador": info_g['jugador'], "Caballo": caballo_ganador_elegido, "Premio": formatear_bs(premio_final_liq)
                }
                st.success("¡Premio liquidado correctamente!")
                st.rerun()

# ==========================================
# PESTAÑA 5: CUENTAS POR JUGADOR
# ==========================================
with tab5:
    st.markdown("<div class='subasta-header'>📊 Cuentas y Balances</div>", unsafe_allow_html=True)
    datos_cuentas = []
    tot_pujas_gen = 0.0
    tot_premios_gen = 0.0
    
    for jugador, vals in st.session_state.cuentas.items():
        pujas, premios, abonos = vals['Pujas'], vals['Premios'], vals['Abonos']
        balance_neto = pujas - abonos - premios
        tot_pujas_gen += pujas
        tot_premios_gen += premios
        
        datos_cuentas.append({
            "Jugador": jugador, "Compras": formatear_bs(pujas),
            "Premios": formatear_bs(premios), "Neto": formatear_bs(balance_neto)
        })
        
    st.dataframe(pd.DataFrame(datos_cuentas), use_container_width=True, hide_index=True)
    
    c_tot1, c_tot2 = st.columns(2)
    c_tot1.metric("Total General Compras", formatear_bs(tot_pujas_gen))
    c_tot2.metric("Ganancia Casa", formatear_bs(st.session_state.ganancia_casa))

# ==========================================
# PESTAÑA 6: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab6:
    st.markdown("<div class='subasta-header'>🧾 Historial de Transacciones</div>", unsafe_allow_html=True)
    if not st.session_state.historial_transacciones:
        st.info("Sin transacciones registradas.")
    else:
        st.dataframe(pd.DataFrame(st.session_state.historial_transacciones), use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 7: LECTOR TABULAR PDF (BANCO)
# ==========================================
with tab7:
    st.markdown("<div class='subasta-header'>📄 Lector PDF e Importador al Banco</div>", unsafe_allow_html=True)
    st.markdown("Sube el programa oficial en formato PDF. El sistema extraerá los ejemplares y los organizará automáticamente dentro del **Banco de Caballos** por cada carrera.")
    
    pdf_subido = st.file_uploader("Sube el programa en PDF", type=["pdf"])
    if pdf_subido is not None:
        if st.button("🚀 Procesar e Importar al Banco", use_container_width=True, type="primary"):
            exito_pdf = procesar_programa_pdf(pdf_subido)
            if exito_pdf:
                st.success("¡Programa procesado e incorporado al banco de caballos con éxito!")
                st.balloons()
                st.rerun()
            else:
                st.error("No se pudieron extraer carreras y ejemplares automáticamente de este PDF.")
