# 🍽 Restaurantes Madrid — Asistente NLP

Sistema de recomendación de restaurantes de Madrid basado en análisis de lenguaje natural. El asistente procesa más de 16.500 reseñas reales de Google Maps mediante modelos NLP para extraer sentimiento, criterios cualitativos y platos destacados, y los pone a disposición del usuario a través de una interfaz conversacional.

**Demo:** [pwa-restaurantes-pi.vercel.app](https://pwa-restaurantes-pi.vercel.app)

---

## Índice

- [Descripción del proyecto](#descripción-del-proyecto)
- [Arquitectura](#arquitectura)
- [Pipeline de datos](#pipeline-de-datos)
- [Backend](#backend)
- [Frontend](#frontend)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación y uso local](#instalación-y-uso-local)
- [Despliegue](#despliegue)
- [Stack tecnológico](#stack-tecnológico)

---

## Descripción del proyecto

El objetivo del proyecto es construir un sistema capaz de responder preguntas en lenguaje natural sobre restaurantes de Madrid — *"¿Dónde puedo comer cocido madrileño cerca de Malasaña?"*, *"Busco un sitio romántico con terraza"* — sin depender de APIs externas de pago en producción.

El sistema analiza 16.574 reseñas de los 180 restaurantes mejor valorados de Madrid y extrae de forma automática:

- **Sentimiento** por reseña (positivo / neutro / negativo) mediante `nlptown/bert-base-multilingual-uncased-sentiment`.
- **Platos más mencionados** usando una whitelist curada, bigramas y trigramas de sustantivos.
- **Criterios cualitativos** (terraza, romántico, apto para niños, sin gluten, etc.) validados por fragmentos de reseñas.
- **Cocina detectada** por nombre del restaurante y platos representativos.
- **Personal destacado** por patrones de mención directa.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                     PIPELINE (local)                    │
│                                                         │
│  resenas_unificadas.csv                                 │
│         ↓                                               │
│  pipeline.py  ──→  nlptown/bert  (sentimiento)          │
│                ──→  bigramas + whitelist  (platos)      │
│                ──→  Gemini API  (criterios, frases)     │
│                ──→  Nominatim  (geocodificación)        │
│         ↓                                               │
│  restaurantes.csv   (datos listos para producción)      │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│                  BACKEND (Render)                       │
│                                                         │
│  main.py  ──  FastAPI                                   │
│    · Carga restaurantes.csv en memoria al arrancar      │
│    · Motor NLP determinista: parsea la consulta,        │
│      filtra por cocina / plato / zona / criterio        │
│      y puntúa los resultados                            │
│    · Endpoints: GET /restaurantes, POST /recomendar     │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│                 FRONTEND (Vercel)                       │
│                                                         │
│  React  ──  interfaz de chat conversacional             │
│    · Landing page con chips de búsqueda rápida          │
│    · Chat con tarjetas de restaurante                   │
│    · Modal de detalle con platos, criterios y frases    │
│    · Mapa interactivo (Leaflet + OpenStreetMap)         │
│    · Historial de sesiones en localStorage              │
└─────────────────────────────────────────────────────────┘
```

---

## Pipeline de datos

El script `backend/pipeline.py` consolida todo el procesado de datos en un único archivo con etapas independientes.

### Ejecución completa

```bash
cd backend
python pipeline.py
```

Esto ejecuta todas las etapas en orden:

1. Análisis NLP con `nlptown/bert` (sentimiento por reseña)
2. Extracción de platos (whitelist + bigramas + Gemini)
3. Clasificación de criterios cualitativos (Gemini sobre fragmentos)
4. Detección de cocina y categoría de carta
5. Actualización de personal destacado
6. Generación de frases parafraseadas con Gemini

### Ejecución por etapa (sin reprocesar BERT)

```bash
python pipeline.py --solo-criterios    # Recalcula criterios cualitativos
python pipeline.py --solo-personal     # Actualiza personal destacado
python pipeline.py --solo-frases       # Regenera frases con Gemini
python pipeline.py --solo-cocina       # Detecta cocina y categoría
python pipeline.py --solo-geo          # Geocodifica direcciones (Nominatim)
```

### Archivos necesarios

| Archivo | Descripción |
|---|---|
| `resenas_unificadas.csv` | Reseñas originales de Google Maps (entrada) |
| `ranking.csv` | Ranking con valoración, votaciones y dirección |
| `.env` | Variables de entorno (opcional, ver abajo) |

### Variables de entorno (opcionales)

```env
GEMINI_API_KEY=tu_clave_aqui
```

Sin `GEMINI_API_KEY` el pipeline funciona en modo heurístico: extrae platos y criterios sin normalización ni validación semántica.

### Archivos generados

| Archivo | Descripción |
|---|---|
| `restaurantes.csv` | Datos completos por restaurante (backend los sirve) |
| `analisis_restaurantes_resenas.csv` | Reseñas con sentimiento asignado |

---

## Backend

FastAPI servido en Render. Al arrancar carga `restaurantes.csv` en memoria y expone dos endpoints.

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/health` | Estado del servidor y número de restaurantes cargados |
| `GET` | `/restaurantes` | Lista todos los restaurantes con coordenadas (para el mapa) |
| `POST` | `/recomendar` | Recibe una consulta en lenguaje natural y devuelve restaurantes |

### Ejemplo de consulta

```bash
curl -X POST https://nlp-restaurantes-madrid.onrender.com/recomendar \
  -H "Content-Type: application/json" \
  -d '{"consulta": "quiero comer pulpo gallego cerca de Malasaña", "historial": []}'
```

### Instalación local

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

---

## Frontend

React desplegado en Vercel. Interfaz conversacional con dos rutas:

- `/` — Landing page con descripción del proyecto y chips de búsqueda rápida.
- `/app` — Chat con el asistente.

### Instalación local

```bash
cd frontend
npm install
npm start
```

La URL del backend se configura directamente en `src/Chat.js`:

```js
const API_URL = "https://nlp-restaurantes-madrid.onrender.com";
```

---

## Estructura del repositorio

```
TFM/
├── backend/
│   ├── main.py                          # Servidor FastAPI
│   ├── pipeline.py                      # Pipeline completo de datos
│   ├── requirements.txt
│   ├── restaurantes.csv                 # Datos procesados (producción)
│   ├── resenas_unificadas.csv           # Reseñas originales (entrada)
│   └── analisis_restaurantes_resenas.csv
│
└── frontend/
    ├── public/
    └── src/
        ├── index.js                     # Punto de entrada React
        ├── Landing.js                   # Página de inicio
        ├── Chat.js                      # Interfaz de chat principal
        └── MapaRestaurantes.js          # Mapa con Leaflet
```

---

## Despliegue

### Backend — Render

| Parámetro | Valor |
|---|---|
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

### Frontend — Vercel

| Parámetro | Valor |
|---|---|
| Root Directory | `frontend` |
| Framework | Create React App |
| Build Command | `npm run build` |

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Análisis de sentimiento | `nlptown/bert-base-multilingual-uncased-sentiment` |
| Extracción de entidades | Python (bigramas, whitelist, TF-IDF) |
| Validación semántica | Google Gemini 2.5 Flash (solo pipeline, no en producción) |
| Geocodificación | Nominatim / OpenStreetMap |
| Backend API | Python · FastAPI · Pandas |
| Frontend | React · React Router |
| Mapas | Leaflet · OpenStreetMap |
| Despliegue backend | Render |
| Despliegue frontend | Vercel |

---

*Proyecto académico · TFM · 2026*
