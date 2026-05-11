param(
  [Parameter(Mandatory=$true)]
  [string]$ComfyUIDir,
  [int]$Port = 8188
)

Set-Location $ComfyUIDir

# Adjust python executable / venv activation to your setup.
Start-Process -FilePath "python" -ArgumentList @("main.py","--listen","0.0.0.0","--port",$Port) -WindowStyle Hidden

Write-Host "ComfyUI started."
Write-Host ("URL: http://127.0.0.1:{0}" -f $Port)
