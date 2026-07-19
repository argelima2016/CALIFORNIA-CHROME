import pdfplumber  # <-- Asegúrate de tener este import al inicio de tu app.py
import re

st.sidebar.header("⚙️ Control de Carrera")
st.sidebar.subheader("📅 Cargar Programa Oficial")

# Configurado para aceptar estrictamente archivos PDF (.pdf)
archivo_pdf = st.sidebar.file_uploader("Sube la revista o programa en formato PDF", type=["pdf"])

if archivo_pdf is not None:
    try:
        st.sidebar.warning("Leyendo el PDF del programa... Por favor espera.")
        
        carrera_actual_detectada = None
        caballos_encontrados = 0
        
        # Abrir el archivo PDF cargado
        with pdfplumber.open(archivo_pdf) as pdf:
            for num_pagina, pagina in enumerate(pdf.pages, 1):
                texto = pagina.extract_text()
                if not texto:
                    continue
                    
                # Analizar el texto línea por línea
                for linea in texto.split("\n"):
                    linea_limpia = linea.strip().upper()
                    
                    # 1. Identificar si la línea anuncia una Carrera (Ej: "CARRERA 1", "1A. CARRERA", "CARRERA: 4")
                    patron_carrera = re.search(r'(?:CARRERA|CARR)\s*(\d+)|(\d+)\s*(?:A\.|A)\s*CARRERA', linea_limpia)
                    if patron_carrera:
                        num_carr = patron_carrera.group(1) or patron_carrera.group(2)
                        carrera_actual_detectada = f"Carrera {int(num_carr)}"
                        
                        # Inicializar la carrera en el sistema si no existe
                        if carrera_actual_detectada not in st.session_state.remates:
                            st.session_state.remates[carrera_actual_detectada] = {}
                    
                    # 2. Identificar los caballos bajo la carrera detectada
                    # Busca líneas que comiencen con el número del caballo y sigan con letras
                    # Ej: "1 PAPÁ PEDRO", "02 SANSÓN", "10 MY RUNNING MATE"
                    patron_caballo = re.match(r'^(\d+)\s+([A-ZÁÉÍÓÚÑ\s\.\-\'\’]+)', linea_limpia)
                    if patron_caballo and carrera_actual_detectada:
                        num_caballo = patron_caballo.group(1)
                        nombre_caballo = patron_caballo.group(2).strip()
                        
                        # Limpieza rápida: Si la línea es muy larga (trae jinete/entrenador), 
                        # nos quedamos solo con las primeras 3 palabras que suelen ser el nombre del caballo
                        palabras = nombre_caballo.split()
                        if len(palabras) > 3:
                            nombre_caballo = " ".join(palabras[:3])
                            
                        ejemplar_final = f"{int(num_caballo)} - {nombre_caballo}"
                        
                        # Guardar el caballo listo para recibir apuestas
                        if ejemplar_final not in st.session_state.remates[carrera_actual_detectada]:
                            st.session_state.remates[carrera_actual_detectada][ejemplar_final] = {"jugador": "Sin Postor", "monto": 0.0}
                            caballos_encontrados += 1
                            
        # Notificaciones de éxito o advertencia al usuario
        if caballos_encontrados > 0:
            st.sidebar.success(f"📋 ¡PDF cargado! Se estructuraron {len(st.session_state.remates)} carreras y {caballos_encontrados} ejemplares.")
        else:
            st.sidebar.warning("Se leyó el documento, pero no pudimos identificar el formato de las carreras. Asegúrate de que el PDF tenga texto seleccionable (no escaneado como foto de baja calidad).")
            
    except Exception as e:
        st.sidebar.error(f"Ocurrió un error al procesar el PDF: {e}")
