param([switch]$Apply)

$ErrorActionPreference = 'Stop'
function Resolve-NetworkPath([string]$path) {
    $full = [IO.Path]::GetFullPath($path).TrimEnd('\')
    if ($full.StartsWith('\\')) { return $full }
    $driveRoot = [IO.Path]::GetPathRoot($full)
    $driveName = $driveRoot.TrimEnd('\').TrimEnd(':')
    $drive = Get-PSDrive -Name $driveName -ErrorAction SilentlyContinue
    if ($drive -and $drive.DisplayRoot -and $drive.DisplayRoot.StartsWith('\\')) {
        return [IO.Path]::GetFullPath((Join-Path $drive.DisplayRoot $full.Substring($driveRoot.Length))).TrimEnd('\')
    }
    throw "Not a network folder. Local/private permissions are not changed: $full"
}
$programRoot = Resolve-NetworkPath (Join-Path $PSScriptRoot '..')
$legacyRoot = Join-Path $programRoot '.local-web'
$roots = [Collections.Generic.List[string]]::new()
$roots.Add($legacyRoot)
$database = Join-Path $legacyRoot 'pronto.sqlite3'
$locator = Join-Path $programRoot 'pronto-installation.json'
if (Test-Path -LiteralPath $locator -PathType Leaf) {
    $config = Get-Content -LiteralPath $locator -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($config.schemaVersion -ne '1.0' -or -not $config.dataRoot -or -not $config.database) {
        throw 'Invalid pronto-installation.json. No permissions changed.'
    }
    $configuredRoot = if ([IO.Path]::IsPathRooted($config.dataRoot)) { $config.dataRoot } else { Join-Path $programRoot $config.dataRoot }
    $database = if ([IO.Path]::IsPathRooted($config.database)) { $config.database } else { Join-Path $programRoot $config.database }
    $roots.Add((Resolve-NetworkPath $configuredRoot))
} elseif (Test-Path -LiteralPath (Join-Path $legacyRoot 'config.json') -PathType Leaf) {
    $config = Get-Content -LiteralPath (Join-Path $legacyRoot 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($config.database) {
        $database = if ([IO.Path]::IsPathRooted($config.database)) { $config.database } else { Join-Path $programRoot $config.database }
    }
}
$database = Resolve-NetworkPath $database
$currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$allowedSids = @($currentSid, 'S-1-5-32-544', 'S-1-5-18')
$backupRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'PRONTO\permission-backups'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$backupFile = Join-Path $backupRoot ("acl-$stamp.jsonl")
$script:changed = 0
$script:skipped = 0

function Repair-OwnedPrivateAcl([string]$path, [string]$boundary) {
    $full = [IO.Path]::GetFullPath($path).TrimEnd('\')
    $limit = [IO.Path]::GetFullPath($boundary).TrimEnd('\')
    if ($full -ne $limit -and -not $full.StartsWith($limit + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Target is outside the selected PRONTO data folder. Stopped.'
    }
    $item = Get-Item -LiteralPath $full -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Write-Output "SKIP link: $full"
        $script:skipped++
        return
    }
    $acl = Get-Acl -LiteralPath $full
    if (-not $acl.AreAccessRulesProtected) { return }
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $currentSid) {
        Write-Output "SKIP other owner: $full"
        $script:skipped++
        return
    }
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if (-not $rules.Count -or @($rules | Where-Object {
        $_.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
        $_.IdentityReference.Value -notin $allowedSids
    }).Count) {
        Write-Output "SKIP custom access policy: $full"
        $script:skipped++
        return
    }
    Write-Output "INHERIT approved parent access: $full"
    if ($Apply) {
        # Save the original descriptor before touching it. Preserve all explicit
        # owner/admin rules; only allow inheritance from the existing parent ACL.
        New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
        [pscustomobject]@{ path = $full; sddl = $acl.Sddl } |
            ConvertTo-Json -Compress | Add-Content -LiteralPath $backupFile -Encoding UTF8
        $acl.SetAccessRuleProtection($false, $true)
        Set-Acl -LiteralPath $full -AclObject $acl
        if ((Get-Acl -LiteralPath $full).AreAccessRulesProtected) {
            throw "The file server did not enable permission inheritance for $full"
        }
        $script:changed++
    }
}

Write-Output 'PRONTO shared access repair. No files, passwords or key contents are replaced.'
if (-not $Apply) { Write-Output 'READ ONLY: add -Apply to enable inheritance for matching owner-only ACLs.' }
foreach ($root in @($roots | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    $root = [IO.Path]::GetFullPath($root).TrimEnd('\')
    $parent = [IO.Path]::GetDirectoryName($root)
    Get-Acl -LiteralPath $parent | Out-Null
    Repair-OwnedPrivateAcl $root $root
    # Only app storage subtrees, never recurse across the rest of the selected area.
    $queue = [Collections.Generic.Queue[string]]::new()
    foreach ($name in @('raw_imports', 'database', 'backups', 'references')) {
        $directory = Join-Path $root $name
        if (Test-Path -LiteralPath $directory -PathType Container) {
            $item = Get-Item -LiteralPath $directory -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            Repair-OwnedPrivateAcl $directory $root
            $queue.Enqueue($directory)
        }
    }
    while ($queue.Count) {
        $directory = $queue.Dequeue()
        foreach ($child in @(Get-ChildItem -LiteralPath $directory -Directory -Force)) {
            if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            Repair-OwnedPrivateAcl $child.FullName $root
            $queue.Enqueue($child.FullName)
        }
    }
    foreach ($name in @('secret.key', 'config.json', 'initial-users.json', 'biomarker-list.xlsx', 'biomarker-list.json')) {
        $path = Join-Path $root $name
        if (Test-Path -LiteralPath $path -PathType Leaf) { Repair-OwnedPrivateAcl $path $root }
    }
}
if (Test-Path -LiteralPath $database -PathType Leaf) {
    Repair-OwnedPrivateAcl $database ([IO.Path]::GetDirectoryName($database))
}
Write-Output "Changed: $script:changed. Skipped policies/owners: $script:skipped."
if ($script:changed) { Write-Output "Original ACL descriptors: $backupFile" }
Write-Output 'Start PRONTO with the owner account, then ask a colleague to start it.'
Write-Output 'If access is still denied, the area administrator must check the inherited group and SMB share permissions.'
