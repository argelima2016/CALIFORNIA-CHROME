if st.button("📥 Inscribir desde Banco", use_container_width=True):
                            nombre_limpio = str(ejemplar_banco).strip().title()
                            if len(st.session_state.remates[carrera_actual]) >= 17:
                                st.error("⚠️ Límite de 17 ejemplares alcanzado.")
                            else:
                                elementos_actuales = list(st.session_state.remates[carrera_actual].keys())
                                numeros_usados = []
                                for elem in elementos_actuales:
                                    match_num = re.match(r'^(\d+)', elem)
                                    if match_num:
                                        numeros_usados.append(int(match_num.group(1)))
                                
                                siguiente_num = 1
                                while siguiente_num in numeros_usados and siguiente_num <= 17:
                                    siguiente_num += 1
                                
                                if siguiente_num <= 17:
                                    formato_llave = f"{siguiente_num} - {nombre_limpio}"
                                    if formato_llave not in st.session_state.remates[carrera_actual]:
                                        st.session_state.remates[carrera_actual][formato_llave] = {"jugador": "Sin Postor", "monto": 0.0}
                                        st.success(f"✅ Añadido: {formato_llave}")
                                        st.rerun()
                                    else:
                                        st.warning("El ejemplar ya está inscrito en esta carrera.")
        else:
            st.info("El banco de nombres está vacío. Escribe uno nuevo arriba para agregarlo al banco.")

    with col_man_2:
        st.subheader("🗑️ Eliminar Ejemplar Individual")
        carr_actual_ejemplares = list(st.session_state.remates[carrera_actual].keys())
        if carr_actual_ejemplares:
            cab_a_borrar = st.selectbox("Seleccionar Ejemplar a Remover", carr_actual_ejemplares, key="sel_borrar_caballo")
            if st.button("🗑️ Eliminar Ejemplar Seleccionado", use_container_width=True, type="secondary"):
                del st.session_state.remates[carrera_actual][cab_a_borrar]
                st.success(f"🗑️ Ejemplar {cab_a_borrar} removido de {carrera_actual}.")
                st.rerun()
        else:
            st.info("No hay ejemplares registrados en esta carrera.")

# ==========================================
# PESTAÑA 3: MÓDULO DE DUPLETA PRO
# ==========================================
with tab3:
    st.markdown("<div class='subasta-header'>🎟️ Módulo de Dupleta Pro (Sistema de Apuestas Combinadas)</div>", unsafe_allow_html=True)
    st.markdown("Arma tu ticket combinando ganadores de las carreras habilitadas. Las dupletas multiplican los factores de pago.")

    if st.session_state.dupleta_bloqueada:
        st.error("🔴 **Módulo de Dupletas BLOQUEADO temporalmente por la administración.** No se pueden registrar nuevos tickets en este momento.")

    col_dup_1, col_dup_2 = st.columns([1, 1], gap="large")

    with col_dup_1:
        with st.container(border=True):
            st.subheader("📝 Registrar Nuevo Ticket de Dupleta")
            
            jugador_dupleta = st.selectbox("Jugador / Postor (Dupleta)", st.session_state.lista_jugadores, key="sel_jugador_dupleta")
            
            carreras_disp_dup = st.session_state.carreras_habilitadas_dupleta
            if not carreras_disp_dup:
                st.warning("⚠️ No hay carreras habilitadas para dupleta por el administrador.")
            else:
                seleccion_carreras_ticket = st.multiselect(
                    "Seleccionar Carreras (Mínimo 2)", 
                    options=carreras_disp_dup,
                    key="multiselect_carreras_dupleta"
                )
                
                detalles_selecciones = {}
                Valido_ticket = True
                
                if len(seleccion_carreras_ticket) >= 2:
                    st.markdown("---")
                    st.markdown("🎯 **Selecciona el ejemplar para cada carrera escogida:**")
                    for c_sel in seleccion_carreras_ticket:
                        caballos_en_carrera = list(st.session_state.remates.get(c_sel, {}).keys())
                        if caballos_en_carrera:
                            cab_elegido = st.selectbox(f"Ejemplar para {c_sel}", caballos_en_carrera, key=f"dup_cab_{c_sel}")
                            detalles_selecciones[c_sel] = cab_elegido
                        else:
                            st.error(f"La carrera {c_sel} no tiene ejemplares cargados.")
                            Valido_ticket = False
                else:
                    st.info("💡 Selecciona al menos 2 carreras para activar las selecciones.")
                    Valido_ticket = False

                monto_apuesta_dupleta = st.number_input(
                    "Monto de la Apuesta (Bs.)", 
                    min_value=10.0, 
                    value=100.0, 
                    step=50.0, 
                    key="input_monto_dupleta"
                )

                if st.session_state.dupleta_bloqueada:
                    st.button("🎟️ Emitir y Registrar Ticket", key="btn_emitir_dupleta_bloqueado", use_container_width=True, type="primary", disabled=True)
                else:
                    if st.button("🎟️ Emitir y Registrar Ticket", key="btn_emitir_dupleta", use_container_width=True, type="primary"):
                        if not Valido_ticket or len(seleccion_carreras_ticket) < 2:
                            st.error("⚠️ Debes seleccionar al menos 2 carreras y configurar sus ejemplares.")
                        else:
                            id_ticket = f"DUP-{int(datetime.now().timestamp())}"
                            nuevo_ticket = {
                                "ID": id_ticket,
                                "Jugador": jugador_dupleta,
                                "Carreras": seleccion_carreras_ticket,
                                "Detalles": detalles_selecciones,
                                "Monto": monto_apuesta_dupleta,
                                "Estado": "En Curso",
                                "Premio": 0.0
                            }
                            st.session_state.dupletas_tickets.append(nuevo_ticket)
                            
                            if jugador_dupleta not in st.session_state.cuentas:
                                st.session_state.cuentas[jugador_dupleta] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                            st.session_state.cuentas[jugador_dupleta]['Pujas'] += monto_apuesta_dupleta
                            
                            st.session_state.historial_transacciones.append({
                                "Carrera": "Múltiple", "Jugador": jugador_dupleta,
                                "Tipo": "Cargo (Dupleta)", "Detalle": f"Ticket {id_ticket} ({len(seleccion_carreras_ticket)} pasos)", "Monto (Bs.)": -monto_apuesta_dupleta
                            })
                            
                            st.success(f"✅ ¡Ticket de Dupleta **{id_ticket}** emitido exitosamente!")
                            st.rerun()

    with col_dup_2:
        st.subheader("📋 Tickets de Dupleta Emitidos")
        if not st.session_state.dupletas_tickets:
            st.info("No hay tickets de dupleta registrados en esta jornada.")
        else:
            for idx_t, ticket in enumerate(st.session_state.dupletas_tickets):
                with st.expander(f"Ticket: {ticket['ID']} | Jugador: {ticket['Jugador']} | Estado: {ticket['Estado']}"):
                    st.markdown(f"**Monto Jugado:** `{formatear_bs(ticket['Monto'])}`")
                    st.markdown("**Selecciones:**")
                    for carr_t, cab_t in ticket['Detalles'].items():
                        ganador_real = st.session_state.historial_ganadores.get(carr_t, {}).get("Caballo")
                        if ganador_real:
                            if ganador_real == cab_t:
                                st.markdown(f"- ✅ `{carr_t}`: **{cab_t}** (ACERTADO)")
                            else:
                                st.markdown(f"- ❌ `{carr_t}`: **{cab_t}** (Fallado - Ganó: {ganador_real})")
                        else:
                            st.markdown(f"- ⏳ `{carr_t}`: **{cab_t}** (Pendiente)")
                    
                    if st.button(f"🗑️ Anular Ticket {ticket['ID']}", key=f"btn_anular_dup_{idx_t}"):
                        if ticket['Jugador'] in st.session_state.cuentas:
                            st.session_state.cuentas[ticket['Jugador']]['Pujas'] -= ticket['Monto']
                        st.session_state.dupletas_tickets.pop(idx_t)
                        st.warning(f"Ticket {ticket['ID']} anulado y descontado de la cuenta.")
                        st.rerun()

# ==========================================
# PESTAÑA 4: CIERRE Y LIQUIDACIÓN
# ==========================================
with tab4:
    st.markdown("<div class='subasta-header'>🏁 Cierre y Liquidación de Carreras</div>", unsafe_allow_html=True)
    st.markdown("Panel de control global para liquidar los premios de cada carrera de forma definitiva.")

    for carr_item in lista_carreras_disponibles:
        with st.container(border=True):
            col_l1, col_l2, col_l3 = st.columns([1.5, 2, 1.5])
            
            with col_l1:
                st.markdown(f"### 🏇 {carr_item}")
                cerrada_estado = st.session_state.carreras_cerradas_remate.get(carr_item, False)
                liquidada_estado = carr_item in st.session_state.historial_ganadores
                
                if liquidada_estado:
                    st.markdown("<p style='color: #00d2d3; font-weight: bold;'>🟢 Liquidada</p>", unsafe_allow_html=True)
                elif cerrada_estado:
                    st.markdown("<p style='color: #f1e05a; font-weight: bold;'>🔒 Cerrada (Pendiente liquidar)</p>", unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color: #ff4757; font-weight: bold;'>🔴 Abierta</p>", unsafe_allow_html=True)

            with col_l2:
                total_pote_carr = sum([info['monto'] for info in st.session_state.remates.get(carr_item, {}).values()])
                monto_casa_carr = total_pote_carr * (porcentaje_casa / 100)
                pote_neto_carr = total_pote_carr - monto_casa_carr
                incentivo_carr = st.session_state.get(f"pote_incentivo_{carr_item}", 0.0)
                premio_final_carr = pote_neto_carr + incentivo_carr
                
                st.markdown(f"**Pote Total:** `{formatear_bs(total_pote_carr)}`")
                st.markdown(f"**Retención Casa ({porcentaje_casa}%):** `{formatear_bs(monto_casa_carr)}`")
                st.markdown(f"**Premio a Repartir:** `{formatear_bs(premio_final_carr)}`")

            with col_l3:
                if liquidada_estado:
                    info_g = st.session_state.historial_ganadores[carr_item]
                    st.success(f"Ganador: {info_g['Ganador']}\n({info_g['Caballo']})")
                else:
                    caballos_carr_opc = list(st.session_state.remates.get(carr_item, {}).keys())
                    if caballos_carr_opc:
                        ganador_sel_tab4 = st.selectbox(f"Ejemplar Ganador", caballos_carr_opc, key=f"sel_ganador_tab4_{carr_item}")
                        if st.button(f"🏆 Liquidar {carr_item}", key=f"btn_liq_tab4_{carr_item}", type="primary", use_container_width=True):
                            if not st.session_state.remates_cargados_en_cuentas.get(carr_item, False):
                                for cab, info in st.session_state.remates[carr_item].items():
                                    if info['jugador'] != "Sin Postor" and info['monto'] > 0:
                                        if info['jugador'] not in st.session_state.cuentas:
                                            st.session_state.cuentas[info['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                                        st.session_state.cuentas[info['jugador']]['Pujas'] += info['monto']
                                        st.session_state.historial_transacciones.append({
                                            "Carrera": carr_item, "Jugador": info['jugador'], 
                                            "Tipo": "Cargo (Compra)", "Detalle": f"Adjudicación de {cab}", "Monto (Bs.)": -info['monto']
                                        })
                                st.session_state.remates_cargados_en_cuentas[carr_item] = True
                            
                            info_ganador_t4 = st.session_state.remates[carr_item][ganador_sel_tab4]
                            if info_ganador_t4['jugador'] != "Sin Postor":
                                if info_ganador_t4['jugador'] not in st.session_state.cuentas:
                                    st.session_state.cuentas[info_ganador_t4['jugador']] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                                st.session_state.cuentas[info_ganador_t4['jugador']]['Premios'] += premio_final_carr
                                st.session_state.historial_transacciones.append({
                                    "Carrera": carr_item, "Jugador": info_ganador_t4['jugador'], 
                                    "Tipo": "Abono (Premio)", "Detalle": f"Ganador con {ganador_sel_tab4}", "Monto (Bs.)": premio_final_carr
                                })
                            
                            st.session_state.ganancia_casa += monto_casa_carr
                            st.session_state.historial_ganadores[carr_item] = {
                                "Ganador": info_ganador_t4['jugador'], "Caballo": ganador_sel_tab4, "Premio": formatear_bs(premio_final_carr)
                            }
                            st.session_state.carreras_cerradas_remate[carr_item] = True
                            st.success(f"¡Carrera {carr_item} liquidada con éxito!")
                            st.rerun()
                    else:
                        st.warning("Sin ejemplares.")

# ==========================================
# PESTAÑA 5: CUENTAS POR JUGADOR
# ==========================================
with tab5:
    st.markdown("<div class='subasta-header'>📊 Estado de Cuentas por Jugador</div>", unsafe_allow_html=True)
    st.markdown("Balance general que resume compras (pujas), premios obtenidos, abonos y saldo neto de cada participante.")

    datos_cuentas = []
    total_general_pujas = 0.0
    total_general_premios = 0.0
    total_general_abonos = 0.0
    total_general_neto = 0.0

    for jugador, valores in st.session_state.cuentas.items():
        pujas = valores['Pujas']
        premios = valores['Premios']
        abonos = valores['Abonos']
        # Neto: lo que debe pagar menos lo que ganó y abonó (o saldo a favor/en contra)
        # Saldo = Premios + Abonos - Pujas (positivo a favor del jugador, negativo si debe)
        neto = (premios + abonos) - pujas
        
        total_general_pujas += pujas
        total_general_premios += premios
        total_general_abonos += abonos
        total_general_neto += neto
        
        datos_cuentas.append({
            "Jugador": jugador,
            "Total Compras": formatear_bs(pujas),
            "Total Premios": formatear_bs(premios),
            "Abonos Extra": formatear_bs(abonos),
            "Saldo Neto": formatear_bs(neto)
        })

    st.dataframe(pd.DataFrame(datos_cuentas), use_container_width=True, hide_index=True)

    st.markdown("---")
    col_inf_1, col_inf_2, col_inf_3, col_inf_4 = st.columns(4)
    col_inf_1.metric("🛒 Total Compras Global", formatear_bs(total_general_pujas))
    col_inf_2.metric("🏆 Total Premios Global", formatear_bs(total_general_premios))
    col_inf_3.metric("🏠 Utilidad Acumulada Casa", formatear_bs(st.session_state.ganancia_casa))
    col_inf_4.metric("⚖️ Balance General Neto", formatear_bs(total_general_neto))

    st.markdown("---")
    with st.expander("💵 Registrar Abono / Pago de Jugador", expanded=False):
        col_ab_1, col_ab_2, col_ab_3 = st.columns(3)
        with col_ab_1:
            jugador_abono = st.selectbox("Seleccionar Jugador", st.session_state.lista_jugadores, key="sel_jugador_abono")
        with col_ab_2:
            monto_abono = st.number_input("Monto del Abono (Bs.)", min_value=0.0, value=100.0, step=50.0, key="input_monto_abono")
        with col_ab_3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Registrar Abono", use_container_width=True, type="primary"):
                if jugador_abono not in st.session_state.cuentas:
                    st.session_state.cuentas[jugador_abono] = {'Pujas': 0.0, 'Premios': 0.0, 'Abonos': 0.0}
                st.session_state.cuentas[jugador_abono]['Abonos'] += monto_abono
                st.session_state.historial_transacciones.append({
                    "Carrera": "General", "Jugador": jugador_abono,
                    "Tipo": "Abono (Pago)", "Detalle": "Registro manual de abono/pago", "Monto (Bs.)": monto_abono
                })
                st.success(f"✅ Abono de {formatear_bs(monto_abono)} registrado a nombre de {jugador_abono}.")
                st.rerun()

# ==========================================
# PESTAÑA 6: HISTORIAL DE TRANSACCIONES
# ==========================================
with tab6:
    st.markdown("<div class='subasta-header'>🧾 Historial Completo de Transacciones</div>", unsafe_allow_html=True)
    st.markdown("Registro cronológico de todas las operaciones financieras realizadas en el sistema.")

    if not st.session_state.historial_transacciones:
        st.info("No hay transacciones registradas todavía.")
    else:
        df_trans = pd.DataFrame(st.session_state.historial_transacciones)
        st.dataframe(df_trans, use_container_width=True, hide_index=True)

        csv_data = df_trans.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Historial en CSV",
            data=csv_data,
            file_name=f"historial_transacciones_{datetime.today().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# ==========================================
# PESTAÑA 7: LECTOR TABULAR PDF
# ==========================================
with tab7:
    st.markdown("<div class='subasta-header'>📄 Lector Tabular de PDF (Programa Oficial)</div>", unsafe_allow_html=True)
    st.markdown("Sube un archivo PDF con la programación oficial de carreras para extraer automáticamente los ejemplares.")

    archivo_pdf_subido = st.file_uploader("Subir Archivo PDF del Programa", type=["pdf"], key="uploader_pdf_programa")

    if archivo_pdf_subido is not None:
        try:
            lector_pdf = PdfReader(archivo_pdf_subido)
            texto_extraido_total = ""
            for pagina in lector_pdf.pages:
                t_pag = pagina.extract_text()
                if t_pag:
                    texto_extraido_total += t_pag + "\n"

            st.success(f"✅ PDF leído con éxito ({len(lector_pdf.pages)} páginas procesadas).")
            
            with st.expander("🔍 Ver Texto Extraído del PDF", expanded=False):
                st.text_area("Texto bruto", texto_extraido_total, height=250)

            if st.button("⚡ Procesar e Importar al Sistema", type="primary", use_container_width=True):
                # Patrón básico para detectar líneas con caballos o carreras
                lineas = texto_extraido_total.split('\n')
                carrera_detectada_actual = "Carrera 1"
                contador_carrera_num = 1
                
                # Reiniciar parcialmente o asegurar estructura
                for linea in lineas:
                    linea_limpia = linea.strip()
                    if "carrera" in linea_limpia.lower():
                        match_c = re.search(r'\d+', linea_limpia)
                        if match_c:
                            contador_carrera_num = int(match_c.group(0))
                            carrera_detectada_actual = f"Carrera {contador_carrera_num}"
                            if carrera_detectada_actual not in st.session_state.remates:
                                st.session_state.remates[carrera_detectada_actual] = {}
                    
                    # Intentar capturar posibles nombres de caballos (ejemplo con números al inicio)
                    match_caballo = re.match(r'^(\d+)[\s\-\.\)]+(.+)', linea_limpia)
                    if match_caballo and len(linea_limpia) < 50:
                        num_cab = int(match_caballo.group(1))
                        nom_cab = match_caballo.group(2).strip().title()
                        if num_cab <= 17 and nom_cab:
                            llave_cab = f"{num_cab} - {nom_cab}"
                            if carrera_detectada_actual not in st.session_state.remates:
                                st.session_state.remates[carrera_detectada_actual] = {}
                            if len(st.session_state.remates[carrera_detectada_actual]) < 17:
                                st.session_state.remates[carrera_detectada_actual][llave_cab] = {"jugador": "Sin Postor", "monto": 0.0}

                st.success("✅ ¡Programa importado y estructurado correctamente desde el PDF!")
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error al procesar el archivo PDF: {e}")
