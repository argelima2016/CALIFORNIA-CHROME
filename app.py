import streamlit as st
import pandas as pd
import plotly.express as px
import io

# Configuración de la página web
st.set_page_config(page_title="Sistema de Subastas Hípicas PRO", layout="wide", page_icon="🏇")

# --- CARGA INICIAL DE JUGADORES ---
@st.cache_data
def cargar_jugadores_base():
    try:
        df_excel = pd.read_excel('TOTAL DE REMATES.xlsx', sheet_name='Hoja1')
        jugadores = df_excel.iloc[5:, 1].dropna().tolist()
        jugadores = [str(j).strip() for j in jugadores if str(j).strip() != '']
        return jugadores
    except Exception:
        return ["CASA", "SOMBI", "LUIS", "CARLOS", "RAMON", "ALDEA", "ANGEL", "ALFONSO", "MACANO", "MIGUEL", "TOCAYO", "EL GOCHO", "PAPIRO", "CHAYO", "ALEXIS"]

# --- INICIALIZACIÓN DEL ESTADO DE LA SESIÓN ---
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
# ⚙️ CONTROL LATERAL (RESPALDOS, CARGA Y RESET)
# ==========================================
st.sidebar.header("⚙️ Panel de Administración")

# 📥 CARGADORES DE ARCHIVOS (EXCEL / PDF)
st.sidebar.subheader("📅 Cargar Programa")
tipo_archivo = st.sidebar.radio("Tipo de archivo a cargar:", ["Excel (.xlsx / .csv)", "Gaceta Oficial (.pdf)"])

if tipo_archivo == "Excel (.xlsx / .csv)":
    archivo_programa = st.sidebar.file_uploader("Sube el Excel de carreras del día", type=["xlsx", "csv"])
    if archivo_programa is not None:
        try:
            df_prog = pd.read_csv(archivo_programa) if archivo_programa.name.endswith('.csv') else pd.read_excel(archivo_programa)
            if "Carrera" in df_prog.columns and "Caballo" in df_prog.columns:
                for carr in df_prog["Carrera"].unique():
                    carr_name = str(carr) if "Carrera" in str(carr) else f"Carrera {carr}"
                    if carr_name not in st.session_state.remates:
                        st.session_state.remates[carr_name] = {}
                    for cab in df_prog[df_prog["Carrera"] == carr]["Caballo"].tolist():
                        nombre_caballo = str(cab).strip()
                        if nombre_caballo not in st.session_state.remates[carr_name]:
                            st.session_state.remates[carr_name][nombre_caballo] = {"jugador": "Sin Postor", "monto": 0.0}
                st.sidebar.success("¡Programa organizado desde Excel!")
            else:
                st.sidebar.error("El archivo debe incluir las columnas 'Carrera' y 'Caballo'.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
else:
    archivo_pdf = st.sidebar.file_uploader("Sube la Gaceta Hípica en PDF", type=["pdf"])
    if archivo_pdf is not None:
        st.sidebar.info("Estructura PDF detectada. (Para programar la lectura exacta de tu gaceta favorita, contáctame para mapear sus textos).")

# SELECCIÓN DE CARRERA Y RETENCIÓN
st.sidebar.markdown("---")
lista_carreras_disponibles = list(st.session_state.remates.keys()) if st.session_state.remates else [f"Carrera {i}" for i in range(1, 15)]
carrera_actual = st.sidebar.selectbox("Seleccionar Carrera Activa", lista_carreras_disponibles)
porcentaje_casa = st.sidebar.slider("Retención de la Casa (%)", 0, 50, 30)

if carrera_actual not in st.session_state.remates or not st.session_state.remates[carrera_actual]:
    st.session_state.remates[carrera_actual] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}

# 💾 SISTEMA DE RESPALDO AUTOMÁTICO EN EXCEL
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Copias de Seguridad")

try:
    # Generar un archivo Excel en memoria con múltiples pestañas de respaldo laboral
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        # Pestaña 1: Balances corrientes
        balance_list = []
        for j, v in st.session_state.cuentas.items():
            balance_list.append({"Jugador": j, "Compras (Debe)": v['Pujas'], "Premios (Haber)": v['Premios'], "Abonos": v['Abonos'], "Saldo Final": v['Premios'] + v['Abonos'] - v['Pujas']})
        pd.DataFrame(balance_list).to_excel(writer, sheet_name='Balances_Jugadores', index=False)
        
        # Pestaña 2: Auditoría
        if st.session_state.historial_transacciones:
            pd.DataFrame(st.session_state.historial_transacciones).to_excel(writer, sheet_name='Historial_Movimientos', index=False)
            
    st.sidebar.download_button(
        label="📥 Descargar Respaldo Total (.xlsx)",
        data=buffer.getvalue(),
        file_name="RESPALDO_SUBASTAS_HIPICAS.xlsx",
        mime="application/vnd.ms-excel",
        use_container_width=True
    )
except Exception:
    st.sidebar.caption("Respaldo listo (esperando primeras transacciones...)")

# 🚨 REINICIO GENERAL DEL SISTEMA (RESET)
st.sidebar.markdown("---")
st.sidebar.subheader("🚨 Peligro / Fin de Jornada")
check_seguridad = st.sidebar.checkbox("Confirmar que deseo borrar todo")
if st.sidebar.button("Limpiar Todo para Próxima Semana", type="primary", disabled=not check_seguridad, use_container_width=True):
    st.session_state.remates = {}
    st.session_state.historial_ganadores = {}
    st.session_state.cuentas = {j: {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0} for j in st.session_state.lista_jugadores}
    st.session_state.ganancia_casa = 0.0
    st.session_state.historial_transacciones = []
    st.session_state.dupletas_tickets = []
    st.success("¡Todo el sistema ha vuelto a cero!")
    st.rerun()

# --- INTERFAZ CENTRAL ---
tab1, tab2, tab3, tab4 = st.tabs(["🏇 Subasta en Vivo", "🎟️ Módulo de Dupleta", "📊 Cuentas y Gráficos", "🧾 Auditoría General"])

# ==========================================
# PESTAÑA 1: SUBASTA EN VIVO
# ==========================================
with tab1:
    st.title(f"🎯 Subasta Activa: {carrera_actual}")
    col_pujas, col_tablero = st.columns([1, 2])

    with col_pujas:
        st.subheader("🔨 Registrar Puja")
        caballo = st.selectbox("Seleccione el Ejemplar", list(st.session_state.remates[carrera_actual].keys()), key=f"sel_caballo_{carrera_actual}")
        jugador = st.selectbox("Seleccione el Jugador", st.session_state.lista_jugadores, key=f"sel_jugador_{carrera_actual}")
        
        puja_actual = st.session_state.remates[carrera_actual][caballo]['monto']
        st.info(f"Puja actual para {caballo}: **{formatear_bs(puja_actual)}**")
        
        monto_sugerido = float(puja_actual + 50) if puja_actual > 0 else 50.0
        monto_puja = st.number_input("Monto de la Nueva Puja (Bs.)", min_value=50.0, value=monto_sugerido, step=50.0, key=f"num_monto_{carrera_actual}_{caballo}")
        
        if st.button("🔨 Confirmar Adjudicación", key=f"btn_pujar_{carrera_actual}", use_container_width=True):
            if monto_puja <= puja_actual:
                st.error(f"El monto debe ser mayor a la puja actual")
            else:
                st.session_state.remates[carrera_actual][caballo] = {"jugador": jugador, "monto": monto_puja}
                st.success(f"Adjudicado: {caballo} a {jugador}")
                st.rerun()

    with col_tablero:
        st.subheader("📋 Estado del Remate")
        datos_tabla = []
        total_pote = 0.0
        for cab, info in st.session_state.remates[carrera_actual].items():
            datos_tabla.append({"Ejemplar": cab, "Comprador": info['jugador'], "Monto": formatear_bs(info['monto'])})
            total_pote += info['monto']
        
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True)
        
        monto_casa = total_pote * (porcentaje_casa / 100)
        pote_ganador = total_pote - monto_casa
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Pote Total Acumulado", formatear_bs(total_pote))
        c2.metric("🏠 Comisión Casa", formatear_bs(monto_casa))
        c3.metric("🏆 Premio Neto a Pagar", formatear_bs(pote_ganador))

    st.markdown("---")
    st.subheader("🏁 Cierre y Liquidación de la Carrera")
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        caballo_ganador = st.selectbox("¿Qué ejemplar ganó la carrera?", list(st.session_state.remates[carrera_actual].keys()), key=f"sel_ganador_{carrera_actual}")
        
        # MEJORA DE SEGURIDAD: Doble check antes de alterar balances monetarios
        confirmar_cierre = st.checkbox("🔄 Confirmo que los datos ingresados son correctos")
        
        if st.button("🏆 Guardar Carrera y Cargar a Cuentas", key=f"btn_cerrar_{carrera_actual}", use_container_width=True, disabled=not confirmar_cierre):
            if carrera_actual in st.session_state.historial_ganadores:
                st.warning("Esta carrera ya fue liquidada.")
            else:
                for cab, info in st.session_state.remates[carrera_actual].items():
                    if info['jugador'] != "Sin Postor" and info['monto'] > 0:
                        st.session_state.cuentas[info['jugador']]['Pujas'] += info['monto']
                        st.session_state.historial_transacciones.append({"Carrera": carrera_actual, "Jugador": info['jugador'], "Tipo": "Cargo (Compra)", "Detalle": f"Adjudicación de {cab}", "Monto (Bs.)": -info['monto']})
                
                info_ganador = st.session_state.remates[carrera_actual][caballo_ganador]
                if info_ganador['jugador'] != "Sin Postor":
                    st.session_state.cuentas[info_ganador['jugador']]['Premios'] += pote_ganador
                    st.session_state.historial_transacciones.append({"Carrera": carrera_actual, "Jugador": info_ganador['jugador'], "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {caballo_ganador}", "Monto (Bs.)": pote_ganador})
                    st.session_state.ganancia_casa += monto_casa
                    st.session_state.historial_ganadores[carrera_actual] = {"Ganador": info_ganador['jugador'], "Caballo": caballo_ganador, "Premio": formatear_bs(pote_ganador)}
                    st.balloons()
                    st.rerun()
                else:
                    st.error("El caballo ganador no tuvo postor hípico.")

    with col_c2:
        st.write("🏁 **Historial de Carreras Cerradas:**")
        if st.session_state.historial_ganadores:
            st.dataframe(pd.DataFrame.from_dict(st.session_state.historial_ganadores, orient='index'), use_container_width=True)

# ==========================================
# PESTAÑA 2: MÓDULO DE DUPLETA
# ==========================================
with tab2:
    st.title("🎟️ Control de Dupletas Combinadas (Casa 30%)")
    col_dup1, col_dup2 = st.columns([1, 2])
    
    with col_dup1:
        st.subheader("📝 Registrar Ticket")
        j_dupleta = st.selectbox("Jugador comprador", st.session_state.lista_jugadores, key="sel_jugador_dupleta")
        c1_dup = st.text_input("Caballo Carrera A", placeholder="Ej: Ejemplar 4", key="c1_dup")
        c2_dup = st.text_input("Caballo Carrera B", placeholder="Ej: Ejemplar 1", key="c2_dup")
        monto_ticket = st.number_input("Costo Ticket (Bs.)", min_value=50.0, step=50.0)
        
        if st.button("📥 Vender Dupleta", use_container_width=True):
            if c1_dup and c2_dup:
                st.session_state.dupletas_tickets.append({"Jugador": j_dupleta, "Selección": f"{c1_dup.strip()} x {c2_dup.strip()}", "Carrera_A": c1_dup.strip(), "Carrera_B": c2_dup.strip(), "Monto": monto_ticket})
                st.success("Ticket registrado.")
                st.rerun()
            
    with col_dup2:
        st.subheader("📋 Tickets en Juego")
        if st.session_state.dupletas_tickets:
            df_dup = pd.DataFrame(st.session_state.dupletas_tickets)
            total_pote_dup = df_dup["Monto"].sum()
            
            df_dup_vis = df_dup.copy()
            df_dup_vis["Monto"] = df_dup_vis["Monto"].apply(formatear_bs)
            st.dataframe(df_dup_vis[["Jugador", "Selección", "Monto"]], use_container_width=True, hide_index=True)
            
            comision_casa_dup = total_pote_dup * 0.30
            premio_neto_dup = total_pote_dup - comision_casa_dup
            
            cd1, cd2, cd3 = st.columns(3)
            cd1.metric("💰 Pote Dupleta", formatear_bs(total_pote_dup))
            cd2.metric("🏠 Casa (30%)", formatear_bs(comision_casa_dup))
            cd3.metric("🏆 Premio Neto", formatear_bs(premio_neto_dup))
            
            st.markdown("---")
            st.subheader("🏁 Liquidar Dupleta")
            cl1, cl2 = st.columns(2)
            with cl1: g_a = st.text_input("Ganador A").strip()
            with cl2: g_b = st.text_input("Ganador B").strip()
            
            if st.button("🏆 Procesar Pagos Dupleta", use_container_width=True, type="primary"):
                ganadores = [tk["Jugador"] for tk in st.session_state.dupletas_tickets if tk["Carrera_A"].lower() == g_a.lower() and tk["Carrera_B"].lower() == g_b.lower()]
                
                for tk in st.session_state.dupletas_tickets:
                    st.session_state.cuentas[tk["Jugador"]]['Pujas'] += tk["Monto"]
                    st.session_state.historial_transacciones.append({"Carrera": "Dupleta", "Jugador": tk["Jugador"], "Tipo": "Cargo", "Detalle": f"Ticket {tk['Selección']}", "Monto (Bs.)": -tk["Monto"]})
                
                if ganadores:
                    premio_p_g = premio_neto_dup / len(ganadores)
                    for g in ganadores:
                        st.session_state.cuentas[g]['Premios'] += premio_p_g
                        st.session_state.historial_transacciones.append({"Carrera": "Dupleta", "Jugador": g, "Tipo": "Premio", "Detalle": f"Ganador {g_a}x{g_b}", "Monto (Bs.)": premio_p_g})
                    st.session_state.ganancia_casa += comision_casa_dup
                    st.balloons()
                else:
                    st.session_state.ganancia_casa += total_pote_dup
                    st.info("Pote acumulado por la casa.")
                st.session_state.dupletas_tickets = []
                st.rerun()
        else:
            st.caption("No hay dupletas en juego.")

# ==========================================
# PESTAÑA 3: CUENTAS POR JUGADOR Y GRÁFICOS
# ==========================================
with tab3:
    st.title("📊 Balance General de Cuentas Corrientes")
    
    # AGREGAR JUGADOR EN VIVO
    with st.expander("➕ Añadir Nuevo Jugador al Sistema"):
        col_add1, col_add2 = st.columns([2, 1])
        with col_add1:
            nuevo_jugador_nombre = st.text_input("Nombre del nuevo jugador:").strip().upper()
        with col_add2:
            if st.button("💾 Registrar Nuevo Jugador", use_container_width=True):
                if nuevo_jugador_nombre and nuevo_jugador_nombre not in st.session_state.lista_jugadores:
                    st.session_state.lista_jugadores.append(nuevo_jugador_nombre)
                    st.session_state.cuentas[nuevo_jugador_nombre] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                    st.success(f"¡{nuevo_jugador_nombre} agregado!")
                    st.rerun()

    # PROCESAMIENTO DE BALANCE
    balance_data = []
    for jug, valores in st.session_state.cuentas.items():
        saldo_final = valores['Premios'] + valores['Abonos'] - valores['Pujas']
        estado = "🔴 Debe" if saldo_final < 0 else ("🟢 A favor" if saldo_final > 0 else "⚪ Al día")
        balance_data.append({"Jugador": jug, "Total Compras (Debe)": formatear_bs(valores['Pujas']), "Total Premios (Haber)": formatear_bs(valores['Premios']), "Abonos": formatear_bs(valores['Abonos']), "Saldo Final": formatear_bs(saldo_final), "Estado": estado, "Monto_Numerico": saldo_final})
    
    df_balances = pd.DataFrame(balance_data)
    
    c_casa1, c_casa2 = st.columns(2)
    c_casa1.metric("🏪 Ganancia Neta de la CASA", formatear_bs(st.session_state.ganancia_casa))
    total_deuda_calle = abs(df_balances[df_balances['Monto_Numerico'] < 0]['Monto_Numerico'].sum())
    c_casa2.metric("💸 Total por Cobrar en la Calle", formatear_bs(total_deuda_calle))
    
    # MEJORA VISUAL: Reporte Gráfico de Saldos Críticos (Deudores)
    st.subheader("📊 Análisis de Saldos en la Calle")
    df_deudores = df_balances[df_balances['Monto_Numerico'] < 0].sort_values(by="Monto_Numerico")
    if not df_deudores.empty:
        fig = px.bar(df_deudores, x="Jugador", y="Monto_Numerico", title="Jugadores con Deudas Pendientes (Bs.)", labels={"Monto_Numerico": "Deuda (Bs.)"}, color_discrete_sequence=['#EF553B'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("🎉 ¡Todos los jugadores están al día o con saldo a favor!")

    st.markdown("---")
    st.dataframe(df_balances.drop(columns=["Monto_Numerico"]), use_container_width=True, hide_index=True)
    
    # MOVIMIENTOS DE CAJA
    st.markdown("---")
    st.subheader("💵 Registrar Pago Móvil / Efectivo / Caja")
    col_abono1, col_abono2 = st.columns(2)
    with col_abono1:
        jugador_paga = st.selectbox("¿Qué jugador realiza el movimiento?", st.session_state.lista_jugadores, key="sel_jugador_paga_admin")
        tipo_movimiento = st.radio("Tipo de movimiento", ["Jugador paga su deudá (Abono en Bs.)", "Casa paga saldo a favor (Retiro en Bs.)"])
        monto_movimiento = st.number_input("Monto del movimiento (Bs.)", min_value=10.0, step=50.0)
        if st.button("💾 Asentar en Caja", use_container_width=True):
            if "paga" in tipo_movimiento:
                st.session_state.cuentas[jugador_paga]['Abonos'] += monto_movimiento
                monto_t = monto_movimiento
                tipo_t = "Abono Manual"
            else:
                st.session_state.cuentas[jugador_paga]['Premios'] -= monto_movimiento
                monto_t = -monto_movimiento
                tipo_t = "Retiro Manual"
            st.session_state.historial_transacciones.append({"Carrera": "Administración", "Jugador": jugador_paga, "Tipo": tipo_t, "Detalle": "Movimiento de caja", "Monto (Bs.)": monto_t})
            st.success("Movimiento registrado con éxito.")
            st.rerun()

# ==========================================
# PESTAÑA 4: AUDITORÍA GENERAL
# ==========================================
with tab4:
    st.title("🧾 Auditoría General de Movimientos (Bs.)")
    if st.session_state.historial_transacciones:
        df_historial_t = pd.DataFrame(st.session_state.historial_transacciones)
        df_mostrar = df_historial_t.copy()
        df_mostrar["Monto (Bs.)"] = df_mostrar["Monto (Bs.)"].apply(formatear_bs)
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
    else:
        st.caption("No hay transacciones registradas.")
