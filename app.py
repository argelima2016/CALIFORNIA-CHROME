import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader
from streamlit_autorefresh import st_autorefresh

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
            st.toast(f"✅ ¡Hora estricta guardada a las {dt_dummy.strftime('%I:%M:%S %p')} para {carrera_actual}!")
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
            st.toast(f"🔒 ¡Remate cerrado para {carrera_actual}!")
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
                    "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {caballo_ganador_side}", "Monto (Bs.)": premio_total_calculado_side
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
    seleccion_admin = []
    for carr in lista_carreras_disponibles:
        default_val = carr in st.session_state.carreras_habilitadas_dupleta
        if st.checkbox(carr, value=default_val, key=f"chk_admin_carr_side_{carr}"):
            seleccion_admin.append(carr)
    if st.button("💾 Guardar Selección", key="btn_save_admin_side", use_container_width=True):
        st.session_state.carreras_habilitadas_dupleta = seleccion_admin
        st.toast("✅ ¡Carreras actualizadas!")
        st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("🔒 Bloqueo de Tickets de Dupleta", expanded=True):
    if st.session_state.dupleta_bloqueada:
        st.markdown("<p style='color: #ff4757; font-weight: bold;'>🔴 Dupletas BLOQUEADAS</p>", unsafe_allow_html=True)
        if st.button("🔓 Desbloquear", key="btn_desbloquear_dupleta_side", use_container_width=True, type="primary"):
            st.session_state.dupleta_bloqueada = False
            st.rerun()
    else:
        st.markdown("<p style='color: #00d2d3; font-weight: bold;'>🟢 Dupletas ABIERTAS</p>", unsafe_allow_html=True)
        if st.button("🔒 Bloquear", key="btn_bloquear_dupleta_side", use_container_width=True, type="secondary"):
            st.session_state.dupleta_bloqueada = True
            st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Reiniciar Jornada Global", use_container_width=True, type="secondary"):
    for key in list(st.session_state.keys()):
        if key != 'banco_ejemplares':
            del st.session_state[key]
    st.toast("🚨 Jornada reiniciada.")
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
        st.markdown(f"<div class='subasta-header'>🎯 Remate Adelantado: {carrera_actual}</div>", unsafe_allow_html=True)
    with col_t_clock:
        st.markdown(f"<div style='text-align: right; font-size: 14px; font-weight: bold; background-color: #161b22; padding: 6px; border-radius: 6px; border: 1px solid #30363d; color: #00d2d3;'>🕒 {ahora_dt.strftime('%I:%M:%S %p')}</div>", unsafe_allow_html=True)
    
    hora_limite = st.session_state.horas_cierre_remate.get(carrera_actual)
    carrera_cerrada = st.session_state.carreras_cerradas_remate.get(carrera_actual, False)
    estado_conteo = st.session_state.estado_conteo_carrera.get(carrera_actual, "INACTIVO")
    
    if hora_limite:
        dt_limite_dummy = datetime.combine(ahora_dt.date(), hora_limite)
        st.markdown(f"<div class='cierre-info-box'>⏰ Cierre Estricta: <b>{dt_limite_dummy.strftime('%I:%M:%S %p')}</b></div>", unsafe_allow_html=True)

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
                st.markdown(f"<div class='timer-box'>⚠️ CIERRE INMINENTE EN: <b>{restantes_10s}s</b></div>", unsafe_allow_html=True)
            else:
                st.session_state.estado_conteo_carrera[carrera_actual] = "ESPERA_POST_PUJA"
                st.session_state.tiempo_inicio_conteo[carrera_actual] = ahora_dt
                st.rerun()

    col_izq_tabla, col_der_pujas = st.columns([1.5, 1], gap="medium")
    
    with col_izq_tabla:
        datos_tabla = []
        total_pote = 0.0
        for cab, info in st.session_state.remates[carrera_actual].items():
            datos_tabla.append({"Ejemplar": cab, "Comprador": info['jugador'], "Monto": formatear_bs(info['monto'])})
            total_pote += info['monto']
        
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True, height=420)
        
        monto_casa = total_pote * (porcentaje_casa / 100)
        pote_neto_base = total_pote - monto_casa

        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("💰 Pote", formatear_bs(total_pote))
        pote_incentivo_extra = c_m2.number_input("🎁 Extra", min_value=0.0, value=0.0, step=50.0, key=f"pote_incentivo_{carrera_actual}")
        premio_total_calculado = pote_neto_base + pote_incentivo_extra
        c_m3.metric("🏆 Premio", formatear_bs(premio_total_calculado))

    with col_der_pujas:
        with st.container(border=True):
            st.markdown("⚡ **Registro Dinámico**")
            lista_caballos_activos = list(st.session_state.remates[carrera_actual].keys())
            
            if not lista_caballos_activos:
                st.warning("Sin ejemplares.")
            else:
                if f"caballo_seleccionado_click_{carrera_actual}" not in st.session_state or st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] not in lista_caballos_activos:
                    st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] = lista_caballos_activos[0]
                    
                cols_botones = st.columns(4)
                for idx, cab_item in enumerate(lista_caballos_activos):
                    num_parte = cab_item.split(" - ")[0]
                    with cols_botones[idx % 4]:
                        if st.button(f"#{num_parte}", key=f"btn_rapido_cab_{carrera_actual}_{idx}", use_container_width=True):
                            st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] = cab_item
                
                caballo_seleccionado = st.session_state[f"caballo_seleccionado_click_{carrera_actual}"]
                st.caption(f"🎯 Seleccionado: **{caballo_seleccionado}**")

                jugador = st.selectbox("Jugador", st.session_state.lista_jugadores, key=f"sel_jugador_{carrera_actual}")
                puja_actual = st.session_state.remates[carrera_actual][caballo_seleccionado]['monto']
                
                opciones_escala = obtener_siguientes_montos(puja_actual)
                monto_puja = st.selectbox("Monto", opciones_escala, format_func=lambda x: formatear_bs(x), key=f"sel_escala_monto_{carrera_actual}_{caballo_seleccionado}")
                
                if carrera_cerrada:
                    st.button("🔨 Confirmar Puja", key=f"btn_pujar_{carrera_actual}", use_container_width=True, type="primary", disabled=True)
                else:
                    if st.button("🔨 Confirmar Puja", key=f"btn_pujar_{carrera_actual}", use_container_width=True, type="primary"):
                        if monto_puja <= puja_actual:
                            st.error("Debe ser mayor")
                        else:
                            st.session_state.remates[carrera_actual][caballo_seleccionado] = {"jugador": jugador, "monto": monto_puja}
                            st.rerun()

# ==========================================
# PESTAÑA 2: GESTIÓN MANUAL DE CABALLOS
# ==========================================
with tab2:
    st.title("✍️ Gestión Manual (1 al 17)")
    col_man_1, col_man_2 = st.columns(2)
    with col_man_1:
        nombre_nuevo_caballo = st.text_input("Nombre del Caballo", placeholder="Ej: Rayo de Luz", key="input_nuevo_caballo_manual")
        if st.button("💾 Guardar", use_container_width=True, type="primary"):
            nombre_limpio = nombre_nuevo_caballo.strip().title()
            if nombre_limpio and len(st.session_state.remates[carrera_actual]) < 17:
                nums = [int(re.match(r'^(\d+)', e).group(1)) for e in st.session_state.remates[carrera_actual].keys() if re.match(r'^(\d+)', e)]
                siguiente_num = 1
                while siguiente_num in nums and siguiente_num <= 17:
                    siguiente_num += 1
                st.session_state.remates[carrera_actual][f"{siguiente_num} - {nombre_limpio}"] = {"jugador": "Sin Postor", "monto": 0.0}
                st.rerun()
    with col_man_2:
        for cab_key in list(st.session_state.remates[carrera_actual].keys()):
            col_info, col_del = st.columns([4, 1])
            with col_info: st.text(cab_key)
            with col_del:
                if st.button("🗑️", key=f"del_cab_{carrera_actual}_{cab_key}", use_container_width=True):
                    del st.session_state.remates[carrera_actual][cab_key]
                    st.rerun()

# ==========================================
# PESTAÑA 3: MÓDULO DE DUPLETA PRO (PREMIO = SUMA DE TICKETS)
# ==========================================
with tab3:
    st.markdown("<div class='subasta-header'>🎟️ Módulo de Dupleta (Antiduplicados & Premio Sumatorio)</div>", unsafe_allow_html=True)

    if st.session_state.dupleta_bloqueada:
        st.error("🔒 **BLOQUEADO:** El administrador cerró la emisión de tickets.")

    # Calcular Pote Total de Dupletas (Suma de todos los tickets activos)
    pote_total_dupletas = sum([t['monto'] for t in st.session_state.dupletas_tickets])

    col_met_d1, col_met_d2 = st.columns(2)
    with col_met_d1:
        st.metric("💰 Pote Acumulado de Dupletas", formatear_bs(pote_total_dupletas))
    with col_met_d2:
        st.metric("🏆 Premio Total Dupleta (Suma de Tickets)", formatear_bs(pote_total_dupletas))

    st.markdown("---")

    carreras_habilitadas = st.session_state.carreras_habilitadas_dupleta
    if not carreras_habilitadas:
        st.warning("⚠️ No hay carreras habilitadas para dupleta.")
    else:
        with st.container(border=True):
            col_d1, col_d2 = st.columns([1.5, 1])
            with col_d1:
                jugador_dupleta = st.selectbox("👤 Jugador Responsable", st.session_state.lista_jugadores, key="sel_jugador_dupleta_lineal")
            with col_d2:
                monto_dupleta = st.number_input("💰 Monto (Bs.)", min_value=50.0, value=500.0, step=50.0, key="input_monto_dupleta_lineal")

        with st.container(border=True):
            st.markdown("### 🏇 Configuración de Selecciones")
            num_legs = st.radio("Número de Carreras en el Ticket:", [2, 3, 4, 5, 6], horizontal=True, key="radio_num_legs_lineal")
            
            st.markdown("---")
            seleccion_legs = []
            carreras_usadas_en_ticket = set()
            valido_legs = True
            
            for i in range(num_legs):
                col_carr, col_cab = st.columns([1, 1.2], gap="small")
                
                with col_carr:
                    carr_leg = st.selectbox(f"{i+1}: Carrera", carreras_habilitadas, key=f"sel_carr_lineal_{i}")
                
                with col_cab:
                    caballos_en_carr = list(st.session_state.remates.get(carr_leg, {}).keys())
                    if not caballos_en_carr:
                        st.caption("⚠️ Sin caballos")
                        cab_leg = "Sin Caballos"
                    else:
                        cab_leg = st.selectbox(f"{i+1}: Ejemplar", caballos_en_carr, key=f"sel_cab_lineal_{i}")
                
                if carr_leg in carreras_usadas_en_ticket:
                    st.error(f"⚠️ Carrera repetida en la posición {i+1}: {carr_leg}")
                    valido_legs = False
                carreras_usadas_en_ticket.add(carr_leg)
                
                seleccion_legs.append({"carrera": carr_leg, "ejemplar": cab_leg})
                st.markdown("<div style='margin-bottom: 4px;'></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.session_state.dupleta_bloqueada:
            st.button("🎟️ Emitir Ticket", use_container_width=True, type="primary", disabled=True)
        else:
            if st.button("🚀 Confirmar y Emitir Ticket de Dupleta", use_container_width=True, type="primary"):
                if not valido_legs:
                    st.error("⚠️ Corrige las carreras repetidas antes de emitir.")
                else:
                    # VERIFICAR SI EL TICKET YA EXISTE EXACTAMENTE EN LA JORNADA
                    ticket_duplicado = False
                    for t_existente in st.session_state.dupletas_tickets:
                        legs_existentes = t_existente['legs']
                        if len(legs_existentes) == len(seleccion_legs):
                            coincide = True
                            for l_nueva, l_ant in zip(seleccion_legs, legs_existentes):
                                if l_nueva['carrera'] != l_ant['carrera'] or l_nueva['ejemplar'] != l_ant['ejemplar']:
                                    coincide = False
                                    break
                            if coincide:
                                ticket_duplicado = True
                                break
                    
                    if ticket_duplicado:
                        st.error("❌ **TICKET REPETIDO:** Esta combinación exacta de ejemplares ya fue jugada en otro ticket de la jornada. No se permiten dupletas idénticas.")
                    else:
                        ticket_id = f"DUP-{len(st.session_state.dupletas_tickets) + 1:04d}"
                        nuevo_ticket = {
                            "id": ticket_id,
                            "jugador": jugador_dupleta,
                            "monto": monto_dupleta,
                            "legs": seleccion_legs,
                            "estado": "Pendiente", # Estado inicial predeterminado
                            "fecha": ahora_dt.strftime('%d/%m/%Y %I:%M %p')
                        }
                        st.session_state.dupletas_tickets.append(nuevo_ticket)
                        
                        if jugador_dupleta not in st.session_state.cuentas:
                            st.session_state.cuentas[jugador_dupleta] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                        st.session_state.cuentas[jugador_dupleta]['Pujas'] += monto_dupleta
                        
                        st.session_state.historial_transacciones.append({
                            "Carrera": "Múltiple", "Jugador": jugador_dupleta,
                            "Tipo": "Cargo (Dupleta)", "Detalle": f"Ticket {ticket_id} ({num_legs} Carreras)", "Monto (Bs.)": -monto_dupleta
                        })
                        
                        st.success(f"✅ ¡Ticket {ticket_id} emitido con éxito!")
                        st.balloons()
                        st.rerun()

    st.markdown("---")
    st.subheader("📋 Tickets Emitidos")
    if not st.session_state.dupletas_tickets:
        st.info("No hay tickets registrados.")
    else:
        for idx_t, tick in enumerate(st.session_state.dupletas_tickets):
            with st.container(border=True):
                # Columnas compactas para ID/Jugador, Estado actual, Botón Ganador, Botón Perdedor y Botón Anular
                col_info_t, col_st_g, col_st_p, col_btn_del = st.columns([2.5, 0.8, 0.8, 0.6])
                
                with col_info_t:
                    resumen_legs_str = " ➔ ".join([f"**{l['carrera']}**: {l['ejemplar']}" for l in tick['legs']])
                    estado_actual = tick.get('estado', 'Pendiente')
                    
                    # Color dinámico según el estado del ticket
                    color_badge = "#00d2d3" if estado_actual == "Ganador" else ("#ff4757" if estado_actual == "Perdedor" else "#f1e05a")
                    
                    st.markdown(f"`{tick['id']}` | **{tick['jugador']}** | 💰 `{formatear_bs(tick['monto'])}` | <span style='color: {color_badge}; font-weight: bold;'>[{estado_actual}]</span>", unsafe_allow_html=True)
                    st.markdown(f"*{resumen_legs_str}*")
                
                with col_st_g:
                    if st.button("🏆 Ganador", key=f"btn_ganador_{idx_t}", use_container_width=True):
                        if tick.get('estado') != "Ganador":
                            tick['estado'] = "Ganador"
                            # Abonar premio automático (Suma total de tickets de la dupleta) al jugador
                            premio_dupleta_actual = sum([t['monto'] for t in st.session_state.dupletas_tickets])
                            jug_t = tick['jugador']
                            if jug_t not in st.session_state.cuentas:
                                st.session_state.cuentas[jug_t] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                            st.session_state.cuentas[jug_t]['Premios'] += premio_dupleta_actual
                            st.session_state.historial_transacciones.append({
                                "Carrera": "Múltiple", "Jugador": jug_t,
                                "Tipo": "Abono (Premio Dupleta)", "Detalle": f"Ganador Ticket {tick['id']}", "Monto (Bs.)": premio_dupleta_actual
                            })
                            st.toast(f"🏆 ¡Ticket {tick['id']} marcado como GANADOR! Se abonaron {formatear_bs(premio_dupleta_actual)} a {jug_t}.")
                            st.rerun()

                with col_st_p:
                    if st.button("❌ Perdedor", key=f"btn_perdedor_{idx_t}", use_container_width=True):
                        if tick.get('estado') == "Ganador":
                            # Si antes era ganador y se cambia a perdedor, restamos el premio abonado previamente para mantener consistencia
                            premio_dupleta_actual = sum([t['monto'] for t in st.session_state.dupletas_tickets])
                            jug_t = tick['jugador']
                            if jug_t in st.session_state.cuentas:
                                st.session_state.cuentas[jug_t]['Premios'] -= premio_dupleta_actual
                        
                        tick['estado'] = "Perdedor"
                        st.toast(f"❌ Ticket {tick['id']} marcado como PERDEDOR.")
                        st.rerun()

                with col_btn_del:
                    st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"del_ticket_lineal_{idx_t}", use_container_width=True, help="Anular Ticket"):
                        jug_t = tick['jugador']
                        mont_t = tick['monto']
                        if jug_t in st.session_state.cuentas:
                            st.session_state.cuentas[jug_t]['Pujas'] -= mont_t
                            if tick.get('estado') == "Ganador":
                                premio_dupleta_actual = sum([t['monto'] for t in st.session_state.dupletas_tickets])
                                st.session_state.cuentas[jug_t]['Premios'] -= premio_dupleta_actual
                        st.session_state.dupletas_tickets.pop(idx_t)
                        st.rerun()

# ==========================================
# PESTAÑA 4: CIERRE Y LIQUIDACIÓN
# ==========================================
with tab4:
    st.title("🏁 Cierre y Liquidación")
    for carr_item in lista_carreras_disponibles:
        with st.container(border=True):
            col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
            with col_c1: st.markdown(f"### {carr_item}")
            with col_c2:
                total_pote_carr = sum([info['monto'] for info in st.session_state.remates[carr_item].values()])
                st.metric("Pote", formatear_bs(total_pote_carr))
            with col_c3:
                if not st.session_state.carreras_cerradas_remate.get(carr_item, False):
                    if st.button("🔒 Cerrar", key=f"btn_c4_{carr_item}", use_container_width=True):
                        st.session_state.carreras_cerradas_remate[carr_item] = True
                        st.rerun()
                else:
                    st.success("Cerrada")

# ==========================================
# PESTAÑA 5: CUENTAS POR JUGADOR
# ==========================================
with tab5:
    st.title("📊 Cuentas Corrientes")
    datos_cuentas = []
    for jug, vals in st.session_state.cuentas.items():
        saldo = vals['Pujas'] - (vals['Premios'] + vals['Abonos'])
        datos_cuentas.append({"Jugador": jug, "Pujas (-)": formatear_bs(vals['Pujas']), "Premios (+)": formatear_bs(vals['Premios']), "Abonos (+)": formatear_bs(vals['Abonos']), "Saldo Neto": formatear_bs(saldo)})
    st.dataframe(pd.DataFrame(datos_cuentas), use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 6: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab6:
    st.title("🧾 Historial de Transacciones")
    if st.session_state.historial_transacciones:
        st.dataframe(pd.DataFrame(st.session_state.historial_transacciones), use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 7: LECTOR TABULAR PDF
# ==========================================
with tab7:
    st.title("📄 Lector Tabular de PDF")
    archivo_pdf_subido = st.file_uploader("Sube tu PDF", type=["pdf"])
    if archivo_pdf_subido:
        lector = PdfReader(archivo_pdf_subido)
        st.success(f"Páginas: {len(lector.pages)}")
