import streamlit as st
import pandas as pd
import io
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader, PdfWriter
from streamlit_autorefresh import st_autorefresh

# Configuración de la página web
st.set_page_config(page_title="Sistema de Remates, Dupletas y PDF en Vivo", layout="wide", page_icon="🏇")

# --- AUTOREFRESH PARA TIEMPO REAL (1 SEGUNDO PARA PRECISIÓN DE CONTEO) ---
st_autorefresh(interval=1000, key="datarefresh_en_vivo")

# --- FUNCIÓN LOCAL PARA OBTENER LA HORA EXACTA DE VENEZUELA (AMERICA/CARACAS) ---
@st.cache_data(ttl=15)
def obtener_hora_venezuela():
    """
    Obtiene la hora exacta actual para la zona horaria de Venezuela (America/Caracas).
    Utiliza zoneinfo de Python con respaldo a UTC-4.
    """
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

# --- ESTILOS CSS PARA ALERTAS Y TEMPORIZADOR ---
st.markdown("""
    <style>
    .subasta-header {
        font-size: 20px;
        font-weight: 700;
        color: #f1f2f6;
        margin-bottom: 2px;
    }
    .timer-box {
        background-color: #1e1e2f;
        border: 2px solid #ff4757;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        color: #ff4757;
        margin-bottom: 15px;
        box-shadow: 0 0 15px rgba(255, 71, 87, 0.4);
    }
    .cierre-info-box {
        background-color: #2f2f42;
        border: 1px solid #4f4f6f;
        padding: 10px;
        border-radius: 6px;
        text-align: center;
        font-size: 16px;
        color: #f1f2f6;
        margin-bottom: 15px;
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

if 'dup_carrera_1' not in st.session_state:
    st.session_state.dup_carrera_1 = None
if 'dup_caballo_1' not in st.session_state:
    st.session_state.dup_caballo_1 = None
if 'dup_carrera_2' not in st.session_state:
    st.session_state.dup_carrera_2 = None
if 'dup_caballo_2' not in st.session_state:
    st.session_state.dup_caballo_2 = None

if 'carreras_habilitadas_dupleta' not in st.session_state:
    st.session_state.carreras_habilitadas_dupleta = []

def formatear_bs(monto):
    return f"Bs. {monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# ⚙️ CONTROL LATERAL Y CARGA DE PROGRAMA
# ==========================================
st.sidebar.header("⚙️ Control de Carrera en Vivo")

ahora_dt = obtener_hora_venezuela()

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
porcentaje_casa = st.sidebar.slider("Retención de la Casa (%)", 0, 50, 30, key="slider_retencion_casa")

if carrera_actual not in st.session_state.remates or not st.session_state.remates[carrera_actual]:
    st.session_state.remates[carrera_actual] = {f"{i} - Caballo": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 11)}

if len(st.session_state.remates[carrera_actual]) > 17:
    claves_limitadas = list(st.session_state.remates[carrera_actual].keys())[:17]
    st.session_state.remates[carrera_actual] = {k: st.session_state.remates[carrera_actual][k] for k in claves_limitadas}

todos_los_caballos = sorted(list({cab for carr in st.session_state.remates.values() for cab in carr.keys()}))

# --- PANEL DE CONFIGURACIÓN DE HORA DE CIERRE ESTRICTA Y MANUAL (ADMIN) ---
st.sidebar.markdown("---")
with st.sidebar.expander("⏰ Hora de Cierre Estricta y Manual", expanded=True):
    st.markdown(f"Configurar para: **{carrera_actual}**")
    
    hora_actual_def = ahora_dt.time()
    hora_guardada_actual = st.session_state.horas_cierre_remate.get(carrera_actual)
    
    hora_seleccionada = st.sidebar.time_input(
        "Modificar Hora Estricta de Cierre", 
        value=hora_guardada_actual if hora_guardada_actual else time(hora_actual_def.hour, min(59, hora_actual_def.minute + 5)),
        key=f"time_input_{carrera_actual}"
    )
    
    col_btn_h1, col_btn_h2 = st.sidebar.columns(2)
    with col_btn_h1:
        if st.button("💾 Guardar", key=f"btn_save_hora_{carrera_actual}", use_container_width=True):
            st.session_state.horas_cierre_remate[carrera_actual] = hora_seleccionada
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            st.toast(f"✅ ¡Hora estricta guardada a las {hora_seleccionada.strftime('%H:%M:%S')} para {carrera_actual}!")
            st.rerun()
            
    with col_btn_h2:
        if st.button("🗑️ Borrar", key=f"btn_clear_hora_{carrera_actual}", use_container_width=True):
            if carrera_actual in st.session_state.horas_cierre_remate:
                del st.session_state.horas_cierre_remate[carrera_actual]
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            st.toast(f"🗑️ Hora programada removida para {carrera_actual}.")
            st.rerun()

# --- PANEL DE ADMINISTRADOR DE DUPLETAS EN LA BARRA LATERAL ---
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

if st.sidebar.button("🗑️ Reiniciar Banco de Caballos", use_container_width=True, type="secondary"):
    st.session_state.banco_ejemplares = []
    st.toast("🚨 ¡El banco de nombres de caballos ha sido vaciado!")
    st.rerun()

# --- INTERFAZ DE PESTAÑAS ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏇 Remate Adelantado", 
    "✍️ Gestión Manual (Caballos)", 
    "🎟️ Módulo de Dupleta", 
    "📊 Cuentas por Jugador", 
    "🧾 Historial de Transacciones", 
    "📄 Lector Tabular PDF"
])

# ==========================================
# PESTAÑA 1: REMATE ADELANTADO (CON BOTONES RÁPIDOS DE EJEMPLAR)
# ==========================================
with tab1:
    st.markdown(f"<div class='subasta-header'>🎯 Remate Adelantado: {carrera_actual} (Máx. 17 Ejemplares)</div>", unsafe_allow_html=True)
    
    # --- LÓGICA DEL TEMPORIZADOR Y HORA ESTRICTA ---
    hora_limite = st.session_state.horas_cierre_remate.get(carrera_actual)
    carrera_cerrada = st.session_state.carreras_cerradas_remate.get(carrera_actual, False)
    estado_conteo = st.session_state.estado_conteo_carrera.get(carrera_actual, "INACTIVO")
    
    if hora_limite:
        st.markdown(f"<div class='cierre-info-box'>⏰ Hora de Cierre Estricta para <b>{carrera_actual}</b>: <b>{hora_limite.strftime('%H:%M:%S')}</b></div>", unsafe_allow_html=True)
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
            
            # --- SELECCIÓN RÁPIDA DE EJEMPLAR EXCLUSIVAMENTE CON BOTONES (SIN BUSCADOR) ---
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

        with st.container(border=True):
            st.markdown("🏁 **Gestión de Cierre y Liquidación**")
            
            if not carrera_cerrada:
                if st.button("🔒 Cerrar Remate de esta Carrera", key=f"btn_cerrar_remate_{carrera_actual}", use_container_width=True, type="secondary"):
                    st.session_state.carreras_cerradas_remate[carrera_actual] = True
                    st.session_state.estado_conteo_carrera[carrera_actual] = "CERRADO"
                    st.toast(f"🔒 ¡El remate para {carrera_actual} ha sido cerrado exitosamente!")
                    st.rerun()
            else:
                st.success("🔒 El remate de esta carrera está cerrado.")
                if st.button("🔓 Reabrir Remate", key=f"btn_reabrir_remate_{carrera_actual}", use_container_width=True):
                    st.session_state.carreras_cerradas_remate[carrera_actual] = False
                    st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
                    st.toast(f"🔓 Remate reabierto para {carrera_actual}.")
                    st.rerun()
            
            st.markdown("---")
            caballo_ganador = st.selectbox("Ejemplar Ganador", list(st.session_state.remates[carrera_actual].keys()), key=f"sel_ganador_{carrera_actual}")
            
            if st.button("🏆 Liquidar Carrera", key=f"btn_cerrar_{carrera_actual}", use_container_width=True, type="primary"):
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
                        st.session_state.cuentas[info_ganador['jugador']]['Premios'] += premio_total_calculado
                        st.session_state.historial_transacciones.append({
                            "Carrera": carrera_actual, "Jugador": info_ganador['jugador'], 
                            "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {caballo_ganador} (Incentivo incl.)", "Monto (Bs.)": premio_total_calculado
                        })
                    st.session_state.ganancia_casa += monto_casa
                    st.session_state.historial_ganadores[carrera_actual] = {
                        "Ganador": info_ganador['jugador'], "Caballo": caballo_ganador, "Premio": formatear_bs(premio_total_calculado)
                    }
                    st.balloons()
                    st.success(f"¡Liquidado! Ganador: {info_ganador['jugador']}")
                    st.rerun()

# ==========================================
# PESTAÑA 2: GESTIÓN MANUAL DE CABALLOS Y CORRELATIVO AUTOMÁTICO (1 A 17)
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
                        st.session_state.remates[carrera_actual][formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                        st.success(f"✅ Cargado como **{formato_llave}** en {carrera_actual}.")
                        st.rerun()
        else:
            st.info("No hay ejemplares en el banco guardado.")

    with col_man_2:
        st.subheader("🗑️ Opciones de Reinicio y Eliminación")
        
        caballos_actuales_lista = list(st.session_state.remates[carrera_actual].keys())
        if caballos_actuales_lista:
            caballo_a_borrar = st.selectbox("Seleccione Ejemplar a Remover de esta Carrera", caballos_actuales_lista, key="sel_borrar_caballo_manual")
            if st.button("🗑️ Eliminar Ejemplar Seleccionado", use_container_width=True, type="secondary"):
                del st.session_state.remates[carrera_actual][caballo_a_borrar]
                st.success(f"🗑️ Ejemplar removido de {carrera_actual}.")
                st.rerun()
        else:
            st.info("No hay ejemplares registrados en esta carrera.")

        st.markdown("---")
        st.markdown("⚠️ **Reinicio de Ejemplares (Carrera Actual)**")
        if st.button("🔄 Vaciar Lista de esta Carrera", use_container_width=True, type="secondary"):
            st.session_state.remates[carrera_actual] = {}
            st.success(f"🧹 Se han vaciado todos los ejemplares de {carrera_actual}.")
            st.rerun()

    st.markdown("---")
    st.subheader(f"📋 Ejemplares Registrados en {carrera_actual} ({len(st.session_state.remates[carrera_actual])}/17)")
    st.write(list(st.session_state.remates[carrera_actual].keys()))

# ==========================================
# PESTAÑA 3: MÓDULO DE DUPLETAS (ANTIDUPLICADOS ESTRICTO)
# ==========================================
with tab3:
    st.title("🎟️ Módulo de Dupletas")
    st.markdown("Selecciona tu combinación de ejemplares para la dupleta basándote exclusivamente en las carreras autorizadas por el administrador desde la **barra lateral**.")

    carreras_permitidas = st.session_state.carreras_habilitadas_dupleta
    if not carreras_permitidas:
        st.warning("⚠️ El administrador aún no ha seleccionado ninguna carrera habilitada para las dupletas en la barra lateral.")
    else:
        col_j_m1, col_j_m2 = st.columns([2, 1])
        with col_j_m1:
            jugador_dupleta = st.selectbox("👤 Jugador / Comprador de la Dupleta", st.session_state.lista_jugadores, key="sel_jugador_dupleta")
        with col_j_m2:
            monto_dupleta = st.number_input("💵 Monto (Bs.)", min_value=50.0, value=100.0, step=50.0, key="num_monto_dupleta")

        st.markdown("---")
        
        col_paso_1, col_paso_2 = st.columns(2, gap="large")

        with col_paso_1:
            with st.container(border=True):
                st.markdown("#### 1️⃣ Primera Válida (Habilitada)")
                carr_sel_1 = st.selectbox("Carrera 1", carreras_permitidas, key="dinamico_carr_1")
                
                ejemplares_dict_1 = st.session_state.remates.get(carr_sel_1, {})
                lista_cab_1 = list(ejemplares_dict_1.keys())
                
                if lista_cab_1:
                    cab_sel_1 = st.selectbox("Selecciona Ejemplar 1:", lista_cab_1, key="sel_cab_1_directo")
                    if cab_sel_1:
                        st.session_state.dup_carrera_1 = carr_sel_1
                        st.session_state.dup_caballo_1 = cab_sel_1
                else:
                    st.warning("⚠️ Esta carrera no tiene ejemplares cargados.")

        with col_paso_2:
            with st.container(border=True):
                st.markdown("#### 2️⃣ Segunda Válida (Habilitada)")
                carr_sel_2 = st.selectbox("Carrera 2", carreras_permitidas, key="dinamico_carr_2")
                
                ejemplares_dict_2 = st.session_state.remates.get(carr_sel_2, {})
                lista_cab_2 = list(ejemplares_dict_2.keys())
                
                if lista_cab_2:
                    cab_sel_2 = st.selectbox("Selecciona Ejemplar 2:", lista_cab_2, key="sel_cab_2_directo")
                    if cab_sel_2:
                        st.session_state.dup_carrera_2 = carr_sel_2
                        st.session_state.dup_caballo_2 = cab_sel_2
                else:
                    st.warning("⚠️ Esta carrera no tiene ejemplares cargados.")

        st.markdown("---")

        c_res_info, c_res_btn = st.columns([2, 1])
        
        with c_res_info:
            c1_res = st.session_state.dup_caballo_1 if st.session_state.dup_caballo_1 else "---"
            c2_res = st.session_state.dup_caballo_2 if st.session_state.dup_caballo_2 else "---"
            st.markdown(f"**📌 Combinación Armada:** `{st.session_state.dup_carrera_1 or 'Carrera X'} : {c1_res}` ➡️ `{st.session_state.dup_carrera_2 or 'Carrera Y'} : {c2_res}`")

        with c_res_btn:
            if st.button("🚀 Emitir Ticket de Dupleta", use_container_width=True, type="primary"):
                if not st.session_state.dup_carrera_1 or not st.session_state.dup_caballo_1 or not st.session_state.dup_carrera_2 or not st.session_state.dup_caballo_2:
                    st.error("⚠️ Debes seleccionar ambos ejemplares de ambas carreras.")
                elif st.session_state.dup_carrera_1 == st.session_state.dup_carrera_2:
                    st.error("⚠️ Las dos carreras de la dupleta deben ser distintas.")
                else:
                    sel_1_str = f"{st.session_state.dup_carrera_1} - {st.session_state.dup_caballo_1}"
                    sel_2_str = f"{st.session_state.dup_carrera_2} - {st.session_state.dup_caballo_2}"
                    
                    ticket_duplicado = False
                    for t in st.session_state.dupletas_tickets:
                        if t["1era Selección"] == sel_1_str and t["2da Selección"] == sel_2_str:
                            ticket_duplicado = True
                            break
                    
                    if ticket_duplicado:
                        st.error("🚫 **¡TICKET RECHAZADO!** Esta combinación exacta ya fue registrada previamente.")
                    else:
                        nuevo_ticket = {
                            "ID": len(st.session_state.dupletas_tickets) + 1,
                            "Jugador": jugador_dupleta,
                            "1era Selección": sel_1_str,
                            "2da Selección": sel_2_str,
                            "Monto": monto_dupleta,
                            "Estado": "Pendiente ⏳"
                        }
                        st.session_state.dupletas_tickets.append(nuevo_ticket)
                        
                        if jugador_dupleta in st.session_state.cuentas:
                            st.session_state.cuentas[jugador_dupleta]['Pujas'] += monto_dupleta
                            st.session_state.historial_transacciones.append({
                                "Carrera": "Dupleta", 
                                "Jugador": jugador_dupleta, 
                                "Tipo": "Cargo (Dupleta)", 
                                "Detalle": f"Ticket #{nuevo_ticket['ID']}", 
                                "Monto (Bs.)": -monto_dupleta
                            })
                        
                        st.toast(f"✅ ¡Dupleta #{nuevo_ticket['ID']} emitida con éxito!")
                        st.rerun()

    st.markdown("---")
    
    c_t_list, c_b_limp = st.columns([2, 1])
    with c_t_list:
        st.subheader("📋 Tickets de Dupletas Emitidos")
    with c_b_limp:
        if st.button("🧹 Limpiar Dupleta", key="btn_limpiar_dupleta_emitidos", use_container_width=True):
            st.session_state.dup_carrera_1 = None
            st.session_state.dup_caballo_1 = None
            st.session_state.dup_carrera_2 = None
            st.session_state.dup_caballo_2 = None
            for k in ["num_monto_dupleta"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.toast("🧹 Formulario de dupleta limpiado con éxito.")
            st.rerun()

    if st.session_state.dupletas_tickets:
        df_dupletas = pd.DataFrame(st.session_state.dupletas_tickets)
        st.dataframe(df_dupletas, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("🎯 Actualizar Estado de Ticket")
        id_a_actualizar = st.selectbox("Seleccione ID de Ticket", [t["ID"] for t in st.session_state.dupletas_tickets], key="sel_id_ticket_act")
        nuevo_estado = st.selectbox("Nuevo Estado", ["Pendiente ⏳", "Ganador 🏆", "Perdedor ❌"], key="sel_nuevo_estado_ticket")
        
        if st.button("🔄 Cambiar Estado del Ticket", use_container_width=True):
            for ticket in st.session_state.dupletas_tickets:
                if ticket["ID"] == id_a_actualizar:
                    ticket["Estado"] = nuevo_estado
                    st.success(f"Estado del ticket #{id_a_actualizar} actualizado a: {nuevo_estado}")
                    st.rerun()
    else:
        st.info("No hay dupletas registradas en la sesión actual.")

# ==========================================
# PESTAÑA 4: CUENTAS POR JUGADOR
# ==========================================
with tab4:
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

# ==========================================
# PESTAÑA 5: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab5:
    st.title("🧾 Historial Global")
    if st.session_state.historial_transacciones:
        st.dataframe(pd.DataFrame(st.session_state.historial_transacciones), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se han registrado transacciones en el historial.")

# ==========================================
# PESTAÑA 6: LECTOR DE PDF
# ==========================================
with tab6:
    st.title("📄 Lector Estricto de Nombres Directo al Banco")
    st.markdown("Extrae **exclusivamente** los nombres de los ejemplares del PDF y los almacena **únicamente en el banco guardado**.")

    archivo_pdf_plumber = st.file_uploader(
        "Sube el programa oficial en PDF", 
        type=["pdf"],
        key="uploader_pdfplumber_banco_solo"
    )

    if archivo_pdf_plumber is not None:
        st.success("¡Archivo PDF cargado correctamente!")
        
        if st.button("🚀 Extraer Nombres y Guardar SÓLO en el Banco", type="primary", use_container_width=True):
            try:
                import pdfplumber
                ejemplares_detectados_nombres = []
                palabras_prohibidas_precio = ['bs', 'usd', '$', 'precio', 'pote', 'premio', 'valor', 'mt', 'pago', 'but']

                with pdfplumber.open(archivo_pdf_plumber) as pdf:
                    for num_pag, page in enumerate(pdf.pages):
                        tables = page.extract_tables()
                        
                        if tables:
                            for table in tables:
                                for row in table:
                                    fila_texto = [str(cell).strip() for cell in row if cell is not None and str(cell).strip() != ""]
                                    if not fila_texto:
                                        continue
                                    
                                    for celda in fila_texto:
                                        match_ej = re.match(r'^(\d{1,2})[\.\-\)]?$', celda)
                                        if match_ej:
                                            celdas_restantes = [c for c in fila_texto if c != celda]
                                            if celdas_restantes:
                                                nombre_bruto = celdas_restantes[0]
                                                nombre_puro = re.sub(r'^\d+[\s\-\.\)]*', '', nombre_bruto).strip().title()
                                                
                                                palabras_nombre = nombre_puro.split()
                                                contiene_palabra_prohibida = any(p.lower() in palabras_prohibidas_precio for p in palabras_nombre)
                                                tiene_precio_o_invalido = contiene_palabra_prohibida or bool(re.search(r'\d{3,}', nombre_puro))
                                                
                                                if nombre_puro and len(nombre_puro) > 2 and not tiene_precio_o_invalido and nombre_puro not in ejemplares_detectados_nombres:
                                                    ejemplares_detectados_nombres.append(nombre_puro)
                                            break

                agregados_nuevos = 0
                for nombre in ejemplares_detectados_nombres:
                    if nombre not in st.session_state.banco_ejemplares:
                        st.session_state.banco_ejemplares.append(nombre)
                        agregados_nuevos += 1

                st.success(f"¡Extracción exitosa! Se añadieron **{agregados_nuevos} nuevos ejemplares** directamente al banco guardado.")
                st.balloons()
                st.rerun()

            except Exception as e:
                st.error(f"Ocurrió un error al procesar el PDF: {e}")
