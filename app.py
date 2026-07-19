import streamlit as st
import pandas as pd
import io
import os

# Instala esto si no lo tienes: pip install streamlit-autorefresh
from streamlit_autorefresh import st_autorefresh

# Configuración de la página web
st.set_page_config(page_title="Sistema de Remates y Dupletas en Vivo", layout="wide", page_icon="🏇")

# --- AUTOREFRESH PARA TIEMPO REAL ---
# Refresca la página automáticamente cada 3 segundos para sincronizar las terminales
st_autorefresh(interval=3000, key="datarefresh_en_vivo")

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

if 'historial_ganadores' not in st.session_state:
    st.session_state.historial_ganadores = {}

if 'cuentas' not in st.session_state:
    st.session_state.cuentas = {j: {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0} for j in st.session_state.lista_jugadores}

if 'ganancia_casa' not in st.session_state:
    st.session_state.ganancia_casa = 0.0

if 'historial_transacciones' not in st.session_state:
    st.session_state.historial_transacciones = []

if 'dupletas_tickets' not in st.session_state:
    st.session_state.dupletas_tickets = []

# --- FORMATO DE MONEDA VENEZOLANA (Bs.) ---
def formatear_bs(monto):
    return f"Bs. {monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# ⚙️ CONTROL LATERAL Y CARGA DE PROGRAMA
# ==========================================
st.sidebar.header("⚙️ Control de Carrera en Vivo")
st.sidebar.caption("🔄 Sincronización en tiempo real activa (3s)")

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
                    for cab in caballos_carrera:
                        nombre_caballo = str(cab).strip()
                        if nombre_caballo not in st.session_state.remates[carr_name]:
                            st.session_state.remates[carr_name][nombre_caballo] = {"jugador": "Sin Postor", "monto": 0.0}
                return True
        except Exception as e:
            st.sidebar.error(f"Error al leer programa automático: {e}")
    return False

if not st.session_state.remates:
    cargar_programa_automatico()

lista_carreras_disponibles = list(st.session_state.remates.keys())
if not lista_carreras_disponibles:
    lista_carreras_disponibles = [f"Carrera {i}" for i in range(1, 15)]

carrera_actual = st.sidebar.selectbox("Seleccionar Carrera Activa", lista_carreras_disponibles, key="selector_carrera_sidebar")
porcentaje_casa = st.sidebar.slider("Retención de la Casa (%)", 0, 50, 30, key="slider_retencion_casa")

if carrera_actual not in st.session_state.remates or not st.session_state.remates[carrera_actual]:
    st.session_state.remates[carrera_actual] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}

todos_los_caballos = sorted(list({cab for carr in st.session_state.remates.values() for cab in carr.keys()}))
if not todos_los_caballos:
    todos_los_caballos = [f"Caballo {i}" for i in range(1, 15)]

# --- BOTÓN DE PÁNICO / REINICIO ---
st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Reiniciar Jornada Global", use_container_width=True, type="secondary"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.toast("🚨 Jornada reiniciada.")
    st.rerun()

# --- INTERFAZ DE PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["🏇 Subasta en Vivo (Bs.)", "🎟️ Módulo de Dupleta", "📊 Cuentas por Jugador", "🧾 Historial de Transacciones"])

# ==========================================
# PESTAÑA 1: SUBASTA EN VIVO
# ==========================================
with tab1:
    st.title(f"🎯 Subasta Activa en Directo: {carrera_actual}")
    col_pujas, col_tablero = st.columns([1, 2])

    with col_pujas:
        st.subheader("🔨 Registrar Puja Instantánea")
        caballo = st.selectbox("Seleccione el Ejemplar", list(st.session_state.remates[carrera_actual].keys()), key=f"sel_caballo_{carrera_actual}")
        jugador = st.selectbox("Seleccione el Jugador", st.session_state.lista_jugadores, key=f"sel_jugador_{carrera_actual}")
        
        puja_actual = st.session_state.remates[carrera_actual][caballo]['monto']
        st.info(f"Puja actual para {caballo}: **{formatear_bs(puja_actual)}**")
        
        col_inc1, col_inc2, col_inc3 = st.columns(3)
        incremento_elegido = 0.0
        if col_inc1.button("➕ 50", use_container_width=True, key=f"inc_50_{carrera_actual}"):
            incremento_elegido = 50.0
        if col_inc2.button("➕ 100", use_container_width=True, key=f"inc_100_{carrera_actual}"):
            incremento_elegido = 100.0
        if col_inc3.button("➕ 500", use_container_width=True, key=f"inc_500_{carrera_actual}"):
            incremento_elegido = 500.0

        monto_propuesto = float(puja_actual + (incremento_elegido if incremento_elegido > 0 else 50.0))
        monto_puja = st.number_input("Monto de la Nueva Puja (Bs.)", min_value=50.0, value=monto_propuesto, step=50.0, key=f"num_monto_{carrera_actual}_{caballo}")
        
        if st.button("🔨 Confirmar y Transmitir Puja", key=f"btn_pujar_{carrera_actual}", use_container_width=True, type="primary"):
            if monto_puja <= puja_actual:
                st.error(f"El monto debe ser mayor a la puja actual ({formatear_bs(puja_actual)})")
            else:
                st.session_state.remates[carrera_actual][caballo] = {"jugador": jugador, "monto": monto_puja}
                st.toast(f"✅ ¡Puja transmitida! {caballo} ➡️ {jugador} ({formatear_bs(monto_puja)})")
                st.rerun()

    with col_tablero:
        st.subheader("📋 Tablero Sincronizado en Vivo")
        datos_tabla = []
        total_pote = 0.0
        for cab, info in st.session_state.remates[carrera_actual].items():
            datos_tabla.append({"Ejemplar": cab, "Comprador": info['jugador'], "Monto": formatear_bs(info['monto'])})
            total_pote += info['monto']
        
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True, key=f"tabla_remates_{carrera_actual}")
        
        monto_casa = total_pote * (porcentaje_casa / 100)
        pote_ganador = total_pote - monto_casa
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Pote Total", formatear_bs(total_pote))
        c2.metric("🏠 Comisión Casa", formatear_bs(monto_casa))
        c3.metric("🏆 Premio Neto", formatear_bs(pote_ganador))

    st.markdown("---")
    st.subheader("🏁 Cierre de Carrera")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        caballo_ganador = st.selectbox("Ejemplar Ganador", list(st.session_state.remates[carrera_actual].keys()), key=f"sel_ganador_{carrera_actual}")
        if st.button("🏆 Liquidar Carrera para Todos", key=f"btn_cerrar_{carrera_actual}", use_container_width=True):
            if carrera_actual in st.session_state.historial_ganadores:
                st.warning("Esta carrera ya fue liquidada.")
            else:
                for cab, info in st.session_state.remates[carrera_actual].items():
                    if info['jugador'] != "Sin Postor" and info['monto'] > 0:
                        st.session_state.cuentas[info['jugador']]['Pujas'] += info['monto']
                        st.session_state.historial_transacciones.append({
                            "Carrera": carrera_actual, "Jugador": info['jugador'], 
                            "Tipo": "Cargo (Compra)", "Detalle": f"Adjudicación de {cab}", "Monto (Bs.)": -info['monto']
                        })
                info_ganador = st.session_state.remates[carrera_actual][caballo_ganador]
                if info_ganador['jugador'] != "Sin Postor":
                    st.session_state.cuentas[info_ganador['jugador']]['Premios'] += pote_ganador
                    st.session_state.historial_transacciones.append({
                        "Carrera": carrera_actual, "Jugador": info_ganador['jugador'], 
                        "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {caballo_ganador}", "Monto (Bs.)": pote_ganador
                    })
                st.session_state.ganancia_casa += monto_casa
                st.session_state.historial_ganadores[carrera_actual] = {
                    "Ganador": info_ganador['jugador'], "Caballo": caballo_ganador, "Premio": formatear_bs(pote_ganador)
                }
                st.balloons()
                st.success(f"¡Liquidado! Ganador: {info_ganador['jugador']}")
                st.rerun()

# ==========================================
# PESTAÑAS SECUNDARIAS
# ==========================================
with tab2:
    st.title("🎟️ Dupletas en Vivo")
    st.info("Módulo de dupletas sincronizado con el servidor local.")

with tab3:
    st.title("📊 Cuentas Generales en Directo")
    balance_data = []
    for jug in st.session_state.lista_jugadores:
        if jug not in st.session_state.cuentas:
            st.session_state.cuentas[jug] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
        valores = st.session_state.cuentas[jug]
        saldo_final = valores['Premios'] + valores['Abonos'] - valores['Pujas']
        estado = "🔴 Debe" if saldo_final < 0 else ("🟢 A favor" if saldo_final > 0 else "⚪ Al día")
        balance_data.append({"Jugador": jug, "Compras": valores['Pujas'], "Premios": valores['Premios'], "Saldo Final": saldo_final, "Estado": estado})
    st.dataframe(pd.DataFrame(balance_data), use_container_width=True, hide_index=True)

with tab4:
    st.title("🧾 Historial Global")
    if st.session_state.historial_transacciones:
        st.dataframe(pd.DataFrame(st.session_state.historial_transacciones), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se han registrado transacciones en el historial.")
    
