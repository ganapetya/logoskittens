# NbAiLab nb-whisper-large on the Windows host GPU. Compose reaches it on port 8082.
$ErrorActionPreference = 'Continue'

if ($env:OS -ne 'Windows_NT') {
    Write-Error 'This launcher is for Windows. On macOS and Linux run ./scripts/host_whisper.sh'
    exit 1
}

$root = if ($env:WHISPER_HOME) { $env:WHISPER_HOME } else { Join-Path $env:LOCALAPPDATA 'logoskittens\whisper' }
$port = if ($env:WHISPER_PORT) { $env:WHISPER_PORT } else { '8082' }
$src = Join-Path $root 'src'
$model = Join-Path $root 'ggml-nb-whisper-large.bin'
$vad = Join-Path $root 'ggml-silero-v6.2.0.bin'
$controlPort = if ($env:WHISPER_CONTROL_PORT) { $env:WHISPER_CONTROL_PORT } else { '8083' }
$jobs = if ($env:NUMBER_OF_PROCESSORS) { $env:NUMBER_OF_PROCESSORS } else { '4' }

New-Item -ItemType Directory -Force -Path $root | Out-Null

foreach ($tool in @('cmake', 'git', 'curl.exe')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "host whisper needs $tool"
        exit 1
    }
}

function Test-CudaReady {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $false }
    if (-not (Get-Command nvcc -ErrorAction SilentlyContinue)) { return $false }
    & nvidia-smi *> $null
    return $LASTEXITCODE -eq 0
}

function Test-VulkanGpu {
    if (-not (Get-Command vulkaninfo -ErrorAction SilentlyContinue)) { return $false }
    $summary = & vulkaninfo --summary 2>&1 | Out-String
    return $summary -match 'PHYSICAL_DEVICE_TYPE_(DISCRETE|INTEGRATED)_GPU'
}

$probe = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$nvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
$nvcc = Get-Command nvcc -ErrorAction SilentlyContinue
$nvidiaOk = $false
if ($nvidia) {
    & nvidia-smi *> $null
    $nvidiaOk = $LASTEXITCODE -eq 0
}
if (Test-CudaReady) {
    $backend = 'cuda'
} else {
    if ($nvidiaOk -and -not $nvcc) {
        Write-Host 'NVIDIA GPU found; nvcc is not on PATH, so CUDA was not selected'
    }
    if (Test-VulkanGpu) {
        $backend = 'vulkan'
    } else {
        $backend = 'cpu'
    }
}
$ErrorActionPreference = $probe

Write-Host "whisper backend: $backend"
if ($backend -eq 'cpu') {
    Write-Host 'GPU is not in use'
}

$build = Join-Path $src "build-$backend"
$server = Join-Path $build 'bin\Release\whisper-server.exe'

if (-not (Test-Path $server)) {
    if (-not (Test-Path (Join-Path $src '.git'))) {
        & git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git $src
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    $cmakeArgs = @(
        '-S', $src,
        '-B', $build,
        '-G', 'Visual Studio 17 2022',
        '-A', 'x64',
        '-DWHISPER_BUILD_SERVER=ON'
    )
    if ($backend -eq 'cuda') {
        $cmakeArgs += '-DGGML_CUDA=ON'
    } elseif ($backend -eq 'vulkan') {
        $cmakeArgs += '-DGGML_VULKAN=ON'
    }
    & cmake @cmakeArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & cmake --build $build --config Release -j $jobs --target whisper-server
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Test-Path $server)) {
    Write-Error "whisper-server.exe was not produced at $server"
    exit 1
}

if (-not (Test-Path $model)) {
    $partial = "$model.partial"
    & curl.exe -L --fail -o $partial 'https://huggingface.co/NbAiLab/nb-whisper-large/resolve/main/ggml-model.bin'
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -Force $partial -ErrorAction SilentlyContinue
        exit $LASTEXITCODE
    }
    Move-Item -Force $partial $model
}

$python = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { 'python3' }
$recognitionScript = Join-Path $PSScriptRoot 'recognition_env.py'
$recognitionLines = & $python $recognitionScript --powershell
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
foreach ($line in $recognitionLines) {
    if ($line -match '^\$(\w+) = ''([^'']*)''$') {
        Set-Variable -Name $Matches[1] -Value $Matches[2]
    }
}
if (-not $RecognitionFile) {
    Write-Error 'recognition config did not name a model'
    exit 1
}
$english = Join-Path $root $RecognitionFile

if (-not (Test-Path $english)) {
    $partial = "$english.partial"
    & curl.exe -L --fail -o $partial $RecognitionUrl
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -Force $partial -ErrorAction SilentlyContinue
        exit $LASTEXITCODE
    }
    Move-Item -Force $partial $english
}

if (-not (Test-Path $vad)) {
    & curl.exe -L --fail -o $vad 'https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin'
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -Force $vad -ErrorAction SilentlyContinue
        exit $LASTEXITCODE
    }
}

# Other live packs (Ukrainian, German) name their weight and its url in config/languages.
$extraArgs = @()
$extraLines = & $python (Join-Path $PSScriptRoot 'extra_weights.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
foreach ($line in $extraLines) {
    $parts = "$line".Trim() -split '\s+'
    if ($parts.Count -ne 3) { continue }
    $weight = Join-Path $root $parts[1]
    if (-not (Test-Path $weight)) {
        Write-Host "downloading $($parts[1]) for $($parts[0])"
        $partial = "$weight.partial"
        & curl.exe -L --fail -o $partial $parts[2]
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -Force $partial -ErrorAction SilentlyContinue
            exit $LASTEXITCODE
        }
        Move-Item -Force $partial $weight
    }
    $extraArgs += @('--model', "$($parts[0])=$weight")
}

$supervisor = Join-Path $PSScriptRoot 'whisper_supervisor.py'
& $python $supervisor @extraArgs --server $server --nb-model $model --en-model $english --en-name $RecognitionModel --vad $vad --port $port --control-port $controlPort --threads $RecognitionThreads
exit $LASTEXITCODE
