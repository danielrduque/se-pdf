# CHATDD — Explicación técnica (guía para la sustentación)

> Datos verificados sobre el proyecto real: versiones instaladas, parámetros de `chatpdf/config.py`, rutas de `server/main.py` y resultados de las pruebas.
> La app la generó una IA (Claude Code); este documento existe para que **tú sepas explicar qué se usó, por qué, y cómo funciona**.

---

## 1. Qué es, en 30 segundos

**CHATDD** es una aplicación web donde subes (o copias a una carpeta) **PDFs, imágenes, audios y videos cortos** y luego **les haces preguntas en lenguaje natural**. La app responde **citando de dónde sacó la respuesta**: la página del PDF (resaltada), el minuto del audio o video, o la imagen.

Técnicamente es un sistema **RAG multimodal** (*Retrieval-Augmented Generation*, "generación aumentada por recuperación"):

1. **Lee** cada archivo y lo convierte a **texto** (extrae texto, transcribe audio, describe imágenes y escenas).
2. **Indexa** ese texto: lo parte en fragmentos y calcula un **embedding** de cada uno (un vector de números que representa su significado).
3. Cuando preguntas, **busca** los fragmentos más relacionados con tu pregunta.
4. Se los pasa a un **modelo de lenguaje (LLM)** que redacta la respuesta usando solo esos fragmentos.

Funciona **100 % local** (tu PC) o con **modelos en la nube** por API, y se puede cambiar desde la pantalla de Ajustes.

---

## 2. Mapa completo de tecnologías

### 2.1 Lenguajes

| Lenguaje | Dónde |
|---|---|
| **Python 3.12** | Todo el backend y la IA (`chatpdf/`, `server/`, `app.py`, `tools/`, `tests/`) |
| **JavaScript (ES modules) + JSX** | El frontend (`web/src/`) |
| **CSS3** | Estilos propios (`web/src/styles.css`): variables, Grid, Flexbox, media queries |
| **HTML5** | `web/index.html` (una sola página; React dibuja el resto) |
| **PowerShell y Batch** | Scripts de arranque (`run_web.bat`, `run.bat`, `setup.bat`, `tools/llamacpp_start.ps1`) |

### 2.2 Backend (servidor)

| Tecnología | Versión | Para qué |
|---|---|---|
| **FastAPI** | 0.156 | Framework web para crear la **API REST**. Rápido, valida datos automáticamente y es asíncrono. |
| **Starlette** | 1.9 | La base sobre la que está construido FastAPI (rutas, respuestas, archivos estáticos). |
| **Pydantic** | 2.14 | Valida los datos que llegan (por ejemplo, que un chat tenga `messages` y `title`). |
| **Uvicorn** | 0.54 | **Servidor ASGI** que ejecuta la aplicación FastAPI en el puerto 8000. |
| **python-multipart** | 0.0.32 | Permite recibir archivos subidos (formularios `multipart/form-data`). |
| **threading** (estándar) | — | Trabajos en segundo plano (leer archivos) y un candado `RLock` para que el índice no se corrompa. |
| **SSE** (Server-Sent Events) | — | Técnica para enviar la respuesta **palabra por palabra** (streaming) al navegador. |

### 2.3 Frontend (lo que ve el usuario)

| Tecnología | Versión | Para qué |
|---|---|---|
| **React** | 18.3.1 | Biblioteca para construir la interfaz con **componentes**. Usa componentes de función y *hooks* (`useState`, `useEffect`, `useMemo`, `useRef`, `useCallback`). |
| **Vite** | 5.4 | Herramienta de **compilación** (*bundler*) y servidor de desarrollo. Convierte JSX en JavaScript que entiende el navegador. |
| **@vitejs/plugin-react** | 4.3 | Plugin de Vite para React. |
| **react-markdown** | 9.1 | Muestra las respuestas con formato (negritas, listas) y permite convertir las citas en botones. |
| **CSS propio** | — | Sin Bootstrap ni Tailwind. Tema claro/oscuro automático (`prefers-color-scheme`) y diseño adaptable a celular. |
| **fetch + ReadableStream** | API del navegador | Para recibir el streaming de la respuesta por POST. |
| **Node 20 + npm 11** | — | Solo para instalar y compilar el frontend. |

### 2.4 Inteligencia artificial

| Tecnología | Versión / dato | Para qué |
|---|---|---|
| **Ollama** | 0.40.6 | Programa que descarga y ejecuta modelos **locales** y los expone por una API. Por dentro usa llama.cpp (en tu PC lo vimos: `ollama ps` mostraba `RUNNER llamacpp`). |
| **llama.cpp** | b11763 (`llama-server`) | El **motor de inferencia** en C/C++ que ejecuta modelos GGUF. Alternativa directa a Ollama. |
| **gemma3:4b** | 3,9 B parámetros · contexto 128 K · cuantizado **Q4_K_M** · proyector de visión de 420 M | El **LLM** de Google. Escribe las respuestas **y entiende imágenes** (multimodal). |
| **EmbeddingGemma 2** (`ggml-org/embeddinggemma-2-GGUF`, Q8_0) | 740 M parámetros (núcleo de texto 270 M + codificador de visión 170 M + de audio 300 M) · **768 dimensiones** · contexto 8192 | Convierte **texto, imágenes y audio** en vectores del MISMO espacio. Se ejecuta con **llama.cpp** (`llama-server --embeddings --mmproj`, puerto 8081). |
| **faster-whisper** | 1.2.1 sobre **CTranslate2** 4.8 · modelo `small`, `int8`, CPU | Transcribe el **audio** (Whisper de OpenAI, versión optimizada). |
| **Gemini API** | vía endpoint compatible con OpenAI | Modelo en la **nube** (gratuito con límites). Cadena de modelos de respaldo. |
| **SDK `ollama`** | 0.6.3 | Cliente Python para hablar con Ollama. |
| **SDK `openai`** | 3.35.1 | Cliente Python que sirve para **llama.cpp** y para **Gemini** (ambos hablan el protocolo de OpenAI). |

### 2.5 Procesamiento de archivos y datos

| Tecnología | Versión | Para qué |
|---|---|---|
| **PyMuPDF** | 2.0 | Leer PDFs, extraer texto, **convertir páginas en imagen** y **resaltar** el texto citado. |
| **OpenCV** (headless) | 5.0 | Extraer **fotogramas** de los videos. |
| **PyAV** | 16.1 | Enlaza con FFmpeg: deja que Whisper abra audio/video sin instalar nada aparte y **convierte** (HEVC → H.264) los videos que el navegador no puede mostrar. |
| **NumPy** | 2.5 | Guarda los vectores y calcula la similitud (producto punto). |
| **SQLite** (estándar) | — | Caché de los análisis lentos (`data/cache.db`). |
| **PostgreSQL + pgvector** | 17 / 0.8 | El índice: tablas `documents` y `chunks` (texto, ubicación, vector `vector`, `tsvector` para palabras exactas). Corre en Docker (`docker-compose.yml`). Los chats también: `chats` y `chat_messages`. |

### 2.6 Otras herramientas

| Herramienta | Uso |
|---|---|
| **Streamlit** 1.66 | Interfaz **alternativa** (`app.py`, `run.bat`). La principal es React. |
| **reportlab** 5.0, **matplotlib** 3.11, **Pillow** 12 | Solo para **generar los documentos de ejemplo** (`tools/`). No son parte de la app. |
| **System.Speech** (Windows) | Voces con las que se generó el audio y el video de ejemplo. |
| **Claude Code** | La IA con la que se desarrolló el proyecto, de forma iterativa y con pruebas automáticas. |

---

## 3. Arquitectura

```
┌──────────────────────────── NAVEGADOR ────────────────────────────┐
│  React 18 (SPA)                                                     │
│  Sidebar · Chat · Visor (PDF/audio/video/imagen) · Ajustes          │
└───────────────▲──────────────────────────────┬──────────────────────┘
        JSON / SSE (streaming)             archivos / imágenes
┌───────────────┴──────────────────────────────▼──────────────────────┐
│  BACKEND  ·  FastAPI + Uvicorn   (server/main.py)                   │
│  22 rutas REST · trabajos en segundo plano · historial de chats     │
└───────────────▲─────────────────────────────────────────────────────┘
                │
┌───────────────┴─────────────────────────────────────────────────────┐
│  NÚCLEO PYTHON  (chatpdf/)                                          │
│  ingest.py  → convierte archivos en texto (PDF, imagen, audio, video)│
│  rag.py     → indexar, buscar, resumir, preguntas globales          │
│  store.py   → PostgreSQL + pgvector (coseno + texto) + fusión RRF   │
│  llm.py     → capa única hacia los modelos (Ollama/llama.cpp/nube)  │
│  cache.py · viewer.py · config.py                                   │
└───────┬───────────────────┬─────────────────────┬───────────────────┘
        ▼                   ▼                     ▼
   Ollama / llama.cpp   Gemini (nube)        faster-whisper
   (gemma3, embeddings)  por API OpenAI       (audio, local)
        │
        ▼
   data/  →  índice, caché, copias de originales, chats
```

**Idea clave de diseño:** el resto del programa **no sabe** si habla con Ollama, llama.cpp o la nube. Todo pasa por `llm.py`. Por eso cambiar de modelo es solo cambiar un ajuste.

### Estructura de carpetas

| Ruta | Qué contiene |
|---|---|
| `chatpdf/` | El núcleo: `config.py` (ajustes), `llm.py` (modelos), `ingest.py` (leer archivos), `rag.py` (lógica de búsqueda y resumen), `store.py` (índice), `cache.py`, `viewer.py` |
| `server/main.py` | API FastAPI (547 líneas) |
| `web/src/` | Frontend React: `App.jsx` (estado general), `components/` (Sidebar, Chat, Viewer, Sources, ChatList, AddDocsModal, SettingsModal, JobPanel), `api.js`, `styles.css` |
| `app.py` | Interfaz alternativa con Streamlit |
| `tests/` | 7 scripts de prueba (≈ 750 líneas) |
| `tools/` | Generador de datos de ejemplo, `qa_check.py` (34 preguntas), script de llama.cpp |
| `base_conocimiento/` | La carpeta de documentos que la app lee |
| `data/` | Índice, caché, copias y chats (no se sube a GitHub) |
| `docs/` | Documentación |

**Tamaño:** ≈ 4 000 líneas de código (sin pruebas) + ≈ 740 de pruebas.

---

## 4. Qué pasa cuando haces una pregunta (paso a paso)

1. **Frontend:** escribes en `Chat.jsx`. `App.send()` llama a `streamChat()` (en `api.js`), que hace un `POST /api/chat`.
2. **Backend** (`server/main.py → chat()`): decide si es una pregunta **global** ("¿de qué trata el video?") o **puntual**.
3. **Pregunta puntual:**
   1. `standalone_question()`: si hay historial, el LLM reescribe la pregunta para que se entienda sola ("¿y cuánto cuesta?" → "¿cuánto cuesta el sensor AG-200?").
   2. `embed_query()`: la pregunta se convierte en un vector de 768 números.
   3. `hybrid_search()`: busca por **significado** (pgvector, distancia coseno `<=>`) **y** por **palabras exactas** (índice de texto completo `tsvector` + GIN) y **fusiona** ambos rankings (RRF). Devuelve los 6 mejores fragmentos.
   4. `build_messages()`: arma el prompt: reglas + los 6 fragmentos, cada uno con su etiqueta `[archivo, ubicación]`.
   5. `llm.chat_stream()`: el modelo escribe la respuesta **token por token**.
4. **Pregunta global:** se lee **todo** el documento, ordenado por minuto o página, y se resume (por partes si es largo).
5. **El servidor envía eventos SSE:** `sources` (las fuentes) → `status` ("Escribiendo el resumen…") → `token` (cada pedazo de texto) → `done`.
6. **Frontend:** muestra el texto a medida que llega. `linkifyCitations()` convierte `[contrato.pdf, pág. 2]` en un **botón**; al pulsarlo se abre el **visor** en esa página con el texto resaltado.
7. **Historial:** al terminar, la conversación se guarda sola en PostgreSQL (`chats` y `chat_messages`).

---

## 5. Cómo se lee cada tipo de archivo (`ingest.py`)

| Tipo | Procesamiento |
|---|---|
| **PDF** | Se extrae el texto con PyMuPDF. Si una página tiene **imágenes o casi nada de texto** (menos de 80 caracteres), se convierte en imagen (110 dpi) y la **describe el modelo de visión**. |
| **Imagen** | El modelo de visión transcribe el texto visible y describe lo que se ve. |
| **Audio** | **faster-whisper** transcribe con marcas de tiempo; se agrupan en bloques de ~45 s. |
| **Video** | Audio con Whisper **+** un fotograma cada ~8 s (máximo 30) que describe el modelo de visión. Se **omiten los fotogramas casi idénticos** (diferencia media < 3 sobre una miniatura de 32×18) para no gastar tiempo en diapositivas quietas. |
| **Texto** | Se divide en fragmentos. |

**Fragmentos (*chunks*):** 1200 caracteres con 200 de solapamiento, cortando en un límite natural (salto de línea o punto).

**Embeddings:** con EmbeddingGemma se usa el formato recomendado: `title: archivo | text: …` para documentos y `task: search result | query: …` para preguntas.

**Embeddings multimodales (lo que pide EmbeddingGemma 2):** además del texto de cada fragmento, la imagen o el audio ORIGINAL se convierten directamente en un vector (`chunks.embedding_mm`), sin pasar por una descripción ni una transcripción:
- una página de PDF con gráficos, una imagen suelta o un fotograma de video → `{"image": …}`;
- un tramo de audio (o la pista de audio de un video), recortado y pasado a 16 kHz mono → `{"audio": …}`.

La pregunta se embebe una sola vez (texto) y se compara con las dos columnas de vectores. **El texto manda** (RRF del significado y de las palabras exactas) y hasta 1 de los 6 resultados puede venir de coincidir con la imagen o el audio (`MM_SLOTS`, umbral `MM_TAU` = 0,68). Es una ranura acotada a propósito: la similitud pregunta↔imagen es alta aunque no tengan relación, y un ranking multimedia completo hundía la fuente correcta de las preguntas de texto de 25/25 a 16/25 (hallazgo de QA). En la práctica: «cronograma con hitos por meses» encuentra la página 6 del plan estratégico por su **imagen** (similitud 0,74 contra 0,65 para «organigrama»), y «una persona hablando en español sobre sensores» encuentra el audio del gerente por su **sonido** (0,74 contra 0,53–0,58 para música o ruido). `python tools/mm_check.py` lo demuestra con los archivos reales.

**Caché** (`cache.py`, SQLite): cada descripción de imagen y cada transcripción se guarda con una clave que incluye el **hash SHA-256 del archivo**, el modelo y el prompt. Releer un archivo ya analizado es casi instantáneo y, si algo se corta, continúa donde quedó.

**Base de conocimiento por carpeta:** `kb_scan()` compara la carpeta con el índice (por hash): detecta **nuevos, modificados y borrados**. `kb_sync()` indexa lo nuevo, reindexa lo modificado y quita lo borrado.

---

## 6. La búsqueda (el corazón del sistema)

Hay tres piezas, todas hechas a mano en `store.py` con NumPy (sin base de datos vectorial externa):

1. **Búsqueda semántica (embeddings + similitud coseno).** Cada fragmento es un vector de 768 números. Los vectores se normalizan, así que el **producto punto** equivale a la similitud coseno: cuanto más cerca de 1, más parecido el significado. Encuentra "cancelar el contrato" aunque el texto diga "terminación anticipada".
2. **Texto completo** (búsqueda por palabras). El índice `tsvector` de PostgreSQL ordena con `ts_rank`, con un tokenizador que ignora tildes y mayúsculas. Encuentra **códigos, cifras y nombres exactos** (por ejemplo `E-4471`), donde los embeddings a veces fallan.
3. **RRF — Reciprocal Rank Fusion.** Combina ambos rankings: cada fragmento suma `1 / (60 + posición)` en cada lista. Quien aparece alto en las dos listas gana. No hay que ajustar pesos.

Opcionalmente (casilla "Búsqueda más precisa") un **reranking**: el LLM reordena los 14 mejores candidatos. En mis pruebas no mejoró nada y añade ~5 s, por eso viene apagado.

---

## 7. Los modelos y por qué hay varios

| Rol | Modelo | Dónde corre |
|---|---|---|
| Escribir respuestas | `gemma3:4b` (o Gemini) | Ollama / llama.cpp / nube |
| Entender imágenes, gráficos y PDFs escaneados | `gemma3:4b` con su proyector de visión (o Gemini) | igual |
| Búsqueda (embeddings) | `embeddinggemma-2` (multimodal, GGUF Q8_0) | llama.cpp en CPU, servidor local en el puerto 8081 |
| Transcribir audio | Whisper `small` | CPU, siempre local |

**Proveedores** (se eligen en ⚙️ Ajustes, por separado para respuestas y para búsqueda):

- **Ollama (local):** el más cómodo; descarga y gestiona los modelos.
- **llama.cpp (local):** el motor directo; `llama-server` expone una API compatible con OpenAI.
- **API en la nube:** cualquier API compatible con OpenAI (OpenAI, Groq, OpenRouter, Gemini…). Aquí se usa **Gemini** con plan gratuito.

**Cadena de modelos de respaldo.** En el campo de modelo se pueden poner varios separados por coma (`a, b, c`). Si uno falla (404, cupo agotado, 503, tiempo de espera), la app pasa al siguiente y deja al que falló "en pausa" un rato. Una clave inválida corta de inmediato.

**Privacidad:** con modelos locales **nada sale de tu PC**. Con la nube, las preguntas y el contenido se envían a ese proveedor (la app lo avisa).

---

## 8. Backend en detalle

**API REST (22 rutas):**

| Grupo | Rutas |
|---|---|
| Estado y ajustes | `GET /api/status`, `POST /api/settings`, `GET /api/health` |
| Documentos | `GET /api/docs`, `DELETE /api/docs/{name}`, `GET /api/docs/{name}/content`, `GET /api/files/{doc}`, `GET /api/page/{doc}/{page}` |
| Lectura de archivos | `POST /api/upload`, `GET /api/kb`, `POST /api/kb/sync`, `POST /api/kb/open`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel` |
| Chat | `POST /api/chat` (streaming SSE), `POST /api/summarize` |
| Historial | `GET/POST /api/chats`, `GET/PUT/PATCH/DELETE /api/chats/{id}` |

**Detalles que muestran buen diseño:**

- **Trabajos en segundo plano.** Leer archivos tarda minutos. La subida y la sincronización devuelven un `job_id` al instante; el frontend consulta `GET /api/jobs/{id}` cada 0,7 s para mostrar **progreso y tiempo restante**, y se puede **cancelar**. Solo corre un trabajo a la vez (un `Lock`) para no saturar la máquina.
- **Streaming con SSE.** `StreamingResponse` con `text/event-stream`: el servidor envía eventos nombrados (`sources`, `token`, `status`, `done`, `error`). Es más simple que WebSockets cuando la comunicación va en un solo sentido.
- **Concurrencia.** El índice tiene un `RLock`: se puede preguntar mientras otro hilo indexa.
- **Archivos con `Range`.** `FileResponse` soporta peticiones por rangos (código 206), lo que permite **saltar a un minuto** en audio y video sin descargar todo.
- **Página resaltada.** `viewer.py` renderiza la página del PDF y marca con resaltador el texto del fragmento citado.
- **Historial de chats.** Tablas `chats` y `chat_messages` en PostgreSQL. Guardar un chat reemplaza sus mensajes dentro de una **transacción**, así un corte no deja un chat roto, y borrarlo elimina sus mensajes en cascada.
- **Videos que el navegador no reproduce.** Muchos videos de TikTok, WhatsApp o celular usan **HEVC (H.265)**: el navegador abre el `.mp4`, reproduce el audio y la imagen sale **negra**. `chatpdf/media.py` inspecciona el códec (PyAV), y si no es compatible crea en segundo plano una copia **H.264 + AAC** (con `faststart`, para empezar a verla al instante, y reducida a 1280 px). `GET /api/docs/{name}/playback` informa el estado (`original`, `converting`, `ready`, `error`) y `GET /api/files/{doc}` sirve la copia en lugar del original. El original no se modifica.
- **Frontend servido por el mismo backend.** `StaticFiles` sirve `web/dist`; `index.html` con `no-cache` y los archivos con hash con caché larga.

**Seguridad básica:**

- La **API key nunca se guarda en disco ni se devuelve** por la API; se lee del archivo `.env` (que `.gitignore` excluye) o se escribe en Ajustes (queda solo en memoria).
- **Protección contra *path traversal***: los nombres de archivo se validan y solo se sirven documentos que están indexados.
- `POST /api/kb/open` (abrir carpeta) solo acepta peticiones desde el propio equipo.
- Los chats se limpian: solo se guardan campos conocidos y roles válidos.

---

## 9. Frontend en detalle

**Arquitectura de React:** una *Single Page Application* (SPA). El navegador carga un solo HTML y React dibuja y actualiza todo en el cliente, hablando con la API.

| Componente | Función |
|---|---|
| `App.jsx` | **Estado global** (documentos, mensajes, trabajo en curso, visor, chats) y la lógica: enviar preguntas, guardar chats, abrir documentos |
| `Sidebar.jsx` | Panel izquierdo: pestañas Documentos / Chats, lista de documentos, aviso de archivos nuevos |
| `Chat.jsx` | Mensajes, citas clicables, ejemplos, caja de texto |
| `Viewer.jsx` | **Visor**: PDF con todas las páginas y resaltado, reproductor de audio y video con salto al minuto, imágenes, y la lista "texto leído" |
| `Sources.jsx` | Las fuentes de cada respuesta, con vista previa |
| `ChatList.jsx` | Historial agrupado por fecha (Hoy, Ayer…) |
| `AddDocsModal.jsx` | Ventana que explica las dos formas de agregar documentos |
| `SettingsModal.jsx` | Ajustes de modelos y API key |
| `JobPanel.jsx` | Barra de progreso con tiempo restante y botón de cancelar |
| `api.js` | Todas las llamadas al backend + el lector de streaming SSE + la conversión de citas en enlaces |

**Conceptos de React que aparecen:**

- **Componentes y *props***: cada pieza recibe datos y funciones del padre.
- **Estado (`useState`)**: lo que cambia y hace que la pantalla se redibuje (mensajes, documento abierto…).
- **Efectos (`useEffect`)**: cosas que pasan "a un lado" — consultar el progreso cada 0,7 s, guardar el chat cuando termina una respuesta, saltar al minuto o página de una cita.
- **`useRef`**: guardar valores sin redibujar (el reproductor de video, la conversación actual).
- **`useMemo` / `useCallback`**: evitar cálculos repetidos.

**Streaming en el cliente:** como `EventSource` solo permite GET, se usa `fetch` con `POST` y se lee el cuerpo con `ReadableStream`, separando los eventos por `\n\n`.

**Citas clicables:** `linkifyCitations()` transforma `[archivo, pág. 3]` en un enlace Markdown especial y `react-markdown` lo pinta como botón verde que abre el visor.

**Diseño:** modo claro/oscuro automático, panel lateral que se vuelve cajón en el celular, y el visor que ocupa toda la pantalla en pantallas pequeñas.

**Cómo llega al navegador:** Vite compila `web/src` a `web/dist` (≈ 300 KB, ≈ 94 KB comprimido). En desarrollo, `npm run dev` abre un servidor con recarga en caliente y reenvía `/api` al puerto 8000 (proxy).

---

## 10. Pruebas y resultados

**Pruebas automáticas** (`tests/`, 7 archivos): API completa con el cliente de pruebas de FastAPI; salto entre modelos usando un **servidor falso** que simula errores 404, 429 y tiempos de espera; carpeta (nuevo/modificado/borrado); caché y reanudación tras un fallo; búsqueda híbrida; preguntas globales. Se ejecutan sin necesitar los modelos (usan simulados).

**Prueba de calidad** (`tools/qa_check.py`): 34 preguntas sobre 10 archivos (PDFs con texto, con gráficos, escaneado, de 4 y 7 páginas, imagen, audio y videos). Verifica la respuesta **y** que cite el archivo y la página correctos.

| Modo | Respuestas correctas | Fuentes correctas | Tiempo por pregunta |
|---|---|---|---|
| **Gemini** (nube) | 35 / 35 | 35 / 35 | ~3 s |
| **Local** (`gemma3:4b` con Ollama) | 34 / 35 | 35 / 35 | ~14 s |
| **llama.cpp** (CPU, 4 documentos) | 11 / 11 | — | ~35 s |

*Esas cifras se midieron con 35 preguntas, antes de quitar la del video `big_buck_bunny_10s.mp4`.*

El único error del modo local fue añadir un riesgo de más al listar los de "probabilidad alta".

---

## 11. Limitaciones honestas (ten esto claro)

1. **`gemma3:4b` es un modelo pequeño.** Entiende imágenes sueltas, pero no video: la app saca fotogramas y los describe uno por uno, sin ver el movimiento. Puede inventar detalles (en una prueba dijo "gol" cuando el audio solo decía "ataca").
2. **Con Gemini tampoco "mira" el video completo:** usa el mismo método de fotogramas.
3. **El plan gratuito de Gemini tiene tope diario por modelo.** Si se agota, la app cae a modelos de respaldo más lentos.
4. **Corremos EmbeddingGemma 2** (multimodal). Ollama no embebe imágenes ni audio (ignora esos campos); llama.cpp sí, con el proyector multimodal (`--mmproj`).
5. **llama.cpp no puede leer el `embeddinggemma` (v1) que guarda Ollama** (formato propio): para embeddings con llama.cpp hace falta otro archivo GGUF.
6. En un equipo con GPU de 4 GB, **todo lo local es lento**: indexar 10 archivos tardó 450 s con el modelo local contra 121 s con Gemini.
7. El índice es una matriz en memoria: perfecto para cientos o miles de fragmentos, no para millones (ahí se usaría una base vectorial como Chroma, FAISS o Qdrant).

---

## 12. Preguntas probables del profesor, con respuesta

**1. ¿Qué es RAG y por qué no le damos todo el documento al modelo?**
RAG = buscar primero los fragmentos relevantes y dárselos al modelo para que responda. Los modelos tienen un contexto limitado y, cuanto más texto reciben, más lento y menos preciso es. Además así podemos **citar la fuente** y reducir las invenciones.

**2. ¿Qué es un embedding?**
Un vector de números (aquí 768) que representa el **significado** de un texto. Textos con significado parecido quedan cerca en ese espacio, aunque usen palabras distintas.

**3. ¿Cómo se mide qué tan parecidos son?**
Con **similitud coseno**: el ángulo entre dos vectores. Como los normalizamos, basta el producto punto con NumPy.

**4. ¿Por qué usan búsqueda híbrida y no solo embeddings?**
Los embeddings captan significado pero fallan con códigos y cifras exactas (`E-4471`). BM25 es lo contrario. Los combinamos con RRF y obtenemos lo mejor de ambos.

**5. ¿Qué es BM25?**
Un algoritmo clásico de búsqueda por palabras: puntúa más a los fragmentos que contienen las palabras de la pregunta, dando más peso a las palabras raras y penalizando textos muy largos.

**6. ¿Qué es RRF?**
Reciprocal Rank Fusion: une dos rankings sumando `1/(60+posición)` de cada uno. No requiere ajustar pesos.

**7. ¿Por qué FastAPI y no Flask o Django?**
FastAPI es asíncrono, valida los datos con Pydantic, genera documentación automática (`/docs`) y maneja bien el streaming. Django es muy grande para una API pequeña, y Flask no trae validación ni asincronía nativas.

**8. ¿Por qué React y no HTML con JavaScript normal?**
La interfaz tiene mucho estado que cambia (mensajes que llegan por pedazos, progreso, visor, historial). React redibuja solo lo que cambió, y los componentes se reutilizan.

**9. ¿Qué es Vite?**
La herramienta que compila el proyecto React para producción y da un servidor de desarrollo con recarga instantánea.

**10. ¿Qué es SSE y por qué no WebSockets?**
Server-Sent Events: el servidor envía eventos al navegador por una conexión HTTP abierta. Para el streaming de una respuesta, donde solo el servidor "habla", es más simple que WebSockets.

**11. ¿Qué es Ollama? ¿Y llama.cpp? ¿Cuál es la diferencia?**
llama.cpp es el **motor** que ejecuta modelos en tu PC. Ollama es una herramienta que lo usa por dentro y añade comodidades (descargar modelos, un servicio en segundo plano). En CHATDD se pueden usar ambos.

**12. ¿Qué significa "cuantizado Q4_K_M"?**
Que los pesos del modelo se guardan con menos bits (≈4) para que ocupe menos memoria, a cambio de perder muy poca calidad. En números: gemma3 de 3,9 B parámetros ocuparía unos 8 GB sin comprimir; cuantizado a Q4_K_M son ~2,4 GB (más ~0,8 GB del proyector de visión), y por eso cabe en una GPU de 4 GB.

**13. ¿Cómo entiende imágenes un modelo de lenguaje?**
Un **proyector de visión** (un codificador de imágenes, aquí de 420 M parámetros) convierte la imagen en vectores que el modelo trata como si fueran palabras.

**14. ¿Cómo analizan un video si el modelo no acepta video?**
Lo descomponemos: **Whisper** transcribe el audio y sacamos un fotograma cada ~8 s que describe el modelo de visión. Todo se guarda como texto con su minuto y se busca como cualquier documento.

**15. ¿Por qué hay un modelo para transcribir y otro para responder?**
Son tareas distintas. Whisper es un modelo especializado en voz a texto; gemma3 en conversar y entender imágenes; EmbeddingGemma en representar significado.

**16. ¿Qué pasa si el modelo se equivoca o inventa?**
El prompt le exige usar solo el contexto, citar con la etiqueta exacta y decir que no lo encuentra si no está. Además, el **visor** permite comprobar la respuesta contra el documento original, y la pestaña "Texto leído" muestra lo que la app entendió.

**17. ¿Cómo evitan reprocesar lo mismo?**
Una caché (SQLite) con clave = hash del archivo + modelo + prompt. Releer un archivo es instantáneo.

**18. ¿Cómo detecta la app archivos nuevos en la carpeta?**
Calcula el hash SHA-256 de cada archivo y lo compara con el guardado en el índice: nuevo, modificado o borrado.

**19. ¿Cómo se protege la API key?**
Vive en `.env` (excluido de GitHub) o solo en memoria; nunca se escribe en disco desde la interfaz ni se devuelve por la API.

**20. ¿Cómo probaron que funciona?**
Pruebas automáticas (7 archivos) y 35 preguntas con respuesta conocida sobre 10 archivos: Gemini 35/35, local 34/35, llama.cpp 11/11.

**21. ¿Qué cambiarían para producción o más datos?**
Una base vectorial (Chroma, FAISS, Qdrant), una cola de trabajos (Celery o RQ), autenticación de usuarios, una GPU mayor o modelos en la nube de pago.

**22. Un video de TikTok se veía negro. ¿Por qué y cómo lo resolvieron?**
Estaba en **HEVC (H.265)**, un códec que muchos navegadores en Windows no decodifican sin una extensión de pago: reproducen el audio pero no la imagen. La app inspecciona el códec de cada video y, si no es compatible, genera una copia **H.264** que cualquier navegador reproduce. Mientras se prepara muestra un aviso, y el original queda intacto.

**23. ¿Qué parte la hizo la IA y qué sabes tú?**
La IA escribió el código; yo sé qué tecnologías se usaron, para qué sirve cada una, cómo fluye una pregunta de principio a fin y cuáles son las limitaciones (secciones 2 a 11 de este documento).

---

## 13. Guion sugerido para mostrar en Google Meet (10–12 minutos)

**Antes de empezar (checklist, 10 minutos antes):**

- [ ] **Ollama abierto** (icono en la bandeja) y los modelos descargados (`ollama list` debe mostrar `gemma3:4b`) y el llama-server de embeddings respondiendo en `http://127.0.0.1:8081/health` (`run_web.bat` lo arranca).
- [ ] Ejecutar **`run_web.bat`** y abrir http://127.0.0.1:8000 en el navegador. Debe verse tu lista de documentos.
- [ ] **Probar una pregunta con el modelo que vayas a usar**. Si usas Gemini, comprobar que no se haya agotado el cupo diario.
- [ ] Cerrar programas pesados (el modelo local necesita RAM y GPU).
- [ ] Tener abiertas en otra pestaña: `README.md` y `docs/explicacion_tecnica.md`.
- [ ] **Plan B si falla internet:** usar el modo local con Ollama (no necesita internet).
- [ ] Si usas una API key: **revócala al terminar** (apareció en el chat con Claude).

**Orden de la demostración:**

1. **(1 min) Qué es:** "Una app que responde preguntas sobre PDFs, imágenes, audios y videos citando la fuente. Funciona local o con la nube."
2. **(2 min) Tecnologías:** React + Vite en el frontend; FastAPI + Uvicorn en el backend; Python 3.12; Ollama, llama.cpp, Gemini; Whisper; EmbeddingGemma. Mostrar el diagrama de la sección 3.
3. **(2 min) Base de conocimiento:** abrir "Agregar documentos", explicar las dos formas, mostrar la carpeta `base_conocimiento/` y cómo detecta archivos nuevos.
4. **(3 min) Preguntas y citas:** una sobre un **PDF con gráfico** ("¿Cuánto se vendió en cada trimestre?"), una sobre el **PDF escaneado**, una sobre el **video** y una global ("¿de qué trata el video?"). Pulsar una cita y mostrar el **visor** con la página resaltada y el reproductor saltando al minuto.
5. **(1 min) Ajustes:** mostrar el cambio entre Ollama, llama.cpp y la nube, y la cadena de modelos de respaldo.
6. **(1 min) Pruebas:** mencionar los 35 casos y los resultados.
7. **(1 min) Limitaciones** (sección 11) y mejoras futuras.

**Consejos:** pregunta primero algo que ya sabes que funciona; no improvises preguntas difíciles delante del profe; si una respuesta tarda con el modelo local, explica qué está pasando mientras espera (lee los fragmentos, el modelo escribe palabra por palabra).

---

## 14. Pendientes antes de entregar

El profesor pide dos enlaces; **ninguno está listo todavía**:

1. **Enlace de GitHub.** El proyecto ya trae `README.md`, `.gitignore` (excluye `.env`, `data/`, tus archivos y los binarios) y `.env.example`. Falta crear el repositorio con tu cuenta y subirlo.
2. **Enlace del video de YouTube** donde expliques el funcionamiento. El guion de la sección 13 sirve de base.
3. **Mostrar `python tools/mm_check.py`**: una pregunta escrita comparada directamente con una imagen y con un audio.
4. **Revocar la API key de Gemini** al terminar el proyecto (apareció en la conversación con Claude).

---

## 15. Glosario rápido

| Término | Significado |
|---|---|
| **LLM** | Modelo de lenguaje grande (gemma3, Gemini…). |
| **RAG** | Buscar fragmentos relevantes y dárselos al LLM para que responda. |
| **Embedding** | Vector numérico que representa el significado de un texto. |
| **Chunk** | Fragmento de texto de ~1200 caracteres. |
| **Similitud coseno** | Medida de parecido entre dos vectores. |
| **BM25** | Algoritmo de búsqueda por palabras. |
| **RRF** | Fusión de dos rankings. |
| **Multimodal** | Que entiende más de un tipo de dato (texto + imagen). |
| **Cuantización** | Comprimir un modelo usando menos bits por peso. |
| **GGUF** | Formato de archivo de modelos para llama.cpp. |
| **API REST** | Conjunto de URLs a las que el frontend pide datos. |
| **SSE** | Streaming de servidor a navegador por HTTP. |
| **SPA** | Aplicación de una sola página (React). |
| **ASGI** | Estándar de servidores web asíncronos de Python (Uvicorn). |
| **Hook** | Función de React (`useState`, `useEffect`…) para manejar estado y efectos. |
| **Bundler** | Herramienta que empaqueta el frontend (Vite). |
