"""
app.py — Interfaz Streamlit para el Agente de Constancias
"""
import json
import os
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.types import Command

import tools as tools_module
from agent import crear_grafo

def extraer_texto(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        partes = []
        for bloque in content:
            if isinstance(bloque, dict) and bloque.get("type") == "text":
                partes.append(bloque.get("text", ""))
            elif isinstance(bloque, str):
                partes.append(bloque)
        return " ".join(partes).strip()
    return str(content)



# ─── Página ───────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Agente Constancias", page_icon="📄", layout="centered")

# ─── Credenciales desde secrets ───────────────────────────────────────────────
GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_ID   = st.secrets["SHEET_ID"]
CREDS_INFO = dict(st.secrets["gcp_service_account"])

# LangSmith observabilidad (opcional)
if "LANGSMITH_API_KEY" in st.secrets:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]    = st.secrets["LANGSMITH_API_KEY"]
    os.environ["LANGCHAIN_PROJECT"]    = "agente-constancias"

# Inyectar credenciales a las tools
tools_module.configurar(CREDS_INFO, SHEET_ID)

# ─── Inicializar grafo una sola vez por sesión ────────────────────────────────
if "grafo" not in st.session_state:
    st.session_state.grafo, _ = crear_grafo(GEMINI_KEY)
    st.session_state.thread_id = "sesion-1"
    st.session_state.mensajes_ui = []

grafo  = st.session_state.grafo
config = {"configurable": {"thread_id": st.session_state.thread_id}}

# ─── UI ───────────────────────────────────────────────────────────────────────
st.title("📄 Agente Constancias")
st.caption("Planifica → tú apruebas → ejecuta")

with st.sidebar:
    if st.button("🔄 Nueva conversación"):
        st.session_state.mensajes_ui = []
        st.session_state.thread_id = f"sesion-{id(st.session_state)}"
        st.session_state.grafo, _ = crear_grafo(GEMINI_KEY)
        st.rerun()

# Mostrar historial
for msg in st.session_state.mensajes_ui:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("zip_path") and os.path.exists(msg["zip_path"]):
            with open(msg["zip_path"], "rb") as f:
                st.download_button(
                    "⬇️ Descargar constancias (.zip)",
                    data=f.read(),
                    file_name=msg["zip_path"],
                    mime="application/zip",
                    key=msg["zip_path"]
                )

# ─── Verificar si el grafo está interrumpido esperando aprobación ─────────────
estado = grafo.get_state(config)
interrumpido = estado.next and any("tools" in n for n in estado.next)

if interrumpido:
    msgs = estado.values.get("messages", [])
    ultimo_ai = next((m for m in reversed(msgs) if isinstance(m, AIMessage)), None)

    if ultimo_ai and ultimo_ai.tool_calls:
        with st.container(border=True):
            st.markdown("### 🤖 Plan del agente — ¿confirmas?")
            for tc in ultimo_ai.tool_calls:
                nombre = tc["name"]
                args = tc["args"]
                if nombre == "generar_constancias":
                    solo = args.get("incluir_solo", [])
                    excluidos = args.get("excluidos_sesion", [])
                    st.markdown(f"""
**Acción:** Generar constancias  
**Quincena:** {args.get('quincena')} / {args.get('anio')}  
**Fecha emisión:** {args.get('fecha_emision')}  
**Empleados:** {"Solo: " + ", ".join(solo) if solo else "Todos los disponibles"}  
**Excluidos esta vez:** {", ".join(excluidos) if excluidos else "Ninguno"}
""")
                elif nombre == "excluir_empleados":
                    st.markdown(f"**Acción:** Excluir — {args.get('nombres')} ({'permanente' if args.get('permanente') else 'solo esta vez'})")
                elif nombre == "reactivar_empleados":
                    st.markdown(f"**Acción:** Reactivar — {args.get('nombres')}")
                else:
                    st.markdown(f"**Acción:** `{nombre}`")
                    st.json(args)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Sí, ejecutar", use_container_width=True, type="primary"):
                    with st.spinner("Ejecutando..."):
                        resultado = grafo.invoke(None, config)
                        msgs_nuevos = resultado.get("messages", [])

                        tool_msg = next(
                            (m for m in reversed(msgs_nuevos) if isinstance(m, ToolMessage)), None
                        )
                        ai_final = next(
                            (m for m in reversed(msgs_nuevos)
                             if isinstance(m, AIMessage) and not m.tool_calls), None
                        )

                        zip_path = None
                        if tool_msg:
                            try:
                                data = json.loads(tool_msg.content)
                                zip_path = data.get("zip_path")
                            except Exception:
                                pass

                        st.session_state.mensajes_ui.append({
                            "role": "assistant",
                            "content": extraer_texto(ai_final.content) if ai_final else "Listo.",
                            "zip_path": zip_path
                        })
                    st.rerun()

            with col2:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.session_state.mensajes_ui.append({
                        "role": "assistant",
                        "content": "Cancelado. ¿Qué quieres hacer?"
                    })
                    # Reiniciar el hilo para limpiar el estado interrumpido
                    st.session_state.thread_id = f"sesion-{id(st.session_state)}"
                    st.session_state.grafo, _ = crear_grafo(GEMINI_KEY)
                    grafo  = st.session_state.grafo
                    config = {"configurable": {"thread_id": st.session_state.thread_id}}
                    st.rerun()

# ─── Input del usuario (solo cuando no está interrumpido) ─────────────────────
if not interrumpido:
    if prompt := st.chat_input("Escribe un comando..."):
        st.session_state.mensajes_ui.append({"role": "user", "content": prompt})

        with st.spinner("Pensando..."):
            resultado = grafo.invoke(
                {"messages": [HumanMessage(content=prompt)]},
                config
            )
            msgs = resultado.get("messages", [])
            ultimo_ai = next((m for m in reversed(msgs) if isinstance(m, AIMessage)), None)

            if ultimo_ai:
                texto = extraer_texto(ultimo_ai.content)
                if texto:
                    st.session_state.mensajes_ui.append({
                        "role": "assistant",
                        "content": texto
                    })

        st.rerun()