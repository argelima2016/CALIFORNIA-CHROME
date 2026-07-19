# ==========================================
# PESTAÑA 2: MÓDULO DE DUPLETA (OPTIMIZADO)
# ==========================================
with tab2:
    st.title("🎟️ Control de Dupletas Combinadas")
    
    # --- NUEVO PANEL ACCESIBLE: GESTIÓN RÁPIDA DE JUGADORES ---
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
        
        # Opciones dinámicas de carreras basadas en el programa cargado
        carreras_dup_disponibles = list(st.session_state.remates.keys())
        if not carreras_dup_disponibles:
            carreras_dup_disponibles = [f"Carrera {i}" for i in range(1, 15)]
            
        # 1. Seleccionar Carreras que componen la Dupleta
        carrera_a_select = st.selectbox("Seleccione Carrera A", carreras_dup_disponibles, key="carrera_a_dup_sel")
        carrera_b_select = st.selectbox("Seleccione Carrera B", carreras_dup_disponibles, key="carrera_b_dup_sel")
        
        # Inicializar carreras por defecto en sesión si el usuario no ha subido programa y se eligen aquí
        if carrera_a_select not in st.session_state.remates or not st.session_state.remates[carrera_a_select]:
            st.session_state.remates[carrera_a_select] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}
        if carrera_b_select not in st.session_state.remates or not st.session_state.remates[carrera_b_select]:
            st.session_state.remates[carrera_b_select] = {f"Caballo {i}": {"jugador": "Sin Postor", "monto": 0.0} for i in range(1, 13)}
            
        # 2. Selección de los caballos reales mapeados de esas carreras
        caballos_a_disp = list(st.session_state.remates[carrera_a_select].keys())
        caballos_b_disp = list(st.session_state.remates[carrera_b_select].keys())
        
        c1_dup = st.selectbox(f"Ejemplar de la {carrera_a_select}", caballos_a_disp, key="c1_dup_select")
        c2_dup = st.selectbox(f"Ejemplar de la {carrera_b_select}", caballos_b_disp, key="c2_dup_select")
        
        monto_ticket = st.number_input("Costo del Ticket (Bs.)", min_value=50.0, step=50.0, key="monto_ticket_dupleta_nuevo")
        
        if st.button("📥 Vender / Registrar Dupleta", key="btn_registrar_dupleta_final", use_container_width=True):
            # Cargo inmediato a la cuenta del jugador al comprar
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
            
            # Muestra las combinaciones de carreras que realmente se han vendido para saber qué escrutar
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
                
                # Filtrado estricto por carrera y por nombre de caballo
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
                    st.info(f"Ningún jugador acertó la combinación {ganador_a} x {ganador_b} para estas carreras. El dinero pasa a la Casa.")
                
                # Se limpian los tickets de la dupleta jugada
                st.session_state.dupletas_tickets = []
                st.rerun()
        else:
            st.caption("No hay tickets de dupleta registrados.")
