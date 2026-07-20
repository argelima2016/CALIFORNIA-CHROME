import streamlit as st
import pandas as pd
import io
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader, PdfWriter
from streamlit_autorefresh import st_autorefresh
import urllib.request
import json

# Configuración de la página web
st.set_page_config(page_title="Sistema de Remates, Dupletas y PDF en Vivo", layout="wide", page_icon="🏇")

# --- AUTOREFRESH OPTIMIZADO (3 SEGUNDOS PARA EVITAR CONFLICTOS DOM DE REACT) ---
st_autorefresh(interval=3000, key="datarefresh_en_vivo")

# --- FUNCIÓN PARA OBTENER LA HORA DE VENEZUELA DESDE INTERNET ---
@st.cache_data(ttl=15)
def obtener_hora_venezuela_internet():
    try:
        url = "http://worldtimeapi.org/api/timezone/America/Caracas"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            datetime_str = data.get("datetime")
            if datetime_str:
                dt_internet = datetime.fromisoformat(datetime_str).replace(tzinfo=None)
                return dt_internet
    except Exception:
        pass

    try:
        zona_venezuela = ZoneInfo("America/Caracas")
        dt_zonificado = datetime.now(zona_venezuela).replace(tzinfo=None)
        return dt_zonificado
    except Exception:
        pass
    
    tz_venezuela = timezone(timedelta(hours=-4))
    dt_venezuela = datetime.now(tz_venezuela).replace(tzinfo=None)
    return dt_venezuela

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

# --- PALETA DE COLORES E INYECCIÓN DE ESTILOS CSS ---
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
        font-size: 22px;
        font-weight: 800;
        color: var(--accent-gold);
        margin-bottom: 5px;
        border-bottom: 2px solid var(--accent-gold);
        padding-bottom: 5px;
    }
    
    .timer-box {
        background-color: var(--bg-card);
        border: 2px solid var(--accent-red);
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        color: var(--accent-red);
        margin-bottom: 15px;
        box-shadow: 0 0 15px rgba(255, 71, 87, 0.4);
    }
    
    .cierre-info-box {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 10px;
        border-radius: 6px;
        text-align: center;
        font-size: 16px;
        color: var(--text-primary);
        margin-bottom: 15px;
    }

    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 10px 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }

    div[data-testid="stMetricValue"] {
        color: var(--accent-gold) !important;
        font-weight: 700;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
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

if 'remates' not in st.session_state:
    st.session_state.remates = {}

if 'banco_ejemplares' not in st.session_state:
    st.session_state.banco_ejemplares = [
        "Gran Alex", "Rey David", "Sombra Negra", 
        "Rayo Veloz", "Catire Bory", "Doña Rosa"
    ]

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

def formatear_bs(monto):
    return f"Bs. {monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# ⚙️ BARRA LATERAL Y CARGA DE PROGRAMA
# ==========================================
st.sidebar.header("⚙️ Barra Lateral")

ahora_dt = obtener_hora_venezuela_internet()
st.sidebar.markdown(f"🕒 **Hora Venezuela (Internet):** `{ahora_dt.strftime('%I:%M:%S %p')}`")

def cargar_programa_automatico():
    archivo_fijo = "programa_del_dia.xlsx" 
    if os.path.exists(archivo_fijo):
        try:
            df_prog = pd.read_excel(archivo_fijo)
            if "Carrera" in df_prog.columns and "Caballo" in df_prog.columns:
                carreras_detectadas = sorted(df_prog["Carrera"].unique(), key=lambda x: int(''.join(filter(str.isdigit, str(x))) or 0))
                for carr in carreras_detectadas:
                    carr_name = str(carr) if "Carrera" in str(carr) else f"Carrera {carr}"
                    if carr_name not in st.session_state.remates:
                        st.session_state.remates[carr_name] = {}
                    caballos_carrera = df_prog[df_prog["Carrera"] == carr]["Caballo"].tolist()
                    for idx, cab in enumerate(caballos_carrera[:17], start=1):
                        nombre_limpio = str(cab).strip()
                        nombre_limpio = re.sub(r'^\d+[\s\-\.\)]*', '', nombre_limpio).strip().title()
                        formato_llave = f"{idx} - {nombre_limpio}"
                        if formato_llave not in st.session_state.remates[carr_name]:
                            st.session_state.remates[carr_name][formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                return True
        except Exception as e:
            st.sidebar.error(f"Error al leer programa automático: {e}")
    return False

if not st.session_state.remates:
    exito_carga = cargar_programa_automatico()
    if not exito_carga:
        for i in range(1, 11):
            carr_nombre = f"Carrera {i}"
            st.session_state.remates[carr_nombre] = {f"{j} - Ejemplar": {"jugador": "Sin Postor", "monto": 0.0} for j in range(1, 11)}

lista_carreras_disponibles = list(st.session_state.remates.keys())

if not st.session_state.carreras_habilitadas_dupleta and lista_carreras_disponibles:
    st.session_state.carreras_habilitadas_dupleta = list(lista_carreras_disponibles)

carrera_actual = st.sidebar.selectbox("Seleccionar Carrera Activa", lista_carreras_disponibles, key="selector_carrera_sidebar")

with st.sidebar.expander("🏠 ⚙️ Configuración de Retención de la Casa", expanded=False):
    porcentaje_casa = st.slider("Retención de la Casa (%)", 0, 50, 30, key="slider_retencion_casa")

if carrera_actual not in st.session_state.remates or not st.session_state.remates[carrera_actual]:
    st.session_state.remates[carrera_actual] = {f"{i} - Caballo": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 11)}

if len(st.session_state.remates[carrera_actual]) > 17:
    claves_limitadas = list(st.session_state.remates[carrera_actual].keys())[:17]
    st.session_state.remates[carrera_actual] = {k: st.session_state.remates[carrera_actual][k] for k in claves_limitadas}

todos_los_caballos = sorted(list({cab for carr in st.session_state.remates.values() for cab in carr.keys()}))

with st.sidebar.expander("⏰ ⚙️ Ajustar Hora de Cierre Estricta", expanded=False):
    st.markdown(f"Configurar para: **{carrera_actual}**")
    
    hora_guardada_actual = st.session_state.horas_cierre_remate.get(carrera_actual)
    
    periodo_opciones = ["AM", "PM"]
    periodo_actual = "AM"
    if hora_guardada_actual:
        periodo_actual = "PM" if hora_guardada_actual.hour >= 12 else "AM"
    
    col_per_1, col_per_2 = st.columns(2)
    with col_per_1:
        periodo_sel = st.radio("Periodo", periodo_opciones, index=0 if periodo_actual == "AM" else 1, key=f"radio_periodo_{carrera_actual}", horizontal=True)
    
    hora_def_12 = 1
    min_def = 0
    if hora_guardada_actual:
        h_24 = hora_guardada_actual.hour
        if h_24 == 0:
            hora_def_12 = 12
        elif h_24 > 12:
            hora_def_12 = h_24 - 12
        else:
            hora_def_12 = h_24
        min_def = hora_guardada_actual.minute
    else:
        h_24_act = ahora_dt.hour
        m_act = min(59, ahora_dt.minute + 5)
        if m_act >= 60:
            m_act = 59
        if h_24_act == 0:
            hora_def_12 = 12
        elif h_24_act > 12:
            hora_def_12 = h_24_act - 12
        else:
            hora_def_12 = h_24_act
        min_def = m_act

    col_h_sel_1, col_h_sel_2 = st.columns(2)
    with col_h_sel_1:
        hora_12 = st.selectbox("Hora (1-12)", list(range(1, 13)), index=int(hora_def_12) - 1, key=f"sel_h12_{carrera_actual}")
    with col_h_sel_2:
        minuto_sel = st.selectbox("Minutos (0-59)", list(range(0, 60)), index=int(min_def), key=f"sel_m12_{carrera_actual}")
    
    h_24_conv = int(hora_12)
    if periodo_sel == "PM" and h_24_conv < 12:
        h_24_conv += 12
    elif periodo_sel == "AM" and h_24_conv == 12:
        h_24_conv = 0
        
    hora_seleccionada = time(h_24_conv, int(minuto_sel))
    
    col_btn_h1, col_btn_h2 = st.sidebar.columns(2)
    with col_btn_h1:
        if st.button("💾 Guardar", key=f"btn_save_hora_{carrera_actual}", use_container_width=True):
            st.session_state.horas_cierre_remate[carrera_actual] = hora_seleccionada
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            
            dt_dummy = datetime.combine(datetime.today(), hora_seleccionada)
            hora_12h_str = dt_dummy.strftime('%I:%M:%S %p')
            st.toast(f"✅ ¡Hora estricta guardada a las {hora_12h_str} para {carrera_actual}!")
            st.rerun()
            
    with col_btn_h2:
        if st.button("🗑️ Borrar", key=f"btn_clear_hora_{carrera_actual}", use_container_width=True):
            if carrera_actual in st.session_state.horas_cierre_remate:
                del st.session_state.horas_cierre_remate[carrera_actual]
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            st.toast(f"🗑️ Hora programada removida para {carrera_actual}.")
            st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("🏁 Gestión de Cierre y Liquidación", expanded=True):
    st.markdown(f"Acciones para: **{carrera_actual}**")
    
    carrera_cerrada = st.session_state.carreras_cerradas_remate.get(carrera_actual, False)
    
    def procesar_cierre_remate(carr):
        if not st.session_state.remates_cargados_en_cuentas.get(carr, False):
            for cab, info in st.session_state.remates[carr].items():
                if info['jugador'] != "Sin Postor" and info['monto'] > 0:
                    if info['jugador'] not in st.session_state.cuentas:
                        st.session_state.cuentas[info['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                    st.session_state.cuentas[info['jugador']]['Pujas'] += info['monto']
                    st.session_state.historial_transacciones.append({
                        "Carrera": carr, "Jugador": info['jugador'], 
                        "Tipo": "Cargo (Compra)", "Detalle": f"Adjudicación de {cab}", "Monto (Bs.)": -info['monto']
                    })
            st.session_state.remates_cargados_en_cuentas[carr] = True

    if not carrera_cerrada:
        if st.button("🔒 Cerrar Remate", key=f"btn_cerrar_remate_side_{carrera_actual}", use_container_width=True, type="secondary"):
            st.session_state.carreras_cerradas_remate[carrera_actual] = True
            st.session_state.estado_conteo_carrera[carrera_actual] = "CERRADO"
            procesar_cierre_remate(carrera_actual)
            st.toast(f"🔒 ¡El remate para {carrera_actual} ha sido cerrado y cargado a las cuentas!")
            st.rerun()
    else:
        st.success("🔒 Remate cerrado y cargado.")
        if st.button("🔓 Reabrir Remate", key=f"btn_reabrir_remate_side_{carrera_actual}", use_container_width=True):
            st.session_state.carreras_cerradas_remate[carrera_actual] = False
            st.session_state.remates_cargados_en_cuentas[carrera_actual] = False
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            st.toast(f"🔓 Remate reabierto para {carrera_actual}.")
            st.rerun()
            
    st.markdown("---")
    
    total_pote_side = sum([info['monto'] for info in st.session_state.remates[carrera_actual].values()])
    monto_casa_side = total_pote_side * (porcentaje_casa / 100)
    pote_neto_base_side = total_pote_side - monto_casa_side
    pote_incentivo_extra_side = st.session_state.get(f"pote_incentivo_{carrera_actual}", 0.0)
    premio_total_calculado_side = pote_neto_base_side + pote_incentivo_extra_side
    
    caballo_ganador_side = st.selectbox("Ejemplar Ganador", list(st.session_state.remates[carrera_actual].keys()), key=f"sel_ganador_side_{carrera_actual}")
    
    if st.button("🏆 Liquidar Carrera", key=f"btn_liquidar_side_{carrera_actual}", use_container_width=True, type="primary"):
        if carrera_actual in st.session_state.historial_ganadores:
            st.warning("Esta carrera ya fue liquidada.")
        else:
            if not st.session_state.remates_cargados_en_cuentas.get(carrera_actual, False):
                procesar_cierre_remate(carrera_actual)
            
            info_ganador = st.session_state.remates[carrera_actual][caballo_ganador_side]
            if info_ganador['jugador'] != "Sin Postor":
                if info_ganador['jugador'] not in st.session_state.cuentas:
                    st.session_state.cuentas[info_ganador['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                st.session_state.cuentas[info_ganador['jugador']]['Premios'] += premio_total_calculado_side
                st.session_state.historial_transacciones.append({
                    "Carrera": carrera_actual, "Jugador": info_ganador['jugador'], 
                    "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {caballo_ganador_side} (Incentivo incl.)", "Monto (Bs.)": premio_total_calculado_side
                })
            st.session_state.ganancia_casa += monto_casa_side
            st.session_state.historial_ganadores[carrera_actual] = {
                "Ganador": info_ganador['jugador'], "Caballo": caballo_ganador_side, "Premio": formatear_bs(premio_total_calculado_side)
            }
            st.balloons()
            st.success(f"¡Liquidado! Ganador: {info_ganador['jugador']}")
            st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("🛠️ Admin: Carreras de Dupleta", expanded=False):
    st.markdown("Selecciona las carreras habilitadas:")
    seleccion_admin = []
    for carr in lista_carreras_disponibles:
        default_val = carr in st.session_state.carreras_habilitadas_dupleta
        if st.checkbox(carr, value=default_val, key=f"chk_admin_carr_side_{carr}"):
            seleccion_admin.append(carr)
    
    if st.button("💾 Guardar Selección", key="btn_save_admin_side", use_container_width=True):
        st.session_state.carreras_habilitadas_dupleta = seleccion_admin
        st.toast("✅ ¡Carreras de dupleta actualizadas por el administrador!")
        st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Reiniciar Jornada Global", use_container_width=True, type="secondary"):
    for key in list(st.session_state.keys()):
        if key != 'banco_ejemplares':
            del st.session_state[key]
    st.toast("🚨 Jornada reiniciada (Banco de nombres conservado).")
    st.rerun()

with st.sidebar.expander("🐴 🗑️ Opciones Avanzadas del Banco", expanded=False):
    if st.button("🗑️ Reiniciar Banco de Caballos", use_container_width=True, type="secondary"):
        st.session_state.banco_ejemplares = []
        st.toast("🚨 ¡El banco de nombres de caballos ha sido vaciado!")
        st.rerun()

# --- INTERFAZ DE PESTAÑAS ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏇 Remate Adelantado", 
    "✍️ Gestión Manual (Caballos)", 
    "🎟️ Módulo de Dupleta", 
    "🏁 Cierre y Liquidación", 
    "📊 Cuentas por Jugador", 
    "🧾 Historial de Transacciones", 
    "📄 Lector Tabular PDF"
])

# ==========================================
# PESTAÑA 1: REMATE ADELANTADO
# ==========================================
with tab1:
    col_t_title, col_t_clock = st.columns([2, 1])
    with col_t_title:
        st.markdown(f"<div class='subasta-header'>🎯 Remate Adelantado: {carrera_actual} (Máx. 17 Ejemplares)</div>", unsafe_allow_html=True)
    with col_t_clock:
        st.markdown(f"<div style='text-align: right; font-size: 16px; font-weight: bold; background-color: #161b22; padding: 6px 12px; border-radius: 6px; border: 1px solid #30363d; color: #00d2d3;'>🕒 Hora Venezuela: {ahora_dt.strftime('%I:%M:%S %p')}</div>", unsafe_allow_html=True)
    
    hora_limite = st.session_state.horas_cierre_remate.get(carrera_actual)
    carrera_cerrada = st.session_state.carreras_cerradas_remate.get(carrera_actual, False)
    estado_conteo = st.session_state.estado_conteo_carrera.get(carrera_actual, "INACTIVO")
    
    if hora_limite:
        dt_limite_dummy = datetime.combine(ahora_dt.date(), hora_limite)
        hora_limite_12h_str = dt_limite_dummy.strftime('%I:%M:%S %p')
        st.markdown(f"<div class='cierre-info-box'>⏰ Hora de Cierre Estricta para <b>{carrera_actual}</b>: <b>{hora_limite_12h_str}</b> (Internet)</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='cierre-info-box'>⚠️ Sin hora de cierre estricta configurada para <b>{carrera_actual}</b></div>", unsafe_allow_html=True)

    if hora_limite and not carrera_cerrada:
        dt_limite = datetime.combine(ahora_dt.date(), hora_limite)
        diferencia_segundos = (dt_limite - ahora_dt).total_seconds()
        
        if estado_conteo == "INACTIVO":
            if diferencia_segundos <= 10 and diferencia_segundos > 0:
                st.session_state.estado_conteo_carrera[carrera_actual] = "CONTEO_10S"
                st.session_state.tiempo_inicio_conteo[carrera_actual] = ahora_dt
                st.rerun()
            elif diferencia_segundos <= 0:
                st.session_state.carreras_cerradas_remate[carrera_actual] = True
                st.session_state.estado_conteo_carrera[carrera_actual] = "CERRADO"
                if not st.session_state.remates_cargados_en_cuentas.get(carrera_actual, False):
                    for cab, info in st.session_state.remates[carrera_actual].items():
                        if info['jugador'] != "Sin Postor" and info['monto'] > 0:
                            if info['jugador'] not in st.session_state.cuentas:
                                st.session_state.cuentas[info['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                            st.session_state.cuentas[info['jugador']]['Pujas'] += info['monto']
                            st.session_state.historial_transacciones.append({
                                "Carrera": carrera_actual, "Jugador": info['jugador'], 
                                "Tipo": "Cargo (Compra)", "Detalle": f"Adjudicación de {cab}", "Monto (Bs.)": -info['monto']
                            })
                    st.session_state.remates_cargados_en_cuentas[carrera_actual] = True
                st.rerun()
                
        elif estado_conteo == "CONTEO_10S":
            tiempo_inicio = st.session_state.tiempo_inicio_conteo.get(carrera_actual, ahora_dt)
            tiempo_transcurrido = (ahora_dt - tiempo_inicio).total_seconds()
            restantes_10s = max(0, 10 - int(tiempo_transcurrido))
            
            if restantes_10s > 0:
                st.markdown(f"<div class='timer-box'>⚠️ ¡ATENCIÓN! CIERRE INMINENTE EN: <b>{restantes_10s}</b> SEGUNDOS</div>", unsafe_allow_html=True)
            else:
                st.session_state.estado_conteo_carrera[carrera_actual] = "ESPERA_POST_PUJA"
                st.session_state.tiempo_inicio_conteo[carrera_actual] = ahora_dt
                st.rerun()
                
        elif estado_conteo == "ESPERA_POST_PUJA":
            tiempo_inicio = st.session_state.tiempo_inicio_conteo.get(carrera_actual, ahora_dt)
            tiempo_transcurrido = (ahora_dt - tiempo_inicio).total_seconds()
            restantes_3s = max(0, 3 - int(tiempo_transcurrido))
            
            if restantes_3s > 0:
                st.markdown(f"<div class='timer-box'>🔒 Conteo finalizado. Cerrando en {restantes_3s}s (Cualquier puja reinicia el conteo)...</div>", unsafe_allow_html=True)
            else:
                st.session_state.carreras_cerradas_remate[carrera_actual] = True
                st.session_state.estado_conteo_carrera[carrera_actual] = "CERRADO"
                if not st.session_state.remates_cargados_en_cuentas.get(carrera_actual, False):
                    for cab, info in st.session_state.remates[carrera_actual].items():
                        if info['jugador'] != "Sin Postor" and info['monto'] > 0:
                            if info['jugador'] not in st.session_state.cuentas:
                                st.session_state.cuentas[info['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                            st.session_state.cuentas[info['jugador']]['Pujas'] += info['monto']
                            st.session_state.historial_transacciones.append({
                                "Carrera": carrera_actual, "Jugador": info['jugador'], 
                                "Tipo": "Cargo (Compra)", "Detalle": f"Adjudicación de {cab}", "Monto (Bs.)": -info['monto']
                            })
                    st.session_state.remates_cargados_en_cuentas[carrera_actual] = True
                st.toast(f"🔒 ¡El remate para {carrera_actual} se ha cerrado estrictamente y cargado a cuentas!")
                st.rerun()

    col_izq_tabla, col_der_pujas = st.columns([1.5, 1], gap="medium")
    
    with col_izq_tabla:
        datos_tabla = []
        total_pote = 0.0
        for cab, info in st.session_state.remates[carrera_actual].items():
            datos_tabla.append({"Ejemplar": cab, "Comprador": info['jugador'], "Monto": formatear_bs(info['monto'])})
            total_pote += info['monto']
        
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True, height=420, key=f"tabla_remates_{carrera_actual}")
        
        monto_casa = total_pote * (porcentaje_casa / 100)
        pote_neto_base = total_pote - monto_casa

        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("💰 Pote", formatear_bs(total_pote))
        
        pote_incentivo_extra = c_m2.number_input(
            "🎁 Extra", 
            min_value=0.0, 
            value=0.0, 
            step=50.0, 
            key=f"pote_incentivo_{carrera_actual}"
        )
        
        premio_total_calculado = pote_neto_base + pote_incentivo_extra
        c_m3.metric("🏆 Premio", formatear_bs(premio_total_calculado))

    with col_der_pujas:
        carrera_cerrada = st.session_state.carreras_cerradas_remate.get(carrera_actual, False)
        
        with st.container(border=True):
            st.markdown("⚡ **Registro Dinámico de Puja**")
            
            lista_caballos_activos = list(st.session_state.remates[carrera_actual].keys())
            
            if not lista_caballos_activos:
                st.warning("No hay ejemplares en esta carrera.")
            else:
                st.markdown("Haz clic en el número del ejemplar para seleccionarlo:")
                cols_botones = st.columns(4)
                if f"caballo_seleccionado_click_{carrera_actual}" not in st.session_state or st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] not in lista_caballos_activos:
                    st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] = lista_caballos_activos[0]
                    
                for idx, cab_item in enumerate(lista_caballos_activos):
                    num_parte = cab_item.split(" - ")[0]
                    with cols_botones[idx % 4]:
                        if st.button(f"#{num_parte}", key=f"btn_rapido_cab_{carrera_actual}_{idx}", use_container_width=True):
                            st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] = cab_item
                
                caballo_seleccionado = st.session_state[f"caballo_seleccionado_click_{carrera_actual}"]
                st.info(f"🎯 Seleccionado: **{caballo_seleccionado}**")

                st.markdown("---")
                jugador = st.selectbox("Comprador / Jugador", st.session_state.lista_jugadores, key=f"sel_jugador_{carrera_actual}")
                
                puja_actual = st.session_state.remates[carrera_actual][caballo_seleccionado]['monto']
                st.caption(f"📌 Actual en **{caballo_seleccionado}**: `{formatear_bs(puja_actual)}`")
                
                opciones_escala = obtener_siguientes_montos(puja_actual)
                
                monto_puja = st.selectbox(
                    "Siguiente Monto (Escala)", 
                    opciones_escala, 
                    format_func=lambda x: formatear_bs(x),
                    key=f"sel_escala_monto_{carrera_actual}_{caballo_seleccionado}"
                )
                
                if carrera_cerrada:
                    st.warning("🔒 Este remate está cerrado estrictamente para nuevas pujas.")
                    st.button("🔨 Confirmar Puja", key=f"btn_pujar_{carrera_actual}", use_container_width=True, type="primary", disabled=True)
                else:
                    if st.button("🔨 Confirmar Puja", key=f"btn_pujar_{carrera_actual}", use_container_width=True, type="primary"):
                        if monto_puja <= puja_actual:
                            st.error(f"Debe ser mayor a {formatear_bs(puja_actual)}")
                        else:
                            st.session_state.remates[carrera_actual][caballo_seleccionado] = {"jugador": jugador, "monto": monto_puja}
                            
                            if estado_conteo in ["CONTEO_10S", "ESPERA_POST_PUJA"]:
                                st.session_state.estado_conteo_carrera[carrera_actual] = "CONTEO_10S"
                                st.session_state.tiempo_inicio_conteo[carrera_actual] = ahora_dt
                                st.toast("⚡ ¡Nueva puja registrada! El conteo regresivo se ha reiniciado por 10 segundos.")
                            else:
                                st.toast(f"✅ {caballo_seleccionado} ➡️ {jugador} ({formatear_bs(monto_puja)})")
                                
                            st.rerun()

# ==========================================
# PESTAÑA 2: GESTIÓN MANUAL DE CABALLOS
# ==========================================
with tab2:
    st.title("✍️ Gestión Manual con Paginación Automática (1 al 17)")
    st.markdown("Al inscribir un ejemplar, el sistema le asignará automáticamente el número consecutivo correspondiente desde el **1 hasta el 17**.")

    col_man_1, col_man_2 = st.columns(2)

    with col_man_1:
        st.subheader("➕ Añadir / Cargar Ejemplar")
        
        nombre_nuevo_caballo = st.text_input("Escribir Nombre del Caballo", placeholder="Ej: Rayo de Luz", key="input_nuevo_caballo_manual")
        
        if st.button("💾 Guardar y Asignar Número", use_container_width=True, type="primary"):
            nombre_limpio = nombre_nuevo_caballo.strip().title()
            if not nombre_limpio:
                st.error("⚠️ El nombre del ejemplar no puede estar vacío.")
            elif len(st.session_state.remates[carrera_actual]) >= 17:
                st.error("⚠️ Has alcanzado el límite máximo de 17 ejemplares para esta carrera.")
            else:
                elementos_actuales = list(st.session_state.remates[carrera_actual].keys())
                numeros_usados = []
                for elem in elementos_actuales:
                    match_num = re.match(r'^(\d+)', elem)
                    if match_num:
                        numeros_usados.append(int(match_num.group(1)))
                
                siguiente_num = 1
                while siguiente_num in numeros_usados and siguiente_num <= 17:
                    siguiente_num += 1
                
                if siguiente_num > 17:
                    st.error("⚠️ No hay posiciones disponibles (máximo 17).")
                else:
                    formato_llave = f"{siguiente_num} - {nombre_limpio}"
                    st.session_state.remates[carrera_actual][formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                    
                    if nombre_limpio not in st.session_state.banco_ejemplares:
                        st.session_state.banco_ejemplares.append(nombre_limpio)
                        
                    st.success(f"✅ Registrado como **{formato_llave}** en {carrera_actual}.")
                    st.rerun()

        st.markdown("---")
        st.subheader("📚 Cargar desde Banco Guardado")
        if st.session_state.banco_ejemplares:
            ejemplar_banco = st.selectbox("Seleccionar Ejemplar del Banco", st.session_state.banco_ejemplares, key="sel_banco_ejemplar_simple")
            if st.button("📥 Inscribir con Siguiente Número (1-17)", use_container_width=True):
                if len(st.session_state.remates[carrera_actual]) >= 17:
                    st.error("⚠️ Límite de 17 ejemplares alcanzado en esta carrera.")
                else:
                    nombre_limpio = re.sub(r'^\d+[\s\-\.\)]*', '', ejemplar_banco).strip().title()
                    
                    elementos_actuales = list(st.session_state.remates[carrera_actual].keys())
                    numeros_usados = []
                    for elem in elementos_actuales:
                        match_num = re.match(r'^(\d+)', elem)
                        if match_num:
                            numeros_usados.append(int(match_num.group(1)))
                            
                    siguiente_num = 1
                    while siguiente_num in numeros_usados and siguiente_num <= 17:
                        siguiente_num += 1
                        
                    if siguiente_num > 17:
                        st.error("⚠️ No hay posiciones disponibles.")
                    else:
                        formato_llave = f"{siguiente_num} - {nombre_limpio}"
                        if formato_llave not in st.session_state.remates[carrera_actual]:
                            st.session_state.remates[carrera_actual][formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                            st.success(f"✅ Añadido **{formato_llave}** a {carrera_actual}.")
                            st.rerun()
                        else:
                            st.warning("⚠️ Este ejemplar ya está inscrito en esta carrera.")

    with col_man_2:
        st.subheader("🗑️ Eliminar Ejemplares Inscritos")
        ejemplares_actuales_lista = list(st.session_state.remates[carrera_actual].keys())
        if ejemplares_actuales_lista:
            caballo_a_borrar = st.selectbox("Seleccionar Ejemplar a Remover", ejemplares_actuales_lista, key="sel_borrar_caballo")
            if st.button("🗑️ Eliminar Ejemplar Seleccionado", use_container_width=True, type="secondary"):
                del st.session_state.remates[carrera_actual][caballo_a_borrar]
                st.success(f"🗑️ Ejemplar {caballo_a_borrar} eliminado de {carrera_actual}.")
                st.rerun()
        else:
            st.info("No hay ejemplares inscritos en esta carrera.")

# ==========================================
# PESTAÑA 3: MÓDULO DE DUPLETA MODERNO Y SEGURO
# ==========================================
with tab3:
    st.title("🎟️ Módulo de Dupletas de La Rinconada")
    st.markdown("Crea combinaciones de forma rápida. El sistema valida automáticamente las carreras autorizadas y evita que se repita exactamente la misma combinación de ejemplares.")

    carreras_dup_activas = st.session_state.carreras_habilitadas_dupleta
    
    if not carreras_dup_activas:
        st.warning("⚠️ No hay carreras habilitadas para dupletas por el administrador en la barra lateral.")
    else:
        col_dup_izq, col_dup_der = st.columns([1.2, 1], gap="large")

        with col_dup_izq:
            with st.container(border=True):
                st.subheader("📝 Registrar Nueva Dupleta")
                
                jugador_dup = st.selectbox("Comprador / Jugador", st.session_state.lista_jugadores, key="sel_jugador_dupleta_simple")
                
                # Selector limpio de 2 o 3 selecciones
                tipo_dupleta = st.radio("Estructura de la Dupleta", ["Dupleta (2 Carreras)", "Trpleta (3 Carreras)"], horizontal=True, key="radio_tipo_dupleta_simple")
                num_picks = 2 if "2" in tipo_dupleta else 3
                
                picks_actuales = []
                carreras_elegidas = []
                bloqueo_carrera_repetida = True
                
                for i in range(num_picks):
                    st.markdown(f"**Selección #{i+1}**")
                    col_c_sel, col_e_sel = st.columns(2)
                    
                    with col_c_sel:
                        carr_sel = st.selectbox(f"Carrera #{i+1}", carreras_dup_activas, key=f"dup_carr_simple_{i}")
                    
                    with col_e_sel:
                        caballos_en_carr = list(st.session_state.remates.get(carr_sel, {}).keys())
                        cab_sel = st.selectbox(f"Ejemplar #{i+1}", caballos_en_carr if caballos_en_carr else ["Sin ejemplares"], key=f"dup_cab_simple_{i}")
                    
                    if carr_sel in carreras_elegidas:
                        bloqueo_carrera_repetida = False
                    else:
                        carreras_elegidas.append(carr_sel)
                        
                    picks_actuales.append({"Carrera": carr_sel, "Ejemplar": cab_sel})
                    if i < num_picks - 1:
                        st.markdown("---")

                monto_dup = st.number_input("Monto de la Dupleta (Bs.)", min_value=50.0, value=500.0, step=50.0, key="input_monto_dupleta_simple")
                
                # Cálculo de premio base estimado (x2 por cada logro)
                premio_estimado = monto_dup * (2 ** num_picks)
                st.info(f"💡 **Premio Estimado:** `{formatear_bs(premio_estimado)}`")

                if st.button("🎟️ Emitir Dupleta", use_container_width=True, type="primary"):
                    if not bloqueo_carrera_repetida:
                        st.error("⚠️ No puedes seleccionar la misma carrera two veces en una misma combinada.")
                    else:
                        # VERIFICAR BLOQUEO DE COMBINACIÓN EXACTAMENTE IGUAL
                        combinacion_actual_clave = tuple(sorted([(p["Carrera"], p["Ejemplar"]) for p in picks_actuales]))
                        
                        dupleta_repetida = False
                        for t_existente in st.session_state.dupletas_tickets:
                            if t_existente.get("Estado") != "Perdedor":
                                t_clave = tuple(sorted([(p["Carrera"], p["Ejemplar"]) for p in t_existente["Picks"]]))
                                if t_clave == combinacion_actual_clave:
                                    dupleta_repetida = True
                                    break
                        
                        if dupleta_repetida:
                            st.error("🚫 ¡Bloqueo de seguridad! Esta combinación exacta de ejemplares ya fue registrada previamente en otro ticket activo.")
                        else:
                            ticket_nuevo = {
                                "Jugador": jugador_dup,
                                "Picks": picks_actuales,
                                "Monto": monto_dup,
                                "Premio": premio_estimado,
                                "Estado": "En Curso",
                                "Fecha": ahora_dt.strftime('%I:%M:%S %p')
                            }
                            st.session_state.dupletas_tickets.append(ticket_nuevo)
                            
                            # Cargo automático a cuenta del jugador
                            if jugador_dup not in st.session_state.cuentas:
                                st.session_state.cuentas[jugador_dup] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                            st.session_state.cuentas[jugador_dup]['Pujas'] += monto_dup
                            
                            st.session_state.historial_transacciones.append({
                                "Carrera": "Dupleta", "Jugador": jugador_dup,
                                "Tipo": "Cargo (Dupleta)", "Detalle": f"Ticket de {num_picks} selecciones", "Monto (Bs.)": -monto_dup
                            })
                            
                            st.success("✅ ¡Dupleta registrada y cargada a cuentas exitosamente!")
                            st.rerun()

        with col_dup_der:
            st.subheader("📋 Tickets Emitidos (Visibilidad de Duplicados)")
            
            if not st.session_state.dupletas_tickets:
                st.info("No hay tickets registrados en esta sesión.")
            else:
                filtro_t = st.selectbox("Filtrar Estado", ["Todos", "En Curso", "Ganador", "Perdedor"], key="filtro_dupleta_simple")
                
                # Sección para mostrar tabla resumen general de combinaciones activas y evitar duplicados a simple vista
                with st.expander("🔍 Tabla Resumen de Combinaciones Activas", expanded=True):
                    datos_resumen_dup = []
                    for t_idx, tk in enumerate(st.session_state.dupletas_tickets):
                        picks_str = " + ".join([f"{p['Carrera']} ({p['Ejemplar']})" for p in tk['Picks']])
                        datos_resumen_dup.append({
                            "Tk #": t_idx + 1,
                            "Jugador": tk['Jugador'],
                            "Combinación": picks_str,
                            "Estado": tk['Estado']
                        })
                    st.dataframe(pd.DataFrame(datos_resumen_dup), use_container_width=True, hide_index=True)

                st.markdown("---")
                for idx_t, ticket in enumerate(st.session_state.dupletas_tickets):
                    if filtro_t != "Todos" and ticket['Estado'] != filtro_t:
                        continue
                        
                    badge_estado = "🟡" if ticket['Estado'] == "En Curso" else ("🟢" if ticket['Estado'] == "Ganador" else "🔴")
                    
                    with st.container(border=True):
                        st.markdown(f"**Ticket #{idx_t + 1}** {badge_estado} | **{ticket['Jugador']}**")
                        st.markdown(f"💰 **Monto:** `{formatear_bs(ticket['Monto'])}` | 🏆 **Premio:** `{formatear_bs(ticket['Premio'])}`")
                        
                        for p in ticket['Picks']:
                            st.caption(f"• **{p['Carrera']}** ➡️ {p['Ejemplar']}")
                            
                        c_acc1, c_acc2 = st.columns(2)
                        with c_acc1:
                            if st.button("✅ Ganador", key=f"btn_s_ganador_{idx_t}", use_container_width=True):
                                if ticket['Estado'] != "Ganador":
                                    st.session_state.dupletas_tickets[idx_t]['Estado'] = "Ganador"
                                    if ticket['Jugador'] not in st.session_state.cuentas:
                                        st.session_state.cuentas[ticket['Jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                                    st.session_state.cuentas[ticket['Jugador']]['Premios'] += ticket['Premio']
                                    st.session_state.historial_transacciones.append({
                                        "Carrera": "Dupleta", "Jugador": ticket['Jugador'],
                                        "Tipo": "Abono (Premio Dupleta)", "Detalle": f"Ticket #{idx_t + 1} acertado", "Monto (Bs.)": ticket['Premio']
                                    })
                                    st.success("¡Premio abonado al jugador!")
                                    st.rerun()
                        with c_acc2:
                            if st.button("❌ Perdedor", key=f"btn_s_perdedor_{idx_t}", use_container_width=True):
                                st.session_state.dupletas_tickets[idx_t]['Estado'] = "Perdedor"
                                st.rerun()

# ==========================================
# PESTAÑA 4: CIERRE Y LIQUIDACIÓN
# ==========================================
with tab4:
    st.title("🏁 Panel General de Cierre y Liquidación")
    st.markdown("Resumen de todas las carreras y su estado actual en la jornada.")

    for carr_item in lista_carreras_disponibles:
        with st.expander(f"📌 {carr_item}", expanded=False):
            c_est1, c_est2, c_est3 = st.columns(3)
            cerrada_estado = st.session_state.carreras_cerradas_remate.get(carr_item, False)
            liquidada_info = st.session_state.historial_ganadores.get(carr_item)
            
            c_est1.markdown(f"**Remate:** `{'Cerrado 🔒' if cerrada_estado else 'Abierto 🔓'}`")
            c_est2.markdown(f"**Liquidación:** `{'Liquidada 🏆' if liquidada_info else 'Pendiente ⏳'}`")
            
            total_carr = sum([info['monto'] for info in st.session_state.remates[carr_item].values()])
            c_est3.markdown(f"**Pote Total:** `{formatear_bs(total_carr)}`")
            
            if liquidada_info:
                st.success(f"🏆 Ganador: **{liquidada_info['Ganador']}** con el ejemplar **{liquidada_info['Caballo']}** — Premio: **{liquidada_info['Premio']}**")

# ==========================================
# PESTAÑA 5: CUENTAS POR JUGADOR
# ==========================================
with tab5:
    st.title("📊 Estado de Cuentas por Jugador")
    st.markdown("Balance financiero detallado de cada participante en la jornada.")

    tabla_cuentas = []
    total_general_pujas = 0.0
    total_general_premios = 0.0
    total_general_abonos = 0.0

    for jugador, valores in st.session_state.cuentas.items():
        neto = valores['Premios'] + valores['Abonos'] - valores['Pujas']
        tabla_cuentas.append({
            "Jugador": jugador,
            "Total Compras (Pujas)": formatear_bs(valores['Pujas']),
            "Total Premios": formatear_bs(valores['Premios']),
            "Abonos / Pagos": formatear_bs(valores['Abonos']),
            "Neto a Pagar / Cobrar": formatear_bs(neto)
        })
        total_general_pujas += valores['Pujas']
        total_general_premios += valores['Premios']
        total_general_abonos += valores['Abonos']

    st.dataframe(pd.DataFrame(tabla_cuentas), use_container_width=True, hide_index=True)

    c_g1, c_g2, c_g3, c_g4 = st.columns(4)
    c_g1.metric("🛒 Total Pujas Global", formatear_bs(total_general_pujas))
    c_g2.metric("🏆 Total Premios Global", formatear_bs(total_general_premios))
    c_g3.metric("💵 Total Abonos Global", formatear_bs(total_general_abonos))
    c_g4.metric("🏠 Utilidad Total Casa", formatear_bs(st.session_state.ganancia_casa))

    st.markdown("---")
    st.subheader("💵 Registrar Abono / Pago Manual a Jugador")
    c_ab1, c_ab2, c_ab3 = st.columns(3)
    with c_ab1:
        jugador_abono = st.selectbox("Seleccionar Jugador", st.session_state.lista_jugadores, key="sel_jugador_abono")
    with c_ab2:
        monto_abono = st.number_input("Monto del Abono (Bs.)", min_value=0.0, value=1000.0, step=100.0, key="input_monto_abono")
    with c_ab3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📥 Registrar Abono", use_container_width=True, type="primary"):
            if jugador_abono not in st.session_state.cuentas:
                st.session_state.cuentas[jugador_abono] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
            st.session_state.cuentas[jugador_abono]['Abonos'] += monto_abono
            st.session_state.historial_transacciones.append({
                "Carrera": "General", "Jugador": jugador_abono,
                "Tipo": "Abono / Pago", "Detalle": "Ingreso de dinero en cuenta", "Monto (Bs.)": monto_abono
            })
            st.success(f"✅ Abono de {formatear_bs(monto_abono)} registrado a {jugador_abono}.")
            st.rerun()

# ==========================================
# PESTAÑA 6: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab6:
    st.title("🧾 Historial Completo de Transacciones")
    st.markdown("Registro cronológico de cargos, abonos y movimientos en la jornada.")

    if not st.session_state.historial_transacciones:
        st.info("No hay transacciones registradas todavía.")
    else:
        df_transacciones = pd.DataFrame(st.session_state.historial_transacciones)
        st.dataframe(df_transacciones, use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 7: LECTOR TABULAR PDF
# ==========================================
with tab7:
    st.title("📄 Lector Tabular de PDF y Extracción")
    st.markdown("Sube un programa de carreras u hoja oficial en formato PDF para extraer su contenido de texto de forma estructurada.")

    pdf_subido = st.file_uploader("Subir Archivo PDF", type=["pdf"], key="uploader_pdf_tablas")

    if pdf_subido is not None:
        try:
            lector_pdf = PdfReader(pdf_subido)
            texto_completo_pdf = ""
            for idx_p, pagina in enumerate(lector_pdf.pages):
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto_completo_pdf += f"\n--- PÁGINA {idx_p + 1} ---\n" + texto_pagina

            st.success(f"✅ ¡PDF leído con éxito! Total de páginas: {len(lector_pdf.pages)}")
            
            with st.expander("🔍 Ver Texto Extraído del PDF", expanded=False):
                st.text_area("Contenido bruto", texto_completo_pdf, height=300)
                
            if st.button("📥 Importar como Programa del Día", type="primary"):
                lineas = texto_completo_pdf.split("\n")
                carrera_detectada_pdf = "Carrera 1"
                contador_caballos = 1
                
                nuevo_prog_dict = {}
                for linea in lineas:
                    linea_limpia = linea.strip()
                    if "carrera" in linea_limpia.lower():
                        carrera_detectada_pdf = linea_limpia.title()
                        if carrera_detectada_pdf not in nuevo_prog_dict:
                            nuevo_prog_dict[carrera_detectada_pdf] = {}
                        contador_caballos = 1
                    elif len(linea_limpia) > 3:
                        if carrera_detectada_pdf not in nuevo_prog_dict:
                            nuevo_prog_dict[carrera_detectada_pdf] = {}
                        if contador_caballos <= 17:
                            llave_cab = f"{contador_caballos} - {linea_limpia[:30].title()}"
                            nuevo_prog_dict[carrera_detectada_pdf][llave_cab] = {"jugador": "Sin Postor", "monto": 0.0}
                            contador_caballos += 1
                            
                if nuevo_prog_dict:
                    st.session_state.remates = nuevo_prog_dict
                    st.success("✅ ¡Programa importado exitosamente desde el PDF!")
                    st.rerun()
                else:
                    st.warning("⚠️ No se pudieron estructurar datos automáticos del PDF.")
                    
        except Exception as e:
            st.error(f"Error procesando el documento PDF: {e}")
