import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader
from streamlit_autorefresh import st_autorefresh

# Configuración de la página web optimizada para móviles
st.set_page_config(page_title="Sistema de Remates Móvil", layout="centered", page_icon="🏇")

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

# --- ESTILOS CSS ADAPTADOS PARA MÓVILES ---
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
        font-size: 18px;
        font-weight: 800;
        color: var(--accent-gold);
        margin-bottom: 5px;
        border-bottom: 2px solid var(--accent-gold);
        padding-bottom: 5px;
    }
    
    .timer-box {
        background-color: var(--bg-card);
        border: 2px solid var(--accent-red);
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
        color: var(--accent-red);
        margin-bottom: 10px;
    }
    
    .cierre-info-box {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 8px;
        border-radius: 6px;
        text-align: center;
        font-size: 14px;
        color: var(--text-primary);
        margin-bottom: 10px;
    }

    div[data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        padding: 8px;
        border-radius: 8px;
        margin-bottom: 8px;
    }

    div[data-testid="stMetricValue"] {
        color: var(--accent-gold) !important;
        font-size: 18px !important;
        font-weight: 700;
    }

    .block-container {
        padding-top: 0.8rem;
        padding-bottom: 1rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }
    
    /* Botones más grandes para uso táctil */
    .stButton button {
        width: 100%;
        border-radius: 6px;
        font-weight: bold;
        padding: 0.5rem;
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
    st.session_state.banco_ejemplares = ["Gran Alex", "Rey David", "Sombra Negra", "Rayo Veloz", "Catire Bory", "Doña Rosa"]

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
# ⚙️ BARRA LATERAL MÓVIL
# ==========================================
st.sidebar.header("⚙️ Menú de Control")

ahora_dt = obtener_hora_venezuela_local()
st.sidebar.markdown(f"🕒 **Hora:** `{ahora_dt.strftime('%I:%M:%S %p')}`")

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
        except Exception:
            pass
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
        if st.button("🔓 Desbloquear", key="btn_desbloq_mob"):
            st.session_state.dupleta_bloqueada = False
            st.rerun()
    else:
        st.markdown("<p style='color: #00d2d3; font-weight: bold;'>🟢 Dupletas ABIERTAS</p>", unsafe_allow_html=True)
        if st.button("🔒 Bloquear", key="btn_bloq_mob"):
            st.session_state.dupleta_bloqueada = True
            st.rerun()

if st.sidebar.button("🗑️ Reiniciar Jornada", use_container_width=True):
    for key in list(st.session_state.keys()):
        if key != 'banco_ejemplares':
            del st.session_state[key]
    st.toast("🚨 Jornada reiniciada.")
    st.rerun()

# --- INTERFAZ DE PESTAÑAS (OPTIMIZADAS PARA MÓVIL) ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏇 Remate", 
    "✍️ Manual", 
    "🎟️ Dupletas", 
    "🏁 Cierre", 
    "📊 Cuentas", 
    "🧾 Hist.", 
    "📄 PDF"
])

# ==========================================
# PESTAÑA 1: REMATE ADELANTADO (MÓVIL)
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

    # Formato vertical optimizado para móviles (primero panel de puja rápido, luego la tabla)
    with st.container(border=True):
        st.markdown("⚡ **Registro Rápido de Puja**")
        lista_caballos_activos = list(st.session_state.remates[carrera_actual].keys())
        
        if not lista_caballos_activos:
            st.warning("Sin ejemplares.")
        else:
            if f"caballo_seleccionado_click_{carrera_actual}" not in st.session_state or st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] not in lista_caballos_activos:
                st.session_state[f"caballo_seleccionado_click_{carrera_actual}"] = lista_caballos_activos[0]
                
            cols_botones = st.columns(3) # 3 columnas de botones en móvil para mejor espacio
            for idx, cab_item in enumerate(lista_caballos_activos):
                num_parte = cab_item.split(" - ")[0]
                with cols_botones[idx % 3]:
                    if st.button(f"#{num_parte}", key=f"btn_m_cab_{carrera_actual}_{idx}", use_container_width=True):
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

    st.markdown("---")
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
# PESTAÑA 2: GESTIÓN MANUAL DE CABALLOS
# ==========================================
with tab2:
    st.markdown("<div class='subasta-header'>✍️ Gestión Manual</div>", unsafe_allow_html=True)
    nombre_nuevo_caballo = st.text_input("Nombre del Caballo", placeholder="Ej: Rayo de Luz", key="input_nuevo_caballo_manual")
    if st.button("💾 Agregar Caballo", use_container_width=True, type="primary"):
        nombre_limpio = nombre_nuevo_caballo.strip().title()
        if nombre_limpio and len(st.session_state.remates[carrera_actual]) < 17:
            nums = [int(re.match(r'^(\d+)', e).group(1)) for e in st.session_state.remates[carrera_actual].keys() if re.match(r'^(\d+)', e)]
            siguiente_num = 1
            while siguiente_num in nums and siguiente_num <= 17:
                siguiente_num += 1
            st.session_state.remates[carrera_actual][f"{siguiente_num} - {nombre_limpio}"] = {"jugador": "Sin Postor", "monto": 0.0}
            st.rerun()
            
    st.markdown("---")
    for cab_key in list(st.session_state.remates[carrera_actual].keys()):
        col_info, col_del = st.columns([3, 1])
        with col_info: st.text(cab_key)
        with col_del:
            if st.button("🗑️", key=f"del_cab_m_{carrera_actual}_{cab_key}", use_container_width=True):
                del st.session_state.remates[carrera_actual][cab_key]
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

    with st.container(border=True):
        jugador_dupleta = st.selectbox("👤 Jugador", st.session_state.lista_jugadores, key="sel_jug_dup_mob")
        monto_dupleta = st.number_input("💰 Monto (Bs.)", min_value=50.0, value=500.0, step=50.0, key="input_m_dup_mob")

    with st.container(border=True):
        st.markdown("**Selecciones**")
        num_legs = st.radio("Cantidad:", [2, 3, 4, 5, 6], horizontal=True, key="radio_legs_mob")
        
        seleccion_legs = []
        carreras_usadas_en_ticket = set()
        valido_legs = True
        
        carreras_habilitadas = st.session_state.carreras_habilitadas_dupleta
        for i in range(num_legs):
            st.markdown(f"**Selección {i+1}**")
            carr_leg = st.selectbox(f"Carrera {i+1}", carreras_habilitadas, key=f"sel_c_mob_{i}")
            caballos_en_carr = list(st.session_state.remates.get(carr_leg, {}).keys())
            cab_leg = st.selectbox(f"Ejemplar {i+1}", caballos_en_carr if caballos_en_carr else ["Sin Caballos"], key=f"sel_cb_mob_{i}")
            
            if carr_leg in carreras_usadas_en_ticket:
                st.error(f"⚠️ Carrera repetida: {carr_leg}")
                valido_legs = False
            carreras_usadas_en_ticket.add(carr_leg)
            seleccion_legs.append({"carrera": carr_leg, "ejemplar": cab_leg})

    if not st.session_state.dupleta_bloqueada:
        if st.button("🚀 Emitir Ticket", use_container_width=True, type="primary"):
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
    st.subheader("📋 Tickets")
    if not st.session_state.dupletas_tickets:
        st.info("Sin tickets.")
    else:
        for idx_t, tick in enumerate(st.session_state.dupletas_tickets):
            with st.container(border=True):
                st.markdown(f"**ID:** `{tick['id']}` | **Jugador:** {tick['jugador']}")
                st.markdown(f"Monto: {formatear_bs(tick['monto'])} | Estado: **{tick.get('estado', 'Pendiente')}**")
                
                c_g, c_p, c_d = st.columns(3)
                with c_g:
                    if st.button("✅", key=f"bg_mob_{idx_t}", use_container_width=True):
                        tick['estado'] = "Ganador"
                        st.session_state.cuentas[tick['jugador']]['Premios'] += pote_total_dupletas
                        st.rerun()
                with c_p:
                    if st.button("❌", key=f"bp_mob_{idx_t}", use_container_width=True):
                        tick['estado'] = "Perdedor"
                        st.rerun()
                with c_d:
                    if st.button("🗑️", key=f"bd_mob_{idx_t}", use_container_width=True):
                        st.session_state.dupletas_tickets.pop(idx_t)
                        st.rerun()

# ==========================================
# PESTAÑA 4: CIERRE Y LIQUIDACIÓN (MÓVIL)
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
    carr_seleccionada_liq = st.selectbox("Gestionar Carrera", lista_carreras_disponibles, key="sel_c_liq_mob")

    with st.container(border=True):
        st.markdown(f"**Gestión: {carr_seleccionada_liq}**")
        c_cerrada_actual = st.session_state.carreras_cerradas_remate.get(carr_seleccionada_liq, False)
        
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
            st.success("✅ Ya liquidada.")
        else:
            pote_carr_total = sum([info['monto'] for info in st.session_state.remates[carr_seleccionada_liq].values()])
            monto_casa_calc = pote_carr_total * (porcentaje_casa / 100)
            premio_final_liq = pote_carr_total - monto_casa_calc + st.session_state.get(f"pote_inc_{carr_seleccionada_liq}", 0.0)
            
            caballo_ganador_elegido = st.selectbox("Ganador", list(st.session_state.remates[carr_seleccionada_liq].keys()), key=f"sel_g_mob_{carr_seleccionada_liq}")
            
            if st.button("🎯 Liquidar Premio", key=f"btn_liq_{carr_seleccionada_liq}", use_container_width=True, type="primary"):
                info_g = st.session_state.remates[carr_seleccionada_liq][caballo_ganador_elegido]
                if info_g['jugador'] != "Sin Postor":
                    if info_g['jugador'] not in st.session_state.cuentas:
                        st.session_state.cuentas[info_g['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                    st.session_state.cuentas[info_g['jugador']]['Premios'] += premio_final_liq
                st.session_state.ganancia_casa += monto_casa_calc
                st.session_state.historial_ganadores[carr_seleccionada_liq] = {
                    "Ganador": info_g['jugador'], "Caballo": caballo_ganador_elegido, "Premio": formatear_bs(premio_final_liq)
                }
                st.success("¡Liquidado!")
                st.rerun()

# ==========================================
# PESTAÑA 5: CUENTAS POR JUGADOR
# ==========================================
with tab5:
    st.markdown("<div class='subasta-header'>📊 Cuentas</div>", unsafe_allow_html=True)
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
    st.metric("Total General Compras", formatear_bs(tot_pujas_gen))
    st.metric("Ganancia Casa", formatear_bs(st.session_state.ganancia_casa))

# ==========================================
# PESTAÑA 6: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab6:
    st.markdown("<div class='subasta-header'>🧾 Transacciones</div>", unsafe_allow_html=True)
    if not st.session_state.historial_transacciones:
        st.info("Sin transacciones.")
    else:
        st.dataframe(pd.DataFrame(st.session_state.historial_transacciones), use_container_width=True, hide_index=True)

# ==========================================
# PESTAÑA 7: LECTOR TABULAR PDF
# ==========================================
with tab7:
    st.markdown("<div class='subasta-header'>📄 Lector PDF</div>", unsafe_allow_html=True)
    pdf_subido = st.file_uploader("Sube el PDF", type=["pdf"])
    if pdf_subido is not None:
        try:
            lector_pdf = PdfReader(pdf_subido)
            texto_extraido = "".join([p.extract_text() + "\n" for p in lector_pdf.pages if p.extract_text()])
            st.success("¡PDF leído!")
            st.text_area("Contenido", texto_extraido, height=200)
        except Exception as e:
            st.error(f"Error: {e}")
