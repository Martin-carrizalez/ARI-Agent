# ARI — Agente de Constancias de Servicio
> Agente de IA para la generación automatizada de constancias de servicio quincenales · Dirección de Formación Continua · SEJ Jalisco

---

## ¿Qué es ARI?

ARI es un agente de inteligencia artificial desarrollado como proyecto de Ingeniería de Software. A diferencia de un chatbot tradicional, ARI puede **planificar, decidir y ejecutar acciones** de forma autónoma — pero siempre con aprobación humana antes de generar archivos.

ARI automatiza la generación de constancias de servicio para ~36 empleados cada quincena, un proceso que antes requería llenar plantillas Word manualmente una por una.

---

## Arquitectura

ARI sigue una **Arquitectura Basada en Agentes con Human-in-the-Loop**, implementada con un Grafo de Estados Dirigido (LangGraph).

```
Usuario
   ↓ comando en lenguaje natural
Streamlit (app.py)
   ↓ HumanMessage
LangGraph — Grafo de estados (agent.py)
   ├── Nodo agente       → LLM decide qué tool llamar
   ├── tools_consulta    → lee datos sin pedir permiso
   └── tools_accion      → ⏸ pausa y pide confirmación
         ↓ aprobado
   Tools (tools.py)
   ├── Google Sheets     → datos de empleados
   ├── memory.json       → quincena actual + exclusiones
   └── Plantilla .docx   → genera constancias Word
         ↓
   ZIP con constancias
```

---

## Componentes del agente

| Componente | Implementación |
|---|---|
| **Memoria** | `memory.json` — persiste quincena generada y exclusiones permanentes |
| **Ventana de contexto** | Historial de mensajes en `MemorySaver` de LangGraph |
| **Tools** | 5 herramientas formales con `@tool` de LangChain |
| **Planificación** | Grafo de estados con routing condicional |
| **Human-in-the-loop** | `interrupt_before=["tools_accion"]` en LangGraph |
| **Manejo de errores** | try/except en cada tool con mensajes descriptivos |
| **Observabilidad** | LangSmith — trazabilidad de cada paso del agente |

---

## Tools disponibles

| Tool | Tipo | Descripción |
|---|---|---|
| `consultar_estado` | Consulta | Quincena actual, año, empleados disponibles, exclusiones |
| `buscar_empleado` | Consulta | Busca nombre exacto por nombre parcial o con errores |
| `generar_constancias` | Acción ⏸ | Genera archivos Word y los empaqueta en ZIP |
| `excluir_empleados` | Acción ⏸ | Excluye empleados temporal o permanentemente |
| `reactivar_empleados` | Acción ⏸ | Reactiva empleados excluidos |

---

## Stack tecnológico

**IA y orquestación**
- `langgraph` — Grafo de estados, memoria y human-in-the-loop
- `langchain-google-genai` — Integración con Gemini y tool calling
- `langsmith` — Observabilidad y trazabilidad
- Google Gemini 2.5 Flash — LLM principal

**Datos y archivos**
- `gspread` + Google Sheets API — Base de datos de empleados
- `python-docx` — Generación de constancias desde plantilla Word
- `zipfile` — Empaquetado de constancias

**Interfaz**
- `streamlit` — Interfaz web con chat y botones de aprobación
- `st.secrets` — Gestión segura de credenciales

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/ari-constancias.git
cd ari-constancias

# 2. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate         # Windows
source venv/bin/activate      # Mac/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar credenciales en .streamlit/secrets.toml

# 5. Ejecutar
streamlit run app.py
```

---

## Configuración (.streamlit/secrets.toml)

```toml
GEMINI_API_KEY = "tu_api_key"
SHEET_ID = "id_de_tu_google_sheet"
LANGSMITH_API_KEY = "tu_api_key_langsmith"  # opcional

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```

---

## Comandos que entiende ARI

```
"genera las constancias de la quincena 9"
"haz las constancias pero solo la de Arcelia"
"genera todas excepto Héctor Lara"
"elimina a Héctor Lara de la lista permanentemente"
"vuelve a incluir a Héctor Lara"
"¿cuántos empleados hay disponibles?"
```

---

## Estructura del proyecto

```
├── app.py                               # Interfaz Streamlit + ciclo de aprobación
├── agent.py                             # Grafo LangGraph + LLM
├── tools.py                             # Herramientas formales del agente
├── requirements.txt
├── FORMATO_CONSTANCIA_DE_SERVICIO.docx  # Plantilla Word con <<CAMPOS>>
├── memory.json                          # Generado automáticamente
└── .streamlit/
    └── secrets.toml                     # Credenciales (no se sube al repo)
```

---

## Autor

Desarrollado por Angel Carrizalez · Ingeniería de Software · 2026
