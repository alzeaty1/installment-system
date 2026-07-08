$ErrorActionPreference = "Stop"

$appDir = Split-Path -Parent $PSCommandPath
$projectRoot = Split-Path -Parent $appDir
$waitress = Join-Path $projectRoot "venv\Scripts\waitress-serve.exe"
$python = Join-Path $projectRoot "venv\Scripts\python.exe"
$url = "http://127.0.0.1:8000/"
$outLog = Join-Path $appDir "server-desktop.out.log"
$errLog = Join-Path $appDir "server-desktop.err.log"

function Test-PortOpen {
    param([string] $HostName, [int] $Port)

    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(300)
        if ($connected) {
            $client.EndConnect($async)
        }
        $client.Close()
        return $connected
    } catch {
        return $false
    }
}

if (-not (Test-PortOpen -HostName "127.0.0.1" -Port 8000)) {
    if (Test-Path $waitress) {
        Start-Process `
            -FilePath $waitress `
            -ArgumentList @("--listen=127.0.0.1:8000", "installments.wsgi:application") `
            -WorkingDirectory $appDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput $outLog `
            -RedirectStandardError $errLog
    } elseif (Test-Path $python) {
        Start-Process `
            -FilePath $python `
            -ArgumentList @("manage.py", "runserver", "127.0.0.1:8000", "--noreload") `
            -WorkingDirectory $appDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput $outLog `
            -RedirectStandardError $errLog
    } else {
        throw "Python virtual environment was not found."
    }

    for ($i = 0; $i -lt 40; $i++) {
        if (Test-PortOpen -HostName "127.0.0.1" -Port 8000) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
}

Start-Process $url
