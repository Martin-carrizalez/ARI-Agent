"""
agent.py — Grafo LangGraph con aprobación solo para tools de acción
"""
from typing import TypedDict, Annotated, Sequence, Literal
import operator

from langchain_core.messages import BaseMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from tools import TOOLS, consultar_estado, buscar_empleado, generar_constancias, excluir_empleados, reactivar_empleados

TOOLS_CONSULTA = [consultar_estado, buscar_empleado]
TOOLS_ACCION   = [generar_constancias, excluir_empleados, reactivar_empleados]
NOMBRES_CONSULTA = {t.name for t in TOOLS_CONSULTA}
NOMBRES_ACCION   = {t.name for t in TOOLS_ACCION}

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

SYSTEM_PROMPT = """Eres un agente que genera constancias de servicio quincenales. Eres eficiente y no haces preguntas innecesarias.

TOOLS:
- `consultar_estado`: llámala UNA vez al inicio para obtener quincena actual, año y empleados disponibles
- `buscar_empleado`: úsala SOLO si el usuario da un nombre parcial o con errores
- `generar_constancias`: genera los archivos
- `excluir_empleados` / `reactivar_empleados`: gestión de exclusiones

REGLAS DE ORO:
1. Si el usuario no da fecha → usa la fecha de hoy sin preguntar
2. Si el usuario no da año → usa el año de `consultar_estado` sin preguntar  
3. Si el usuario dice "sí", "si", "hazlo", "genera", "adelante" → llama la tool DE INMEDIATO, sin preguntar nada más
4. Si ya tienes quincena + año + empleados → llama `generar_constancias` sin más preguntas
5. NUNCA pidas datos que ya tienes en el historial de conversación
6. NUNCA inventes resultados

EJEMPLO CORRECTO:
- Usuario: "genera quincena 8 solo para arcelia"
- Agente: llama `buscar_empleado("arcelia")` → obtiene nombre exacto → llama `generar_constancias(quincena=8, anio=2026, fecha_emision="2026-04-21", incluir_solo=["Ávalos Domínguez Arcelia"])`

Responde siempre en español.
"""

def crear_grafo(gemini_key: str):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=gemini_key,
        temperature=0
    ).bind_tools(TOOLS)

    def nodo_agente(state: AgentState) -> dict:
        mensajes = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
        respuesta = llm.invoke(mensajes)
        return {"messages": [respuesta]}

    def enrutar(state: AgentState) -> Literal["tools_consulta", "tools_accion", "__end__"]:
        ultimo = state["messages"][-1]
        if not isinstance(ultimo, AIMessage) or not ultimo.tool_calls:
            return "__end__"
        nombre_tool = ultimo.tool_calls[0]["name"]
        if nombre_tool in NOMBRES_CONSULTA:
            return "tools_consulta"
        return "tools_accion"

    grafo = StateGraph(AgentState)
    grafo.add_node("agente", nodo_agente)
    grafo.add_node("tools_consulta", ToolNode(TOOLS_CONSULTA))
    grafo.add_node("tools_accion",   ToolNode(TOOLS_ACCION))

    grafo.set_entry_point("agente")
    grafo.add_conditional_edges("agente", enrutar)
    grafo.add_edge("tools_consulta", "agente")
    grafo.add_edge("tools_accion",   "agente")

    checkpointer = MemorySaver()
    compilado = grafo.compile(
        checkpointer=checkpointer,
        interrupt_before=["tools_accion"]   # Solo pausa antes de acciones
    )
    return compilado, checkpointer