# Requires Docker Desktop with NVIDIA Container Toolkit support.
param(
    [string]$Model = "Qwen/Qwen2.5-1.5B-Instruct",
    [int]$Port = 8001,
    [string]$Image = "vllm/vllm-openai:latest",
    [string]$ContainerName = "vllm-openai",
    [string]$HfToken = "",
    [string]$CacheDir = "$env:USERPROFILE\.cache\huggingface"
)

$ErrorActionPreference = "Stop"

Write-Host "Pulling image: $Image"
docker pull $Image

$envArgs = @()
if ($HfToken) {
    $envArgs += @("-e", "HUGGING_FACE_HUB_TOKEN=$HfToken")
}

if (-not (Test-Path $CacheDir)) {
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
}

Write-Host "Removing old container if it exists: $ContainerName"
docker rm -f $ContainerName 2>$null | Out-Null

Write-Host "Starting vLLM on port $Port with model $Model"
docker run `
  --runtime nvidia `
  --gpus all `
  --name $ContainerName `
  -p "${Port}:8000" `
  -v "${CacheDir}:/root/.cache/huggingface" `
  @envArgs `
  $Image `
  --model $Model
