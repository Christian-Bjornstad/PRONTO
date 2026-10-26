param(
    [string]$DataRoot = '',
    [int]$Port = 0
)
$ErrorActionPreference = 'Stop'
$projectPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$startPath = Join-Path $projectPath 'PRONTO_START.cmd'
$iconPath = Join-Path $projectPath 'pronto_report\static\branding\pronto.ico'
if (-not (Test-Path -LiteralPath $startPath -PathType Leaf) -or -not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
    throw 'Pakk ut hele PRONTO-programmappen før du lager snarveien.'
}
$desktopPath = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutPath = Join-Path $desktopPath 'PRONTO.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
if ((Test-Path -LiteralPath $shortcutPath) -and $shortcut.TargetPath -ne $startPath) {
    throw 'En annen PRONTO-snarvei finnes allerede. Gi den et annet navn før du fortsetter.'
}
$shortcut.TargetPath = $startPath
$launchArguments = @()
if ($DataRoot) {
    $resolvedDataRoot = [IO.Path]::GetFullPath($DataRoot)
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedDataRoot 'database\pronto.sqlite3') -PathType Leaf)) {
        throw 'Datamappen må inneholde en eksisterende PRONTO-database.'
    }
    $launchArguments += '--data-root "' + $resolvedDataRoot + '"'
}
if ($Port -ne 0) {
    if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Serverport må være mellom 1024 og 65535.' }
    $launchArguments += '--port ' + $Port
}
$shortcut.Arguments = $launchArguments -join ' '
$shortcut.WorkingDirectory = $projectPath
$shortcut.IconLocation = $iconPath + ',0'
$shortcut.Description = 'PRONTO analyse og rapport'
$shortcut.Save()
Write-Output ('Snarveien er klar: ' + $shortcutPath)
