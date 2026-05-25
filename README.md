# Agente Generador de Constancias de Servicio

## Instalación
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Archivos necesarios en la misma carpeta
- `app.py`
- `FORMATO_CONSTANCIA_DE_SERVICIO__1_.docx` (tu plantilla)
- `requirements.txt`

## Configuración (panel lateral en la app)
| Campo | Qué poner |
|-------|-----------|
| API Key Gemini | Tu key de Google AI Studio |
| ID de Google Sheet | El ID en la URL de tu hoja (el string largo entre /d/ y /edit) |
| Credenciales JSON | El contenido completo de tu archivo JSON de Service Account |

## Comandos que entiende el agente
| Comando | Resultado |
|---------|-----------|
| `genera todas` | Genera todas las constancias de la siguiente quincena |
| `genera todas excepto Héctor Lara` | Genera todas menos Héctor (solo esta vez) |
| `elimina a Héctor Lara de la lista` | Héctor queda excluido permanentemente |
| `vuelve a incluir a Héctor Lara` | Quita a Héctor de los excluidos permanentes |
| `genera la quincena 5 del 2026` | Genera una quincena específica |
| `¿cuántos empleados hay?` | Info sobre la lista actual |

## Columnas requeridas en Google Sheets
`Nombre Completo`, `Apellido paterno`, `Apellido Materno`, `Nombre(s)`,
`C.C.T. ADSCRIPCIÓN`, `Clave Presupuestal`, `RFC`, `INGRESOA LA SEJ`,
`Descripción de puesto`, `TEL. PERSONAL`, `TEL. ext.`

## Cómo funciona
1. Gemini interpreta tu comando en lenguaje natural
2. El agente decide qué quincena, qué fecha y a quién incluir
3. Genera un .docx por empleado reemplazando los `<<CAMPOS>>` de tu plantilla
4. Descarga un .zip con todas las constancias
5. Recuerda la última quincena y las exclusiones permanentes en `memory.json`
