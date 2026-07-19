import streamlit as st
import pandas as pd
import io

# Configuración de la página web
st.set_page_config(page_title="Sistema de Remates y Dupletas Pro", layout="wide", page_icon="🏇")

# --- CARGA INICIAL DE JUGADORES ---
@st.cache_data
def cargar_jugadores_base():
    try:
        df_excel = pd.read_excel('TOTAL DE REMATES.xlsx', sheet_name='Hoja1')
        jugadores = df_excel.iloc[5:, 1].dropna().tolist()
        jugadores = [str(j).strip().upper() for j in jugadores if str(j).strip() != '']
        return list(set(jugadores))
    except Exception:
        return ["CASA", "SOMBI", "LUIS", "CARLOS", "RAMON", "ALDEA", "ANGEL", "ALFONSO", "MACANO", "MIGUEL", "TOCAYO", "EL GOCHO", "PAPIRO", "CHAYO", "ALEXIS"]

# --- ESTADO DE LA SESIÓN (PERSISTENCIA DE DATOS) ---
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
st.sidebar.header("⚙️ Control de Carrera")

st.sidebar.subheader("📅 Cargar Programa del Día")
archivo_programa = st.sidebar.file_uploader("Sube el Excel de las carreras del día", type=["xlsx", "csv"])

if archivo_programa is not None:
    try:
        if archivo_programa.name.endswith('.csv'):
            df_prog = pd.read_csv(archivo_programa)
        else:
            df_prog = pd.read_excel(archivo_programa)
            
        if "Carrera" in df_prog.columns and "Caballo" in df_prog.columns:
            carreras_detectadas = df_prog["Carrera"].unique()
            
            for carr in carreras_detectadas:
                carr_name = str(carr) if "Carrera" in str(carr) else f"Carrera {carr}"
                if carr_name not in st.session_state.remates:
                    st.session_state.remates[carr_name] = {}
                
                caballos_carrera = df_prog[df_prog["Carrera"] == carr]["Caballo"].tolist()
                for cab in caballos_carrera:
                    nombre_caballo = str(cab).strip()
                    if nombre_caballo not in st.session_state.remates[carr_name]:
                        st.session_state.remates[carr_name][nombre_caballo] = {"jugador": "Sin Postor", "monto": 0.0}
            st.sidebar.success("¡Programa cargado con éxito!")
        else:
            st.sidebar.error("El Excel debe tener 'Carrera' y 'Caballo'.")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

lista_carreras_disponibles = list(st.session_state.remates.keys())
if not lista_carreras_disponibles:
    lista_carreras_disponibles = [f"Carrera {i}" for i in range(1, 15)]

carrera_actual = st.sidebar.selectbox("Seleccionar Carrera Activa", lista_carreras_disponibles, key="selector_carrera_sidebar")
porcentaje_casa = st.sidebar.slider("Retención de la Casa (%)", 0, 50, 30, key="slider_retencion_casa")

if carrera_actual not in st.session_state.remates or not st.session_state.remates[carrera_actual]:
    st.session_state.remates[carrera_actual] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}

# --- CREACIÓN DE INTERFAZ DE PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["🏇 Subasta en Vivo (Bs.)", "🎟️ Módulo de Dupleta", "📊 Cuentas por Jugador", "🧾 Historial de Transacciones"])

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
                st.error(f"El monto debe ser mayor a la puja actual ({formatear_bs(puja_actual)})")
            else:
                st.session_state.remates[carrera_actual][caballo] = {"jugador": jugador, "monto": monto_puja}
                st.success(f"Adjudicado: {caballo} a {jugador} por {formatear_bs(monto_puja)}")
                st.rerun()

    with col_tablero:
        st.subheader("📋 Estado del Remate")
        datos_tabla = []
        total_pote = 0.0
        for cab, info in st.session_state.remates[carrera_actual].items():
            datos_tabla.append({"Ejemplar": cab, "Comprador": info['jugador'], "Monto": formatear_bs(info['monto'])})
            total_pote += info['monto']
        
        st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True, key=f"tabla_remates_{carrera_actual}")
        
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
        if st.button("🏆 Guardar Carrera y Cargar a Cuentas", key=f"btn_cerrar_{carrera_actual}", use_container_width=True):
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
                    st.success(f"¡Cuentas actualizadas! {info_ganador['jugador']} ganó {formatear_bs(pote_ganador)}")
                    st.rerun()
                else:
                    st.error("El caballo ganador no tuvo postor.")

    with col_c2:
        st.write("🏁 **Historial de Carreras Cerradas:**")
        if st.session_state.historial_ganadores:
            st.dataframe(pd.DataFrame.from_dict(st.session_state.historial_ganadores, orient='index'), use_container_width=True, key="tabla_historial_ganadores")

# ==========================================
# PESTAÑA 2: MÓDULO DE DUPLETA
# ==========================================
with tab2:
    st.title("🎟️ Control de Dupletas Combinadas")
    
    with st.expander("👤 Panel Rápido de Jugadores (Ver / Agregar)"):
        st.write(f"**Jugadores activos en el sistema ({len(st.session_state.lista_jugadores)}):**")
        st.caption(", ".join(st.session_state.lista_jugadores))
        
        col_rj1, col_rj2 = st.columns([2, 1])
        with col_rj1:
            nuevo_jug_dup = st.text_input("Nombre del nuevo jugador (Acceso rápido):", key="txt_jugador_rapido_dup").strip().upper()
        with col_rj2:
            if st.button("➕ Agregar Jugador", key="btn_agregar_rapido_dup", use_container_width=True):
                if nuevo_jug_dup == "":
                    st.error("El nombre no puede estar vacío.")
                elif nuevo_jug_dup in st.session_state.lista_jugadores:
                    st.warning("El jugador ya existe.")
                else:
                    st.session_state.lista_jugadores.append(nuevo_jug_dup)
                    st.session_state.cuentas[nuevo_jug_dup] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                    st.success(f"¡{nuevo_jug_dup} agregado!")
                    st.rerun()
                    
    st.markdown("---")
    col_dup1, col_dup2 = st.columns([1, 2])
    
    with col_dup1:
        st.subheader("📝 Registrar Ticket de Dupleta")
        j_dupleta = st.selectbox("Jugador que compra la Dupleta", st.session_state.lista_jugadores, key="sel_jugador_dupleta_nueva")
        
        carreras_dup_disponibles = list(st.session_state.remates.keys())
        if not carreras_dup_disponibles:
            carreras_dup_disponibles = [f"Carrera {i}" for i in range(1, 15)]
            
        carrera_a_select = st.selectbox("Seleccione Carrera A", carreras_dup_disponibles, key="carrera_a_dup_sel")
        carrera_b_select = st.selectbox("Seleccione Carrera B", carreras_dup_disponibles, key="carrera_b_dup_sel")
        
        if carrera_a_select not in st.session_state.remates or not st.session_state.remates[carrera_a_select]:
            st.session_state.remates[carrera_a_select] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}
        if carrera_b_select not in st.session_state.remates or not st.session_state.remates[carrera_b_select]:
            st.session_state.remates[carrera_b_select] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}
            
        caballos_a_disp = list(st.session_state.remates[carrera_a_select].keys())
        caballos_b_disp = list(st.session_state.remates[carrera_b_select].keys())
        
        c1_dup = st.selectbox(f"Ejemplar de la {carrera_a_select}", caballos_a_disp, key="c1_dup_select")
        c2_dup = st.selectbox(f"Ejemplar de la {carrera_b_select}", caballos_b_disp, key="c2_dup_select")
        
        monto_ticket = st.number_input("Costo del Ticket (Bs.)", min_value=50.0, step=50.0, key="monto_ticket_dupleta_nuevo")
        
        if st.button("📥 Vender / Registrar Dupleta", key="btn_registrar_dupleta_final", use_container_width=True):
            st.session_state.cuentas[j_dupleta]['Pujas'] += monto_ticket
            st.session_state.historial_transacciones.append({
                "Carrera": f"Dupleta ({carrera_a_select}x{carrera_b_select})", 
                "Jugador": j_dupleta, 
                "Tipo": "Cargo (Compra)", 
                "Detalle": f"Ticket Dupleta: {c1_dup} x {c2_dup}", 
                "Monto (Bs.)": -monto_ticket
            })
            
            st.session_state.dupletas_tickets.append({
                "Jugador": j_dupleta,
                "Selección": f"[{carrera_a_select}] {c1_dup} x [{carrera_b_select}] {c2_dup}",
                "Carrera_A_Nombre": carrera_a_select,
                "Carrera_B_Nombre": carrera_b_select,
                "Carrera_A": c1_dup,
                "Carrera_B": c2_dup,
                "Monto": monto_ticket
            })
            st.success(f"Ticket registrado a {j_dupleta}: {c1_dup} x {c2_dup}")
            st.rerun()
            
    with col_dup2:
        st.subheader("📋 Tickets en Juego")
        if st.session_state.dupletas_tickets:
            df_dup = pd.DataFrame(st.session_state.dupletas_tickets)
            total_pote_dup = df_dup["Monto"].sum()
            
            df_dup_visual = df_dup.copy()
            df_dup_visual["Monto"] = df_dup_visual["Monto"].apply(formatear_bs)
            st.dataframe(df_dup_visual[["Jugador", "Selección", "Monto"]], use_container_width=True, hide_index=True)
            
            comision_casa_dup = total_pote_dup * 0.30
            premio_neto_dup = total_pote_dup - comision_casa_dup
            
            cd1, cd2, cd3 = st.columns(3)
            cd1.metric("💰 Pote Dupleta", formatear_bs(total_pote_dup))
            cd2.metric("🏠 Casa (30%)", formatear_bs(comision_casa_dup))
            cd3.metric("🏆 Premio a Pagar", formatear_bs(premio_neto_dup))
            
            st.markdown("---")
            st.subheader("🏁 Liquidar Ganadores de la Dupleta")
            
            carreras_a_en_juego = list(df_dup["Carrera_A_Nombre"].unique())
            carreras_b_en_juego = list(df_dup["Carrera_B_Nombre"].unique())
            
            col_liq1, col_liq2 = st.columns(2)
            with col_liq1:
                carrera_a_liq = st.selectbox("Escrutar Carrera A:", carreras_a_en_juego, key="carrera_a_liq_sel")
                caballos_a_liq_disp = list(st.session_state.remates[carrera_a_liq].keys()) if carrera_a_liq in st.session_state.remates else []
                ganador_a = st.selectbox("Caballo Ganador A", caballos_a_liq_disp, key="ganador_a_dup_select")
            with col_liq2:
                carrera_b_liq = st.selectbox("Escrutar Carrera B:", carreras_b_en_juego, key="carrera_b_liq_sel")
                caballos_b_liq_disp = list(st.session_state.remates[carrera_b_liq].keys()) if carrera_b_liq in st.session_state.remates else []
                ganador_b = st.selectbox("Caballo Ganador B", caballos_b_liq_disp, key="ganador_b_dup_select")
                
            if st.button("🏆 Escrutar y Pagar Dupleta", key="btn_escrutar_dupleta_final", use_container_width=True, type="primary"):
                ganadores_dupleta = []
                
                for tk in st.session_state.dupletas_tickets:
                    condicion_carrera = (tk["Carrera_A_Nombre"] == carrera_a_liq) and (tk["Carrera_B_Nombre"] == carrera_b_liq)
                    condicion_caballo = (tk["Carrera_A"].lower() == ganador_a.lower()) and (tk["Carrera_B"].lower() == ganador_b.lower())
                    
                    if condicion_carrera and condicion_caballo:
                        ganadores_dupleta.append(tk["Jugador"])
                
                if ganadores_dupleta:
                    premio_por_ganador = premio_neto_dup / len(ganadores_dupleta)
                    for g in ganadores_dupleta:
                        st.session_state.cuentas[g]['Premios'] += premio_por_ganador
                        st.session_state.historial_transacciones.append({
                            "Carrera": f"Premio Dupleta ({carrera_a_liq}x{carrera_b_liq})", 
                            "Jugador": g, 
                            "Tipo": "Abono (Premio)", 
                            "Detalle": f"Ganador Dupleta: {ganador_a} x {ganador_b}", 
                            "Monto (Bs.)": premio_por_ganador
                        })
                    st.session_state.ganancia_casa += comision_casa_dup
                    st.balloons()
                    st.success(f"¡Dupleta Liquidada! Ganadores: {', '.join(ganadores_dupleta)}. Cada uno recibe {formatear_bs(premio_por_ganador)}")
                else:
                    st.session_state.ganancia_casa += total_pote_dup
                    st.info(f"Ningún jugador acertó la combinación {ganador_a} x {ganador_b}. Dinero pasa a la Casa.")
                
                st.session_state.dupletas_tickets = []
                st.rerun()
        else:
            st.caption("No hay tickets de dupleta registrados.")

# ==========================================
# PESTAÑA 3: CUENTAS POR JUGADOR
# ==========================================
with tab3:
    st.title("📊 Balance General de Cuentas Corrientes (Bs.)")
    
    st.subheader("➕ Añadir Nuevo Jugador al Sistema")
    col_add1, col_add2 = st.columns([2, 1])
    with col_add1:
        nuevo_jugador_nombre = st.text_input("Nombre del nuevo jugador:", key="txt_nuevo_jugador").strip().upper()
    with col_add2:
        if st.button("💾 Registrar Jugador", use_container_width=True):
            if nuevo_jugador_nombre == "":
                st.error("El nombre no puede estar vacío.")
            elif nuevo_jugador_nombre in st.session_state.lista_jugadores:
                st.warning(f"El jugador '{nuevo_jugador_nombre}' ya existe.")
            else:
                st.session_state.lista_jugadores.append(nuevo_jugador_nombre)
                st.session_state.cuentas[nuevo_jugador_nombre] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                st.success(f"¡Jugador '{nuevo_jugador_nombre}' agregado exitosamente!")
                st.rerun()
                
    st.markdown("---")
    
    balance_data = []
    for jug in st.session_state.lista_jugadores:
        if jug not in st.session_state.cuentas:
            st.session_state.cuentas[jug] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
        valores = st.session_state.cuentas[jug]
        saldo_final = valores['Premios'] + valores['Abonos'] - valores['Pujas']
        estado = "🔴 Debe dinero" if saldo_final < 0 else ("🟢 Saldo a favor" if saldo_final > 0 else "⚪ Al día")
        balance_data.append({
            "Jugador": jug, "Total Compras (Debe)": valores['Pujas'],
            "Total Premios (Haber)": valores['Premios'], "Abonos Realizados": valores['Abonos'],
            "Saldo Final": saldo_final, "Estado": estado
        })
    
    df_balances = pd.DataFrame(balance_data)
    
    c_casa1, c_casa2 = st.columns(2)
    c_casa1.metric("🏪 Ganancia Neta de la CASA", formatear_bs(st.session_state.ganancia_casa))
    total_deuda_calle = abs(df_balances[df_balances['Saldo Final'] < 0]['Saldo Final'].sum())
    c_casa2.metric("💸 Total por Cobrar en la Calle", formatear_bs(total_deuda_calle))
    
    st.markdown("---")
    
    df_balances_visual = df_balances.copy()
    for col in ["Total Compras (Debe)", "Total Premios (Haber)", "Abonos Realizados", "Saldo Final"]:
        df_balances_visual[col] = df_balances_visual[col].apply(formatear_bs)
        
    st.dataframe(df_balances_visual, use_container_width=True, hide_index=True, key="tabla_balances_general")
    
    st.markdown("### 📥 Descargar Cierre Financiero")
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_balances.to_excel(writer, sheet_name='Saldos_Jugadores', index=False)
            if st.session_state.historial_transacciones:
                pd.DataFrame(st.session_state.historial_transacciones).to_excel(writer, sheet_name='Auditoria_Detallada', index=False)
        st.download_button(
            label="📊 Descargar Reporte de Cuentas en Excel",
            data=buffer.getvalue(),
            file_name="CIERRE_DE_REMATES.xlsx",
            mime="application/vnd.ms-excel"
        )
    except Exception as e:
        st.caption("El botón de exportación se activará al generar transacciones.")

    st.markdown("---")
    st.subheader("💵 Registrar Pago Móvil / Efectivo / Transferencia")
    col_abono1, col_abono2 = st.columns(2)
    with col_abono1:
        jugador_paga = st.selectbox("¿Qué jugador realiza el movimiento?", st.session_state.lista_jugadores, key="sel_jugador_paga_admin")
        tipo_movimiento = st.radio("Tipo de movimiento", ["Jugador paga su deuda (Abono en Bs.)", "Casa paga saldo a favor al jugador (Retiro en Bs.)"], key="radio_tipo_movimiento")
        monto_movimiento = st.number_input("Monto del movimiento (Bs.)", min_value=10.0, step=50.0, key="num_monto_movimiento_admin")
        if st.button("💾 Registrar Movimiento de Caja", key="btn_registrar_movimiento_caja", use_container_width=True):
            if "paga su deuda" in tipo_movimiento:
                st.session_state.cuentas[jugador_paga]['Abonos'] += monto_movimiento
                monto_registro = monto_movimiento
                tipo_t = "Abono Manual (Caja)"
            else:
                st.session_state.cuentas[jugador_paga]['Premios'] -= monto_movimiento
                monto_registro = -monto_movimiento
                tipo_t = "Retiro Manual (Caja)"
            st.session_state.historial_transacciones.append({
                "Carrera": "Administración", "Jugador": jugador_paga, "Tipo": tipo_t, "Detalle": "Movimiento de caja liquidado", "Monto (Bs.)": monto_registro
            })
            st.success(f"Movimiento de {formatear_bs(monto_movimiento)} asentado.")
            st.rerun()

# ==========================================
# PESTAÑA 4: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab4:
    st.title("🧾 Auditoría General de Movimientos (Bs.)")
    if st.session_state.historial_transacciones:
        df_historial_t = pd.DataFrame(st.session_state.historial_transacciones)
        df_mostrar = df_historial_t.copy()
        df_mostrar["Monto (Bs.)"] = df_mostrar["Monto (Bs.)"].apply(formatear_bs)
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True, key="tabla_auditoria_final")
    else:
        st.caption("No hay transacciones registradas.")
