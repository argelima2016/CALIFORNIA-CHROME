import pdfplumber  # <-- Asegúrate de agregar este import arriba con los demás
import re

st.sidebar.header("⚙️ Control de Carrera")

st.sidebar.subheader("📅 Cargar Programa (PDF o Excel)")
# Ahora aceptamos PDF además de xlsx y csv
archivo_programa = st.sidebar.file_uploader("Sube el PDF o Excel de las carreras", type=["pdf", "xlsx", "csv"])

if archivo_programa is not None:
    try:
        # --- NUEVA LÓGICA PARA PROCESAR PDF DIRECTAMENTE ---
        if archivo_programa.name.endswith('.pdf'):
            carrera_actual_detectada = None
            caballos_encontrados = 0
            
            with pdfplumber.open(archivo_programa) as pdf:
                for num_pagina, pagina in enumerate(pdf.pages, 1):
                    texto = pagina.extract_text()
                    if not texto:
                        continue
                        
                    for linea in texto.split("\n"):
                        linea_limpia = linea.strip().upper()
                        
                        # 1. Detectar el inicio de una Carrera (Ej: "CARRERA 1", "1A. CARRERA", "CARRERA: 2")
                        patron_carrera = re.search(r'(?:CARRERA|CARR)\s*(\d+)|(\d+)\s*(?:A\.|A)\s*CARRERA', linea_limpia)
                        if patron_carrera:
                            num_carr = patron_carrera.group(1) or patron_carrera.group(2)
                            carrera_actual_detectada = f"Carrera {int(num_carr)}"
                            if carrera_actual_detectada not in st.session_state.remates:
                                st.session_state.remates[carrera_actual_detectada] = {}
                        
                        # 2. Capturar los caballos si ya estamos dentro de una carrera.
                        # Este patrón busca líneas que comiencen con un número (el del caballo) seguido por el nombre.
                        # Ej: "1 SANSÓN", "02 GRAN TATÚ", "12 MY RUNNING MATE"
                        patron_caballo = re.match(r'^(\d+)\s+([A-ZÁÉÍÓÚÑ\s\.\-\'\’]+)', linea_limpia)
                        if patron_caballo and carrera_actual_detectada:
                            num_caballo = patron_caballo.group(1)
                            nombre_caballo = patron_caballo.group(2).strip()
                            
                            # Limpieza para quitar jinetes o entrenadores si la línea es muy larga
                            # Usualmente los nombres de caballos no pasan de 4 palabras
                            palabras = nombre_caballo.split()
                            if len(palabras) > 3:
                                # Si la línea trae jinete, nos quedamos con las primeras palabras (el nombre base)
                                nombre_caballo = " ".join(palabras[:3])
                                
                            ejemplar_final = f"{num_caballo} - {nombre_caballo}"
                            
                            if ejemplar_final not in st.session_state.remates[carrera_actual_detectada]:
                                st.session_state.remates[carrera_actual_detectada][ejemplar_final] = {"jugador": "Sin Postor", "monto": 0.0}
                                caballos_encontrados += 1
                                
            if caballos_encontrados > 0:
                st.sidebar.success(f"¡PDF procesado! Se crearon {len(st.session_state.remates)} carreras y {caballos_encontrados} ejemplares.")
            else:
                st.sidebar.warning("Se leyó el PDF pero no se identificó el formato de caballos. Verifica el texto.")

        # --- MANTENEMOS LA COMPATIBILIDAD CON EXCEL/CSV POR SI ACASO ---
        else:
            if archivo_programa.name.endswith('.csv'):
                df_prog = pd.read_csv(archivo_programa)
            else:
                df_prog = pd.read_excel(archivo_programa)
                
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
                st.sidebar.success("¡Programa Excel cargado con éxito!")
            else:
                st.sidebar.error("El Excel debe tener columnas 'Carrera' y 'Caballo'.")
                
    except Exception as e:
        st.sidebar.error(f"Error procesando el archivo: {e}")
