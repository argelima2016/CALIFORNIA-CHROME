import streamlit as st
import pandas as pd
import io
import os
from pypdf import PdfWriter

# Instala esto si no lo tienes: pip install streamlit-autorefresh pypdf
from streamlit_autorefresh import st_autorefresh

# Configuración de la página web
st.set_page_config(page_title="Sistema de Remates, Dupletas y PDF en Vivo", layout="wide", page_icon="🏇")

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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏇 Subasta en Vivo (Bs.)", 
    "🎟️ Módulo de Dupleta", 
    "📊 Cuentas por Jugador", 
    "🧾 Historial de Transacciones", 
    "📄 Unir Programas PDF"
])

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
# PESTAÑA 5: UNIR PROGRAMAS PDF
# ==========================================
with tab5:
    st.title("📄 Unificador de Programas PDF de Carreras")
    st.markdown("Sube los archivos PDF correspondientes a los programas o boletines de cada carrera y únelos en un solo documento listo para imprimir o compartir.")

    col_upload, col_preview = st.columns([1, 1])

    with col_upload:
        st.subheader("📤 Cargar Archivos PDF")
        
        uploaded_files = st.file_uploader(
            "Selecciona o arrastra los archivos PDF en orden (Carrera 1, Carrera 2, etc.)", 
            type=["pdf"], 
            accept_multiple_files=True,
            key="uploader_pdfs_carreras"
        )
        
        if uploaded_files:
            st.session_state.archivos_subidos = uploaded_files
            st.success(f"¡Se han cargado {len(uploaded_files)} archivos PDF correctamente!")

    with col_preview:
        st.subheader("📋 Orden de los Archivos")
        if st.session_state.archivos_subidos:
            st.info("Verifica el orden en el que se fusionarán los documentos:")
            lista_nombres = [f"{idx + 1}. {file.name}" for idx, file in enumerate(st.session_state.archivos_subidos)]
            for nombre in lista_nombres:
                st.markdown(f"- {nombre}")
        else:
            st.warning("Aún no has cargado ningún archivo PDF.")

    st.markdown("---")

    if st.session_state.archivos_subidos:
        st.subheader("⚙️ Generar Documento Consolidado")
        
        nombre_salida = st.text_input("Nombre del archivo PDF resultante:", value="Programa_Completo_Carreras.pdf")
        
        # Initialize the writer
merger = PdfWriter()

# List of your PDF files to merge
pdf_files = ["file1.pdf", "file2.pdf"]

for pdf in pdf_files:
    merger.append(pdf)

# Write the combined PDF to an output file or stream
with open("merged-output.pdf", "wb") as output_file:
    merger.write(output_file)
merger.close()
# Re-type this section cleanly
if st.button("Unificar PDFs"):
        st.success("¡Los archivos PDF se han unificado con éxito!")
if st.button("Unificar PDFs"):
        st.success("¡Los archivos PDF se han unificado con éxito!")
        st.download_button(
            label="Descargar PDF unificado",
            data=output_pdf,
            file_name="archivo_unificado.pdf",
            mime="application/pdf"
        )
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"Ocurrió un error al intentar fusionar los archivos PDF: {e}")
            
