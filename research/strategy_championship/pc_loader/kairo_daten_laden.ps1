# Kairo Research – Rohdaten über den eigenen PC laden (SEC blockiert GitHub Actions / Cloud-IPs).
# Windows-Bordmittel: PowerShell 5.1 + curl.exe (ab Windows 10). Keine Installation nötig, alles kostenlos.
# Start über kairo_daten_laden.bat (Doppelklick). Abbrechen und erneut starten ist jederzeit möglich.
# Ergebnis: Ordner „kairo_daten“ neben diesem Skript; Fortschritt in kairo_daten\log.txt
#
#  1. SEC companyfacts.zip  (XBRL-Bilanzen mit Einreichungsdatum)
#  2. SEC submissions.zip   (Einreichungen inkl. 8-K Item 2.02 = Quartalszahlen)
#  3. SEC Insider-Datensätze Form 3/4/5, quartalsweise ab 2006 Q1
#  4. Dukascopy-Stundenkerzen (BID, Rohformat .bi5) für US-Aktien (…USUSD) und DE-Aktien (…DEEUR), ab 2017 (frühere Jahre gibt es bei Dukascopy für Aktien nicht)
# Jede SEC-Anfrage trägt einen User-Agent mit Kontaktangabe und bleibt deutlich unter 10 Anfragen/Sekunde.
# Dateien > 380 MB werden zusätzlich in Teile zerlegt (Ordner upload\), damit sie übertragen werden können.

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$UA_SEC  = 'Kairo-Research (privat, nicht kommerziell) gregor.omonsky@gmx.de'
$UA_DUKA = 'Mozilla/5.0 (Kairo-Research; gregor.omonsky@gmx.de)'
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$OUT  = Join-Path $HERE 'kairo_daten'
$PART = 380MB
$DUKA_START = 2017   # Dukascopy-Aktien-CFDs beginnen im Jan. 2017 (2015/16: 404)
$CURL = Join-Path $env:SystemRoot 'System32\curl.exe'
New-Item -ItemType Directory -Force -Path $OUT, "$OUT\sec\form345", "$OUT\dukascopy", "$OUT\upload" | Out-Null
$LOG = Join-Path $OUT 'log.txt'

function Log($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $m; Write-Host $l; Add-Content -Path $LOG -Value $l -Encoding UTF8 }
function Status($m) { Set-Content -Path (Join-Path $OUT 'status.txt') -Value ((Get-Date -Format s) + ' ' + $m) -Encoding UTF8 }

function Split-ForUpload($path) {
    $f = Get-Item $path
    if ($f.Length -le $PART) { return }
    $n = [int][math]::Ceiling($f.Length / $PART)
    $last = Join-Path "$OUT\upload" ($f.Name + '.part' + ([int]($n - 1)).ToString('00'))
    if (Test-Path $last) { return }
    Log "   zerlege $($f.Name) ($([math]::Round($f.Length/1MB)) MB) in $n Teile"
    $in = [System.IO.File]::OpenRead($f.FullName)
    $buf = New-Object byte[] (4MB)
    for ([int]$i = 0; $i -lt $n; $i++) {
        $o = [System.IO.File]::Create((Join-Path "$OUT\upload" ($f.Name + '.part' + $i.ToString('00'))))
        $left = [long]$PART
        while ($left -gt 0) {
            $r = $in.Read($buf, 0, [int][math]::Min($buf.Length, $left))
            if ($r -le 0) { break }
            $o.Write($buf, 0, $r); $left -= $r
        }
        $o.Close()
    }
    $in.Close()
}

function Test-Zip($path) {
    try { Add-Type -AssemblyName System.IO.Compression.FileSystem; $z = [System.IO.Compression.ZipFile]::OpenRead($path); $c = $z.Entries.Count; $z.Dispose(); return $c -gt 0 } catch { return $false }
}

# ------------------------------------------------------------------ SEC Bulk
function Sec-Bulk {
    foreach ($it in @(
        @('companyfacts.zip', 'https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip'),
        @('submissions.zip',  'https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip'))) {
        $p = Join-Path "$OUT\sec" $it[0]
        if ((Test-Path $p) -and (Test-Zip $p)) { Log "SEC $($it[0]): vorhanden, übersprungen"; Split-ForUpload $p; continue }
        Log "SEC $($it[0]): lade … (über 1 GB, je nach Leitung 5–30 Min.)"
        Status "SEC $($it[0])"
        & $CURL -sS -L -A $UA_SEC --retry 5 --retry-delay 10 -C - -o "$p.part" $it[1]
        $code = $LASTEXITCODE
        if ($code -eq 0 -and (Test-Zip "$p.part")) {
            Move-Item -Force "$p.part" $p
            Log "SEC $($it[0]): fertig, $([math]::Round((Get-Item $p).Length/1MB)) MB"
            Split-ForUpload $p
        } else {
            $head = ''; if (Test-Path "$p.part") { $head = (Get-Content "$p.part" -TotalCount 3 -ErrorAction SilentlyContinue) -join ' ' }
            Log "!! SEC $($it[0]) fehlgeschlagen (curl $code) $head"
        }
        Start-Sleep -Seconds 1
    }
}

# ------------------------------------------------------------------ SEC Insider (Form 3/4/5)
function Sec-Insider {
    $base = 'https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/'
    $ok = 0; $miss = 0
    $today = Get-Date
    for ($y = 2006; $y -le $today.Year; $y++) {
        for ($q = 1; $q -le 4; $q++) {
            if ((Get-Date -Year $y -Month (3 * $q) -Day 1) -gt $today) { break }
            $name = "${y}q${q}_form345.zip"
            $p = Join-Path "$OUT\sec\form345" $name
            if ((Test-Path $p) -and (Test-Zip $p)) { $ok++; continue }
            Status "SEC Insider $name"
            & $CURL -sS -L -f -A $UA_SEC --retry 4 --retry-delay 5 -o "$p.part" ($base + $name)
            if ($LASTEXITCODE -eq 0 -and (Test-Zip "$p.part")) {
                Move-Item -Force "$p.part" $p; $ok++
                Log "SEC Insider ${name}: $([math]::Round((Get-Item $p).Length/1MB,1)) MB"
            } else {
                Remove-Item -ErrorAction SilentlyContinue "$p.part"; $miss++
                Log "SEC Insider ${name}: nicht verfügbar (curl $LASTEXITCODE)"
            }
            Start-Sleep -Milliseconds 300
        }
    }
    Log "SEC Insider: $ok Quartale vorhanden, $miss fehlen"
}

# ------------------------------------------------------------------ Dukascopy
function Duka-Url($sym, $y, $m0) { return ('https://datafeed.dukascopy.com/datafeed/' + $sym + '/' + $y + '/' + ([int]$m0).ToString('00') + '/BID_candles_hour_1.bi5') }

function Run-CurlList($list, $cfg) {
    # $list: Array von @(url, ausgabepfad); lädt parallel (16 gleichzeitig), Fehler (404) erzeugen keine Datei
    $sb = New-Object System.Text.StringBuilder
    foreach ($e in $list) { [void]$sb.AppendLine('url = "' + $e[0] + '"'); [void]$sb.AppendLine('output = "' + ($e[1] -replace '\\', '/') + '"') }
    [System.IO.File]::WriteAllText($cfg, $sb.ToString())
    & $CURL -s -f -L -A $UA_DUKA --retry 6 --retry-delay 20 --create-dirs -Z --parallel-max 4 -K $cfg 2>$null | Out-Null
}

function Dukascopy {
    $d = "$OUT\dukascopy"
    $test = "$d\_schema_test.bi5"
    & $CURL -s -f -A $UA_DUKA -o $test (Duka-Url 'AAPLUSUSD' 2023 0)
    if (-not (Test-Path $test) -or (Get-Item $test).Length -lt 100) { Log '!! Dukascopy: Schema-Test (AAPLUSUSD 2023-01, Stundenkerzen) liefert nichts – Teil übersprungen.'; return }
    Log "Dukascopy Schema-Test ok ($((Get-Item $test).Length) Byte)"

    $availF = "$d\_verfuegbar.txt"
    if (-not (Test-Path $availF)) {
        $cands = @()
        foreach ($t in (Get-Content (Join-Path $HERE 'kairo_universe_tickers.txt'))) {
            $t = $t.Trim(); if (-not $t) { continue }
            if ($t.EndsWith('.DE')) { $cands += ($t.Substring(0, $t.Length - 3) -replace '[-.]', '').ToUpper() + 'DEEUR' }
            elseif ($t -notmatch '\.') { $cands += ($t -replace '[-.]', '').ToUpper() + 'USUSD' }
        }
        $cands = $cands | Sort-Object -Unique
        Log "Dukascopy: prüfe $($cands.Count) Kandidaten …"; Status 'Dukascopy Verfügbarkeit'
        $list = @(); foreach ($s in $cands) { foreach ($ym in @(@(2024, 5), @(2019, 5))) { $list += , @((Duka-Url $s $ym[0] $ym[1]), "$d\_probe\${s}_$($ym[0]).bi5") } }
        Run-CurlList $list "$d\_probe.cfg"
        $avail = @(); foreach ($s in $cands) { if (Get-ChildItem "$d\_probe\${s}_*.bi5" -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 50 }) { $avail += $s } }
        Set-Content -Path $availF -Value $avail
    }
    $avail = @(Get-Content $availF)
    Log "Dukascopy: $($avail.Count) Titel verfügbar → lade Stundenkerzen ab $DUKA_START"
    if ($avail.Count -eq 0) { Log '!! Dukascopy: kein Titel verfügbar'; return }
    $today = Get-Date
    $i = 0
    foreach ($chunk in (0..([math]::Ceiling($avail.Count / 25) - 1))) {
        $list = @()
        foreach ($s in $avail[($chunk * 25)..([math]::Min($avail.Count, ($chunk + 1) * 25) - 1)]) {
            for ($y = $DUKA_START; $y -le $today.Year; $y++) {
                for ($m0 = 0; $m0 -lt 12; $m0++) {
                    if ((Get-Date -Year $y -Month ($m0 + 1) -Day 1) -gt $today) { break }
                    $o = "$d\h1\$s\$y-$(([int]$m0).ToString('00')).bi5"
                    if (-not (Test-Path $o)) { $list += , @((Duka-Url $s $y $m0), $o) }
                }
            }
        }
        if ($list.Count) { Run-CurlList $list "$d\_h1.cfg" }
        $i = [math]::Min($avail.Count, ($chunk + 1) * 25)
        Log "   Dukascopy $i / $($avail.Count) Titel"; Status "Dukascopy $i / $($avail.Count)"
    }
    Copy-Item $availF "$d\h1\_verfuegbar.txt" -Force
    $zip = "$OUT\upload\dukascopy_h1_bi5.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory("$d\h1", $zip, [System.IO.Compression.CompressionLevel]::NoCompression, $false)
    Log "Dukascopy: Paket $([math]::Round((Get-Item $zip).Length/1MB)) MB"
    if ((Get-Item $zip).Length -gt $PART) { Split-ForUpload $zip; Remove-Item $zip }
}

Log "=== Start (PowerShell $($PSVersionTable.PSVersion), curl: $(& $CURL --version | Select-Object -First 1)) ==="
$only = $args
if (-not $only -or ($only -match 'sec'))      { try { Sec-Bulk } catch { Log "!! SEC Bulk: $_" } }
if (-not $only -or ($only -match 'insider'))  { try { Sec-Insider } catch { Log "!! SEC Insider: $_" } }
if (-not $only -or ($only -match 'duka'))     { try { Dukascopy } catch { Log "!! Dukascopy: $_" } }
Status 'FERTIG'
Log '=== FERTIG – Fenster kann geschlossen werden ==='
