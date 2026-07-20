import streamlit as st
import pandas as pd
import io
import os
import re
import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="Sistema de Remates, Dupletas y PDF en Vivo", layout="wide", page_icon="🏇")

# --- AUTOREFRESH OPTIMIZADO (3 SEGUNDOS) ---
st_autorefresh(interval=3000, key="datarefresh_en_vivo")

# --- HORA LOCAL DE VENEZUELA (ESTRICTA 12 HORAS) ---
def obtener_hora_venezuela_local():
    try:
        zona_venezuela = ZoneInfo("America/Caracas")
        return datetime.now(zona_venezuela).replace(tzinfo=None)
    except (ZoneInfoNotFoundError, Exception):
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
    except (FileNotFoundError, ValueError, Exception):
        return ["CASA", "SOMBI", "LUIS", "CARLOS", "RAMON", "ALDEA", "ANGEL", "ALFONSO", "MACANO", "MIGUEL", "TOCAYO", "EL GOCHO", "PAPIRO", "CHAYO", "ALEXIS"]

# --- ARCHIVO DE RESPALDO LOCAL (JSON) ---
ARCHIVO_BACKUP = "estado_jornada_backup.json"

def guardar_estado_json():
    try:
        # Serializar estado excluyendo elementos complejos de session_state si los hubiera
        estado_serializable = {
            "remates": st.session_state.get('remates', {}),
            "banco_ejemplares": st.session_state.get('banco_ejemplares', []),
            "historial_ganadores": st.session_state.get('historial_ganadores', {}),
            "carreras_cerradas_remate": st.session_state.get('carreras_cerradas_remate', {}),
            "remates_cargados_en_cuentas": st.session_state.get('remates_cargados_en_cuentas', {}),
            "horas_cierre_remate": {k: v.strftime("%H:%M") for k, v in st.session_state.get('horas_cierre_remate', {}).items()},
            "cuentas": st.session_state.get('cuentas', {}),
            "ganancia_casa": st.session_state.get('ganancia_casa', 0.0),
            "historial_transacciones": st.session_state.get('historial_transacciones', []),
            "dupletas_tickets": st.session_state.get('dupletas_tickets', []),
            "carreras_habilitadas_dupleta": st.session_state.get('carreras_habilitadas_dupleta', []),
            "dupleta_bloqueada": st.session_state.get('dupleta_bloqueada', False)
        }
        with open(ARCHIVO_BACKUP, "w", encoding="utf-8") as f:
            json.dump(estado_serializable, f, ensure_ascii=False, indent=4)
    except Exception as e:
        pass

def cargar_estado_json():
    if os.path.exists(ARCHIVO_BACKUP):
        try:
            with open(ARCHIVO_BACKUP, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state.remates = data.get("remates", {})
                st.session_state.banco_ejemplares = data.get("banco_ejemplares", [])
                st.session_state.historial_ganadores = data.get("historial_ganadores", {})
                st.session_state.carreras_cerradas_remate = data.get("carreras_cerradas_remate", {})
                st.session_state.remates_cargados_en_cuentas = data.get("remates_cargados_en_cuentas", {})
                
                horas_cargadas = {}
                for k, v in data.get("horas_cierre_remate", {}).items():
                    partes = v.split(":")
                    horas_cargadas[k] = time(int(partes[0]), int(partes[1]))
                st.session_state.horas_cierre_remate = horas_cargadas
                
                st.session_state.cuentas = data.get("cuentas", {})
                st.session_state.ganancia_casa = data.get("ganancia_casa", 0.0)
                st.session_state.historial_transacciones = data.get("historial_transacciones", [])
                st.session_state.dupletas_tickets = data.get("dupletas_tickets", [])
                st.session_state.carreras_habilitadas_dupleta = data.get("carreras_habilitadas_dupleta", [])
                st.session_state.dupleta_bloqueada = data.get("dupleta_bloqueada", False)
                return True
        except Exception:
            return False
    return False

# --- ESTADO GLOBAL DE LA SESIÓN ---
if 'lista_jugadores' not in st.session_state:
    st.session_state.lista_jugadores = cargar_jugadores_base()

if 'banco_ejemplares' not in st.session_state:
    st.session_state.banco_ejemplares = ["Gran Alex", "Rey David", "Sombra Negra", "Rayo Veloz", "Catire Bory", "Doña Rosa"]

# Intentar restaurar sesión si no existe previamente
if 'remates' not in st.session_state or not st.session_state.remates:
    cargado_exitoso = cargar_estado_json()
    if not cargado_exitoso:
        st.session_state.remates = {}
        st.session_state.historial_ganadores = {}
        st.session_state.carreras_cerradas_remate = {}
        st.session_state.remates_cargados_en_cuentas = {}
        st.session_state.horas_cierre_remate = {}
        st.session_state.estado_conteo_carrera = {}
        st.session_state.tiempo_inicio_conteo = {}
        st.session_state.cuentas = {j: {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0} for j in st.session_state.lista_jugadores}
        st.session_state.ganancia_casa = 0.0
        st.session_state.historial_transacciones = []
        st.session_state.dupletas_tickets = []
        st.session_state.carreras_habilitadas_dupleta = []
        st.session_state.dupleta_bloqueada = False

if 'estado_conteo_carrera' not in st.session_state:
    st.session_state.estado_conteo_carrera = {}
if 'tiempo_inicio_conteo' not in st.session_state:
    st.session_state.tiempo_inicio_conteo = {}

def formatear_bs(monto):
    return f"Bs. {monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# ⚙️ BARRA LATERAL Y CARGA DE PROGRAMA
# ==========================================
st.sidebar.header("⚙️ Barra Lateral")

ahora_dt = obtener_hora_venezuela_local()
st.sidebar.markdown(f"🕒 **Hora Venezuela:** `{ahora_dt.strftime('%I:%M:%S %p')}`")

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
        except (FileNotFoundError, ValueError, Exception) as e:
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
            guardar_estado_json()
            st.toast(f"✅ ¡Hora estricta guardada para {carrera_actual}!")
            st.rerun()
            
    with col_btn_h2:
        if st.button("🗑️ Borrar", key=f"btn_clear_hora_{carrera_actual}", use_container_width=True):
            if carrera_actual in st.session_state.horas_cierre_remate:
                del st.session_state.horas_cierre_remate[carrera_actual]
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            guardar_estado_json()
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
            guardar_estado_json()
            st.toast(f"🔒 ¡El remate para {carrera_actual} ha sido cerrado y cargado!")
            st.rerun()
    else:
        st.success("🔒 Remate cerrado y cargado.")
        if st.button("🔓 Reabrir Remate", key=f"btn_reabrir_remate_side_{carrera_actual}", use_container_width=True):
            st.session_state.carreras_cerradas_remate[carrera_actual] = False
            st.session_state.remates_cargados_en_cuentas[carrera_actual] = False
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            guardar_estado_json()
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
                    "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {caballo_ganador_side}", "Monto (Bs.)": premio_total_calculado_side
                })
            st.session_state.ganancia_casa += monto_casa_side
            st.session_state.historial_ganadores[carrera_actual] = {
                "Ganador": info_ganador['jugador'], "Caballo": caballo_ganador_side, "Premio": formatear_bs(premio_total_calculado_side)
            }
            guardar_estado_json()
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
        guardar_estado_json()
        st.toast("✅ ¡Carreras de dupleta actualizadas!")
        st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("🔒 Bloqueo de Tickets de Dupleta", expanded=True):
    estado_actual_bloqueo = st.session_state.dupleta_bloqueada
    if estado_actual_bloqueo:
        st.markdown("<p style='color: #ff4757; font-weight: bold;'>🔴 Dupletas BLOQUEADAS</p>", unsafe_allow_html=True)
        if st.button("🔓 Desbloquear Dupletas", key="btn_desbloquear_dupleta_side", use_container_width=True, type="primary"):
            st.session_state.dupleta_bloqueada = False
            guardar_estado_json()
            st.toast("🔓 ¡Módulo de dupletas desbloqueado!")
            st.rerun()
    else:
        st.markdown("<p style='color: #00d2d3; font-weight: bold;'>🟢 Dupletas ABIERTAS</p>", unsafe_allow_html=True)
        if st.button("🔒 Bloquear Dupletas", key="btn_bloquear_dupleta_side", use_container_width=True, type="secondary"):
            st.session_state.dupleta_bloqueada = True
            guardar_estado_json()
            st.toast("🔒 ¡Módulo de dupletas bloqueado!")
            st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Reiniciar Jornada Global", use_container_width=True, type="secondary"):
    for key in list(st.session_state.keys()):
        if key != 'banco_ejemplares':
            del st.session_state[key]
    if os.path.exists(ARCHIVO_BACKUP):
        os.remove(ARCHIVO_BACKUP)
    st.toast("🚨 Jornada reiniciada por completo.")
    st.rerun()

with st.sidebar.expander("🐴 🗑️ Opciones Avanzadas del Banco", expanded=False):
    if st.button("🗑️ Reiniciar Banco de Caballos", use_container_width=True, type="secondary"):
        st.session_state.banco_ejemplares = []
        guardar_estado_json()
        st.toast("🚨 ¡Banco vaciado!")
        st.rerun()

# --- INTERFAZ DE PESTAÑAS ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏇 Remate Adelantado", 
    "✍️ Gestión Manual (Caballos)", 
    "🎟️ Módulo de Dupleta Pro", 
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
        st.markdown(f"<div class='cierre-info-box'>⏰ Hora de Cierre Estricta para <b>{carrera_actual}</b>: <b>{hora_limite_12h_str}</b></div>", unsafe_allow_html=True)
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
                guardar_estado_json()
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
                guardar_estado_json()
                st.toast(f"🔒 ¡El remate para {carrera_actual} se ha cerrado estrictamente!")
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
                    st.warning("🔒 Este remate está cerrado estrictamente.")
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
                                st.toast("⚡ ¡Puja registrada! Conteo reiniciado.")
                            else:
                                st.toast(f"✅ {caballo_seleccionado} ➡️ {jugador} ({formatear_bs(monto_puja)})")
                            
                            guardar_estado_json()
                            st.rerun()

# ==========================================
# PESTAÑA 2: GESTIÓN MANUAL DE CABALLOS
# ==========================================
with tab2:
    st.title("✍️ Gestión Manual con Paginación Automática (1 al 17)")
    st.markdown("Al inscribir un ejemplar, el sistema le asignará automáticamente el número consecutivo del **1 al 17**.")

    col_man_1, col_man_2 = st.columns(2)

    with col_man_1:
        st.subheader("➕ Añadir / Cargar Ejemplar")
        nombre_nuevo_caballo = st.text_input("Escribir Nombre del Caballo", placeholder="Ej: Rayo de Luz", key="input_nuevo_caballo_manual")
        
        if st.button("💾 Guardar y Asignar Número", use_container_width=True, type="primary"):
            nombre_limpio = nombre_nuevo_caballo.strip().title()
            if not nombre_limpio:
                st.error("⚠️ El nombre del ejemplar no puede estar vacío.")
            elif len(st.session_state.remates[carrera_actual]) >= 17:
                st.error("⚠️ Has alcanzado el límite máximo de 17 ejemplares.")
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
                    st.error("⚠️ No hay posiciones disponibles.")
                else:
                    formato_llave = f"{siguiente_num} - {nombre_limpio}"
                    st.session_state.remates[carrera_actual][formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                    if nombre_limpio not in st.session_state.banco_ejemplares:
                        st.session_state.banco_ejemplares.append(nombre_limpio)
                    guardar_estado_json()
                    st.success(f"✅ Registrado como **{formato_llave}**.")
                    st.rerun()

        st.markdown("---")
        st.subheader("📚 Cargar desde Banco Guardado")
        if st.session_state.banco_ejemplares:
            ejemplar_banco = st.selectbox("Seleccionar Ejemplar del Banco", st.session_state.banco_ejemplares, key="sel_banco_ejemplar_simple")
            if st.button("📥 Inscribir desde Banco", use_container_width=True):
                nombre_limpio = str(ejemplar_banco).strip().title()
                if len(st.session_state.remates[carrera_actual]) >= 17:
                    st.error("⚠️ Límite de 17 ejemplares alcanzado.")
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
                    
                    if siguiente_num <= 17:
                        formato_llave = f"{siguiente_num} - {nombre_limpio}"
                        if formato_llave not in st.session_state.remates[carrera_actual]:
                            st.session_state.remates[carrera_actual][formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                            guardar_estado_json()
                            st.success(f"✅ Añadido: {formato_llave}")
                            st.rerun()
                        else:
                            st.warning("El ejemplar ya está inscrito.")
        else:
            st.info("El banco de nombres está vacío.")

    with col_man_2:
        st.subheader("🗑️ Eliminar Ejemplar Individual")
        carr_actual_ejemplares = list(st.session_state.remates[carrera_actual].keys())
        if carr_actual_ejemplares:
            cab_a_borrar = st.selectbox("Seleccionar Ejemplar a Remover", carr_actual_ejemplares, key="sel_borrar_caballo")
            if st.button("🗑️ Eliminar Ejemplar Seleccionado", use_container_width=True, type="secondary"):
                del st.session_state.remates[carrera_actual][cab_a_borrar]
                guardar_estado_json()
                st.success(f"🗑️ Ejemplar {cab_a_borrar} removido.")
                st.rerun()
        else:
            st.info("No hay ejemplares registrados.")

# ==========================================
# PESTAÑA 3: MÓDULO DE DUPLETA PRO
# ==========================================
with tab3:
    st.markdown("<div class='subasta-header'>🎟️ Módulo de Dupleta Pro (Sistema de Apuestas Combinadas)</div>", unsafe_allow_html=True)
    st.markdown("Arma tu ticket combinando ganadores de las carreras habilitadas.")

    if st.session_state.dupleta_bloqueada:
        st.error("🔴 **Módulo de Dupletas BLOQUEADO por la administración.**")

    col_dup_1, col_dup_2 = st.columns([1, 1], gap="large")

    with col_dup_1:
        with st.container(border=True):
            st.subheader("📝 Registrar Nuevo Ticket de Dupleta")
            
            jugador_dupleta = st.selectbox("Jugador / Postor (Dupleta)", st.session_state.lista_jugadores, key="sel_jugador_dupleta")
            
            carreras_disp_dup = st.session_state.carreras_habilitadas_dupleta
            if not carreras_disp_dup:
                st.warning("⚠️ No hay carreras habilitadas para dupleta.")
            else:
                seleccion_carreras_ticket = st.multiselect(
                    "Seleccionar Carreras (Mínimo 2)", 
                    options=carreras_disp_dup,
                    key="multiselect_carreras_dupleta"
                )
                
                detalles_selecciones = {}
                Valido_ticket = True
                
                if len(seleccion_carreras_ticket) >= 2:
                    st.markdown("---")
                    st.markdown("🎯 **Selecciona el ejemplar para cada carrera escogida:**")
                    for c_sel in seleccion_carreras_ticket:
                        caballos_en_carrera = list(st.session_state.remates.get(c_sel, {}).keys())
                        if caballos_en_carrera:
                            cab_elegido = st.selectbox(f"Ejemplar para {c_sel}", caballos_en_carrera, key=f"dup_cab_{c_sel}")
                            detalles_selecciones[c_sel] = cab_elegido
                        else:
                            st.error(f"La carrera {c_sel} no tiene ejemplares cargados.")
                            Valido_ticket = False
                else:
                    st.info("💡 Selecciona al menos 2 carreras.")
                    Valido_ticket = False

                monto_apuesta_dupleta = st.number_input(
                    "Monto de la Apuesta (Bs.)", 
                    min_value=10.0, 
                    value=100.0, 
                    step=50.0, 
                    key="input_monto_dupleta"
                )

                if st.session_state.dupleta_bloqueada:
                    st.button("🎟️ Emitir y Registrar Ticket", key="btn_emitir_dupleta_bloqueado", use_container_width=True, type="primary", disabled=True)
                else:
                    if st.button("🎟️ Emitir y Registrar Ticket", key="btn_emitir_dupleta", use_container_width=True, type="primary"):
                        if not Valido_ticket or len(seleccion_carreras_ticket) < 2:
                            st.error("⚠️ Debes seleccionar al menos 2 carreras configuradas.")
                        else:
                            id_ticket = f"DUP-{int(datetime.now().timestamp())}"
                            nuevo_ticket = {
                                "ID": id_ticket,
                                "Jugador": jugador_dupleta,
                                "Carreras": seleccion_carreras_ticket,
                                "Detalles": detalles_selecciones,
                                "Monto": monto_apuesta_dupleta,
                                "Estado": "En Curso",
                                "Premio": 0.0
                            }
                            st.session_state.dupletas_tickets.append(nuevo_ticket)
                            
                            if jugador_dupleta not in st.session_state.cuentas:
                                st.session_state.cuentas[jugador_dupleta] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                            st.session_state.cuentas[jugador_dupleta]['Pujas'] += monto_apuesta_dupleta
                            
                            st.session_state.historial_transacciones.append({
                                "Carrera": "Múltiple", "Jugador": jugador_dupleta,
                                "Tipo": "Cargo (Dupleta)", "Detalle": f"Ticket {id_ticket} ({len(seleccion_carreras_ticket)} pasos)", "Monto (Bs.)": -monto_apuesta_dupleta
                            })
                            
                            guardar_estado_json()
                            st.success(f"✅ ¡Ticket **{id_ticket}** emitido exitosamente!")
                            st.rerun()

    with col_dup_2:
        st.subheader("📋 Tickets de Dupleta Emitidos")
        if not st.session_state.dupletas_tickets:
            st.info("No hay tickets de dupleta registrados.")
        else:
            for idx_t, ticket in enumerate(st.session_state.dupletas_tickets):
                with st.expander(f"Ticket: {ticket['ID']} | Jugador: {ticket['Jugador']}"):
                    st.markdown(f"**Monto Jugado:** `{formatear_bs(ticket['Monto'])}`")
                    st.markdown("**Selecciones:**")
                    for carr_t, cab_t in ticket['Detalles'].items():
                        ganador_real = st.session_state.historial_ganadores.get(carr_t, {}).get("Caballo")
                        if ganador_real:
                            if ganador_real == cab_t:
                                st.markdown(f"- ✅ `{carr_t}`: **{cab_t}** (ACERTADO)")
                            else:
                                st.markdown(f"- ❌ `{carr_t}`: **{cab_t}** (Fallado - Ganó: {ganador_real})")
                        else:
                            st.markdown(f"- ⏳ `{carr_t}`: **{cab_t}** (Pendiente)")
                    
                    if st.button(f"🗑️ Anular Ticket {ticket['ID']}", key=f"btn_anular_dup_{idx_t}"):
                        if ticket['Jugador'] in st.session_state.cuentas:
                            st.session_state.cuentas[ticket['Jugador']]['Pujas'] -= ticket['Monto']
                        st.session_state.dupletas_tickets.pop(idx_t)
                        guardar_estado_json()
                        st.warning(f"Ticket {ticket['ID']} anulado.")
                        st.rerun()

# ==========================================
# PESTAÑA 4: CIERRE Y LIQUIDACIÓN
# ==========================================
with tab4:
    st.markdown("<div class='subasta-header'>🏁 Cierre y Liquidación de Carreras</div>", unsafe_allow_html=True)
    st.markdown("Panel de control global para liquidar premios.")

    for carr_item in lista_carreras_disponibles:
        with st.container(border=True):
            col_l1, col_l2, col_l3 = st.columns([1.5, 2, 1.5])
            
            with col_l1:
                st.markdown(f"### 🏇 {carr_item}")
                cerrada_estado = st.session_state.carreras_cerradas_remate.get(carr_item, False)
                liquidada_estado = carr_item in st.session_state.historial_ganadores
                
                if liquidada_estado:
                    st.markdown("<p style='color: #00d2d3; font-weight: bold;'>🟢 Liquidada</p>", unsafe_allow_html=True)
                elif cerrada_estado:
                    st.markdown("<p style='color: #f1e05a; font-weight: bold;'>🔒 Cerrada</p>", unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color: #ff4757; font-weight: bold;'>🔴 Abierta</p>", unsafe_allow_html=True)

            with col_l2:
                total_pote_carr = sum([info['monto'] for info in st.session_state.remates.get(carr_item, {}).values()])
                monto_casa_carr = total_pote_carr * (porcentaje_casa / 100)
                pote_neto_carr = total_pote_carr - monto_casa_carr
                incentivo_carr = st.session_state.get(f"pote_incentivo_{carr_item}", 0.0)
                premio_final_carr = pote_neto_carr + incentivo_carr
                
                st.markdown(f"**Pote Total:** `{formatear_bs(total_pote_carr)}`")
                st.markdown(f"**Retención Casa ({porcentaje_casa}%):** `{formatear_bs(monto_casa_carr)}`")
                st.markdown(f"**Premio a Repartir:** `{formatear_bs(premio_final_carr)}`")

            with col_l3:
                if liquidada_estado:
                    info_g = st.session_state.historial_ganadores[carr_item]
                    st.success(f"Ganador: {info_g['Ganador']}\n({info_g['Caballo']})")
                else:
                    caballos_carr_opc = list(st.session_state.remates.get(carr_item, {}).keys())
                    if caballos_carr_opc:
                        ganador_sel_tab4 = st.selectbox(f"Ejemplar Ganador", caballos_carr_opc, key=f"sel_ganador_tab4_{carr_item}")
                        if st.button(f"🏆 Liquidar {carr_item}", key=f"btn_liq_tab4_{carr_item}", type="primary", use_container_width=True):
                            if not st.session_state.remates_cargados_en_cuentas.get(carr_item, False):
                                for cab, info in st.session_state.remates[carr_item].items():
                                    if info['jugador'] != "Sin Postor" and info['monto'] > 0:
                                        if info['jugador'] not in st.session_state.cuentas:
                                            st.session_state.cuentas[info['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                                        st.session_state.cuentas[info['jugador']]['Pujas'] += info['monto']
                                        st.session_state.historial_transacciones.append({
                                            "Carrera": carr_item, "Jugador": info['jugador'], 
                                            "Tipo": "Cargo (Compra)", "Detalle": f"Adjudicación de {cab}", "Monto (Bs.)": -info['monto']
                                        })
                                st.session_state.remates_cargados_en_cuentas[carr_item] = True
                            
                            info_ganador_t4 = st.session_state.remates[carr_item][ganador_sel_tab4]
                            if info_ganador_t4['jugador'] != "Sin Postor":
                                if info_ganador_t4['jugador'] not in st.session_state.cuentas:
                                    st.session_state.cuentas[info_ganador_t4['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                                st.session_state.cuentas[info_ganador_t4['jugador']]['Premios'] += premio_final_carr
                                st.session_state.historial_transacciones.append({
                                    "Carrera": carr_item, "Jugador": info_ganador_t4['jugador'], 
                                    "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {ganador_sel_tab4}", "Monto (Bs.)": premio_final_carr
                                })
                            
                            st.session_state.ganancia_casa += monto_casa_carr
                            st.session_state.historial_ganadores[carr_item] = {
                                "Ganador": info_ganador_t4['jugador'], "Caballo": ganador_sel_tab4, "Premio": formatear_bs(premio_final_carr)
                            }
                            st.session_state.carreras_cerradas_remate[carr_item] = True
                            guardar_estado_json()
                            st.success(f"¡Carrera {carr_item} liquidada!")
                            st.rerun()
                    else:
                        st.warning("Sin ejemplares.")

# ==========================================
# PESTAÑA 5: CUENTAS POR JUGADOR
# ==========================================
with tab5:
    st.markdown("<div class='subasta-header'>📊 Estado de Cuentas por Jugador</div>", unsafe_allow_html=True)
    st.markdown("Balance general que resume compras, premios obtenidos, abonos y saldo neto.")

    datos_cuentas = []
    total_general_pujas = 0.0
    total_general_premios = 0.0
    total_general_abonos = 0.0
    total_general_neto = 0.0

    for jugador, valores in st.session_state.cuentas.items():
        pujas = valores['Pujas']
        premios = valores['Premios']
        abonos = valores['Abonos']
        neto = (premios + abonos) - pujas
        
        total_general_pujas += pujas
        total_general_premios += premios
        total_general_abonos += abonos
        total_general_neto += neto
        
        datos_cuentas.append({
            "Jugador": jugador,
            "Total Compras": formatear_bs(pujas),
            "Total Premios": formatear_bs(premios),
            "Abonos Extra": formatear_bs(abonos),
            "Saldo Neto": formatear_bs(neto)
        })

    st.dataframe(pd.DataFrame(datos_cuentas), use_container_width=True, hide_index=True)

    st.markdown("---")
    col_inf_1, col_inf_2, col_inf_3, col_inf_4 = st.columns(4)
    col_inf_1.metric("🛒 Total Compras Global", formatear_bs(total_general_pujas))
    col_inf_2.metric("🏆 Total Premios Global", formatear_bs(total_general_premios))
    col_inf_3.metric("🏠 Utilidad Acumulada Casa", formatear_bs(st.session_state.ganancia_casa))
    col_inf_4.metric("⚖️ Balance General Neto", formatear_bs(total_general_neto))

    st.markdown("---")
    with st.expander("💵 Registrar Abono / Pago de Jugador", expanded=False):
        col_ab_1, col_ab_2, col_ab_3 = st.columns(3)
        with col_ab_1:
            jugador_abono = st.selectbox("Seleccionar Jugador", st.session_state.lista_jugadores, key="sel_jugador_abono")
        with col_ab_2:
            monto_abono = st.number_input("Monto del Abono (Bs.)", min_value=0.0, value=100.0, step=50.0, key="input_monto_abono")
        with col_ab_3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Registrar Abono", use_container_width=True, type="primary"):
                if jugador_abono not in st.session_state.cuentas:
                    st.session_state.cuentas[jugador_abono] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                st.session_state.cuentas[jugador_abono]['Abonos'] += monto_abono
                st.session_state.historial_transacciones.append({
                    "Carrera": "General", "Jugador": jugador_abono,
                    "Tipo": "Abono (Pago)", "Detalle": "Registro manual de abono", "Monto (Bs.)": monto_abono
                })
                guardar_estado_json()
                st.success(f"✅ Abono de {formatear_bs(monto_abono)} registrado para {jugador_abono}.")
                st.rerun()

# ==========================================
# PESTAÑA 6: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab6:
    st.markdown("<div class='subasta-header'>🧾 Historial Completo de Transacciones</div>", unsafe_allow_html=True)
    st.markdown("Registro cronológico de todas las operaciones financieras.")

    if not st.session_state.historial_transacciones:
        st.info("No hay transacciones registradas.")
    else:
        df_trans = pd.DataFrame(st.session_state.historial_transacciones)
        st.dataframe(df_trans, use_container_width=True, hide_index=True)

        csv_data = df_trans.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Historial en CSV",
            data=csv_data,
            file_name=f"historial_transacciones_{datetime.today().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# ==========================================
# PESTAÑA 7: LECTOR TABULAR PDF
# ==========================================
with tab7:
    st.markdown("<div class='subasta-header'>📄 Lector Tabular de PDF (Programa Oficial)</div>", unsafe_allow_html=True)
    st.markdown("Sube un archivo PDF con la programación oficial de carreras.")

    archivo_pdf_subido = st.file_uploader("Subir Archivo PDF del Programa", type=["pdf"], key="uploader_pdf_programa")

    if archivo_pdf_subido is not None:
        try:
            lector_pdf = PdfReader(archivo_pdf_subido)
            texto_extraido_total = ""
            for pagina in lector_pdf.pages:
                t_pag = pagina.extract_text()
                if t_pag:
                    texto_extraido_total += t_pag + "\n"

            st.success(f"✅ PDF leído con éxito ({len(lector_pdf.pages)} páginas procesadas).")
            
            with st.expander("🔍 Ver Texto Extraído del PDF", expanded=False):
                st.text_area("Texto bruto", texto_extraido_total, height=250)

            if st.button("⚡ Procesar e Importar al Sistema", type="primary", use_container_width=True):
                lineas = texto_extraido_total.split('\n')
                carrera_detectada_actual = "Carrera 1"
                contador_carrera_num = 1
                
                for linea in lineas:
                    linea_limpia = linea.strip()
                    if "carrera" in linea_limpia.lower():
                        match_c = re.search(r'\d+', linea_limpia)
                        if match_c:
                            contador_carrera_num = int(match_c.group(0))
                            carrera_detectada_actual = f"Carrera {contador_carrera_num}"
                            if carrera_detectada_actual not in st.session_state.remates:
                                st.session_state.remates[carrera_detectada_actual] = {}
                    
                    match_caballo = re.match(r'^(\d+)[\s\-\.\)]+(.+)', linea_limpia)
                    if match_caballo and len(linea_limpia) < 50:
                        num_cab = int(match_caballo.group(1))
                        nom_cab = match_caballo.group(2).strip().title()
                        if num_cab <= 17 and nom_cab:
                            llave_cab = f"{num_cab} - {nom_cab}"
                            if carrera_detectada_actual not in st.session_state.remates:
                                st.session_state.remates[carrera_detectada_actual] = {}
                            if len(st.session_state.remates[carrera_detectada_actual]) < 17:
                                st.session_state.remates[carrera_detectada_actual][llave_cab] = {"jugador": "Sin Postor", "monto": 0.0}

                guardar_estado_json()
                st.success("✅ ¡Programa importado y estructurado correctamente desde el PDF!")
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error al procesar el archivo PDF: {e}")
