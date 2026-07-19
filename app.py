import streamlit as st
import pandas as pd

# Configuración de la página web
st.set_page_config(page_title="Sistema de Remates en Bolívares", layout="wide", page_icon="🏇")

# --- CARGA AUTOMÁTICA DESDE TU EXCEL ---
@st.cache_data
def cargar_jugadores():
    try:
        # Lee directamente tu archivo adjunto
        df_excel = pd.read_excel('TOTAL DE REMATES.xlsx', sheet_name='Hoja1')
        jugadores = df_excel.iloc[5:, 1].dropna().tolist()
        jugadores = [str(j).strip() for j in jugadores if str(j).strip() != '']
        return jugadores
    except Exception:
        # Respaldo exacto de tu lista si el archivo no está en la misma carpeta
        return ["CASA", "SOMBI", "LUIS", "CARLOS", "RAMON", "ALDEA", "ANGEL", "ALFONSO", "MACANO", "MIGUEL", "TOCAYO", "EL GOCHO", "PAPIRO", "CHAYO", "ALEXIS"]

lista_jugadores = cargar_jugadores()

# --- ESTADO DE LA SESIÓN ---
if 'remates' not in st.session_state:
    st.session_state.remates = {}
if 'historial_ganadores' not in st.session_state:
    st.session_state.historial_ganadores = {}
if 'cuentas' not in st.session_state:
    st.session_state.cuentas = {j: {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0} for j in lista_jugadores}
if 'ganancia_casa' not in st.session_state:
    st.session_state.ganancia_casa = 0.0
if 'historial_transacciones' not in st.session_state:
    st.session_state.historial_transacciones = []

# --- FORMATO DE MONEDA VENEZOLANA (Bs.) ---
def formatear_bs(monto):
    return f"Bs. {monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- CONTROL LATERAL ---
st.sidebar.header("⚙️ Control de Carrera")
carrera_actual = st.sidebar.selectbox("Seleccionar Carrera", [f"Carrera {i}" for i in range(1, 15)], key="selector_carrera_sidebar")
porcentaje_casa = st.sidebar.slider("Retención de la Casa (%)", 0, 20, 10, key="slider_retencion_casa")

if carrera_actual not in st.session_state.remates:
    st.session_state.remates[carrera_actual] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}

# --- INTERFAZ ---
tab1, tab2, tab3 = st.tabs(["🏇 Subasta en Vivo (Bs.)", "📊 Cuentas por Jugador", "🧾 Historial de Transacciones"])

# ==========================================
# PESTAÑA 1: SUBASTA EN VIVO
# ==========================================
with tab1:
    st.title(f"🎯 Subasta Activa: {carrera_actual}")
    col_pujas, col_tablero = st.columns([1, 2])

    with col_pujas:
        st.subheader("🔨 Registrar Puja")
        
        # Eliminamos st.form para evitar el bug de removeChild en Streamlit Cloud
        caballo = st.selectbox("Seleccione el Ejemplar", list(st.session_state.remates[carrera_actual].keys()), key=f"sel_caballo_{carrera_actual}")
        jugador = st.selectbox("Seleccione el Jugador", lista_jugadores, key=f"sel_jugador_{carrera_actual}")
        
        puja_actual = st.session_state.remates[carrera_actual][caballo]['monto']
        st.info(f"Puja actual para {caballo}: **{formatear_bs(puja_actual)}**")
        
        # El monto mínimo sugerido calcula automáticamente +50 si ya hay puja previa
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
# PESTAÑA 2: CUENTAS POR JUGADOR
# ==========================================
with tab2:
    st.title("📊 Balance General de Cuentas Corrientes (Bs.)")
    balance_data = []
    for jug, valores in st.session_state.cuentas.items():
        saldo_final = valores['Premios'] + valores['Abonos'] - valores['Pujas']
        estado = "🔴 Debe dinero" if saldo_final < 0 else ("🟢 Saldo a favor" if saldo_final > 0 else "⚪ Al día")
        balance_data.append({
            "Jugador": jug, "Total Compras (Debe)": formatear_bs(valores['Pujas']),
            "Total Premios (Haber)": formatear_bs(valores['Premios']), "Abonos Realizados": formatear_bs(valores['Abonos']),
            "Saldo Final": formatear_bs(saldo_final), "Estado": estado, "_saldo_numerico": saldo_final
        })
    df_balances = pd.DataFrame(balance_data)
    
    c_casa1, c_casa2 = st.columns(2)
    c_casa1.metric("🏪 Ganancia Neta de la CASA", formatear_bs(st.session_state.ganancia_casa))
    total_deuda_calle = abs(df_balances[df_balances['_saldo_numerico'] < 0]['_saldo_numerico'].sum())
    c_casa2.metric("💸 Total por Cobrar en la Calle", formatear_bs(total_deuda_calle))
    
    st.markdown("---")
    st.dataframe(df_balances.drop(columns=["_saldo_numerico"]), use_container_width=True, hide_index=True, key="tabla_balances_general")
    
    st.markdown("---")
    st.subheader("💵 Registrar Pago Móvil / Efectivo / Transferencia")
    col_abono1, col_abono2 = st.columns(2)
    with col_abono1:
        jugador_paga = st.selectbox("¿Qué jugador realiza el movimiento?", lista_jugadores, key="sel_jugador_paga_admin")
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
# PESTAÑA 3: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab3:
    st.title("🧾 Auditoría General de Movimientos (Bs.)")
    if st.session_state.historial_transacciones:
        df_historial_t = pd.DataFrame(st.session_state.historial_transacciones)
        df_mostrar = df_historial_t.copy()
        df_mostrar["Monto (Bs.)"] = df_mostrar["Monto (Bs.)"].apply(formatear_bs)
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True, key="tabla_auditoria_final")
    else:
        st.caption("No hay transacciones registradas.")
