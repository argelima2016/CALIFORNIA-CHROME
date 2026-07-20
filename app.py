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
                            st.success(f"✅ Ejemplar {formato_llave} cargado exitosamente en {carrera_actual}.")
                            st.rerun()
                        else:
                            st.warning("⚠️ Este ejemplar ya se encuentra inscrito en esta carrera.")

    with col_man_2:
        st.subheader("📋 Ejemplares Inscritos Actuales")
        ciber_items = list(st.session_state.remates[carrera_actual].keys())
        if not ciber_items:
            st.info("No hay ejemplares cargados.")
        else:
            for item in ciber_items:
                col_i1, col_i2 = st.columns([3, 1])
                with col_i1:
                    st.markdown(f"• **{item}**")
                with col_i2:
                    if st.button("🗑️", key=f"del_cab_{carrera_actual}_{item}"):
                        del st.session_state.remates[carrera_actual][item]
                        st.toast(f"🗑️ Eliminado {item}")
                        st.rerun()

# ==========================================
# PESTAÑA 3: MÓDULO DE DUPLETA PRO
# ==========================================
with tab3:
    st.title("🎟️ Módulo de Dupleta Pro")
    st.markdown("Arma tus tickets combinando ganadores de las carreras habilitadas. (No se permiten tickets con combinaciones idénticas).")

    col_dup_1, col_dup_2 = st.columns([1, 1], gap="large")

    with col_dup_1:
        st.subheader("📝 Registrar Nuevo Ticket")
        jugador_dupleta = st.selectbox("Jugador / Dueño del Ticket", st.session_state.lista_jugadores, key="sel_jugador_dupleta")
        monto_dupleta = st.number_input("Monto Apostado (Bs.)", min_value=50.0, value=500.0, step=50.0, key="num_monto_dupleta")

        carreras_h = st.session_state.carreras_habilitadas_dupleta
        if not carreras_h:
            st.warning("⚠️ No hay carreras habilitadas para dupletas por el administrador.")
        else:
            seleccion_etapas = {}
            for carr in carreras_h:
                caballos_carr = list(st.session_state.remates.get(carr, {}).keys())
                opciones_caballos = ["-- Seleccionar --"] + caballos_carr
                sel_cab = st.selectbox(f"Ganador para {carr}", opciones_caballos, key=f"dupleta_sel_{carr}")
                if sel_cab != "-- Seleccionar --":
                    seleccion_etapas[carr] = sel_cab

            if st.button("🎟️ Emitir Ticket de Dupleta", type="primary", use_container_width=True):
                if len(seleccion_etapas) < 2:
                    st.error("⚠️ Debes seleccionar al menos 2 ejemplares en diferentes carreras para armar una dupleta válida.")
                else:
                    # Validar que no exista un ticket idéntico (misma combinación exacta de carreras y ejemplares)
                    ticket_duplicado = False
                    for t_existente in st.session_state.dupletas_tickets:
                        if t_existente['etapas'] == seleccion_etapas:
                            ticket_duplicado = True
                            break

                    if ticket_duplicado:
                        st.error("⚠️ ¡Ya existe un ticket registrado con exactamente esta misma combinación de ejemplares y carreras!")
                    else:
                        nuevo_ticket = {
                            "id": len(st.session_state.dupletas_tickets) + 1,
                            "jugador": jugador_dupleta,
                            "monto": monto_dupleta,
                            "etapas": seleccion_etapas,
                            "estado": "En Curso"
                        }
                        st.session_state.dupletas_tickets.append(nuevo_ticket)
                        
                        if jugador_dupleta not in st.session_state.cuentas:
                            st.session_state.cuentas[jugador_dupleta] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                        st.session_state.cuentas[jugador_dupleta]['Pujas'] += monto_dupleta
                        st.session_state.historial_transacciones.append({
                            "Carrera": "Dupleta", "Jugador": jugador_dupleta,
                            "Tipo": "Cargo (Dupleta)", "Detalle": f"Ticket #{nuevo_ticket['id']} emitido", "Monto (Bs.)": -monto_dupleta
                        })
                        
                        st.success(f"✅ ¡Ticket de Dupleta #{nuevo_ticket['id']} emitido con éxito!")
                        st.rerun()

    with col_dup_2:
        st.subheader("📜 Tickets Registrados y Premios")
        # El premio es el acumulado total en tickets emitidos
        pote_total_dupletas = sum([t['monto'] for t in st.session_state.dupletas_tickets])
        st.metric("🏆 Premio Acumulado (Total Dupletas)", formatear_bs(pote_total_dupletas))
        st.markdown("---")

        if not st.session_state.dupletas_tickets:
            st.info("No hay tickets de dupleta registrados.")
        else:
            for t in st.session_state.dupletas_tickets:
                with st.container(border=True):
                    st.markdown(f"**Ticket #{t['id']}** | Jugador: **{t['jugador']}** | Monto: `{formatear_bs(t['monto'])}`")
                    st.markdown(f"Estado: **{t['estado']}**")
                    for c_key, cab_val in t['etapas'].items():
                        ganador_real = st.session_state.historial_ganadores.get(c_key, {}).get("Caballo")
                        if ganador_real:
                            if ganador_real == cab_val:
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;✅ `{c_key}`: **{cab_val}** (Acertado)")
                            else:
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;❌ `{c_key}`: **{cab_val}** (Fallado - Real: {ganador_real})")
                        else:
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;⏳ `{c_key}`: **{cab_val}** (Pendiente)")

# ==========================================
# PESTAÑA 4: CIERRE Y LIQUIDACIÓN
# ==========================================
with tab4:
    st.title("🏁 Cierre y Liquidación de Carreras")
    st.markdown("Resumen general del estado de las carreras y panel de control de ganadores.")

    for carr in lista_carreras_disponibles:
        with st.expander(f"📁 {carr} - Estado: {'Liquidada 🏆' if carr in st.session_state.historial_ganadores else ('Cerrada 🔒' if st.session_state.carreras_cerradas_remate.get(carr) else 'Abierta 🟢')}"):
            if carr in st.session_state.historial_ganadores:
                info_h = st.session_state.historial_ganadores[carr]
                st.success(f"🏆 Ganador Oficial: **{info_h['Ganador']}** con el ejemplar **{info_h['Caballo']}**. Premio entregado: **{info_h['Premio']}**")
            else:
                total_c = sum([i['monto'] for i in st.session_state.remates[carr].values()])
                st.markdown(f"Pote acumulado actual: **{formatear_bs(total_c)}**")
                
                caballos_carr_list = list(st.session_state.remates[carr].keys())
                if caballos_carr_list:
                    ganador_sel = st.selectbox("Seleccionar Ejemplar Ganador", caballos_carr_list, key=f"liq_tab4_{carr}")
                    if st.button(f"🏆 Liquidar {carr}", key=f"btn_liq_tab4_{carr}", type="primary"):
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

                        m_casa = total_c * (porcentaje_casa / 100)
                        p_neto = total_c - m_casa
                        p_extra = st.session_state.get(f"pote_incentivo_{carr}", 0.0)
                        premio_total = p_neto + p_extra

                        info_g = st.session_state.remates[carr][ganador_sel]
                        if info_g['jugador'] != "Sin Postor":
                            if info_g['jugador'] not in st.session_state.cuentas:
                                st.session_state.cuentas[info_g['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                            st.session_state.cuentas[info_g['jugador']]['Premios'] += premio_total
                            st.session_state.historial_transacciones.append({
                                "Carrera": carr, "Jugador": info_g['jugador'], 
                                "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {ganador_sel}", "Monto (Bs.)": premio_total
                            })
                        st.session_state.ganancia_casa += m_casa
                        st.session_state.historial_ganadores[carr] = {
                            "Ganador": info_g['jugador'], "Caballo": ganador_sel, "Premio": formatear_bs(premio_total)
                        }
                        st.success(f"¡Carrera {carr} liquidada con éxito!")
                        st.rerun()

# ==========================================
# PESTAÑA 5: CUENTAS POR JUGADOR
# ==========================================
with tab5:
    st.title("📊 Cuentas Corrientes por Jugador")
    st.markdown("Balance general de compras (pujas) frente a premios obtenidos y abonos en efectivo.")

    datos_cuentas = []
    total_general_pujas = 0.0
    total_general_premios = 0.0
    total_general_abonos = 0.0
    total_general_neto = 0.0

    for jugador, vals in st.session_state.cuentas.items():
        pujas = vals['Pujas']
        premios = vals['Premios']
        abonos = vals['Abonos']
        neto = premios + abonos - pujas

        total_general_pujas += pujas
        total_general_premios += premios
        total_general_abonos += abonos
        total_general_neto += neto

        datos_cuentas.append({
            "Jugador": jugador,
            "Total Pujas (-)": formatear_bs(pujas),
            "Total Premios (+)": formatear_bs(premios),
            "Abonos (+)": formatear_bs(abonos),
            "Neto a Pagar / Cobrar": formatear_bs(neto)
        })

    st.dataframe(pd.DataFrame(datos_cuentas), use_container_width=True, hide_index=True)

    st.markdown("---")
    c_res1, c_res2, c_res3, c_res4 = st.columns(4)
    c_res1.metric("Total Pujas", formatear_bs(total_general_pujas))
    c_res2.metric("Total Premios", formatear_bs(total_general_premios))
    c_res3.metric("Ganancia Acumulada Casa", formatear_bs(st.session_state.ganancia_casa))
    c_res4.metric("Balance Neto Global", formatear_bs(total_general_neto))

    st.markdown("---")
    st.subheader("💵 Registrar Abono de Dinero en Efectivo/Pago")
    col_ab1, col_ab2, col_ab3 = st.columns(3)
    with col_ab1:
        jugador_abonar = st.selectbox("Jugador", st.session_state.lista_jugadores, key="sel_jugador_abono")
    with col_ab2:
        monto_abonar = st.number_input("Monto del Abono (Bs.)", min_value=0.0, value=1000.0, step=100.0, key="num_monto_abono")
    with col_ab3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Registrar Abono", type="primary", use_container_width=True):
            if jugador_abonar not in st.session_state.cuentas:
                st.session_state.cuentas[jugador_abonar] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
            st.session_state.cuentas[jugador_abonar]['Abonos'] += monto_abonar
            st.session_state.historial_transacciones.append({
                "Carrera": "General", "Jugador": jugador_abonar,
                "Tipo": "Abono (Efectivo)", "Detalle": "Ingreso de dinero a cuenta", "Monto (Bs.)": monto_abonar
            })
            st.success(f"✅ Abono de {formatear_bs(monto_abonar)} registrado a {jugador_abonar}.")
            st.rerun()

# ==========================================
# PESTAÑA 6: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab6:
    st.title("🧾 Historial de Transacciones")
    st.markdown("Registro cronológico detallado de todos los movimientos financieros generados en la jornada.")

    if not st.session_state.historial_transacciones:
        st.info("No hay transacciones registradas todavía.")
    else:
        df_tx = pd.DataFrame(st.session_state.historial_transacciones)
        st.dataframe(df_tx, use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 7: LECTOR TABULAR PDF
# ==========================================
with tab7:
    st.title("📄 Lector Tabular PDF de Programas Oficiales")
    st.markdown("Sube el PDF oficial del programa de carreras para extraer y cargar automáticamente los ejemplares.")

    archivo_pdf_subido = st.file_uploader("Seleccionar Archivo PDF", type=["pdf"], key="uploader_pdf_programa")

    if archivo_pdf_subido is not None:
        try:
            lector_pdf = PdfReader(archivo_pdf_subido)
            texto_extraido_completo = ""
            for pagina in lector_pdf.pages:
                t_pag = pagina.extract_text()
                if t_pag:
                    texto_extraido_completo += t_pag + "\n"

            st.success(f"✅ PDF leído con éxito ({len(lector_pdf.pages)} páginas procesadas).")
            
            with st.expander("🔍 Ver texto extraído en bruto", expanded=False):
                st.text(texto_extraido_completo[:3000])

            if st.button("📥 Importar Ejemplares del PDF a la Carrera Activa", type="primary"):
                lineas = texto_extraido_completo.split('\n')
                contador_importados = 0
                for linea in lineas:
                    linea_limpia = linea.strip()
                    if re.match(r'^\d+[\s\-\.\)]+', linea_limpia):
                        if len(st.session_state.remates[carrera_actual]) < 17:
                            nombre_cab = re.sub(r'^\d+[\s\-\.\)]*', '', linea_limpia).strip().title()
                            if len(nombre_cab) > 2:
                                elementos_actuales = list(st.session_state.remates[carrera_actual].keys())
                                numeros_usados = [int(re.match(r'^(\d+)', e).group(1)) for e in elementos_actuales if re.match(r'^(\d+)', e)]
                                
                                siguiente_num = 1
                                while siguiente_num in numeros_usados and siguiente_num <= 17:
                                    siguiente_num += 1
                                    
                                if siguiente_num <= 17:
                                    llave_nueva = f"{siguiente_num} - {nombre_cab}"
                                    if llave_nueva not in st.session_state.remates[carrera_actual]:
                                        st.session_state.remates[carrera_actual][llave_nueva] = {"jugador": "Sin Postor", "monto": 0.0}
                                        if nombre_cab not in st.session_state.banco_ejemplares:
                                            st.session_state.banco_ejemplares.append(nombre_cab)
                                        contador_importados += 1

                st.success(f"✅ Se importaron {contador_importados} ejemplares automáticamente a **{carrera_actual}**.")
                st.rerun()

        except Exception as e:
                st.error(f"❌ Error al procesar el archivo PDF: {e}")
