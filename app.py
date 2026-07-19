import json
import os

ARCHIVO_ESTADO = "estado_remates_global.json"

# --- FUNCIÓN PARA CARGAR EL ESTADO GLOBAL ---
def cargar_estado_global():
    if os.path.exists(ARCHIVO_ESTADO):
        try:
            with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

# --- FUNCIÓN PARA GUARDAR EL ESTADO GLOBAL ---
def guardar_estado_global():
    estado_a_guardar = {
        "remates": st.session_state.remates,
        "cuentas": st.session_state.cuentas,
        "historial_transacciones": st.session_state.historial_transacciones,
        "historial_ganadores": st.session_state.historial_ganadores
    }
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado_a_guardar, f, ensure_ascii=False, indent=4)

# Al inicio de tu script, en lugar de inicializar vacío, intentas cargar del archivo:
datos_guardados = cargar_estado_global()

if datos_guardados and 'remates' in datos_guardados:
    if 'remates' not in st.session_state or not st.session_state.remates:
        st.session_state.remates = datos_guardados["remates"]
    if 'cuentas' not in st.session_state:
        st.session_state.cuentas = datos_guardados["cuentas"]
    if 'historial_transacciones' not in st.session_state:
        st.session_state.historial_transacciones = datos_guardados["historial_transacciones"]
    if 'historial_ganadores' not in st.session_state:
        st.session_state.historial_ganadores = datos_guardados["historial_ganadores"]
