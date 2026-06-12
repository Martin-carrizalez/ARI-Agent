"""
agent.py — Grafo LangGraph con aprobación solo para tools de acción
Cambios vs versión anterior (optimización de tokens/cuota):
  - El estado del sistema se inyecta al system prompt en cada turno
    (estado_sistema() es Python puro → 0 llamadas al LLM; antes
    consultar_estado costaba 2 round-trips por conversación)
  - El historial se recorta a los últimos MAX_MENSAJES antes de cada invoke
    (el MemorySaver acumulaba todo y cada llamada reenviaba la conversación completa)
  - Modelo configurable; default gemini-2.5-flash-lite (cuota gratuita más holgada,
    suficiente para esta tarea)
  - enrutar() revisa TODAS las tool_calls: si alguna es de acción, pasa por aprobación
"""
import json
from typing import TypedDict, Annotated, Sequence, Literal
import operator

from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from tools import TOOLS, estado_sistema, buscar_empleado, generar_constancias, excluir_empleados, reactivar_empleados

TOOLS_CONSULTA = [buscar_empleado]
TOOLS_ACCION   = [generar_constancias, excluir_empleados, reactivar_empleados]
NOMBRES_CONSULTA = {t.name for t in TOOLS_CONSULTA}
NOMBRES_ACCION   = {t.name for t in TOOLS_ACCION}

MAX_MENSAJES = 12  # historial máximo enviado al LLM por turno

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

SYSTEM_PROMPT = """Eres un agente que genera constancias de servicio quincenales. Eres eficiente y no haces preguntas innecesarias.

ESTADO ACTUAL DEL SISTEMA (ya consultado, NO necesitas pedirlo):
{estado}

TOOLS:
- `buscar_empleado`: úsala SOLO si el usuario da un nombre parcial o con errores
- `generar_constancias`: genera los archivos
- `excluir_empleados` / `reactivar_empleados`: gestión de exclusiones

REGLAS DE ORO:
1. Si el usuario no da fecha → usa fecha_hoy del estado, sin preguntar
2. Si el usuario no da año → usa ultimo_anio del estado, sin preguntar
3. Si el usuario no da quincena → usa siguiente_quincena_sugerida, sin preguntar
4. Si el usuario dice "sí", "si", "hazlo", "genera", "adelante" → llama la tool DE INMEDIATO, sin preguntar nada más
5. NUNCA pidas datos que ya tienes en el estado o en el historial
6. NUNCA inventes resultados

EJEMPLO CORRECTO:
- Usuario: "genera quincena 8 solo para arcelia"
- Agente: llama `buscar_empleado("arcelia")` → obtiene nombre exacto → llama `generar_constancias(quincena=8, anio=<ultimo_anio>, fecha_emision=<fecha_hoy>, incluir_solo=["Ávalos Domínguez Arcelia"])`

Responde siempre en español.
"""

def _recortar_historial(mensajes: list[BaseMessage]) -> list[BaseMessage]:
    """Últimos MAX_MENSAJES, sin dejar ToolMessages huérfanos al inicio
    (un ToolMessage sin su AIMessage con tool_calls previo rompe la API)."""
    recorte = list(mensajes)[-MAX_MENSAJES:]
    while recorte and isinstance(recorte[0], ToolMessage):
        recorte.pop(0)
    return recorte

def crear_grafo(gemini_key: str, modelo: str = "gemini-2.5-flash-lite"):
    llm = ChatGoogleGenerativeAI(
        model=modelo,
        google_api_key=gemini_key,
        temperature=0
    ).bind_tools(TOOLS)

    def nodo_agente(state: AgentState) -> dict:
        estado = json.dumps(estado_sistema(), ensure_ascii=False)
        sistema = SystemMessage(content=SYSTEM_PROMPT.format(estado=estado))
        historial = _recortar_historial(list(state["messages"]))
        respuesta = llm.invoke([sistema] + historial)
        return {"messages": [respuesta]}

    def enrutar(state: AgentState) -> Literal["tools_consulta", "tools_accion", "__end__"]:
        ultimo = state["messages"][-1]
        if not isinstance(ultimo, AIMessage) or not ultimo.tool_calls:
            return "__end__"
        nombres = {tc["name"] for tc in ultimo.tool_calls}
        # Si CUALQUIER tool llamada es de acción, todo el lote pasa por aprobación
        if nombres & NOMBRES_ACCION:
            return "tools_accion"
        return "tools_consulta"

    grafo = StateGraph(AgentState)
    grafo.add_node("agente", nodo_agente)
    grafo.add_node("tools_consulta", ToolNode(TOOLS_CONSULTA))
    grafo.add_node("tools_accion",   ToolNode(TOOLS_ACCION + TOOLS_CONSULTA))

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