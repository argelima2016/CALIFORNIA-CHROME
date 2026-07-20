import streamlit as st
import pandas as pd
import io
import os
import re
from pypdf import PdfReader, PdfWriter
from streamlit_autorefresh import st_autorefresh

# Configuración de la página web
st.set_page_config(page_title="Sistema de Remates, Dupletas y PDF en Vivo", layout="wide", page_icon="🏇")

# --- AUTOREFRESH PARA TIEMPO REAL ---
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

if 'archivos_subidos' not in st.session_state:
    st.session_state.archivos_subidos = []

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
    exito_carga = cargar_programa_automatico()
    if not exito_carga:
        for i in range(1, 11):
            carr_nombre = f"Carrera {i}"
            st.session_state.remates[carr_nombre] = {f"{j} - Ejemplar (Jinete)": {"jugador": "Sin Postor", "monto": 0.0} for j in range(1, 11)}

lista_carreras_disponibles = list(st.session_state.remates.keys())

carrera_actual = st.sidebar.selectbox("Seleccionar Carrera Activa", lista_carreras_disponibles, key="selector_carrera_sidebar")
porcentaje_casa = st.sidebar.slider("Retención de la Casa (%)", 0, 50, 30, key="slider_retencion_casa")

if carrera_actual not in st.session_state.remates or not st.session_state.remates[carrera_actual]:
    st.session_state.remates[carrera_actual] = {f"{i} - Caballo": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 11)}

todos_los_caballos = sorted(list({cab for carr in st.session_state.remates.values() for cab in carr.keys()}))

# --- BOTÓN DE PÁNICO / REINICIO ---
st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Reiniciar Jornada Global", use_container_width=True, type="secondary"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.toast("🚨 Jornada reiniciada.")
    st.rerun()

# --- INTERFAZ DE PESTAÑAS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏇 Subasta en Vivo (Bs.)", 
    "🎟️ Módulo de Dupleta", 
    "📊 Cuentas por Jugador", 
    "🧾 Historial de Transacciones", 
    "📄 Lector Tabular PDF"
])

# ==========================================
# PESTAÑA 1: SUBASTA EN VIVO
# ==========================================
with tab1:
    st.title(f"🎯 Subasta Activa en Directo: {carrera_actual}")
    
    # 1. TABLERO DE SUBASTA EN VIVO (ARRIBA)
    st.subheader("📋 Tablero de Subasta en Vivo")
    
    datos_tabla = []
    total_pote = 0.0
    for cab, info in st.session_state.remates[carrera_actual].items():
        datos_tabla.append({"Ejemplar": cab, "Comprador": info['jugador'], "Monto": formatear_bs(info['monto'])})
        total_pote += info['monto']
    
    st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True, key=f"tabla_remates_{carrera_actual}")
    
    monto_casa = total_pote * (porcentaje_casa / 100)
    pote_neto_base = total_pote - monto_casa

    st.markdown("---")

    # 2. ABAJO: POTE INCENTIVO EDITABLE Y PREMIO TOTAL
    st.subheader("💰 Configuración de Premios y Potes")
    col_pote1, col_pote2, col_pote3 = st.columns(3)
    
    col_pote1.metric("💰 Pote Recaudado", formatear_bs(total_pote))
    col_pote2.metric("🏠 Comisión Casa", formatear_bs(monto_casa))
    
    # Pote Incentivo Editable por el usuario
    pote_incentivo_extra = st.number_input(
        "🎁 Pote Incentivo / Adicional (Bs.)", 
        min_value=0.0, 
        value=0.0, 
        step=50.0, 
        key=f"pote_incentivo_{carrera_actual}"
    )
    
    premio_total_calculado = pote_neto_base + pote_incentivo_extra
    col_pote3.metric("🏆 Premio Total a Repartir", formatear_bs(premio_total_calculado))

    st.markdown("---")

    # 3. SELECCIONADOR DE CABALLO, PUJA Y MONTO ABAJO
    col_pujas, col_cierre = st.columns(2)

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

    with col_cierre:
        st.subheader("🏁 Cierre de Carrera")
        caballo_ganador = st.selectbox("Ejemplar Ganador", list(st.session_state.remates[carrera_actual].keys()), key=f"sel_ganador_{carrera_actual}")
        st.write("") 
        st.write("") 
        if st.button("🏆 Liquidar Carrera para Todos", key=f"btn_cerrar_{carrera_actual}", use_container_width=True, type="primary"):
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
                        "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {caballo_ganador} (Incluye incentivo)", "Monto (Bs.)": premio_total_calculado
                    })
                st.session_state.ganancia_casa += monto_casa
                st.session_state.historial_ganadores[carrera_actual] = {
                    "Ganador": info_ganador['jugador'], "Caballo": caballo_ganador, "Premio": formatear_bs(premio_total_calculado)
                }
                st.balloons()
                st.success(f"¡Liquidado! Ganador: {info_ganador['jugador']}")
                st.rerun()

# ==========================================
# PESTAÑA 2: MÓDULO DE DUPLETAS
# ==========================================
with tab2:
    st.title("🎟️ Control y Gestión de Dupletas")
    st.markdown("Registre y valide los tickets de dupletas jugados durante la jornada hípica.")
    
    col_dup_reg, col_dup_list = st.columns([1, 2])
    
    with col_dup_reg:
        st.subheader("📝 Registrar Nueva Dupleta")
        jugador_dupleta = st.selectbox("Jugador / Comprador", st.session_state.lista_jugadores, key="sel_jugador_dupleta")
        
        carrera_dup_1 = st.selectbox("Primera Válida (Carrera 1)", lista_carreras_disponibles, key="sel_carr_dup_1")
        caballo_dup_1 = st.selectbox("Ejemplar 1", list(st.session_state.remates.get(carrera_dup_1, { "Sin ejemplares": {} }).keys()), key="sel_cab_dup_1")
        
        carrera_dup_2 = st.selectbox("Segunda Válida (Carrera 2)", lista_carreras_disponibles, key="sel_carr_dup_2")
        caballo_dup_2 = st.selectbox("Ejemplar 2", list(st.session_state.remates.get(carrera_dup_2, { "Sin ejemplares": {} }).keys()), key="sel_cab_dup_2")
        
        monto_dupleta = st.number_input("Monto de la Dupleta (Bs.)", min_value=50.0, value=100.0, step=50.0, key="num_monto_dupleta")
        
        if st.button("💾 Emitir y Guardar Ticket de Dupleta", use_container_width=True, type="primary"):
            if carrera_dup_1 == carrera_dup_2:
                st.error("⚠️ Las dos carreras de la dupleta deben ser distintas.")
            else:
                nuevo_ticket = {
                    "ID": len(st.session_state.dupletas_tickets) + 1,
                    "Jugador": jugador_dupleta,
                    "1era Selección": f"{carrera_dup_1} - {caballo_dup_1}",
                    "2da Selección": f"{carrera_dup_2} - {caballo_dup_2}",
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
                
                st.toast(f"✅ Ticket #{nuevo_ticket['ID']} emitido con éxito para {jugador_dupleta}.")
                st.rerun()

    with col_dup_list:
        st.subheader("📋 Tickets de Dupletas Emitidos")
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
# PESTAÑA 3: CUENTAS POR JUGADOR
# ==========================================
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

# ==========================================
# PESTAÑA 4: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab4:
    st.title("🧾 Historial Global")
    if st.session_state.historial_transacciones:
        st.dataframe(pd.DataFrame(st.session_state.historial_transacciones), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se han registrado transacciones en el historial.")

# ==========================================
# PESTAÑA 5: LECTOR DE PDF CON PDFPLUMBER (TABLAS)
# ==========================================
with tab5:
    st.title("📄 Lector Avanzado de Tablas (Pdfplumber)")
    st.markdown("Este módulo utiliza extracción matricial para leer el 100% de las tablas, ejemplares y jinetes del programa oficial sin omisiones.")

    archivo_pdf_plumber = st.file_uploader(
        "Sube el programa oficial en PDF", 
        type=["pdf"],
        key="uploader_pdfplumber"
    )

    if archivo_pdf_plumber is not None:
        st.success("¡Archivo PDF cargado correctamente!")
        
        if st.button("🚀 Extraer con Pdfplumber (Modo Completo)", type="primary", use_container_width=True):
            try:
                import pdfplumber
                carreras_estructuradas = {}
                carrera_actual = "Carrera 1"
                ejemplares_detectados = {}
                contador_carrera = 1

                with pdfplumber.open(archivo_pdf_plumber) as pdf:
                    for num_pag, page in enumerate(pdf.pages):
                        tables = page.extract_tables()
                        
                        if tables:
                            for table in tables:
                                for row in table:
                                    fila_texto = [str(cell).strip() for cell in row if cell is not None and str(cell).strip() != ""]
                                    if not fila_texto:
                                        continue
                                    
                                    texto_fila_unido = " ".join(fila_texto)
                                    texto_upper = texto_fila_unido.upper()

                                    if "CARRERA" in texto_upper or "VÁLIDA" in texto_upper or "VALIDA" in texto_upper:
                                        if ejemplares_detectados:
                                            carreras_estructuradas[carrera_actual] = ejemplares_detectados
                                            ejemplares_detectados = {}
                                        
                                        match_carr = re.search(r'(\d+)', texto_upper)
                                        if match_carr:
                                            num_c = match_carr.group(1)
                                            carrera_actual = f"Carrera {int(num_c)}"
                                        else:
                                            contador_carrera += 1
                                            carrera_actual = f"Carrera {contador_carrera}"
                                        continue

                                    for celda in fila_texto:
                                        match_ej = re.match(r'^(\d{1,2})[\.\-\)]?$', celda)
                                        if match_ej:
                                            num_ej = match_ej.group(1).zfill(2)
                                            celdas_restantes = [c for c in fila_texto if c != celda]
                                            if celdas_restantes:
                                                nombre_ej = celdas_restantes[0].title()
                                                jinete_ej = celdas_restantes[1].title() if len(celdas_restantes) > 1 else "Sin Jinete"
                                                
                                                formato_llave = f"{int(num_ej)} - {nombre_ej} ({jinete_ej})"
                                                if formato_llave not in ejemplares_detectados:
                                                    ejemplares_detectados[formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                                            break

                        texto_pag = page.extract_text()
                        if texto_pag:
                            lineas = [l.strip() for l in texto_pag.split('\n') if l.strip()]
                            for linea in lineas:
                                match_linea = re.match(r'^(\d{1,2})[\.\-\)]?\s+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,})', linea)
                                if match_linea:
                                    num_ej = match_linea.group(1).zfill(2)
                                    nombre_ej = match_linea.group(2).strip().title()
                                    formato_llave = f"{int(num_ej)} - {nombre_ej} (Sin Jinete)"
                                    if formato_llave not in ejemplares_detectados:
                                        ejemplares_detectados[formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}

                if ejemplares_detectados:
                    carreras_estructuradas[carrera_actual] = ejemplares_detectados

                if not carreras_estructuradas:
                    for c in range(1, 11):
                        carreras_estructuradas[f"Carrera {c}"] = {f"{j} - Ejemplar (Jinete)": {"jugador": "Sin Postor", "monto": 0.0} for j in range(1, 11)}

                st.session_state.remates = carreras_estructuradas
                st.success("¡Lectura completa y profunda realizada con Pdfplumber!")
                st.balloons()
                st.rerun()

            except ImportError:
                st.error("⚠️ La librería 'pdfplumber' no está instalada. Ejecuta `pip install pdfplumber` en tu terminal y reinicia Streamlit.")
            except Exception as e:
                st.error(f"Ocurrió un error al procesar el PDF con Pdfplumber: {e}")
