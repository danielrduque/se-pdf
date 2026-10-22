<#
Arranca los llama-server (llama.cpp) que usa CHATDD. Verificado con llama.cpp b11763 en Windows.

  powershell -File tools\llamacpp_start.ps1            # EmbeddingGemma 2 multimodal (puerto 8081): texto, imágenes y audio -> vectores
  powershell -File tools\llamacpp_start.ps1 -Chat      # además, el chat + visión con gemma3:4b (puerto 8080)
  powershell -File tools\llamacpp_start.ps1 -Chat -Gpu # el chat en la GPU (-ngl 99); los embeddings siempre van en CPU
  powershell -File tools\llamacpp_start.ps1 -IfDown    # solo arranca lo que no esté respondiendo (lo usan run.bat y run_web.bat)
  powershell -File tools\llamacpp_start.ps1 -Stop      # apagar los servidores

Requisitos:
  - llama.cpp (llama-bNNNN-bin-win-cpu-x64.zip de https://github.com/ggml-org/llama.cpp/releases) descomprimido en tools\llama.cpp\
    (no se sube a git). Hace falta una versión >= b11658, que ya trae la arquitectura `gemma-embedding2`.
  - Los GGUF de EmbeddingGemma 2 y su proyector multimodal en tools\models\ (python tools\download_models.py, ~870 MB).
  - Para -Chat: ollama pull gemma3:4b (se reutilizan sus archivos, no se descarga otra vez).
Pasa siempre --port: desde la v0.7 el puerto por defecto ya no es el 8080.
#>
param([switch]$Chat, [switch]$Gpu, [switch]$IfDown, [switch]$Stop)

$root = Split-Path $PSScriptRoot -Parent
$exe = Join-Path $root "tools\llama.cpp\llama-server.exe"
if ($Stop) { Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force; "llama-server apagado"; return }
if (-not (Test-Path $exe)) { throw "Falta $exe. Descarga llama.cpp (ver instrucciones arriba)." }

function Up($port) { try { (Invoke-WebRequest "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $false } }

# --- embeddings: EmbeddingGemma 2 + proyector multimodal (imágenes y audio), en CPU y con contexto de 8192 tokens.
# -b/-ub 8192: un embedding no se puede partir en lotes; con el valor por defecto (512) falla todo audio de más de ~25 s (25 tokens por segundo)
if (-not ($IfDown -and (Up 8081))) {
    $emb = Join-Path $root "tools\models\embeddinggemma-2-Q8_0.gguf"
    $mm = Join-Path $root "tools\models\mmproj-embeddinggemma-2-Q8_0.gguf"
    foreach ($f in $emb, $mm) { if (-not (Test-Path $f)) { throw "No encuentro ${f}. Ejecuta antes: python tools\download_models.py" } }
    Start-Process $exe -WindowStyle Hidden -ArgumentList @("-m", "`"$emb`"", "--mmproj", "`"$mm`"", "--embeddings", "--host", "127.0.0.1", "--port", "8081", "-c", "8192", "-b", "8192", "-ub", "8192", "-ngl", "0", "--alias", "embeddinggemma-2")
    "embeddings (EmbeddingGemma 2, texto + imagen + audio): http://127.0.0.1:8081/v1"
}

# --- chat + visión: gemma3:4b con los archivos que ya descargó Ollama
if ($Chat -and -not ($IfDown -and (Up 8080))) {
    $models = Join-Path $env:USERPROFILE ".ollama\models"
    function Blob($name, $mediaType) {
        $manifest = Get-Content (Join-Path $models "manifests\registry.ollama.ai\library\$name") -Raw | ConvertFrom-Json
        $digest = ($manifest.layers | Where-Object { $_.mediaType -eq $mediaType }).digest
        Join-Path $models ("blobs\" + $digest.Replace(":", "-"))
    }
    $gemma = Blob "gemma3\4b" "application/vnd.ollama.image.model"
    $proj = Blob "gemma3\4b" "application/vnd.ollama.image.projector"
    foreach ($f in $gemma, $proj) { if (-not (Test-Path $f)) { throw "No encuentro ${f}. Ejecuta antes: ollama pull gemma3:4b" } }
    $ngl = if ($Gpu) { "99" } else { "0" }
    Start-Process $exe -WindowStyle Hidden -ArgumentList @("-m", "`"$gemma`"", "--mmproj", "`"$proj`"", "--host", "127.0.0.1", "--port", "8080", "-c", "4096", "-ngl", $ngl, "--alias", "gemma3")
    "chat + visión: http://127.0.0.1:8080/v1  (modelo: gemma3)"
}
"Tardan unos segundos en cargar. En CHATDD: embeddings -> proveedor «llama.cpp», modelo «embeddinggemma-2», URL http://127.0.0.1:8081/v1."
