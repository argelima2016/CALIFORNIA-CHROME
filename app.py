from datetime import datetime, time, timedelta, timezone
import os
import re
from zoneinfo import ZoneInfo
import pdfplumber
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN DE PANTALLA ---
st.set_page_config(
    page_title="Sistema de Remates", layout="wide", page_icon="🏇"
)

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
    50,
    100,
    150,
    200,
    250,
    300,
    350,
    400,
    500,
    600,
    700,
    800,
    900,
    1000,
    1200,
    1400,
    1600,
    1800,
    2000,
    2500,
    3000,
    3500,
    4000,
    4500,
    5000,
    5500,
    6000,
    6500,
    7000,
    7500,
    8000,
    8500,
    9000,
    9500,
    10000,
] + list(range(11000, 1000001, 1000))


def obtener_siguientes_montos(monto_actual):
  siguientes = [m for m in ESCALA_PUJAS if m > monto_actual]
  if not siguientes:
    ultimo = ESCALA_PUJAS[-1] if ESCALA_PUJAS else max(monto_actual, 10000)
    siguientes = [ultimo + i * 1000 for i in range(1, 50)]
  return siguientes


# --- ESTILOS CSS ---
st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #f0f6fc; }
    .subasta-header { font-size: clamp(20px, 4vw, 26px); font-weight: 800; color: #f1e05a; margin-bottom: 4px; border-bottom: 2px solid #f1e05a; padding-bottom: 6px; }
    .live-clock-banner { background-color: #161b22; border: 1px solid #30363d; padding: 6px 12px; border-radius: 6px; font-size: 14px; color: #58a6ff; font-weight: 600; margin-bottom: 12px; display: inline-block; }
    .timer-box { background-color: #161b22; border: 2px solid #ff4757; padding: 12px; border-radius: 8px; text-align: center; font-size: clamp(16px, 3.5vw, 22px); font-weight: bold; color: #ff4757; margin-bottom: 12px; }
    .cierre-info-box { background-color: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 6px; text-align: center; font-size: 16px; color: #f0f6fc; margin-bottom: 12px; }
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; padding-left: 0.6rem !important; padding-right: 0.6rem !important; max-width: 100% !important; }
    div[data-testid="stDataFrame"] { font-size: 18px !important; border: 2px solid #30363d !important; border-radius: 10px !important; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4) !important; overflow: hidden !important; background-color: #13171f !important; }
    div[data-testid="stDataFrame"] table { font-size: 18px !important; border-collapse: separate !important; border-spacing: 0 !important; width: 100% !important; }
    div[data-testid="stDataFrame"] th { font-size: 19px !important; font-weight: 800 !important; background: linear-gradient(135deg, #1f242c 0%, #161b22 100%) !important; color: #f1e05a !important; text-transform: uppercase; border-bottom: 3px solid #f1e05a !important; border-right: 1px solid #30363d !important; padding: 14px 16px !important; text-align: left !important; letter-spacing: 0.5px; }
    div[data-testid="stDataFrame"] td { font-size: 18px !important; font-weight: 700 !important; padding: 12px 16px !important; color: #ffffff !important; background-color: #161b22 !important; border-bottom: 1px solid #21262d !important; border-right: 1px solid #21262d !important; }
    div[data-testid="stDataFrame"] tr:hover td { background-color: #1c212c !important; color: #58a6ff !important; }
    .stButton button { width: 100% !important; border-radius: 6px !important; font-weight: 500 !important; padding: 0.1rem 0.02rem !important; min-height: 32px !important; line-height: 1.1 !important; font-size: 11px !important; white-space: pre-line !important; letter-spacing: 0.2px; }
    @media (max-width: 768px) { [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important; margin-bottom: 4px; } div[data-testid="stDataFrame"] { overflow-x: auto; } }
    </style>
""",
    unsafe_allow_html=True,
)


# --- JUGADORES BASE ---
@st.cache_data
def cargar_jugadores_base():
  return [
      "CASA",
      "SOMBI",
      "LUIS",
      "CARLOS",
      "RAMON",
      "ALDEA",
      "ANGEL",
      "ALFONSO",
      "MACANO",
      "MIGUEL",
      "TOCAYO",
      "EL GOCHO",
      "PAPIRO",
      "CHAYO",
      "ALEXIS",
  ]


# --- ESTADO GLOBAL ---
if "lista_jugadores" not in st.session_state:
  st.session_state.lista_jugadores = cargar_jugadores_base()
if "banco_caballos_por_carrera" not in st.session_state:
  st.session_state.banco_caballos_por_carrera = {}
if "banco_general_extraido" not in st.session_state:
  st.session_state.banco_general_extraido = []
if "carreras_extraidas_pdf" not in st.session_state:
  st.session_state.carreras_extraidas_pdf = []
if "remates" not in st.session_state:
  st.session_state.remates = {}
if "historial_ganadores" not in st.session_state:
  st.session_state.historial_ganadores = {}
if "carreras_cerradas_remate" not in st.session_state:
  st.session_state.carreras_cerradas_remate = {}
if "remates_cargados_en_cuentas" not in st.session_state:
  st.session_state.remates_cargados_en_cuentas = {}
if "fechas_horas_cierre_remate" not in st.session_state:
  st.session_state.fechas_horas_cierre_remate = {}
if "estado_conteo_carrera" not in st.session_state:
  st.session_state.estado_conteo_carrera = {}
if "tiempo_inicio_conteo" not in st.session_state:
  st.session_state.tiempo_inicio_conteo = {}
if "cuentas" not in st.session_state:
  st.session_state.cuentas = {
      j: {"Pujas": 0.0, "Premios": 0.0, "Abonos": 0.0}
      for j in st.session_state.lista_jugadores
  }
if "ganancia_casa" not in st.session_state:
  st.session_state.ganancia_casa = 0.0
if "historial_transacciones" not in st.session_state:
  st.session_state.historial_transacciones = []
if "dupletas_tickets" not in st.session_state:
  st.session_state.dupletas_tickets = []
if "carreras_habilitadas_dupleta" not in st.session_state:
  st.session_state.carreras_habilitadas_dupleta = []
if "dupleta_bloqueada" not in st.session_state:
  st.session_state.dupleta_bloqueada = False
if "carreras_activas_remate" not in st.session_state:
  st.session_state.carreras_activas_remate = []
if "programa_pdf_bytes" not in st.session_state:
  st.session_state.programa_pdf_bytes = None
if "programa_pdf_nombre" not in st.session_state:
  st.session_state.programa_pdf_nombre = None


def formatear_bs(monto):
  return f"Bs. {monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def obtener_abreviatura_carrera(nombre_carrera):
  match = re.search(r"\d+", nombre_carrera)
  if match:
    return f"C{match.group(0)}"
  return nombre_carrera[:3].upper()


def formatear_tabla_remate(remates_dict):
  colores_badges = {
      1: "🟦 1",
      2: "🟩 2",
      3: "🟪 3",
      4: "🟧 4",
      5: "🟨 5",
      6: "🟥 6",
      7: "🔷 7",
      8: "🟢 8",
      9: "🟣 9",
      10: "🟤 10",
      11: "🔵 11",
      12: "🟢 12",
      13: "🟣 13",
      14: "🟠 14",
      15: "🟡 15",
  }
  datos = []
  for cab, info in remates_dict.items():
    match_num = re.match(r"^(\d+)", cab)
    if match_num:
      num = int(match_num.group(1))
      nombre_solo = cab.split(" - ", 1)[1] if " - " in cab else cab
      etiqueta_colorida = colores_badges.get(num, f"🔹 {num}")
      ejemplar_formateado = f"{etiqueta_colorida} ➔ {nombre_solo.upper()}"
    else:
      ejemplar_formateado = f"{cab}"

    datos.append({
        "Ejemplar / Posición": ejemplar_formateado,
        "Comprador": info["jugador"],
        "Monto Actual": formatear_bs(info["monto"]),
    })
  return datos


# --- EXTRACCIÓN ESTRUCTURADA CON PDFPLUMBER ---
def extraer_datos_completos_pdf(archivo_pdf):
  try:
    bytes_data = archivo_pdf.getvalue()
    st.session_state.programa_pdf_bytes = bytes_data
    st.session_state.programa_pdf_nombre = getattr(
        archivo_pdf, "name", "Inscritos_Semana.pdf"
    )

    carreras_extraidas = []
    texto_completo = ""

    with pdfplumber.open(archivo_pdf) as pdf:
      for pagina in pdf.pages:
        texto_pagina = pagina.extract_text()
        if texto_pagina:
          texto_completo += texto_pagina + "\n"

    # Buscar bloques de carrera (ej: "1a. CARRERA", "CARRERA 1", "1ª Carrera")
    patron_carrera = re.compile(
        r"(?:(?:\d{1,2}[aªá]\.?\s*CARRERA)|(?:CARRERA\s*\d{1,2}))", re.IGNORECASE
    )
    bloques = patron_carrera.split(texto_completo)
    encabezados = patron_carrera.findall(texto_completo)

    excluir = [
        "RETIRADO",
        "JINETE",
        "ENTRENADOR",
        "DISTANCIA",
        "PREMIO",
        "HIPODROMO",
        "PROPIETARIO",
        "HARAS",
        "STUD",
    ]

    for idx, bloque in enumerate(bloques[1:]):
      nombre_carrera = encabezados[idx].strip().upper()
      num_match = re.search(r"\d+", nombre_carrera)
      num_carrera = num_match.group(0) if num_match else str(idx + 1)
      nombre_carrera_estandar = f"Carrera {num_carrera}"

      # Extraer Hora
      match_hora = re.search(
          r"\b(1[0-2]|0?[1-9]):([0-5][0-9])\s*(AM|PM|a\.m\.|p\.m\.)\b",
          bloque,
          re.IGNORECASE,
      )
      hora = match_hora.group(0) if match_hora else "No especificada"

      # Extraer Distancia
      match_distancia = re.search(
          r"\b(\d[\d\.]*)\s*(metros|mts|m)\b", bloque, re.IGNORECASE
      )
      distancia = (
          match_distancia.group(0) if match_distancia else "No especificada"
      )

      # Extraer Ejemplares con su Puesto
      ejemplares = []
      lineas = bloque.split("\n")

      for linea in lineas:
        linea_limpia = linea.strip()
        match_ej = re.match(
            r"^\(?(\d{1,2})\)?[\s\-\.\)]+([A-Za-z\s]+)", linea_limpia
        )
        if match_ej:
          puesto = match_ej.group(1)
          nom_ej = (
              re.split(r"\s{2,}|\d+[\.,]\d+|\b[A-Z]{2,}\b", match_ej.group(2))[0]
              .strip()
              .title()
          )

          if len(nom_ej) > 1 and not any(
              p in nom_ej.upper() for p in excluir
          ):
            formato_completo = f"{puesto} - {nom_ej}"
            ejemplares.append({
                "puesto": puesto,
                "nombre": nom_ej,
                "formato": formato_completo,
            })

      carreras_extraidas.append({
          "carrera": nombre_carrera_estandar,
          "hora": hora,
          "distancia": distancia,
          "ejemplares": ejemplares,
      })

    st.session_state.carreras_extraidas_pdf = carreras_extraidas

    # Actualizar Banco General
    banco_temp = set(st.session_state.banco_general_extraido)
    for c in carreras_extraidas:
      for ej in c["ejemplares"]:
        banco_temp.add(ej["nombre"])
    st.session_state.banco_general_extraido = sorted(list(banco_temp))

    return True
  except Exception as e:
    st.sidebar.error(f"Error procesando PDF: {e}")
  return False


if not st.session_state.remates:
  for i in range(1, 11):
    carr = f"Carrera {i}"
    st.session_state.banco_caballos_por_carrera[carr] = [
        f"{j} - Ejemplar {j}" for j in range(1, 11)
    ]
    st.session_state.remates[carr] = {
        f"{j} - Ejemplar {j}": {"jugador": "Sin Postor", "monto": 0.0}
        for j in range(1, 11)
    }

lista_carreras_disponibles = list(st.session_state.remates.keys())
if not st.session_state.carreras_activas_remate and lista_carreras_disponibles:
  st.session_state.carreras_activas_remate = list(lista_carreras_disponibles)
if (
    not st.session_state.carreras_habilitadas_dupleta
    and lista_carreras_disponibles
):
  st.session_state.carreras_habilitadas_dupleta = list(
      lista_carreras_disponibles
  )

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Menú de Control")
ahora_dt = obtener_hora_venezuela_local()
st.sidebar.markdown(f"🕒 **Hora:** `{ahora_dt.strftime('%I:%M:%S %p')}`")

with st.sidebar.expander("⚡ Carreras Activas para Remate", expanded=True):
  carreras_seleccionadas_activas = st.multiselect(
      "Carreras Activas",
      options=lista_carreras_disponibles,
      default=[
          c
          for c in st.session_state.carreras_activas_remate
          if c in lista_carreras_disponibles
      ],
      key="multiselect_carreras_activas_menu",
  )
  if carreras_seleccionadas_activas != st.session_state.carreras_activas_remate:
    st.session_state.carreras_activas_remate = carreras_seleccionadas_activas
    st.rerun()

with st.sidebar.expander("🏠 Retención de la Casa", expanded=False):
  porcentaje_casa = st.slider(
      "Retención (%)", 0, 50, 30, key="slider_retencion_casa"
  )

with st.sidebar.expander("📅⏰ Cierres Estrictos por Carrera", expanded=False):
  carrera_config_sel = st.selectbox(
      "Seleccionar Carrera",
      lista_carreras_disponibles,
      key="selector_carrera_config_sidebar",
  )
  fecha_sel = st.date_input(
      "Fecha de Cierre",
      value=ahora_dt.date(),
      key=f"sel_f_{carrera_config_sel}",
  )
  periodo_sel = st.radio(
      "Periodo", ["AM", "PM"], key=f"radio_p_{carrera_config_sel}", horizontal=True
  )
  hora_12 = st.selectbox(
      "Hora", list(range(1, 13)), key=f"sel_h_{carrera_config_sel}"
  )
  minuto_sel = st.selectbox(
      "Minutos", list(range(0, 60)), key=f"sel_m_{carrera_config_sel}"
  )

  h_24 = int(hora_12)
  if periodo_sel == "PM" and h_24 < 12:
    h_24 += 12
  elif periodo_sel == "AM" and h_24 == 12:
    h_24 = 0

  dt_cierre_completo = datetime.combine(fecha_sel, time(h_24, int(minuto_sel)))

  col_bh1, col_bh2 = st.sidebar.columns(2)
  with col_bh1:
    if st.button("💾 Guardar", key=f"bs_h_{carrera_config_sel}"):
      st.session_state.fechas_horas_cierre_remate[carrera_config_sel] = (
          dt_cierre_completo
      )
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
    st.markdown(
        "<p style='color: #ff4757; font-weight: bold;'>🔴 BLOQUEADAS</p>",
        unsafe_allow_html=True,
    )
    if st.button("🔓 Desbloquear", key="b_des_dup"):
      st.session_state.dupleta_bloqueada = False
      st.rerun()
  else:
    st.markdown(
        "<p style='color: #00d2d3; font-weight: bold;'>🟢 ABIERTAS</p>",
        unsafe_allow_html=True,
    )
    if st.button("🔒 Bloquear", key="b_blo_dup"):
      st.session_state.dupleta_bloqueada = True
      st.rerun()

if st.sidebar.button("🗑️ Reiniciar Jornada", use_container_width=True):
  for key in list(st.session_state.keys()):
    if key != "banco_caballos_por_carrera":
      del st.session_state[key]
  st.toast("🚨 Jornada reiniciada.")
  st.rerun()

# --- PESTAÑAS PRINCIPALES ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏇 Remates Adelantados Activos",
    "✍️ Banco y Selección",
    "🎟️ Dupletas",
    "🏁 Cierre",
    "📊 Cuentas",
    "🧾 Hist.",
    "📄 PDF / Auto",
])

# 1. REMATES ADELANTADOS ACTIVOS
with tab1:
  col_t_title, col_t_pdf = st.columns([5, 1])
  with col_t_title:
    st.markdown(
        "<div class='subasta-header' style='margin-bottom:0;'>🎯 Remates"
        " Adelantados Activos</div>",
        unsafe_allow_html=True,
    )
  with col_t_pdf:
    if st.session_state.programa_pdf_bytes is not None:
      st.download_button(
          label="📄",
          data=st.session_state.programa_pdf_bytes,
          file_name=st.session_state.programa_pdf_nombre
          or "Inscritos_Semana.pdf",
          mime="application/pdf",
          key="btn_descarga_pdf_top",
      )

  st.markdown(
      "<div class='live-clock-banner'>📅 Fecha y Hora Actual:"
      f" <b>{ahora_dt.strftime('%d/%m/%Y - %I:%M:%S %p')}</b></div>",
      unsafe_allow_html=True,
  )

  carreras_filtradas = [
      c
      for c in lista_carreras_disponibles
      if (c in st.session_state.carreras_activas_remate)
      or st.session_state.carreras_cerradas_remate.get(c, False)
  ]

  if not carreras_filtradas:
    st.info("ℹ️ No hay carreras activas. Actívalas en el menú lateral.")
  else:
    cols_selector = st.columns(len(carreras_filtradas))
    for idx, c_nombre in enumerate(carreras_filtradas):
      c_cerrada = st.session_state.carreras_cerradas_remate.get(
          c_nombre, False
      )
      abrev = obtener_abreviatura_carrera(c_nombre)
      label_btn = f"{abrev} 🔴" if c_cerrada else f"{abrev} 🟢"
      type_btn = "secondary" if c_cerrada else "primary"

      with cols_selector[idx]:
        if st.button(
            label_btn,
            key=f"btn_sel_carr_{idx}",
            use_container_width=True,
            type=type_btn,
        ):
          st.session_state["carrera_remate_activa_seleccionada"] = c_nombre
          st.rerun()

    if (
        "carrera_remate_activa_seleccionada" not in st.session_state
        or st.session_state["carrera_remate_activa_seleccionada"]
        not in carreras_filtradas
    ):
      st.session_state["carrera_remate_activa_seleccionada"] = (
          carreras_filtradas[0]
      )

    carr_activa = st.session_state["carrera_remate_activa_seleccionada"]
    st.markdown("---")
    carrera_cerrada = st.session_state.carreras_cerradas_remate.get(
        carr_activa, False
    )

    if carrera_cerrada:
      st.error(
          f"🔴 La carrera **{carr_activa}** se encuentra **CERRADA** para"
          " nuevas pujas."
      )
    else:
      st.success(f"🟢 Panel activo y abierto para: **{carr_activa}**")

    dt_limite = st.session_state.fechas_horas_cierre_remate.get(carr_activa)
    estado_conteo = st.session_state.estado_conteo_carrera.get(
        carr_activa, "INACTIVO"
    )

    if dt_limite:
      st.markdown(
          "<div class='cierre-info-box'>⏰ Cierre Estricto:"
          f" <b>{dt_limite.strftime('%d/%m/%Y - %I:%M %p')}</b></div>",
          unsafe_allow_html=True,
      )

    if dt_limite and not carrera_cerrada:
      dif_sec = (dt_limite - ahora_dt).total_seconds()
      if estado_conteo == "INACTIVO":
        if 0 < dif_sec <= 10:
          st.session_state.estado_conteo_carrera[carr_activa] = "CONTEO_10S"
          st.session_state.tiempo_inicio_conteo[carr_activa] = ahora_dt
          st.rerun()
        elif dif_sec <= 0:
          st.session_state.carreras_cerradas_remate[carr_activa] = True
          st.session_state.estado_conteo_carrera[carr_activa] = "CERRADO"
          st.rerun()
      elif estado_conteo == "CONTEO_10S":
        t_inicio = st.session_state.tiempo_inicio_conteo.get(
            carr_activa, ahora_dt
        )
        transcurridos = (ahora_dt - t_inicio).total_seconds()
        if transcurridos >= 12:
          st.session_state.carreras_cerradas_remate[carr_activa] = True
          st.session_state.estado_conteo_carrera[carr_activa] = "CERRADO"
          st.rerun()
        else:
          restantes = max(0, 10 - int(transcurridos))
          st.markdown(
              "<div class='timer-box'>⚠️ CIERRE EN:"
              f" <b>{restantes}s</b> ({carr_activa})</div>",
              unsafe_allow_html=True,
          )

    # Tabla de ejemplares
    datos_tabla = formatear_tabla_remate(st.session_state.remates[carr_activa])
    total_pote = sum(
        [
            info["monto"]
            for info in st.session_state.remates[carr_activa].values()
        ]
    )
    altura_tabla = min(max(180, (len(datos_tabla) + 1) * 44), 500)

    st.dataframe(
        pd.DataFrame(datos_tabla),
        use_container_width=True,
        hide_index=True,
        height=altura_tabla,
    )

    monto_casa = total_pote * (porcentaje_casa / 100)
    pote_neto = total_pote - monto_casa

    c_m1, c_m2 = st.columns(2)
    c_m1.metric(f"💰 Pote ({carr_activa})", formatear_bs(total_pote))
    extra = c_m2.number_input(
        "🎁 Extra",
        min_value=0.0,
        value=0.0,
        step=50.0,
        key=f"pote_inc_{carr_activa}",
    )
    st.metric(
        f"🏆 Premio Total ({carr_activa})", formatear_bs(pote_neto + extra)
    )

    # Registro de Puja
    with st.container(border=True):
      st.markdown(f"⚡ **Registro Rápido de Puja - {carr_activa}**")
      lista_cab = list(st.session_state.remates[carr_activa].keys())

      if lista_cab:
        k_sel_cab = f"cab_sel_{carr_activa}"
        if (
            k_sel_cab not in st.session_state
            or st.session_state[k_sel_cab] not in lista_cab
        ):
          st.session_state[k_sel_cab] = lista_cab[0]

        cols_cab = st.columns(4)
        for idx_c, cab_item in enumerate(lista_cab):
          num_p = cab_item.split(" - ")[0]
          with cols_cab[idx_c % 4]:
            if st.button(
                f"#{num_p}",
                key=f"btn_r_cab_{carr_activa}_{idx_c}",
                use_container_width=True,
            ):
              st.session_state[k_sel_cab] = cab_item

        cab_seleccionado = st.session_state[k_sel_cab]
        st.info(f"Ejemplar activo en {carr_activa}: **{cab_seleccionado}**")

        col_p1, col_p2 = st.columns(2)
        with col_p1:
          comprador_sel = st.selectbox(
              "👤 **Comprador**",
              st.session_state.lista_jugadores,
              key=f"sel_jug_{carr_activa}_{cab_seleccionado}",
          )
        with col_p2:
          puja_act = st.session_state.remates[carr_activa][cab_seleccionado][
              "monto"
          ]
          monto_puja = st.selectbox(
              "💰 **Monto de Puja**",
              obtener_siguientes_montos(puja_act),
              format_func=formatear_bs,
              key=f"sel_esc_{carr_activa}_{cab_seleccionado}",
          )

        if st.button(
            f"🔨 Confirmar Puja ({carr_activa})",
            key=f"btn_p_{carr_activa}",
            use_container_width=True,
            type="primary",
            disabled=carrera_cerrada,
        ):
          if monto_puja <= puja_act:
            st.error("El monto debe ser mayor a la puja actual.")
          else:
            st.session_state.remates[carr_activa][cab_seleccionado] = {
                "jugador": comprador_sel,
                "monto": monto_puja,
            }
            if estado_conteo == "CONTEO_10S":
              st.session_state.tiempo_inicio_conteo[carr_activa] = (
                  obtener_hora_venezuela_local()
              )
            st.success("✅ ¡Puja registrada!")
            st.rerun()

# 2. BANCO Y SELECCIÓN PARA CARRERAS
with tab2:
  st.markdown(
      "<div class='subasta-header'>✍️ Banco General y Asignación por"
      " Carrera</div>",
      unsafe_allow_html=True,
  )

  carr_banco_sel = st.selectbox(
      "Seleccionar Carrera a Configurar",
      lista_carreras_disponibles,
      key="sel_c_banco_asignar",
  )

  col_b1, col_b2 = st.columns(2)

  with col_b1:
    st.markdown("### 📋 Caballos Disponibles en el Banco")
    if not st.session_state.banco_general_extraido:
      st.info(
          "ℹ️ Sube un PDF en la pestaña 'PDF / Auto' para poblar el banco"
          " automáticamente, o agrega ejemplares abajo."
      )
    else:
      caballos_seleccionados_para_carrera = st.multiselect(
          "Selecciona los ejemplares que corren en esta carrera:",
          options=st.session_state.banco_general_extraido,
          key=f"ms_banco_carr_{carr_banco_sel}",
      )
      if st.button(
          "➕ Agregar seleccionados a la Carrera",
          type="primary",
          use_container_width=True,
      ):
        if carr_banco_sel not in st.session_state.remates:
          st.session_state.remates[carr_banco_sel] = {}
        if carr_banco_sel not in st.session_state.banco_caballos_por_carrera:
          st.session_state.banco_caballos_por_carrera[carr_banco_sel] = []

        for idx_nom, nom_c in enumerate(
            caballos_seleccionados_para_carrera, start=1
        ):
          nums = [
              int(re.match(r"^(\d+)", e).group(1))
              for e in st.session_state.banco_caballos_por_carrera[
                  carr_banco_sel
              ]
              if re.match(r"^(\d+)", e)
          ]
          sig_num = 1
          while sig_num in nums and sig_num <= 25:
            sig_num += 1
          formato = f"{sig_num} - {nom_c}"

          if (
              formato
              not in st.session_state.banco_caballos_por_carrera[carr_banco_sel]
          ):
            st.session_state.banco_caballos_por_carrera[carr_banco_sel].append(
                formato
            )
            st.session_state.banco_caballos_por_carrera[carr_banco_sel].sort(
                key=lambda x: int(re.match(r"^(\d+)", x).group(1))
            )

          if formato not in st.session_state.remates[carr_banco_sel]:
            st.session_state.remates[carr_banco_sel][formato] = {
                "jugador": "Sin Postor",
                "monto": 0.0,
            }
        st.success(f"✅ Ejemplares agregados a {carr_banco_sel}")
        st.rerun()

    with st.container(border=True):
      st.markdown("##### ➕ Agregar Manual al Banco General")
      nuevo_nom = st.text_input(
          "Nombre del Ejemplar",
          placeholder="Ej: Rey David",
          key="in_b_general",
      )
      if st.button("💾 Guardar en Banco General", use_container_width=True):
        nom_l = nuevo_nom.strip().title()
        if nom_l and nom_l not in st.session_state.banco_general_extraido:
          st.session_state.banco_general_extraido.append(nom_l)
          st.session_state.banco_general_extraido.sort()
          st.success("✅ Agregado al banco general")
          st.rerun()

  with col_b2:
    st.markdown(f"### 🏇 Inscritos Actuales en: {carr_banco_sel}")
    caballos_actuales = st.session_state.banco_caballos_por_carrera.get(
        carr_banco_sel, []
    )
    if not caballos_actuales:
      st.info("No hay caballos asignados a esta carrera.")
    else:
      for idx_b, ej_item in enumerate(caballos_actuales):
        col_ib1, col_ib2 = st.columns([5, 1])
        with col_ib1:
          st.text(ej_item)
        with col_ib2:
          if st.button(
              "🗑️",
              key=f"del_b_{carr_banco_sel}_{idx_b}",
              use_container_width=True,
          ):
            st.session_state.banco_caballos_por_carrera[carr_banco_sel].pop(
                idx_b
            )
            if (
                carr_banco_sel in st.session_state.remates
                and ej_item in st.session_state.remates[carr_banco_sel]
            ):
              del st.session_state.remates[carr_banco_sel][ej_item]
            st.rerun()

# 3. DUPLETAS
with tab3:
  st.markdown(
      "<div class='subasta-header'>🎟️ Módulo de Dupletas</div>",
      unsafe_allow_html=True,
  )
  if st.session_state.dupleta_bloqueada:
    st.error("🔒 **BLOQUEADO:** Emisión cerrada.")

  pote_dupletas = sum([t["monto"] for t in st.session_state.dupletas_tickets])
  st.metric("💰 Pote Acumulado Dupletas", formatear_bs(pote_dupletas))

  col_d1, col_d2 = st.columns(2)
  with col_d1:
    with st.container(border=True):
      jug_dup = st.selectbox(
          "👤 Jugador", st.session_state.lista_jugadores, key="jug_dup"
      )
      monto_dup = st.number_input(
          "💰 Monto (Bs.)", min_value=50.0, value=500.0, step=50.0, key="m_dup"
      )
      num_legs = st.radio(
          "Cantidad de Selecciones:", [2, 3, 4, 5, 6], horizontal=True
      )

  with col_d2:
    with st.container(border=True):
      selecciones = []
      carreras_usadas = set()
      valido = True
      for i in range(num_legs):
        c1, c2 = st.columns(2)
        with c1:
          carr_leg = st.selectbox(
              f"Carrera {i+1}",
              st.session_state.carreras_habilitadas_dupleta,
              key=f"c_dup_{i}",
          )
        with c2:
          cabs = list(st.session_state.remates.get(carr_leg, {}).keys())
          cab_leg = st.selectbox(
              f"Ejemplar {i+1}",
              cabs if cabs else ["Sin Caballos"],
              key=f"cb_dup_{i}",
          )

        if carr_leg in carreras_usadas:
          valido = False
        carreras_usadas.add(carr_leg)
        selecciones.append({"carrera": carr_leg, "ejemplar": cab_leg})

  if not st.session_state.dupleta_bloqueada:
    if st.button(
        "🚀 Emitir Ticket de Dupleta",
        use_container_width=True,
        type="primary",
    ):
      if not valido:
        st.error("⚠️ No puedes repetir carreras en el mismo ticket.")
      else:
        t_id = f"DUP-{len(st.session_state.dupletas_tickets) + 1:04d}"
        st.session_state.dupletas_tickets.append({
            "id": t_id,
            "jugador": jug_dup,
            "monto": monto_dup,
            "legs": selecciones,
            "estado": "Pendiente",
            "fecha": ahora_dt.strftime("%d/%m %I:%M %p"),
        })
        if jug_dup not in st.session_state.cuentas:
          st.session_state.cuentas[jug_dup] = {
              "Pujas": 0.0,
              "Premios": 0.0,
              "Abonos": 0.0,
          }
        st.session_state.cuentas[jug_dup]["Pujas"] += monto_dup
        st.success(f"✅ Ticket {t_id} emitido")
        st.rerun()

# 4. CIERRE Y LIQUIDACIÓN
with tab4:
  st.markdown(
      "<div class='subasta-header'>🏁 Cierre y Liquidación</div>",
      unsafe_allow_html=True,
  )
  carr_liq = st.selectbox(
      "Gestionar Carrera", lista_carreras_disponibles, key="c_liq"
  )

  with st.container(border=True):
    c_cerrada = st.session_state.carreras_cerradas_remate.get(carr_liq, False)
    if not c_cerrada:
      if st.button(
          "🔒 Cerrar Remate", key=f"btn_c_{carr_liq}", use_container_width=True
      ):
        st.session_state.carreras_cerradas_remate[carr_liq] = True
        st.session_state.estado_conteo_carrera[carr_liq] = "CERRADO"
        if not st.session_state.remates_cargados_en_cuentas.get(
            carr_liq, False
        ):
          for cab, info in st.session_state.remates[carr_liq].items():
            if info["jugador"] != "Sin Postor" and info["monto"] > 0:
              if info["jugador"] not in st.session_state.cuentas:
                st.session_state.cuentas[info["jugador"]] = {
                    "Pujas": 0.0,
                    "Premios": 0.0,
                    "Abonos": 0.0,
                }
              st.session_state.cuentas[info["jugador"]]["Pujas"] += info[
                  "monto"
              ]
          st.session_state.remates_cargados_en_cuentas[carr_liq] = True
        st.rerun()
    else:
      if st.button(
          "🔓 Reabrir Remate",
          key=f"btn_re_{carr_liq}",
          use_container_width=True,
      ):
        st.session_state.carreras_cerradas_remate[carr_liq] = False
        st.session_state.remates_cargados_en_cuentas[carr_liq] = False
        st.rerun()

    st.markdown("---")
    st.markdown("### 🏆 Liquidar Ganador")

    if carr_liq in st.session_state.historial_ganadores:
      st.success("✅ Carrera ya liquidada.")
    else:
      cabs_disponibles = list(st.session_state.remates.get(carr_liq, {}).keys())
      ganador_sel = st.selectbox(
          "Seleccionar Ejemplar Ganador Oficial",
          cabs_disponibles if cabs_disponibles else ["Sin Ejemplares"],
          key=f"ganador_{carr_liq}",
      )

      extra_liq = st.number_input(
          "🎁 Monto Extra / Bono para este Premio",
          min_value=0.0,
          value=0.0,
          step=50.0,
          key=f"extra_liq_{carr_liq}",
      )

      if st.button(
          f"🏁 Liquidar y Pagar {carr_liq}",
          type="primary",
          use_container_width=True,
      ):
        if not cabs_disponibles:
          st.error("No hay ejemplares registrados en esta carrera.")
        else:
          total_pote = sum([
              info["monto"]
              for info in st.session_state.remates[carr_liq].values()
          ])
          monto_casa_ret = total_pote * (porcentaje_casa / 100)
          pote_neto = total_pote - monto_casa_ret
          premio_total = pote_neto + extra_liq

          st.session_state.ganancia_casa += monto_casa_ret

          info_ganador = st.session_state.remates[carr_liq].get(
              ganador_sel, {"jugador": "Sin Postor", "monto": 0.0}
          )
          propietario_ganador = info_ganador["jugador"]

          if propietario_ganador != "Sin Postor":
            if propietario_ganador not in st.session_state.cuentas:
              st.session_state.cuentas[propietario_ganador] = {
                  "Pujas": 0.0,
                  "Premios": 0.0,
                  "Abonos": 0.0,
              }
            st.session_state.cuentas[propietario_ganador][
                "Premios"
            ] += premio_total

          st.session_state.historial_ganadores[carr_liq] = {
              "ganador": ganador_sel,
              "propietario": propietario_ganador,
              "premio": premio_total,
              "pote": total_pote,
          }

          st.session_state.historial_transacciones.insert(
              0,
              {
                  "fecha": ahora_dt.strftime("%d/%m/%Y %I:%M:%S %p"),
                  "descripcion": (
                      f"Liquidación {carr_liq}: Ganador {ganador_sel}"
                      f" ({propietario_ganador}) - Premio:"
                      f" {formatear_bs(premio_total)}"
                  ),
              },
          )

          st.success(
              f"✅ ¡Carrera {carr_liq} liquidada con éxito! Ganador:"
              f" **{ganador_sel}** (Jugador: **{propietario_ganador}**). Premio:"
              f" **{formatear_bs(premio_total)}**"
          )
          st.rerun()

# 5. CUENTAS
with tab5:
  st.markdown(
      "<div class='subasta-header'>📊 Estado de Cuentas y Balances</div>",
      unsafe_allow_html=True,
  )

  total_general_pujas = sum(
      [v["Pujas"] for v in st.session_state.cuentas.values()]
  )
  total_general_premios = sum(
      [v["Premios"] for v in st.session_state.cuentas.values()]
  )
  total_general_abonos = sum(
      [v["Abonos"] for v in st.session_state.cuentas.values()]
  )

  col_cg1, col_cg2, col_cg3, col_cg4 = st.columns(4)
  col_cg1.metric("💰 Total Pujas", formatear_bs(total_general_pujas))
  col_cg2.metric("🏆 Total Premios", formatear_bs(total_general_premios))
  col_cg3.metric("💳 Total Abonos", formatear_bs(total_general_abonos))
  col_cg4.metric(
      "🏠 Ganancia Casa", formatear_bs(st.session_state.ganancia_casa)
  )

  st.markdown("---")

  datos_cuentas = []
  for jug, vals in st.session_state.cuentas.items():
    neto = vals["Premios"] - vals["Pujas"] + vals["Abonos"]
    datos_cuentas.append({
        "Jugador": jug,
        "Pujas (- )": formatear_bs(vals["Pujas"]),
        "Premios (+ )": formatear_bs(vals["Premios"]),
        "Abonos (+ )": formatear_bs(vals["Abonos"]),
        "Balance Neto": formatear_bs(neto),
    })

  if datos_cuentas:
    st.dataframe(
        pd.DataFrame(datos_cuentas), use_container_width=True, hide_index=True
    )

  with st.expander("🛠️ Ajuste Manual de Cuentas", expanded=False):
    jug_ajuste = st.selectbox(
        "Seleccionar Jugador",
        st.session_state.lista_jugadores,
        key="jug_ajuste_sel",
    )
    tipo_ajuste = st.selectbox(
        "Tipo de Operación",
        ["Abono (Pago)", "Pérdida/Cargo Extra"],
        key="tipo_aj_sel",
    )
    monto_ajuste = st.number_input(
        "Monto (Bs.)", min_value=0.0, value=100.0, step=50.0, key="monto_aj_sel"
    )

    if st.button("💾 Aplicar Ajuste a Cuenta", use_container_width=True):
      if jug_ajuste not in st.session_state.cuentas:
        st.session_state.cuentas[jug_ajuste] = {
            "Pujas": 0.0,
            "Premios": 0.0,
            "Abonos": 0.0,
        }

      if tipo_ajuste == "Abono (Pago)":
        st.session_state.cuentas[jug_ajuste]["Abonos"] += monto_ajuste
        desc = (
            f"Abono registrado a {jug_ajuste}: {formatear_bs(monto_ajuste)}"
        )
      else:
        st.session_state.cuentas[jug_ajuste]["Pujas"] += monto_ajuste
        desc = (
            f"Cargo extra registrado a {jug_ajuste}:"
            f" {formatear_bs(monto_ajuste)}"
        )

      st.session_state.historial_transacciones.insert(
          0,
          {
              "fecha": ahora_dt.strftime("%d/%m/%Y %I:%M:%S %p"),
              "descripcion": desc,
          },
      )
      st.success("✅ Ajuste aplicado correctamente.")
      st.rerun()

# 6. HISTORIAL Y TRANSACCIONES
with tab6:
  st.markdown(
      "<div class='subasta-header'>🧾 Historial de Transacciones</div>",
      unsafe_allow_html=True,
  )
  if not st.session_state.historial_transacciones:
    st.info("No hay transacciones registradas aún.")
  else:
    for t in st.session_state.historial_transacciones:
      st.markdown(f"- **{t['fecha']}** : {t['descripcion']}")

# 7. PDF Y AUTOMATIZACIÓN
with tab7:
  st.markdown(
      "<div class='subasta-header'>📄 Carga de Programa y Extracción"
      " Estructurada</div>",
      unsafe_allow_html=True,
  )

  archivo_subido = st.file_uploader(
      "Subir Programa Oficial (PDF)", type=["pdf"]
  )

  if archivo_subido is not None:
    if extraer_datos_completos_pdf(archivo_subido):
      st.success("✅ PDF analizado correctamente con `pdfplumber`.")

      carreras = st.session_state.carreras_extraidas_pdf

      if carreras:
        st.markdown(f"### 📊 Se detectaron {len(carreras)} carreras:")

        for c in carreras:
          with st.expander(
              f"🏇 {c['carrera']} | ⏰ Hora: {c['hora']} | 📏 Distancia:"
              f" {c['distancia']}"
          ):
            if c["ejemplares"]:
              df_ej = pd.DataFrame(c["ejemplares"])
              st.dataframe(
                  df_ej[["puesto", "nombre"]],
                  use_container_width=True,
                  hide_index=True,
              )
            else:
              st.warning("No se detectaron ejemplares para esta carrera.")

        if st.button(
            "🚀 Cargar Carreras y Ejemplares al Sistema",
            type="primary",
            use_container_width=True,
        ):
          for c in carreras:
            c_nombre = c["carrera"]
            if c_nombre not in st.session_state.remates:
              st.session_state.remates[c_nombre] = {}
            if (
                c_nombre
                not in st.session_state.banco_caballos_por_carrera
            ):
              st.session_state.banco_caballos_por_carrera[c_nombre] = []

            for ej in c["ejemplares"]:
              fmt = ej["formato"]
              if (
                  fmt
                  not in st.session_state.banco_caballos_por_carrera[c_nombre]
              ):
                st.session_state.banco_caballos_por_carrera[c_nombre].append(
                    fmt
                )
              if fmt not in st.session_state.remates[c_nombre]:
                st.session_state.remates[c_nombre][fmt] = {
                    "jugador": "Sin Postor",
                    "monto": 0.0,
                }

          st.success("✅ ¡Carreras y ejemplares asignados correctamente!")
          st.rerun()
      else:
        st.error(
            "⚠️ No se pudieron extraer datos estructurados de carreras del PDF."
        )
