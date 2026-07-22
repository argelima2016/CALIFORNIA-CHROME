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

# --- ESTILOS CSS CON TARJETAS COLORIDAS Y LETRAS GIGANTES Y LEGIBLES PARA LA TABLA ---
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
        margin-bottom: 4px;
        border-bottom: 2px solid #f1e05a;
        padding-bottom: 6px;
    }
    .live-clock-banner {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 14px;
        color: #58a6ff;
        font-weight: 600;
        margin-bottom: 12px;
        display: inline-block;
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
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        max-width: 100% !important;
    }
    
    /* --- ESTILOS ULTRA-LEGIBLES PARA LA TABLA PRINCIPAL DE EJEMPLARES --- */
    div[data-testid="stDataFrame"] {
        font-size: 18px !important;
    }
    div[data-testid="stDataFrame"] table {
        font-size: 18px !important;
    }
    div[data-testid="stDataFrame"] th {
        font-size: 18px !important;
        font-weight: 800 !important;
        background-color: #1f242c !important;
        color: #f1e05a !important;
        text-transform: uppercase;
    }
    div[data-testid="stDataFrame"] td {
        font-size: 18px !important;
        font-weight: 700 !important;
        padding: 10px 14px !important;
        color: #ffffff !important;
    }

    /* --- BOTONES BASE DE REGISTRO RÁPIDO --- */
    .stButton button {
        width: 100% !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        padding: 0.1rem 0.02rem !important;
        min-height: 32px !important;
        line-height: 1.1 !important;
        font-size: 11px !important;
        white-space: pre-line !important;
        letter-spacing: 0.2px;
    }

    /* --- ADAPTACIÓN MÓVIL MEJORADA (RESPONSIVE) --- */
    @media (max-width: 768px) {
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 4px;
        }
        div[data-testid="stDataFrame"] {
            overflow-x: auto;
        }
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

if 'fechas_horas_cierre_remate' not in st.session_state:
    st.session_state.fechas_horas_cierre_remate = {}

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

if 'carreras_activas_remate' not in st.session_state:
    st.session_state.carreras_activas_remate = []

if 'programa_pdf_bytes' not in st.session_state:
    st.session_state.programa_pdf_bytes = None

if 'programa_pdf_nombre' not in st.session_state:
    st.session_state.programa_pdf_nombre = None

if 'texto_completo_pdf' not in st.session_state:
    st.session_state.texto_completo_pdf = ""

def formatear_bs(monto):
    return f"Bs. {monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def obtener_abreviatura_carrera(nombre_carrera):
    match = re.search(r'\d+', nombre_carrera)
    if match:
        return f"C{match.group(0)}"
    return nombre_carrera[:3].upper()

# --- FORMATEADOR VISUAL LLAMATIVO PARA LA TABLA ---
def formatear_tabla_remate(remates_dict):
    """Convierte el diccionario de remates en una tabla con números de posición visualmente coloridos tipo etiqueta y nombres claros."""
    colores_badges = {
        1: "🟦 1", 2: "🟩 2", 3: "🟪 3", 4: "🟧 4", 5: "🟨 5",
        6: "🟥 6", 7: "🔷 7", 8: "🟢 8", 9: "🟣 9", 10: "🟤 10",
        11: "🔵 11", 12: "🟢 12", 13: "🟣 13", 14: "🟠 14", 15: "🟡 15",
        16: "🔴 16", 17: "💠 17", 18: "❇️ 18", 19: "🌀 19", 20: "🔶 20",
        21: "🔹 21", 22: "🟩 22", 23: "💜 23", 24: "🧡 24", 25: "💛 25"
    }
    
    datos = []
    for cab, info in remates_dict.items():
        match_num = re.match(r'^(\d+)', cab)
        if match_num:
            num = int(match_num.group(1))
            nombre_solo = cab.split(" - ", 1)[1] if " - " in cab else cab
            etiqueta_colorida = colores_badges.get(num, f"🔹 {num}")
            ejemplar_formateado = f"{etiqueta_colorida} ➔ {nombre_solo.upper()}"
        else:
            ejemplar_formateado = f"{cab}"
            
        datos.append({
            "Ejemplar / Posición": ejemplar_formateado,
            "Comprador": info['jugador'],
            "Monto Actual": formatear_bs(info['monto'])
        })
    return datos

# --- EXTRACCIÓN GENERAL DE TEXTO DEL PDF ---
def extraer_texto_pdf(archivo_pdf):
    try:
        bytes_data = archivo_pdf.getvalue()
        st.session_state.programa_pdf_bytes = bytes_data
        st.session_state.programa_pdf_nombre = getattr(archivo_pdf, "name", "Inscritos_Semana.pdf")
        
        lector_pdf = PdfReader(archivo_pdf)
        texto_extraido = ""
        for pagina in lector_pdf.pages:
            t_pag = pagina.extract_text()
            if t_pag:
                texto_extraido += t_pag + "\n"
        
        st.session_state.texto_completo_pdf = texto_extraido
        return True
    except Exception as e:
        st.sidebar.error(f"Error al leer PDF: {e}")
    return False

# --- MOTOR DE EXTRACCIÓN Y ORGANIZACIÓN ESTRICTA POR POSICIÓN Y CARRERA ---
def procesar_texto_para_remates(texto_a_procesar):
    try:
        lineas = texto_a_procesar.split('\n')
        carrera_actual_detectada = None
        banco_temporal = {}
        
        patron_carrera = re.compile(
            r'(?:carrera|primera|segunda|tercera|cuarta|quinta|sexta|septima|octava|novena|decima|\d+)\s*(?:ª|º|\.)?\s*carrera', 
            re.IGNORECASE
        )
        
        for linea in lineas:
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue
            
            match_carr = patron_carrera.search(linea_limpia)
            if match_carr or ("carrera" in linea_limpia.lower() and len(linea_limpia) < 35):
                for c_n in range(1, 15):
                    if str(c_n) in linea_limpia or f"carrera {c_n}" in linea_limpia.lower() or f"{c_n}ra" in linea_limpia.lower() or f"{c_n}da" in linea_limpia.lower() or f"{c_n}ta" in linea_limpia.lower():
                        carrera_actual_detectada = f"Carrera {c_n}"
                        if carrera_actual_detectada not in banco_temporal:
                            banco_temporal[carrera_actual_detectada] = []
                        break
            
            if carrera_actual_detectada:
                match_ejemplar = re.match(r'^(?:[Pp][Oo][Ss]\.?\s*)?(\d{1,2})[\s\-\.\)]+(.+)', linea_limpia)
                if match_ejemplar:
                    num_pos = int(match_ejemplar.group(1))
                    nom_ej = match_ejemplar.group(2).strip()
                    
                    palabras_excluir = ['retirado', 'jinete', 'entrenador', 'distancia', 'premio', 'propietario', 'condicion', 'hipodromo', 'metros', 'haras', 'stud', 'aprox']
                    if 1 <= num_pos <= 25 and len(nom_ej) > 1 and not any(p in nom_ej.lower() for p in palabras_excluir):
                        formato_ej = f"{num_pos} - {nom_ej.title()}"
                        if formato_ej not in banco_temporal[carrera_actual_detectada]:
                            banco_temporal[carrera_actual_detectada].append(formato_ej)

        if banco_temporal:
            for c_key in banco_temporal:
                banco_temporal[c_key].sort(key=lambda x: int(re.match(r'^(\d+)', x).group(1)))

            st.session_state.banco_caballos_por_carrera = banco_temporal
            for c_key, c_vals in banco_temporal.items():
                if c_key not in st.session_state.remates:
                    st.session_state.remates[c_key] = {}
                for ev in c_vals:
                    if ev not in st.session_state.remates[c_key]:
                        st.session_state.remates[c_key][ev] = {"jugador": "Sin Postor", "monto": 0.0}
            
            todas_carr = list(banco_temporal.keys())
            st.session_state.carreras_activas_remate = list(todas_carr)
            st.session_state.carreras_habilitadas_dupleta = list(todas_carr)
            return True
    except Exception as e:
        st.error(f"Error procesando el segmento: {e}")
    return False

if not st.session_state.remates:
    for i in range(1, 11):
        carr_nombre = f"Carrera {i}"
        st.session_state.banco_caballos_por_carrera[carr_nombre] = [f"{j} - Ejemplar {j}" for j in range(1, 11)]
        st.session_state.remates[carr_nombre] = {f"{j} - Ejemplar {j}": {"jugador": "Sin Postor", "monto": 0.0} for j in range(1, 11)}

lista_carreras_disponibles = list(st.session_state.remates.keys())

if not st.session_state.carreras_activas_remate and lista_carreras_disponibles:
    st.session_state.carreras_activas_remate = list(lista_carreras_disponibles)

if not st.session_state.carreras_habilitadas_dupleta and lista_carreras_disponibles:
    st.session_state.carreras_habilitadas_dupleta = list(lista_carreras_disponibles)

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Menú de Control")
ahora_dt = obtener_hora_venezuela_local()
st.sidebar.markdown(f"🕒 **Hora:** `{ahora_dt.strftime('%I:%M:%S %p')}`")

with st.sidebar.expander("⚡ Carreras Activas para Remate", expanded=True):
    st.markdown("Selecciona cuáles carreras están disponibles y activas en el panel principal:")
    carreras_seleccionadas_activas = st.multiselect(
        "Carreras Activas",
        options=lista_carreras_disponibles,
        default=[c for c in st.session_state.carreras_activas_remate if c in lista_carreras_disponibles],
        key="multiselect_carreras_activas_menu"
    )
    if carreras_seleccionadas_activas != st.session_state.carreras_activas_remate:
        st.session_state.carreras_activas_remate = carreras_seleccionadas_activas
        st.rerun()

with st.sidebar.expander("🏠 Retención de la Casa", expanded=False):
    porcentaje_casa = st.slider("Retención (%)", 0, 50, 30, key="slider_retencion_casa")

with st.sidebar.expander("📅⏰ Cierres Estrictos por Carrera", expanded=False):
    carrera_config_sel = st.selectbox("Seleccionar Carrera", lista_carreras_disponibles, key="selector_carrera_config_sidebar")
    fecha_sel = st.date_input("Fecha de Cierre", value=ahora_dt.date(), key=f"sel_f_{carrera_config_sel}")
    periodo_sel = st.radio("Periodo", ["AM", "PM"], key=f"radio_p_{carrera_config_sel}", horizontal=True)
    hora_12 = st.selectbox("Hora", list(range(1, 13)), key=f"sel_h_{carrera_config_sel}")
    minuto_sel = st.selectbox("Minutos", list(range(0, 60)), key=f"sel_m_{carrera_config_sel}")
    
    h_24_conv = int(hora_12)
    if periodo_sel == "PM" and h_24_conv < 12: h_24_conv += 12
    elif periodo_sel == "AM" and h_24_conv == 12: h_24_conv = 0
    
    hora_seleccionada = time(h_24_conv, int(minuto_sel))
    dt_cierre_completo = datetime.combine(fecha_sel, hora_seleccionada)
    
    col_bh1, col_bh2 = st.sidebar.columns(2)
    with col_bh1:
        if st.button("💾 Guardar", key=f"bs_h_{carrera_config_sel}"):
            st.session_state.fechas_horas_cierre_remate[carrera_config_sel] = dt_cierre_completo
            st.session_state.estado_conteo_carrera[carrera_config_sel] = "INACTIVO"
            st.toast(f"✅ Cierre guardado para {carrera_config_sel}")
            st.rerun()
    with col_bh2:
        if st.button("🗑️ Borrar", key=f"bc_h_{carrera_config_sel}"):
            if carrera_config_sel in st.session_state.fechas_horas_cierre_remate:
                del st.session_state.fechas_horas_cierre_remate[carrera_config_sel]
            st.session_state.estado_conteo_carrera[carrera_config_sel] = "INACTIVO"
            st.toast("🗑️ Cierre removido")
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
    "🏇 Remates Adelantados Activos", "✍️ Banco", "🎟️ Dupletas", "🏁 Cierre", "📊 Cuentas", "🧾 Hist.", "📄 PDF"
])

# 1. REMATES ADELANTADOS ACTIVOS
with tab1:
    col_t_title, col_t_pdf = st.columns([5, 1])
    with col_t_title:
        st.markdown("<div class='subasta-header' style='margin-bottom:0;'>🎯 Remates Adelantados Activos</div>", unsafe_allow_html=True)
    with col_t_pdf:
        if st.session_state.programa_pdf_bytes is not None:
            st.download_button(
                label="📄",
                data=st.session_state.programa_pdf_bytes,
                file_name=st.session_state.programa_pdf_nombre or "Inscritos_Semana.pdf",
                mime="application/pdf",
                key="btn_descarga_pdf_compacto_top",
                help="📥 Ver/Descargar Programa de la Semana (PDF)"
            )
        else:
            st.markdown("<div style='font-size: 11px; color: #8b949e; text-align: right; padding-top: 10px;'>Sin PDF</div>", unsafe_allow_html=True)

    st.markdown(f"<div class='live-clock-banner'>📅 Fecha y Hora Actual: <b>{ahora_dt.strftime('%d/%m/%Y - %I:%M:%S %p')}</b></div>", unsafe_allow_html=True)
    
    if not lista_carreras_disponibles:
        st.warning("⚠️ No hay carreras cargadas en el sistema.")
    else:
        carreras_filtradas_visibles = [
            c for c in lista_carreras_disponibles 
            if (c in st.session_state.carreras_activas_remate) or st.session_state.carreras_cerradas_remate.get(c, False)
        ]
        
        if not carreras_filtradas_visibles:
            st.info("ℹ️ No hay carreras activas ni cerradas para mostrar. Selecciona carreras en el menú lateral de control.")
        else:
            num_carreras_visibles = len(carreras_filtradas_visibles)
            anchos_columnas = [1] * num_carreras_visibles + [max(1, 7 - num_carreras_visibles)]
            cols_selector = st.columns(anchos_columnas)
            
            for idx, c_nombre in enumerate(carreras_filtradas_visibles):
                col_target = cols_selector[idx]
                
                c_cerrada = st.session_state.carreras_cerradas_remate.get(c_nombre, False)
                abreviatura = obtener_abreviatura_carrera(c_nombre)
                
                if c_cerrada:
                    label_btn = f"{abreviatura} 🔴"
                    tipo_btn = "secondary"
                else:
                    label_btn = f"{abreviatura} 🟢"
                    tipo_btn = "primary"
                
                with col_target:
                    if st.button(label_btn, key=f"btn_sel_carr_didactico_{idx}", use_container_width=True, type=tipo_btn, help=f"{c_nombre} - {'Cerrada' if c_cerrada else 'Activa'}"):
                        st.session_state["carrera_remate_activa_seleccionada"] = c_nombre
                        st.rerun()

            if "carrera_remate_activa_seleccionada" not in st.session_state or st.session_state["carrera_remate_activa_seleccionada"] not in carreras_filtradas_visibles:
                carr_activa = carreras_filtradas_visibles[0]
                st.session_state["carrera_remate_activa_seleccionada"] = carr_activa
            else:
                carr_activa = st.session_state["carrera_remate_activa_seleccionada"]

            if not carr_activa:
                st.info("👆 Selecciona una carrera arriba para ver su panel.")
            else:
                st.markdown(f"---")
                
                carrera_cerrada = st.session_state.carreras_cerradas_remate.get(carr_activa, False)
                
                if carrera_cerrada:
                    st.error(f"🔴 La carrera **{carr_activa}** se encuentra **CERRADA** para nuevas pujas.")
                else:
                    st.success(f"🟢 Panel activo y abierto para: **{carr_activa}**")

                st.markdown(f"### 🏁 {carr_activa}")
                
                dt_limite = st.session_state.fechas_horas_cierre_remate.get(carr_activa)
                estado_conteo = st.session_state.estado_conteo_carrera.get(carr_activa, "INACTIVO")
                
                if dt_limite:
                    st.markdown(f"<div class='cierre-info-box'>⏰ Cierre Estricto: <b>{dt_limite.strftime('%d/%m/%Y - %I:%M %p')}</b></div>", unsafe_allow_html=True)

                if dt_limite and not carrera_cerrada:
                    diferencia_segundos = (dt_limite - ahora_dt).total_seconds()
                    
                    if estado_conteo == "INACTIVO":
                        if 0 < diferencia_segundos <= 10:
                            st.session_state.estado_conteo_carrera[carr_activa] = "CONTEO_10S"
                            st.session_state.tiempo_inicio_conteo[carr_activa] = ahora_dt
                            st.rerun()
                        elif diferencia_segundos <= 0:
                            st.session_state.carreras_cerradas_remate[carr_activa] = True
                            st.session_state.estado_conteo_carrera[carr_activa] = "CERRADO"
                            st.rerun()
                    elif estado_conteo == "CONTEO_10S":
                        tiempo_inicio = st.session_state.tiempo_inicio_conteo.get(carr_activa, ahora_dt)
                        transcurridos = (ahora_dt - tiempo_inicio).total_seconds()
                        
                        if transcurridos >= 12:
                            st.session_state.carreras_cerradas_remate[carr_activa] = True
                            st.session_state.estado_conteo_carrera[carr_activa] = "CERRADO"
                            st.rerun()
                        else:
                            restantes_10s = max(0, 10 - int(transcurridos))
                            if restantes_10s > 0:
                                st.markdown(f"<div class='timer-box'>⚠️ CIERRE EN: <b>{restantes_10s}s</b> ({carr_activa})</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='timer-box'>⚠️ ULTIMOS SEGUNDOS ANTES DE CIERRE ({carr_activa})</div>", unsafe_allow_html=True)

                # --- TABLA DE EJEMPLARES CON NÚMEROS COLORIDOS Y LETRA GRANDE ---
                datos_tabla = formatear_tabla_remate(st.session_state.remates[carr_activa])
                total_pote = sum([info['monto'] for info in st.session_state.remates[carr_activa].values()])
                
                cantidad_filas = len(datos_tabla)
                altura_tabla = min(max(180, (cantidad_filas + 1) * 44), 500)
                
                st.dataframe(
                    pd.DataFrame(datos_tabla), 
                    use_container_width=True, 
                    hide_index=True,
                    height=altura_tabla
                )
                
                monto_casa = total_pote * (porcentaje_casa / 100)
                pote_neto_base = total_pote - monto_casa

                c_m1, c_m2 = st.columns(2)
                c_m1.metric(f"💰 Pote ({carr_activa})", formatear_bs(total_pote))
                pote_incentivo_extra = c_m2.number_input("🎁 Extra", min_value=0.0, value=0.0, step=50.0, key=f"pote_inc_{carr_activa}")
                premio_total_calculado = pote_neto_base + pote_incentivo_extra
                st.metric(f"🏆 Premio Total ({carr_activa})", formatear_bs(premio_total_calculado))

                # --- REGISTRO RÁPIDO DE PUJA CON BOTONES COLORIDOS ---
                with st.container(border=True):
                    st.markdown(f"⚡ **Registro Rápido de Puja - {carr_activa}**")
                    lista_caballos_activos = list(st.session_state.remates[carr_activa].keys())
                    
                    if not lista_caballos_activos:
                        st.warning("Sin ejemplares inscritos en esta carrera.")
                    else:
                        k_sel_cab = f"caballo_seleccionado_click_{carr_activa}"
                        if k_sel_cab not in st.session_state or st.session_state[k_sel_cab] not in lista_caballos_activos:
                            st.session_state[k_sel_cab] = lista_caballos_activos[0]
                            
                        st.markdown(f"🔹 **1. Seleccionar Ejemplar (Total inscritos: {len(lista_caballos_activos)}):**")
                        
                        cantidad_ejemplares = len(lista_caballos_activos)
                        columnas_por_fila = 4
                        num_filas = (cantidad_ejemplares + columnas_por_fila - 1) // columnas_por_fila
                        
                        idx_cab = 0
                        for f in range(num_filas):
                            cols_fila = st.columns(columnas_por_fila)
                            for c in range(columnas_por_fila):
                                if idx_cab < cantidad_ejemplares:
                                    cab_item = lista_caballos_activos[idx_cab]
                                    num_parte = cab_item.split(" - ")[0]
                                    with cols_fila[c]:
                                        if st.button(f"#{num_parte}", key=f"btn_r_cab_{carr_activa}_{idx_cab}", use_container_width=True):
                                            st.session_state[k_sel_cab] = cab_item
                                    idx_cab += 1
                        
                        caballo_seleccionado = st.session_state[k_sel_cab]
                        st.info(f"Ejemplar activo en {carr_activa}: **{caballo_seleccionado}**")

                        puja_actual = st.session_state.remates[carr_activa][caballo_seleccionado]['monto']
                        opciones_escala = obtener_siguientes_montos(puja_actual)
                        monto_puja = st.selectbox("💰 **2. Monto de Puja**", opciones_escala, format_func=lambda x: formatear_bs(x), key=f"sel_esc_{carr_activa}_{caballo_seleccionado}")
                        
                        if carrera_cerrada:
                            st.button(f"🔨 Confirmar Puja ({carr_activa})", key=f"btn_p_{carr_activa}", use_container_width=True, type="primary", disabled=True)
                        else:
                            if st.button(f"🔨 Confirmar Puja ({carr_activa})", key=f"btn_p_{carr_activa}", use_container_width=True, type="primary"):
                                if monto_puja <= puja_actual:
                                    st.error("El monto debe ser mayor a la puja actual.")
                                else:
                                    st.session_state.remates[carr_activa][caballo_seleccionado] = {"jugador": "Sin Postor", "monto": monto_puja}
                                    
                                    if estado_conteo == "CONTEO_10S":
                                        st.session_state.tiempo_inicio_conteo[carr_activa] = obtener_hora_venezuela_local()
                                        
                                    st.success("✅ ¡Puja registrada correctamente y conteo reiniciado!")
                                    st.rerun()

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
                while sig_num in nums and sig_num <= 25: sig_num += 1
                formato_nuevo = f"{sig_num} - {nom_limp}"
                
                if formato_nuevo not in st.session_state.banco_caballos_por_carrera[carr_banco_sel]:
                    st.session_state.banco_caballos_por_carrera[carr_banco_sel].append(formato_nuevo)
                    st.session_state.banco_caballos_por_carrera[carr_banco_sel].sort(key=lambda x: int(re.match(r'^(\d+)', x).group(1)))

                if carr_banco_sel not in st.session_state.remates:
                    st.session_state.remates[carr_banco_sel] = {}
                if formato_nuevo not in st.session_state.remates[carr_banco_sel]:
                    st.session_state.remates[carr_banco_sel][formato_nuevo] = {"jugador": "Sin Postor", "monto": 0.0}
                st.toast("✅ ¡Agregado con éxito y ordenado por posición!")
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

# 7. PDF (CON LECTOR MANUAL Y ORGANIZACIÓN ESTRICTA POR POSICIÓN)
with tab7:
    st.markdown("<div class='subasta-header'>📄 Lector PDF e Importador Organizado por Posición</div>", unsafe_allow_html=True)
    
    pdf_subido = st.file_uploader("Sube el programa oficial en PDF", type=["pdf"])
    if pdf_subido is not None:
        if st.button("📥 Cargar PDF en Memoria", use_container_width=True):
            if extraer_texto_pdf(pdf_subido):
                st.success("✅ ¡PDF cargado correctamente! Ya puedes procesarlo abajo.")
                st.rerun()

    if st.session_state.programa_pdf_bytes is not None:
        st.markdown("---")
        st.markdown("### ✂️ Segmento Específico y Ordenamiento Estricto")
        st.markdown("Pega aquí abajo el texto seleccionado o la sección que deseas procesar. El sistema extraerá de forma automática la **Carrera N**, ordenando cada ejemplar por su **Número de Posición / Ejemplar** de menor a mayor:")
        
        texto_seleccion_usuario = st.text_area(
            "Texto del segmento específico a sincronizar:",
            value=st.session_state.texto_completo_pdf[:2000] if st.session_state.texto_completo_pdf else "",
            height=250,
            placeholder="Ejemplo:\nPRIMERA CARRERA. CONDICIÓN: ...\n1 REY DAVID\n2 GRAN AMIGO..."
        )
        
        col_ps1, col_ps2 = st.columns(2)
        with col_ps1:
            if st.button("🚀 Sincronizar y Ordenar por Posición", use_container_width=True, type="primary"):
                if procesar_texto_para_remates(texto_seleccion_usuario):
                    st.success("✅ ¡Segmento procesado, ordenado por posición y sincronizado con éxito!")
                    st.rerun()
                else:
                    st.error("⚠️ No se pudo extraer la estructura correcta. Revisa que el texto contenga el nombre de la carrera y los números de posición.")
        with col_ps2:
            if st.button("⚡ Procesar PDF Completo Organizado", use_container_width=True):
                if procesar_texto_para_remates(st.session_state.texto_completo_pdf):
                    st.success("✅ ¡Programa completo procesado y ordenado por posición!")
                    st.rerun()
                else:
                    st.error("⚠️ No se pudo procesar automáticamente el documento.")
