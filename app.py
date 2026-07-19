# Puedes guardar este código completo como app.py y correrlo con: streamlit run app.py
import streamlit as st
import pandas as pd
import io

# Configuración de la página web
st.set_page_config(page_title="Sistema de Remates y Dupletas Pro v2", layout="wide", page_icon="🏇")

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
# ==========================================
# ⚙️ CONTROL LATERAL Y CARGA AUTOMÁTICA
# ==========================================
st.sidebar.header("⚙️ Control de Carrera")

# --- NUEVA FUNCIÓN AUTOMÁTICA ---
def cargar_programa_automatico():
    import os
    # Nombre fijo del archivo en la carpeta del proyecto
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

# Ejecutar la carga automática silenciosa al iniciar si no hay remates creados
if not st.session_state.remates:
    if cargar_programa_automatico():
        st.sidebar.success("✅ Programa cargado automáticamente desde 'programa_del_dia.xlsx'")
    else:
        st.sidebar.info("💡 Coloca un archivo 'programa_del_dia.xlsx' en la carpeta para carga automática.")

# Mantenemos el file_uploader por si un día quieres cambiar el programa a mitad de jornada manualmente
archivo_programa = st.sidebar.file_uploader("O sube otro Excel manualmente", type=["xlsx", "csv"])
# ... (deja el resto del código del file_uploader tal como estaba)
lista_carreras_disponibles = list(st.session_state.remates.keys())
if not lista_carreras_disponibles:
    lista_carreras_disponibles = [f"Carrera {i}" for i in range(1, 15)]

carrera_actual = st.sidebar.selectbox("Seleccionar Carrera Activa", lista_carreras_disponibles, key="selector_carrera_sidebar")
porcentaje_casa = st.sidebar.slider("Retención de la Casa (%)", 0, 50, 30, key="slider_retencion_casa")

if carrera_actual not in st.session_state.remates or not st.session_state.remates[carrera_actual]:
    st.session_state.remates[carrera_actual] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}

# Generar lista unificada de caballos para el módulo de dupletas blindadas
todos_los_caballos = sorted(list({cab for carr in st.session_state.remates.values() for cab in carr.keys()}))
if not todos_los_caballos:
    todos_los_caballos = [f"Caballo {i}" for i in range(1, 15)]

# --- BOTÓN DE PÁNICO / REINICIO DE JORNADA ---
st.sidebar.markdown("---")
st.sidebar.subheader("🚨 Peligro: Zona de Reinicio")
if st.sidebar.button("🗑️ Reiniciar Jornada (Borrar Todo)", use_container_width=True, type="secondary"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.toast("🚨 Jornada reiniciada por completo. Cargando sistema limpio...")
    st.rerun()

# --- INTERFAZ DE PESTAÑAS ---
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
        
        # --- MEJORA: BOTONES INCREMENTALES RÁPIDOS ---
        st.write("⚡ Incrementos Rápidos:")
        col_inc1, col_inc2, col_inc3 = st.columns(3)
        incremento_elegido = 0.0
        
        if col_inc1.button("➕ Bs. 50", use_container_width=True, key=f"inc_50_{carrera_actual}"):
            incremento_elegido = 50.0
        if col_inc2.button("➕ Bs. 100", use_container_width=True, key=f"inc_100_{carrera_actual}"):
            incremento_elegido = 100.0
        if col_inc3.button("➕ Bs. 500", use_container_width=True, key=f"inc_500_{carrera_actual}"):
            incremento_elegido = 500.0

        if puja_actual == 0:
            monto_propuesto = 50.0 + incremento_elegido
        else:
            monto_propuesto = float(puja_actual + (incremento_elegido if incremento_elegido > 0 else 50.0))
            
        monto_puja = st.number_input("Monto de la Nueva Puja (Bs.)", min_value=50.0, value=monto_propuesto, step=50.0, key=f"num_monto_{carrera_actual}_{caballo}_val")
        
        if st.button("🔨 Confirmar Adjudicación", key=f"btn_pujar_{carrera_actual}", use_container_width=True, type="primary"):
            if monto_puja <= puja_actual:
                st.error(f"El monto debe ser estrictamente mayor a la puja actual ({formatear_bs(puja_actual)})")
            else:
                st.session_state.remates[carrera_actual][caballo] = {"jugador": jugador, "monto": monto_puja}
                st.toast(f" Adjudicado: {caballo} ➡️ {jugador} por {formatear_bs(monto_puja)}")
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
                st.warning("Esta carrera ya fue liquidada previamente.")
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
                    st.success(f"¡Cuentas liquidadas! {info_ganador['jugador']} ganó {formatear_bs(pote_ganador)}")
                    st.rerun()
                else:
                    st.error("El caballo ganador no tuvo postores asignados. No se puede liquidar el premio.")

    with col_c2:
        st.write("🏁 **Historial de Carreras Cerradas:**")
        if st.session_state.historial_ganadores:
            st.dataframe(pd.DataFrame.from_dict(st.session_state.historial_ganadores, orient='index'), use_container_width=True, key="tabla_historial_ganadores")

# ==========================================
# PESTAÑA 2: MÓDULO DE DUPLETA (BLINDADO)
# ==========================================
with tab2:
    st.title("🎟️ Control de Dupletas Combinadas")
    col_dup1, col_dup2 = st.columns([1, 2])
    
    with col_dup1:
        st.subheader("📝 Registrar Ticket de Dupleta")
        j_dupleta = st.selectbox("Jugador que compra la Dupleta", st.session_state.lista_jugadores, key="sel_jugador_dupleta")
        
        # --- MEJORA: SELECCIÓN BLINDADA CON SELECTBOX EN VEZ DE TEXT_INPUT ---
        c1_dup = st.selectbox("Ejemplar - Carrera A", todos_los_caballos, key="c1_dup_select")
        c2_dup = st.selectbox("Ejemplar - Carrera B", todos_los_caballos, key="c2_dup_select")
        monto_ticket = st.number_input("Costo del Ticket (Bs.)", min_value=50.0, step=50.0, key="monto_ticket_dupleta")
        
        if st.button("📥 Vender / Registrar Dupleta", use_container_width=True):
            st.session_state.cuentas[j_dupleta]['Pujas'] += monto_ticket
            st.session_state.historial_transacciones.append({
                "Carrera": "Dupleta (Venta)", "Jugador": j_dupleta, 
                "Tipo": "Cargo (Compra)", "Detalle": f"Ticket Dupleta {c1_dup} x {c2_dup}", "Monto (Bs.)": -monto_ticket
            })
            
            st.session_state.dupletas_tickets.append({
                "Jugador": j_dupleta,
                "Selección": f"{c1_dup} x {c2_dup}",
                "Carrera_A": c1_dup,
                "Carrera_B": c2_dup,
                "Monto": monto_ticket
            })
            st.success(f"Ticket cobrado y registrado para {j_dupleta}: {c1_dup} x {c2_dup}")
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
            
            col_liq1, col_liq2 = st.columns(2)
            with col_liq1:
                ganador_a = st.selectbox("Caballo Ganador Carrera A", todos_los_caballos, key="ganador_a_dup_sel")
            with col_liq2:
                ganador_b = st.selectbox("Caballo Ganador Carrera B", todos_los_caballos, key="ganador_b_dup_sel")
                
            if st.button("🏆 Escrutar y Pagar Dupleta", use_container_width=True, type="primary"):
                ganadores_dupleta = []
                for tk in st.session_state.dupletas_tickets:
                    if tk["Carrera_A"] == ganador_a and tk["Carrera_B"] == ganador_b:
                        ganadores_dupleta.append(tk["Jugador"])
                
                if ganadores_dupleta:
                    premio_por_ganador = premio_neto_dup / len(ganadores_dupleta)
                    for g in ganadores_dupleta:
                        st.session_state.cuentas[g]['Premios'] += premio_por_ganador
                        st.session_state.historial_transacciones.append({
                            "Carrera": "Dupleta (Premio)", "Jugador": g, 
                            "Tipo": "Abono (Premio)", "Detalle": f"Ganador Dupleta {ganador_a} x {ganador_b}", "Monto (Bs.)": premio_por_ganador
                        })
                    st.session_state.ganancia_casa += comision_casa_dup
                    st.balloons()
                    st.success(f"¡Dupleta Liquidada! Ganadores: {', '.join(ganadores_dupleta)}. Reciben {formatear_bs(premio_por_ganador)}")
                else:
                    st.session_state.ganancia_casa += total_pote_dup
                    st.info("Ningún jugador acertó la combinación exacta. El pote pasa íntegro a la Casa.")
                
                st.session_state.dupletas_tickets = []
                st.rerun()
        else:
            st.caption("No hay tickets de dupleta activos en la jornada actual.")

# ==========================================
# PESTAÑA 3: CUENTAS Y TABLERO SEMÁFORO
# ==========================================
with tab3:
    st.title("📊 Balance General de Cuentas Corrientes (Bs.)")
    
    st.subheader("➕ Añadir Nuevo Jugador al Sistema")
    col_add1, col_add2 = st.columns([2, 1])
    with col_add1:
        # MEJORA: Normalización limpia de nombres
        nuevo_jugador_nombre = st.text_input("Nombre del nuevo jugador:", key="txt_nuevo_jugador").strip().upper()
        nuevo_jugador_nombre = " ".join(nuevo_jugador_nombre.split())
    with col_add2:
        if st.button("💾 Registrar Jugador", use_container_width=True):
            if nuevo_jugador_nombre == "":
                st.error("El nombre no puede estar vacío.")
            elif nuevo_jugador_nombre in st.session_state.lista_jugadores:
                st.warning(f"El jugador '{nuevo_jugador_nombre}' ya se encuentra registrado.")
            else:
                st.session_state.lista_jugadores.append(nuevo_jugador_nombre)
                st.session_state.lista_jugadores.sort()
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
    
    # Preparar DF visual formateado sin romper la matemática subyacente
    # Preparar DF visual formateado
    df_balances_visual = df_balances.copy()
    for col in ["Total Compras (Debe)", "Total Premios (Haber)", "Abonos Realizados", "Saldo Final"]:
        df_balances_visual[col] = df_balances_visual[col].apply(formatear_bs)
        
    # --- CORRECCIÓN CRÍTICA: Buscar el saldo numérico real usando el índice de la fila ---
    def colorear_filas_saldos(row):
        # row.name nos da el número de fila actual. 
        # Buscamos el saldo real numérico en el DataFrame original usando esa misma fila.
        saldo_real = df_balances.loc[row.name, "Saldo Final"]
        
        if saldo_real < 0:
            return ['background-color: rgba(217, 83, 79, 0.15)'] * len(row)  # Rojo suave
        elif saldo_real > 0:
            return ['background-color: rgba(92, 184, 92, 0.15)'] * len(row)   # Verde suave
        return [''] * len(row)

    # Es obligatorio pasar axis=1 para que evalúe por filas completas
    df_estilado = df_balances_visual.style.apply(colorear_filas_saldos, axis=1)
    
    # Renderizar la tabla con el estilo corregido
    st.dataframe(df_estilado, use_container_width=True, hide_index=True, key="tabla_balances_general_v2")
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
            file_name="CIERRE_DE_REMATES_PRO.xlsx",
            mime="application/vnd.ms-excel"
        )
    except Exception:
        st.caption("El botón de exportación se activará automáticamente al generar transacciones.")

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
            st.success(f"Movimiento de {formatear_bs(monto_movimiento)} asentado de manera conforme.")
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
        
        # --- MEJORA: COLUMNAS DE AUDITORÍA DINÁMICAS USANDO ST.DATAFRAME COLUMN_CONFIG ---
        st.dataframe(
            df_mostrar,
            use_container_width=True,
            hide_index=True,
            key="tabla_auditoria_final_v2",
            column_config={
                "Tipo": st.column_config.SelectColumn(
                    "Tipo de Operación",
                    options=["Cargo (Compra)", "Abono (Premio)", "Abono Manual (Caja)", "Retiro Manual (Caja)"]
                )
            }
        )
    else:
        st.caption("No se registran transacciones ni movimientos auditables en la jornada actual.")
