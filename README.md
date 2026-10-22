# CHATDD

Base de conocimiento multimodal con consulta semántica: PDFs (con imágenes), audios y videos cortos, imágenes y texto.
Se pregunta en lenguaje natural desde una app web y cada respuesta cita su fuente (página del PDF resaltada, o audio/video
en el minuto exacto).

Funciona 100 % local, o con modelos en la nube por API si se quiere.

## Requisitos del proyecto

| Requisito | Dónde está |
|---|---|
| Base de conocimiento en una carpeta (audios, videos cortos, PDFs) | `base_conocimiento/` + botón **Sincronizar** |
| App web con consulta semántica | `app.py` (Streamlit) |
| PDFs con imágenes, preguntas sobre texto e imágenes | Páginas con imágenes/escaneadas → modelo de visión |
| Embeddings con EmbeddingGemma 2 | **EmbeddingGemma 2** (`ggml-org/embeddinggemma-2-GGUF`, 6-oct-2026) **ejecutado con llama.cpp**: texto, imágenes y audio en el mismo espacio de vectores (ver «Búsqueda multimodal») |
| llama.cpp | Corre los embeddings (EmbeddingGemma 2, puerto 8081) y, si quieres, el chat y la visión (proveedor «llama.cpp», puerto 8080) |
| Modelos locales o en la nube por API (pago o gratis) | Proveedor "API en la nube" (cualquier API compatible con OpenAI) |

## Cómo funciona

| Tipo | Procesamiento |
|---|---|
| PDF | Texto con PyMuPDF; páginas escaneadas o con imágenes/gráficos → render + modelo de visión |
| Imagen | El modelo de visión transcribe el texto y describe la imagen |
| Audio | `faster-whisper` (local) con marcas de tiempo |
| Video | Whisper del audio + un frame cada ~8 s descrito por el modelo de visión (se omiten los frames casi idénticos) |

Todo se convierte en fragmentos de texto → embeddings → índice en PostgreSQL. Las imágenes y el audio, además, se embeben **directamente** (ver «Búsqueda multimodal»). Al preguntar:
búsqueda híbrida en PostgreSQL (pgvector + texto completo, fusión RRF) → opcionalmente reranking con el LLM → el LLM responde citando fuentes.
Lo lento (visión, transcripción) se guarda en caché por contenido del archivo: reindexar es instantáneo y un proceso
cortado continúa donde quedó.

## Instalación

1. Python 3.12, [Ollama](https://ollama.com/download/windows) y [Docker Desktop](https://www.docker.com/products/docker-desktop/) (para la base de datos).
2. Modelos (una sola vez; `setup.bat` los descarga y reintenta si se corta):
   ```
   ollama pull embeddinggemma-2:740m
   ollama pull gemma3:4b
   ```
3. Dependencias:
   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
4. EmbeddingGemma 2 con llama.cpp (~870 MB: el modelo de texto y su proyector de imágenes y audio):
   ```
   python tools\download_models.py
   powershell -File tools\llamacpp_start.ps1
   ```
   Necesita llama.cpp en `tools\llama.cpp\` (versión b11658 o más nueva; ver la sección «llama.cpp»). `run_web.bat` y `run.bat` arrancan ese servidor solos si no está activo (puerto 8081, solo local).
5. Base de datos (PostgreSQL 17 + pgvector en un contenedor, puerto 5434 solo local). Copia `.env.example` como `.env`, pon una
   `POSTGRES_PASSWORD` y arranca:
   ```
   docker compose up -d --wait db
   ```
   `run.bat` y `run_web.bat` ya lo hacen solos. Los datos viven en el volumen `chatdd_pgdata` (sobreviven a reinicios).
   Si venías de la versión con archivos (`data/vectors.npy` y `data/chats/*.json`), pasa el índice y los chats con `python tools/migrate_to_postgres.py`.
   Utilidades: `python tools/db.py status` (qué hay indexado) y `python tools/db.py clean` (borra los esquemas temporales de las pruebas).
6. Ejecutar, a elegir (las dos usan el mismo núcleo y el mismo índice):
   - **App web React + FastAPI:** doble clic en `run_web.bat` y abrir http://127.0.0.1:8000 (la primera vez compila el frontend: requiere Node 20+).
   - **Interfaz Streamlit:** doble clic en `run.bat` y abrir http://localhost:8501

## Uso

- **Base de conocimiento:** copia tus archivos a `base_conocimiento/` y pulsa **Sincronizar**. Indexa lo nuevo,
  reindexa lo que cambió y quita del índice lo que borraste de la carpeta.
- **Subir archivos** sueltos desde la barra lateral.
- Pregunta en el chat; abre **Fuentes** para ver la evidencia.
- **Resumir** hace un resumen de todo un documento.

## App web: React + FastAPI

```
web/                  frontend React (Vite): chat con streaming, subida con progreso, base de conocimiento, ajustes de modelos
server/main.py        API REST + SSE (FastAPI); también sirve el frontend compilado
chatpdf/              núcleo (modelos, indexado, búsqueda, caché) compartido con la interfaz Streamlit
```

**Visor en pantalla dividida:** pulsa el nombre de un documento (o el botón «Abrir en el visor» de una fuente, o la cita `[archivo, pág. 3]`
de una respuesta) y la pantalla se parte en dos: el PDF (con la página citada resaltada), la imagen, el audio o el video a un lado y el chat al otro.
La pestaña «Texto leído» y la lista bajo el reproductor muestran lo que la app entendió de cada página, minuto o escena, para comprobarlo.

**Videos de TikTok, WhatsApp o celular:** muchos vienen en HEVC (H.265), que varios navegadores no saben mostrar (se oye el audio pero la imagen sale negra).
La app lo detecta y crea sola, en segundo plano, una copia H.264 + AAC en `data/previews/` (el original no se toca). El visor muestra un aviso mientras se prepara
y luego reproduce la copia. Los `.avi` y `.mkv` se tratan igual.

**Historial de chats:** cada conversación se guarda sola al terminar cada respuesta (en PostgreSQL: tablas `chats` y `chat_messages`). La pestaña
«Chats» del panel lateral los lista por fecha; se pueden reabrir (con sus fuentes y citas), renombrar y borrar, y «＋ Nuevo chat» empieza uno en blanco.


Compilar el frontend (una vez, o tras cambiarlo): `cd web && npm install && npm run build`. Para desarrollar con recarga en caliente:
`uvicorn server.main:app --port 8000` y, en otra terminal, `cd web && npm run dev` (http://localhost:5173, redirige `/api` al puerto 8000).

| Endpoint | Qué hace |
|---|---|
| `GET /api/status` · `POST /api/settings` | Estado de los modelos y documentos · cambiar proveedor, modelo y API key (la clave no se guarda en disco) |
| `POST /api/upload` · `POST /api/kb/sync` | Indexar archivos subidos o la carpeta, como trabajo en segundo plano |
| `GET /api/jobs/{id}` · `POST /api/jobs/{id}/cancel` | Progreso con tiempo restante · cancelar |
| `POST /api/chat` | Pregunta con streaming (SSE): primero las fuentes, luego los tokens |
| `GET /api/page/{doc}/{página}?chunk=id` | Página del PDF con el fragmento resaltado |
| `GET /api/files/{doc}` | Archivo original (admite `Range`, para saltar al minuto en audio y video) |
| `POST /api/summarize` · `GET /api/kb` · `DELETE /api/docs/{name}` | Resumen · estado de la carpeta · quitar del índice |

## Elegir modelos (⚙️ Modelos en la barra lateral)

El chat/visión y los embeddings se eligen por separado.

### Ollama (por defecto)
Chat `gemma3:4b` (Ollama) y embeddings **EmbeddingGemma 2 en llama.cpp** (proveedor «llama.cpp», modelo `embeddinggemma-2`, URL `http://127.0.0.1:8081/v1`). Si cambias de modelo de embeddings, ejecuta `python tools/reembed.py` para recalcular el índice sin releer los archivos.

### Búsqueda multimodal (EmbeddingGemma 2)
EmbeddingGemma 2 pone texto, imágenes, audio y video en **el mismo espacio de 768 dimensiones**. Por eso, además del texto de cada fragmento (descripción, transcripción), la app guarda el **vector de la propia imagen o del propio audio**:

| Fragmento | Lo que se embebe directamente |
|---|---|
| Página de PDF con gráficos o escaneada, imagen suelta | la imagen (`{"image": …}`) |
| Fotograma de un video | el fotograma |
| Tramo de audio (o pista de audio de un video) | la onda de audio a 16 kHz (`{"audio": …}`) |

Al preguntar, **el texto manda**: RRF del significado del texto y de las palabras exactas. Además, hasta 1 de los 6 resultados (`MM_SLOTS`) puede venir de que la pregunta coincida directamente con el vector de una imagen o un audio (similitud mayor a `MM_TAU`, 0,68). Así se puede encontrar un cronograma o un tramo de voz aunque su descripción o transcripción no mencionen lo que preguntas, y en las fuentes aparece la etiqueta «por la imagen» o «por el audio». Se limita a una ranura a propósito: la similitud pregunta↔imagen es alta aunque no tengan nada que ver (0,5–0,78), y al probar un ranking multimedia completo la fuente correcta de las preguntas de texto bajó de 25/25 a 16/25 (`python tools/qa_check.py --retrieval-only` lo vigila).

- **Cómo se llama:** el `llama-server` de embeddings se arranca con `--embeddings --mmproj` y la app le manda a `/v1/embeddings` entradas `{"content": [{"type": "image_url", …}]}` o `{"type": "input_audio", …}` (`chatpdf/llm.py`, `embed_media`). Solo hace falta que el servidor anuncie los módulos `vision` y `audio` en `/props`; si no (arrancado sin `--mmproj`), la app sigue funcionando solo con texto.
- **Por qué llama.cpp y no Ollama:** Ollama ignora las imágenes y el audio que se le pasan a un modelo de embeddings (el vector sale idéntico al de solo texto). llama.cpp sí los procesa. Comprobado: sus vectores de texto coinciden con los del modelo original en PyTorch (similitud 0,9999) y los de imagen casi (0,97).
- **CPU, no GPU:** la GTX 1650 (4 GB) ya la usa el modelo de chat. En CPU una página tarda ~5–6 s y un tramo de audio de 18 s, ~3 s.
- **Comprobarlo:** `python tools/mm_check.py` embebe imágenes y audio reales y muestra que la frase correcta queda primera.

### llama.cpp
Verificado con llama.cpp **b11763** (`llama-server`) en Windows: chat, streaming, lectura de imágenes y búsqueda de respuestas (11 de 11 correctas).

1. Descarga `llama-bNNNN-bin-win-cpu-x64.zip` de https://github.com/ggml-org/llama.cpp/releases y descomprímelo en `tools\llama.cpp\` (no se sube a git; pesa ~23 MB).
2. Arranca el servidor: `powershell -File tools\llamacpp_start.ps1`. Reutiliza los archivos de `gemma3:4b` que Ollama ya descargó, así que no hay que bajar el modelo otra vez.
   Sin ese atajo: `llama-server -hf ggml-org/gemma-3-4b-it-GGUF --port 8080 -c 4096` (descarga ~3,3 GB; el proyector de visión va incluido).
3. En la app: **⚙️ Ajustes → ¿Dónde corre? → llama.cpp (local)**, modelo `gemma3`.

`tools\llamacpp_start.ps1` arranca siempre el servidor de **embeddings** (EmbeddingGemma 2 + su proyector, puerto 8081) y, con `-Chat`, también el del chat (gemma3, puerto 8080). `-IfDown` solo arranca lo que no responda y `-Stop` apaga todo.

Detalles que conviene saber:
- Pasa siempre `--port`: desde llama.cpp v0.7 el puerto por defecto cambió.
- Por defecto corre en **CPU** (cada respuesta tarda ~35 s en una GTX 1650 de 4 GB sin GPU). Con `-Gpu` usa la tarjeta gráfica, y conviene cerrar Ollama para que no compitan por la VRAM.
- **EmbeddingGemma 2** necesita llama.cpp **b11658 o más nueva** (arquitectura `gemma-embedding2`); `python tools/download_models.py` baja el GGUF oficial y su proyector. El `embeddinggemma` (v1) que guarda Ollama no lo lee llama.cpp (formato propio).
- Usa `127.0.0.1` y no `localhost`: en Windows `localhost` puede añadir ~2 s a cada llamada.

### API en la nube
Elige **API en la nube**, escribe el modelo y la API key. La clave se lee del archivo `.env` (copia `.env.example` como `.env`
y pon `CHATPDF_API_KEY=...`; `.env` no se sube a GitHub) o de la variable de entorno del mismo nombre. La interfaz nunca la guarda.

**Varios modelos con respaldo:** en el campo de modelo del chat puedes poner varios separados por coma
(`a, b, c`). Se prueban en orden y se salta al siguiente si uno falla (modelo inexistente, límite de uso, error del servidor
o sin respuesta). Un modelo que falló queda en pausa un rato para no perder tiempo reintentándolo. Los embeddings usan solo uno.
Ejemplo con Gemini (plan gratuito):
```
URL:    https://generativelanguage.googleapis.com/v1beta/openai/
Modelo: gemini-3-flash-preview, gemini-3.6-flash, gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite
```
Los nombres de modelos de Google cambian y algunos dejan de estar disponibles; por eso la cadena de respaldo.
Sirve cualquier API compatible con OpenAI cambiando la URL: OpenAI, Groq, OpenRouter, Gemini
(`https://generativelanguage.googleapis.com/v1beta/openai/`), DeepSeek, Together…
Con la nube, tus preguntas y el contenido de los archivos salen de tu PC.

> Si cambias de modelo de embeddings, el índice existente deja de ser válido: borra los documentos y vuelve a indexar
> (la app lo avisa).

## Base de ejemplo para probar

`pip install -r requirements-dev.txt` y luego `python tools/make_sample_kb.py` genera en `base_conocimiento/` una empresa ficticia
(Agroandina): 5 PDFs con diseño corporativo (portada, encabezado y pie, tablas, gráficos; de 3 a 7 páginas), un acta escaneada
(solo imagen), un organigrama, un audio y un video con narración, todo coherente entre sí. El generador verifica solo que cada dato
quede en la página prevista y que las cifras "solo en el gráfico" no estén en el texto. Sincroniza la carpeta y
prueba las preguntas de [docs/preguntas_de_prueba.md](docs/preguntas_de_prueba.md). `python tools/qa_check.py` las hace solas
y comprueba las respuestas. (El audio y el video usan las voces de Windows; en otros sistemas solo se generan PDFs e imagen.)

## Pruebas

```
.venv\Scripts\python tests\test_pipeline.py
.venv\Scripts\python tests\test_retrieval.py
.venv\Scripts\python tests\test_cache.py
.venv\Scripts\python tests\test_kb.py
.venv\Scripts\python tests\test_fallback.py
```
No necesitan Ollama (usan modelos simulados). Ajustes finos en `chatpdf/config.py`.

## Estructura

```
app.py                interfaz web
chatpdf/config.py     ajustes y proveedores
chatpdf/llm.py        acceso a modelos (Ollama / llama.cpp / nube)
chatpdf/ingest.py     PDF, imagen, audio y video → fragmentos
chatpdf/store.py      índice en PostgreSQL + pgvector (vectores, texto completo, fusión RRF)
chatpdf/rag.py        indexado, sincronización, búsqueda, reranking, resumen
chatpdf/viewer.py     página resaltada y salto al minuto
chatpdf/cache.py      caché de visión y transcripciones
```
