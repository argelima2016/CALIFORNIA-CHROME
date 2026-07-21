import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pypdf import PdfReader
from streamlit_autorefresh import st_autorefresh

# Configuración de pantalla completa (Responsive para Móviles y PC)
st.set_page_config(page_title="Sistema de Remates", layout="wide", page_icon="🏇")

# --- AUTOREFRESH (3 SEGUNDOS) ---
try:
    st_autorefresh(interval=3000, key="datarefresh_en_vivo")
except Exception:
    pass

# --- HORA LOCAL DE VENEZUELA ---
def obtener_hora_venezuela_local():
    try:
        zona_venezuela = ZoneInfo("America/Caracas")
        return datetime.now(zona_venezuela).replace(tzinfo=None)
    except Exception:
        pass
    tz_venezuela = timezone(timedelta(hours=-4))
    return datetime.now(tz_venezuela).replace(tzinfo=None)

# --- ESCALA DE PUJAS ---
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

# --- ESTILOS CSS MULTIPLATAFORMA Y CONTROL MÓVIL ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #f0f6fc;
    }
    .subasta-header {
        font-size: clamp(20px, 4vw, 26px);
        font-weight: 800;
        color: #f1e05a;
        margin-bottom: 12px;
        border-bottom: 2px solid #f1e05a;
        padding-bottom: 6px;
    }
    .timer-box {
        background-color: #161b22;
        border: 2px solid #ff4757;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        font-size: clamp(16px, 3.5vw, 22px);
        font-weight: bold;
        color: #ff4757;
        margin-bottom: 12px;
    }
    .cierre-info-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 10px;
        border-radius: 6px;
        text-align: center;
        font-size: 16px;
        color: #f0f6fc;
        margin-bottom: 12px;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 100% !important;
    }
    .stButton button {
        width: 100% !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        padding: 0.6rem !important;
        min-height: 42px !important;
    }

    /* --- LÓGICA RESPONSIVA PARA OCULTAR/MOSTRAR SIDEBAR EN TELÉFONOS --- */
    @media (max-width: 768px) {
        /* Fuerza a que la sidebar esté oculta por defecto en pantallas de celulares (Android/iOS) */
        section[data-testid="stSidebar"] {
            width: 0px !important;
            min-width: 0px !important;
            transform: translateX(-100%);
            transition: transform 0.3s ease-in-out;
        }
        /* Cuando el usuario presiona el botón de despliegue, Streamlit le añade clases o podemos forzar su apertura si se desea, 
           pero el botón oficial superior de Streamlit se encargará de desplegarla limpiamente al tocarlo */
    }
    </style>
""", unsafe_allow_html=True)

# --- JUGADORES BASE ---
@st.cache_data
def cargar_jugadores_base():
    return ["CASA", "SOMBI", "LUIS", "CARLOS", "RAMON", "ALDEA", "ANGEL", "ALFONSO", "MACANO", "MIGUEL", "TOCAYO", "EL GOCHO", "PAPIRO", "CHAYO", "ALEXIS"]

# --- ESTADO GLOBAL ---
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

# --- PROCESADOR DE PDF ---
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
            if match_carr or ("carrera" in linea_limpia.lower() and len(linea_limpia) < 30):
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
                    if len(nom_ej) > 2 and not any(p in nom_ej.lower() for p in ['retirado', 'jinete', 'entrenador', 'distancia']):
                        formato_ej = f"{num_ej} - {nom_ej.title()}"
                        if formato_ej not in banco_temporal[carrera_actual_detectada]:
                            banco_temporal[carrera_actual_detectada].append(formato_ej)

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
        st.sidebar.error(f"Error: {e}")
    return False

if not st.session_state.remates:
    for i in range(1, 11):
        carr_nombre = f"Carrera {i}"
        st.session_state.banco_caballos_por_carrera[carr_nombre] = [f"{j} - Ejemplar {j}" for j in range(1, 11)]
        st.session_state.remates[carr_nombre] = {f"{j} - Ejemplar {j}": {"jugador": "Sin Postor", "monto": 0.0} for j in range(1, 11)}

lista_carreras_disponibles = list(st.session_state.remates.keys())
if not st.session_state.carreras_habilitadas_dupleta and lista_carreras_disponibles:
    st.session_state.carreras_habilitadas_dupleta = list(lista_carreras_disponibles)

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Menú de Control")
ahora_dt = obtener_hora_venezuela_local()
st.sidebar.markdown(f"🕒 **Hora:** `{ahora_dt.strftime('%I:%M:%S %p')}`")

carrera_actual = st.sidebar.selectbox("Carrera Activa", lista_carreras_disponibles, key="selector_carrera_sidebar")

with st.sidebar.expander("🏠 Retención de la Casa", expanded=False):
    porcentaje_casa = st.slider("Retención (%)", 0, 50, 30, key="slider_retencion_casa")

with st.sidebar.expander("⏰ Hora de Cierre Estricta", expanded=False):
    periodo_sel = st.radio("Periodo", ["AM", "PM"], key=f"radio_p_{carrera_actual}", horizontal=True)
    hora_12 = st.selectbox("Hora", list(range(1, 13)), key=f"sel_h_{carrera_actual}")
    minuto_sel = st.selectbox("Minutos", list(range(0, 60)), key=f"sel_m_{carrera_actual}")
    
    h_24_conv = int(hora_12)
    if periodo_sel == "PM" and h_24_conv < 12: h_24_conv += 12
    elif periodo_sel == "AM" and h_24_conv == 12: h_24_conv = 0
    
    hora_seleccionada = time(h_24_conv, int(minuto_sel))
    
    col_bh1, col_bh2 = st.sidebar.columns(2)
    with col_bh1:
        if st.button("💾 Guardar", key=f"bs_h_{carrera_actual}"):
            st.session_state.horas_cierre_remate[carrera_actual] = hora_seleccionada
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            st.toast("✅ Hora guardada")
            st.rerun()
    with col_bh2:
        if st.button("🗑️ Borrar", key=f"bc_h_{carrera_actual}"):
            if carrera_actual in st.session_state.horas_cierre_remate:
                del st.session_state.horas_cierre_remate[carrera_actual]
            st.session_state.estado_conteo_carrera[carrera_actual] = "INACTIVO"
            st.toast("🗑️ Removida")
            st.rerun()

with st.sidebar.expander("🔒 Estado Dupletas", expanded=False):
    if st.session_state.dupleta_bloqueada:
        st.markdown("<p style='color: #ff4757; font-weight: bold;'>🔴 BLOQUEADAS</p>", unsafe_allow_html=True)
        if st.button("🔓 Desbloquear", key="b_des_dup"):
            st.session_state.dupleta_bloqueada = False
            st.rerun()
    else:
        st.markdown("<p style='color: #00d2d3; font-weight: bold;'>🟢 ABIERTAS</p>", unsafe_allow_html=True)
        if st.button("🔒 Bloquear", key="b_blo_dup"):
            st.session_state.dupleta_bloqueada = True
            st.rerun()

if st.sidebar.button("🗑️ Reiniciar Jornada", use_container_width=True):
    for key in list(st.session_state.keys()):
        if key != 'banco_caballos_por_carrera':
            del st.session_state[key]
    st.toast("🚨 Jornada reiniciada.")
    st.rerun()

# --- PESTAÑAS PRINCIPALES ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏇 Remate", "✍️ Banco", "🎟️ Dupletas", "🏁 Cierre", "📊 Cuentas", "🧾 Hist.", "📄 PDF"
])

# 1. REMATE
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
                st.session_state.carreras_cerradas_remate[carrera_actual] = True
                st.session_state.estado_conteo_carrera[carrera_actual] = "CERRADO"
                st.rerun()

    col_izq_puja, col_der_tabla = st.columns([1.1, 1.9], gap="medium")

    with col_izq_puja:
        with st.container(border=True):
            st.markdown("⚡ **Registro Rápido de Puja**")
            lista_caballos_activos = list(st.session_state.remates[carrera_actual].keys())
            
            if not lista_caballos_activos:
                st.warning("Sin ejemplares.")
            else:
                k_sel = f"caballo_seleccionado_click_{carrera_actual}"
                if k_sel not in st.session_state or st.session_state[k_sel] not in lista_caballos_activos:
                    st.session_state[k_sel] = lista_caballos_activos[0]
                    
                cols_botones = st.columns(4)
                for idx, cab_item in enumerate(lista_caballos_activos):
                    num_parte = cab_item.split(" - ")[0]
                    with cols_botones[idx % 4]:
                        if st.button(f"#{num_parte}", key=f"btn_r_cab_{carrera_actual}_{idx}", use_container_width=True):
                            st.session_state[k_sel] = cab_item
                
                caballo_seleccionado = st.session_state[k_sel]
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

# 2. BANCO
with tab2:
    st.markdown("<div class='subasta-header'>✍️ Banco de Caballos por Carrera</div>", unsafe_allow_html=True)
    carr_banco_sel = st.selectbox("Seleccionar Carrera", lista_carreras_disponibles, key="sel_c_banco")
    
    if carr_banco_sel not in st.session_state.banco_caballos_por_carrera:
        st.session_state.banco_caballos_por_carrera[carr_banco_sel] = []
        
    with st.container(border=True):
        nuevo_nom_banco = st.text_input("Nombre del Ejemplar", placeholder="Ej: Rey David", key=f"in_b_{carr_banco_sel}")
        if st.button("💾 Agregar al Banco", use_container_width=True, type="primary"):
            nom_limp = nuevo_nom_banco.strip().title()
            if nom_limp:
                nums = [int(re.match(r'^(\d+)', e).group(1)) for e in st.session_state.banco_caballos_por_carrera[carr_banco_sel] if re.match(r'^(\d+)', e)]
                sig_num = 1
                while sig_num in nums and sig_num <= 17: sig_num += 1
                formato_nuevo = f"{sig_num} - {nom_limp}"
                
                if formato_nuevo not in st.session_state.banco_caballos_por_carrera[carr_banco_sel]:
                    st.session_state.banco_caballos_por_carrera[carr_banco_sel].append(formato_nuevo)
                if carr_banco_sel not in st.session_state.remates:
                    st.session_state.remates[carr_banco_sel] = {}
                if formato_nuevo not in st.session_state.remates[carr_banco_sel]:
                    st.session_state.remates[carr_banco_sel][formato_nuevo] = {"jugador": "Sin Postor", "monto": 0.0}
                st.toast("✅ ¡Agregado con éxito!")
                st.rerun()

    for idx_b, ej_item in enumerate(st.session_state.banco_caballos_por_carrera[carr_banco_sel]):
        col_ib1, col_ib2 = st.columns([5, 1])
        with col_ib1: st.text(ej_item)
        with col_ib2:
            if st.button("🗑️", key=f"del_b_{carr_banco_sel}_{idx_b}", use_container_width=True):
                st.session_state.banco_caballos_por_carrera[carr_banco_sel].pop(idx_b)
                if carr_banco_sel in st.session_state.remates and ej_item in st.session_state.remates[carr_banco_sel]:
                    del st.session_state.remates[carr_banco_sel][ej_item]
                st.rerun()

# 3. DUPLETAS
with tab3:
    st.markdown("<div class='subasta-header'>🎟️ Módulo de Dupletas</div>", unsafe_allow_html=True)
    if st.session_state.dupleta_bloqueada:
        st.error("🔒 **BLOQUEADO:** Emisión cerrada.")

    pote_total_dupletas = sum([t['monto'] for t in st.session_state.dupletas_tickets])
    st.metric("💰 Pote Acumulado Dupletas", formatear_bs(pote_total_dupletas))

    col_d1, col_d2 = st.columns(2, gap="medium")
    with col_d1:
        with st.container(border=True):
            jugador_dupleta = st.selectbox("👤 Jugador", st.session_state.lista_jugadores, key="jug_dup")
            monto_dupleta = st.number_input("💰 Monto (Bs.)", min_value=50.0, value=500.0, step=50.0, key="m_dup")
            num_legs = st.radio("Cantidad de Selecciones:", [2, 3, 4, 5, 6], horizontal=True, key="legs_dup")

    with col_d2:
        with st.container(border=True):
            seleccion_legs = []
            carreras_usadas_en_ticket = set()
            valido_legs = True
            carreras_habilitadas = st.session_state.carreras_habilitadas_dupleta
            
            for i in range(num_legs):
                c_leg, cb_leg_col = st.columns(2)
                with c_leg:
                    carr_leg = st.selectbox(f"Carrera {i+1}", carreras_habilitadas, key=f"c_dup_{i}")
                with cb_leg_col:
                    caballos_en_carr = list(st.session_state.remates.get(carr_leg, {}).keys())
                    cab_leg = st.selectbox(f"Ejemplar {i+1}", caballos_en_carr if caballos_en_carr else ["Sin Caballos"], key=f"cb_dup_{i}")
                
                if carr_leg in carreras_usadas_en_ticket:
                    valido_legs = False
                carreras_usadas_en_ticket.add(carr_leg)
                seleccion_legs.append({"carrera": carr_leg, "ejemplar": cab_leg})

    if not st.session_state.dupleta_bloqueada:
        if st.button("🚀 Emitir Ticket de Dupleta", use_container_width=True, type="primary"):
            if not valido_legs:
                st.error("⚠️ No puedes repetir carreras en el mismo ticket.")
            else:
                ticket_id = f"DUP-{len(st.session_state.dupletas_tickets) + 1:04d}"
                st.session_state.dupletas_tickets.append({
                    "id": ticket_id, "jugador": jugador_dupleta, "monto": monto_dupleta,
                    "legs": seleccion_legs, "estado": "Pendiente", "fecha": ahora_dt.strftime('%d/%m %I:%M %p')
                })
                if jugador_dupleta not in st.session_state.cuentas:
                    st.session_state.cuentas[jugador_dupleta] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                st.session_state.cuentas[jugador_dupleta]['Pujas'] += monto_dupleta
                st.success(f"✅ Ticket {ticket_id} emitido")
                st.rerun()

# 4. CIERRE
with tab4:
    st.markdown("<div class='subasta-header'>🏁 Cierre y Liquidación</div>", unsafe_allow_html=True)
    carr_seleccionada_liq = st.selectbox("Gestionar Carrera", lista_carreras_disponibles, key="c_liq")

    with st.container(border=True):
        c_cerrada_actual = st.session_state.carreras_cerradas_remate.get(carr_seleccionada_liq, False)
        
        if not c_cerrada_actual:
            if st.button("🔒 Cerrar Remate", key=f"btn_c_{carr_seleccionada_liq}", use_container_width=True):
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
            if st.button("🔓 Reabrir Remate", key=f"btn_re_{carr_seleccionada_liq}", use_container_width=True):
                st.session_state.carreras_cerradas_remate[carr_seleccionada_liq] = False
                st.session_state.remates_cargados_en_cuentas[carr_seleccionada_liq] = False
                st.rerun()

        if carr_seleccionada_liq in st.session_state.historial_ganadores:
            st.success("✅ Carrera ya liquidada.")
        else:
            pote_carr_total = sum([info['monto'] for info in st.session_state.remates[carr_seleccionada_liq].values()])
            monto_casa_calc = pote_carr_total * (porcentaje_casa / 100)
            premio_final_liq = pote_carr_total - monto_casa_calc + st.session_state.get(f"pote_inc_{carr_seleccionada_liq}", 0.0)
            
            caballo_ganador_elegido = st.selectbox("Ganador", list(st.session_state.remates[carr_seleccionada_liq].keys()), key=f"g_{carr_seleccionada_liq}")
            
            if st.button("🎯 Liquidar Premio", key=f"l_{carr_seleccionada_liq}", use_container_width=True, type="primary"):
                info_g = st.session_state.remates[carr_seleccionada_liq][caballo_ganador_elegido]
                if info_g['jugador'] != "Sin Postor":
                    if info_g['jugador'] not in st.session_state.cuentas:
                        st.session_state.cuentas[info_g['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                    st.session_state.cuentas[info_g['jugador']]['Premios'] += premio_final_liq
                st.session_state.ganancia_casa += monto_casa_calc
                st.session_state.historial_ganadores[carr_seleccionada_liq] = {"Ganador": info_g['jugador'], "Premio": formatear_bs(premio_final_liq)}
                st.success("¡Liquidado!")
                st.rerun()

# 5. CUENTAS
with tab5:
    st.markdown("<div class='subasta-header'>📊 Cuentas y Balances</div>", unsafe_allow_html=True)
    datos_cuentas = []
    tot_pujas_gen = 0.0
    for jugador, vals in st.session_state.cuentas.items():
        pujas, premios, abonos = vals['Pujas'], vals['Premios'], vals['Abonos']
        balance_neto = pujas - abonos - premios
        tot_pujas_gen += pujas
        datos_cuentas.append({"Jugador": jugador, "Compras": formatear_bs(pujas), "Premios": formatear_bs(premios), "Neto": formatear_bs(balance_neto)})
    st.dataframe(pd.DataFrame(datos_cuentas), use_container_width=True, hide_index=True)
    st.metric("Ganancia Casa", formatear_bs(st.session_state.ganancia_casa))

# 6. HISTORIAL
with tab6:
    st.markdown("<div class='subasta-header'>🧾 Historial de Transacciones</div>", unsafe_allow_html=True)
    if not st.session_state.historial_transacciones:
        st.info("Sin transacciones.")
    else:
        st.dataframe(pd.DataFrame(st.session_state.historial_transacciones), use_container_width=True, hide_index=True)

# 7. PDF
with tab7:
    st.markdown("<div class='subasta-header'>📄 Lector PDF e Importador</div>", unsafe_allow_html=True)
    pdf_subido = st.file_uploader("Sube el programa en PDF", type=["pdf"])
    if pdf_subido is not None:
        if st.button("🚀 Procesar e Importar", use_container_width=True, type="primary"):
            if procesar_programa_pdf(pdf_subido):
                st.success("¡Importado con éxito!")
                st.rerun()
            else:
                st.error("No se pudo leer el PDF.")
