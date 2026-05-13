# Sincroniza publicados desde los 3090 a este PC
$PLINK = "C:\Program Files\PuTTY\plink.exe"
$PSCP  = "C:\Program Files\PuTTY\pscp.exe"
$LOG   = "E:\sync.log"

$SOURCES = @(
    @{
        Label     = "inspiring"
        Remote    = "andreu@192.168.1.107"
        RemoteDir = "/home/andreu/inspiring-factory/publicados/"
        LocalDir  = "E:\INSPIRING PUBLICADOS\"
    },
    @{
        Label     = "misterios"
        Remote    = "andreu@100.108.14.124"
        RemoteDir = "/home/andreu/inspiring-factory/publicados/mystery/"
        LocalDir  = "E:\MISTERIOS PUBLICADOS\"
    }
)

Add-Content $LOG "$(Get-Date -Format 'yyyy-MM-dd HH:mm') --- Sync start ---"

foreach ($src in $SOURCES) {
    New-Item -ItemType Directory -Force -Path $src.LocalDir | Out-Null
    $files = & $PLINK -pw 2611 -batch $src.Remote "ls $($src.RemoteDir)*.mp4 2>/dev/null"
    if (-not $files) {
        Add-Content $LOG "$(Get-Date -Format 'yyyy-MM-dd HH:mm') [$($src.Label)] Nada que sincronizar"
        continue
    }
    foreach ($file in $files) {
        $filename = Split-Path $file -Leaf
        $dest = Join-Path $src.LocalDir $filename
        if (-not (Test-Path $dest)) {
            Add-Content $LOG "$(Get-Date -Format 'yyyy-MM-dd HH:mm') [$($src.Label)] Descargando $filename..."
            & $PSCP -pw 2611 -batch "$($src.Remote):${file}" $dest
            if ($LASTEXITCODE -eq 0) {
                Add-Content $LOG "$(Get-Date -Format 'yyyy-MM-dd HH:mm') [$($src.Label)] OK: $filename"
                & $PLINK -pw 2611 -batch $src.Remote "rm '$file'"
            } else {
                Add-Content $LOG "$(Get-Date -Format 'yyyy-MM-dd HH:mm') [$($src.Label)] ERROR: $filename"
            }
        }
    }
}

Add-Content $LOG "$(Get-Date -Format 'yyyy-MM-dd HH:mm') --- Sync done ---"
