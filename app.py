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

# --- ESTADO DE BLOQUEO DE TICKET DE DUPLETA ---
if 'dupleta_bloqueada' not in st.session_state:
    st.session_state.dupleta_bloqueada = False

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
# --- BLOQUEO GENERAL DE TICKETS DE DUPLETA ---
with st.sidebar.expander("🔒 Bloqueo de Tickets de Dupleta", expanded=True):
    estado_actual_bloqueo = st.session_state.dupleta_bloqueada
    if estado_actual_bloqueo:
        st.markdown("<p style='color: #ff4757; font-weight: bold;'>🔴 Dupletas BLOQUEADAS (No se aceptan más tickets)</p>", unsafe_allow_html=True)
        if st.button("🔓 Desbloquear Dupletas", key="btn_desbloquear_dupleta_side", use_container_width=True, type="primary"):
            st.session_state.dupleta_bloqueada = False
            st.toast("🔓 ¡Módulo de dupletas desbloqueado!")
            st.rerun()
    else:
        st.markdown("<p style='color: #00d2d3; font-weight: bold;'>🟢 Dupletas ABIERTAS</p>", unsafe_allow_html=True)
        if st.button("🔒 Bloquear Dupletas", key="btn_bloquear_dupleta_side", use_container_width=True, type="secondary"):
            st.session_state.dupleta_bloqueada = True
            st.toast("🔒 ¡Módulo de dupletas bloqueado contra nuevos registros!")
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
                        st.error("⚠️ No hay posiciones disponibles (máximo 17).")
                    else:
                        formato_llave = f"{siguiente_num} - {nombre_limpio}"
                        if formato_llave not in st.session_state.remates[carrera_actual]:
                            st.session_state.remates[carrera_actual][formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                            st.success(f"✅ Inscrito: **{formato_llave}**")
                            st.rerun()
                        else:
                            st.warning("⚠️ Este ejemplar ya está inscrito en la carrera.")

    with col_man_2:
        st.subheader(f"📋 Ejemplares Inscritos en {carrera_actual}")
        
        datos_manuales = []
        for cab, info in st.session_state.remates[carrera_actual].items():
            datos_manuales.append({
                "Ejemplar": cab, 
                "Postor": info['jugador'], 
                "Monto": formatear_bs(info['monto'])
            })
            
        st.dataframe(pd.DataFrame(datos_manuales), use_container_width=True, hide_index=True, height=250)
        
        if st.session_state.remates[carrera_actual]:
            ejemplar_a_borrar = st.selectbox(
                "Seleccionar Ejemplar a Retirar", 
                list(st.session_state.remates[carrera_actual].keys()), 
                key="sel_borrar_ejemplar_manual"
            )
            if st.button("🗑️ Retirar Ejemplar Seleccionado", use_container_width=True, type="secondary"):
                del st.session_state.remates[carrera_actual][ejemplar_a_borrar]
                st.toast(f"🗑️ Ejemplar {ejemplar_a_borrar} retirado correctamente.")
                st.rerun()

# ==========================================
# PESTAÑA 3: MÓDULO DE DUPLETA PRO (SIN SELECCIONES DE EJEMPLAR IGUALES EN NINGÚN TICKET)
# ==========================================
with tab3:
    st.title("🎟️ Módulo de Dupletas Pro")
    st.markdown("Configura y registra jugadas combinadas (dupletas). **El pozo total de la dupleta se calcula sumando exactamente el valor de todos los tickets vendidos.** Los ejemplares se cargan dinámicamente según las carreras habilitadas, **no se permiten tickets con selecciones de ejemplares iguales** (independientemente del jugador), y puedes **bloquear/desbloquear** el registro desde la barra lateral.")

    carreras_habilitadas = st.session_state.carreras_habilitadas_dupleta

    col_dup_1, col_dup_2 = st.columns([1, 1], gap="large")

    with col_dup_1:
        st.subheader("📝 Registrar Nueva Dupleta")
        
        if st.session_state.dupleta_bloqueada:
            st.warning("🔒 **Módulo de Dupletas Bloqueado:** El administrador ha cerrado la recepción de nuevos tickets de dupleta.")
        
        jugador_dupleta = st.selectbox("Jugador / Comprador", st.session_state.lista_jugadores, key="sel_jugador_dupleta")
        monto_dupleta = st.number_input("Monto de la Dupleta (Bs.)", min_value=50.0, value=100.0, step=50.0, key="input_monto_dupleta")
        
        if len(carreras_habilitadas) < 2:
            st.warning("⚠️ Se necesitan al menos 2 carreras habilitadas en el administrador lateral para armar dupletas.")
        else:
            carrera_leg_1 = st.selectbox("1ra Carrera de la Dupleta", carreras_habilitadas, key="sel_dup_carr_1")
            
            # --- SELECCIÓN DINÁMICA DE EJEMPLARES (1RA VÁLIDA) ---
            caballos_carr_1 = list(st.session_state.remates.get(carrera_leg_1, {}).keys())
            caballo_leg_1 = st.selectbox("Ejemplar 1ra Válida (Dinámico)", caballos_carr_1 if caballos_carr_1 else ["Sin ejemplares"], key="sel_dup_cab_1")
            
            carreras_restantes = [c for c in carreras_habilitadas if c != carrera_leg_1]
            carrera_leg_2 = st.selectbox("2da Carrera de la Dupleta", carreras_restantes if carreras_restantes else [carrera_leg_1], key="sel_dup_carr_2")
            
            # --- SELECCIÓN DINÁMICA DE EJEMPLARES (2DA VÁLIDA) ---
            caballos_carr_2 = list(st.session_state.remates.get(carrera_leg_2, {}).keys())
            caballo_leg_2 = st.selectbox("Ejemplar 2da Válida (Dinámico)", caballos_carr_2 if caballos_carr_2 else ["Sin ejemplares"], key="sel_dup_cab_2")
            
            if st.session_state.dupleta_bloqueada:
                st.button("💾 Guardar Ticket de Dupleta", use_container_width=True, type="primary", disabled=True)
            else:
                if st.button("💾 Guardar Ticket de Dupleta", use_container_width=True, type="primary"):
                    leg_1_str = f"{carrera_leg_1} ({caballo_leg_1})"
                    leg_2_str = f"{carrera_leg_2} ({caballo_leg_2})"
                    
                    # --- VALIDACIÓN ESTRICTA: NO PUEDE HABER TICKETS CON SELECCIONES DE EJEMPLAR IGUALES ---
                    duplicado_ejemplares = False
                    for t in st.session_state.dupletas_tickets:
                        if (t.get("Leg_1") == leg_1_str and t.get("Leg_2") == leg_2_str):
                            duplicado_ejemplares = True
                            break
                    
                    if duplicado_ejemplares:
                        st.error("⚠️ **¡Selección de Ejemplares Duplicada!** Ya existe un ticket registrado con exactamente esta misma combinación de ejemplares para ambas válidas. No se permiten selecciones de ejemplares iguales en ningún ticket.")
                    else:
                        ticket_nuevo = {
                            "Jugador": jugador_dupleta,
                            "Monto": monto_dupleta,
                            "Leg_1": leg_1_str,
                            "Leg_2": leg_2_str,
                            "Estado": "En Curso"
                        }
                        st.session_state.dupletas_tickets.append(ticket_nuevo)
                        
                        if jugador_dupleta not in st.session_state.cuentas:
                            st.session_state.cuentas[jugador_dupleta] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                        st.session_state.cuentas[jugador_dupleta]['Pujas'] += monto_dupleta
                        
                        st.session_state.historial_transacciones.append({
                            "Carrera": "Dupleta", "Jugador": jugador_dupleta,
                            "Tipo": "Cargo (Dupleta)", "Detalle": f"Ticket: {ticket_nuevo['Leg_1']} + {ticket_nuevo['Leg_2']}", "Monto (Bs.)": -monto_dupleta
                        })
                        
                        st.toast(f"✅ ¡Dupleta registrada con éxito para {jugador_dupleta}!")
                        st.rerun()

    with col_dup_2:
        st.subheader("📊 Tickets de Dupletas Activos y Pozo Total")
        
        # --- CÁLCULO DEL POZO COMO LA SUMA DE LOS TICKETS ---
        pozo_total_dupletas = sum([t.get("Monto", 0.0) for t in st.session_state.dupletas_tickets])
        st.metric("💰 Pozo Acumulado de Dupletas (Suma de Tickets)", formatear_bs(pozo_total_dupletas))
        st.markdown("---")

        if not st.session_state.dupletas_tickets:
            st.info("No hay tickets de dupleta registrados en esta jornada.")
        else:
            datos_dup_tabla = []
            for idx, t in enumerate(st.session_state.dupletas_tickets):
                datos_dup_tabla.append({
                    "ID": idx + 1,
                    "Jugador": t.get("Jugador", "Desconocido"),
                    "Monto": formatear_bs(t.get("Monto", 0.0)),
                    "1era Válida": t.get("Leg_1", "-"),
                    "2da Válida": t.get("Leg_2", "-"),
                    "Estado": t.get("Estado", "En Curso")
                })
            st.dataframe(pd.DataFrame(datos_dup_tabla), use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 4: CIERRE Y LIQUIDACIÓN
# ==========================================
with tab4:
    st.title("🏁 Panel Consolidado de Cierre y Liquidación")
    st.markdown("Visualiza el estatus global de todas las carreras, el acumulado de la casa y el estado de adjudicación.")

    col_liq_1, col_liq_2 = st.columns(2)
    with col_liq_1:
        st.metric("🏦 Ganancia Acumulada de la Casa", formatear_bs(st.session_state.ganancia_casa))
    with col_liq_2:
        total_potes_jornada = sum([info['monto'] for carr in st.session_state.remates.values() for info in carr.values()])
        st.metric("🏇 Potes Totales en Juego (Jornada)", formatear_bs(total_potes_jornada))

    st.markdown("---")
    st.subheader("📋 Resumen de Carreras de la Jornada")

    resumen_jornada = []
    for carr in lista_carreras_disponibles:
        cerrada = st.session_state.carreras_cerradas_remate.get(carr, False)
        liquidada = carr in st.session_state.historial_ganadores
        pote_carr = sum([info['monto'] for info in st.session_state.remates[carr].values()])
        
        ganador_info = st.session_state.historial_ganadores.get(carr, {})
        ganador_str = ganador_info.get("Ganador", "Pendiente / Sin Liquidar")
        caballo_str = ganador_info.get("Caballo", "-")
        
        estatus_txt = "Pendiente"
        if liquidada:
            estatus_txt = "🏆 Liquidada"
        elif cerrada:
            estatus_txt = "🔒 Cerrado"
            
        resumen_jornada.append({
            "Carrera": carr,
            "Estatus": estatus_txt,
            "Pote Total": formatear_bs(pote_carr),
            "Ganador Caballo": caballo_str,
            "Afortunado": ganador_str
        })

    st.dataframe(pd.DataFrame(resumen_jornada), use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 5: CUENTAS POR JUGADOR
# ==========================================
with tab5:
    st.title("📊 Estado de Cuenta Consolidado por Jugador")
    st.markdown("Balance general detallado de cargos (pujas/compras), abonos (premios), pagos y saldo neto por cada participante.")

    # --- LISTADO DE DEUDAS ACTIVAS DIRECTAS ---
    st.subheader("🔴 Deudas Pendientes de Jugadores")
    
    jugadores_con_deuda = []
    for jugador, vals in st.session_state.cuentas.items():
        pujas = vals.get('Pujas', 0.0)
        premios = vals.get('Premios', 0.0)
        abonos = vals.get('Abonos', 0.0)
        neto = (premios + abonos) - pujas
        if neto < 0:
            jugadores_con_deuda.append((jugador, abs(neto)))

    if not jugadores_con_deuda:
        st.success("🎉 ¡Excelente! No hay jugadores con deudas pendientes en este momento.")
    else:
        st.markdown("Selecciona el jugador de la lista de deudores para aplicar su **Pago Total** de forma directa:")
        
        for jug_deudor, monto_deuda in jugadores_con_deuda:
            col_d1, col_d2, col_d3 = st.columns([2, 2, 1])
            with col_d1:
                st.markdown(f"👤 **{jug_deudor}**")
            with col_d2:
                st.markdown(f"Deuda: <span style='color: #ff4757; font-weight: bold;'>{formatear_bs(monto_deuda)}</span>", unsafe_allow_html=True)
            with col_d3:
                if st.button("✅ Pagar Total", key=f"btn_pago_directo_{jug_deudor}", use_container_width=True, type="primary"):
                    st.session_state.cuentas[jug_deudor]['Abonos'] += monto_deuda
                    st.session_state.historial_transacciones.append({
                        "Carrera": "Caja", 
                        "Jugador": jug_deudor,
                        "Tipo": "Abono (Pago Total)", 
                        "Detalle": f"Cancelación total de saldo pendiente ({formatear_bs(monto_deuda)})", 
                        "Monto (Bs.)": monto_deuda
                    })
                    st.toast(f"🎉 ¡Pago total de {formatear_bs(monto_deuda)} aplicado directamente a {jug_deudor}!")
                    st.rerun()
        st.markdown("---")

    # --- TABLA GENERAL DE CUENTAS ---
    st.markdown("### 📋 Resumen General de Cuentas")
    datos_cuentas = []
    total_general_pujas = 0.0
    total_general_premios = 0.0
    total_general_abonos = 0.0
    total_general_neto = 0.0

    for jugador, vals in st.session_state.cuentas.items():
        pujas = vals.get('Pujas', 0.0)
        premios = vals.get('Premios', 0.0)
        abonos = vals.get('Abonos', 0.0)
        neto = (premios + abonos) - pujas
        
        total_general_pujas += pujas
        total_general_premios += premios
        total_general_abonos += abonos
        total_general_neto += neto
        
        datos_cuentas.append({
            "Jugador": jugador,
            "Total Pujas / Compras": formatear_bs(pujas),
            "Total Premios": formatear_bs(premios),
            "Abonos / Pagos": formatear_bs(abonos),
            "Saldo Neto": formatear_bs(neto)
        })

    st.dataframe(pd.DataFrame(datos_cuentas), use_container_width=True, hide_index=True)

    c_tot_1, c_tot_2, c_tot_3 = st.columns(3)
    c_tot_1.metric("📉 Total General Compras", formatear_bs(total_general_pujas))
    c_tot_2.metric("🏆 Total General Premios", formatear_bs(total_general_premios))
    c_tot_3.metric("💰 Balance Neto Global", formatear_bs(total_general_neto))

    st.markdown("---")
    
    with st.container(border=True):
        st.subheader("💵 Sección de Abono de Deuda Parcial")
        st.markdown("Aplica un abono rápido por monto fijo seleccionando el jugador.")
        
        jugador_abono = st.selectbox("Jugador (Abono)", st.session_state.lista_jugadores, key="sel_jugador_abono_simple")
        
        col_b_ab1, col_b_ab2, col_b_ab3 = st.columns(3)
        if col_b_ab1.button("Bs. 50", key="btn_ab_50", use_container_width=True):
            monto_abono_elegido = 50.0
            if jugador_abono not in st.session_state.cuentas:
                st.session_state.cuentas[jugador_abono] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
            st.session_state.cuentas[jugador_abono]['Abonos'] += monto_abono_elegido
            st.session_state.historial_transacciones.append({
                "Carrera": "Caja", "Jugador": jugador_abono,
                "Tipo": "Abono (Pago Parcial)", "Detalle": f"Abono rápido de {formatear_bs(monto_abono_elegido)}", "Monto (Bs.)": monto_abono_elegido
            })
            st.toast(f"✅ Abono de {formatear_bs(monto_abono_elegido)} registrado a {jugador_abono}.")
            st.rerun()
            
        if col_b_ab2.button("Bs. 100", key="btn_ab_100", use_container_width=True):
            monto_abono_elegido = 100.0
            if jugador_abono not in st.session_state.cuentas:
                st.session_state.cuentas[jugador_abono] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
            st.session_state.cuentas[jugador_abono]['Abonos'] += monto_abono_elegido
            st.session_state.historial_transacciones.append({
                "Carrera": "Caja", "Jugador": jugador_abono,
                "Tipo": "Abono (Pago Parcial)", "Detalle": f"Abono rápido de {formatear_bs(monto_abono_elegido)}", "Monto (Bs.)": monto_abono_elegido
            })
            st.toast(f"✅ Abono de {formatear_bs(monto_abono_elegido)} registrado a {jugador_abono}.")
            st.rerun()
            
        if col_b_ab3.button("Bs. 200", key="btn_ab_200", use_container_width=True):
            monto_abono_elegido = 200.0
            if jugador_abono not in st.session_state.cuentas:
                st.session_state.cuentas[jugador_abono] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
            st.session_state.cuentas[jugador_abono]['Abonos'] += monto_abono_elegido
            st.session_state.historial_transacciones.append({
                "Carrera": "Caja", "Jugador": jugador_abono,
                "Tipo": "Abono (Pago Parcial)", "Detalle": f"Abono rápido de {formatear_bs(monto_abono_elegido)}", "Monto (Bs.)": monto_abono_elegido
            })
            st.toast(f"✅ Abono de {formatear_bs(monto_abono_elegido)} registrado a {jugador_abono}.")
            st.rerun()

# ==========================================
# PESTAÑA 6: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab6:
    st.title("🧾 Historial Detallado de Transacciones")
    st.markdown("Registro cronológico de todas las operaciones financieras efectuadas en la plataforma.")

    if not st.session_state.historial_transacciones:
        st.info("No hay transacciones registradas todavía.")
    else:
        df_trans = pd.DataFrame(st.session_state.historial_transacciones)
        st.dataframe(df_trans, use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 7: LECTOR TABULAR PDF
# ==========================================
with tab7:
    st.title("📄 Lector Tabular de Programas en PDF")
    st.markdown("Sube el programa oficial de carreras en formato PDF para extraer automáticamente los ejemplares y estructurarlos.")

    archivo_pdf = st.file_uploader("Subir Archivo PDF del Programa", type=["pdf"], key="uploader_programa_pdf")
    
    if archivo_pdf is not None:
        try:
            lector_pdf = PdfReader(archivo_pdf)
            texto_extraido_total = ""
            for pagina in lector_pdf.pages:
                t = pagina.extract_text()
                if t:
                    texto_extraido_total += t + "\n"
            
            st.success("✅ ¡PDF leído exitosamente!")
            with st.expander("🔍 Ver texto bruto extraído", expanded=False):
                st.text(texto_extraido_total[:3000])
                
        except Exception as e:
            st.error(f"Error procesando el documento PDF: {e}")
