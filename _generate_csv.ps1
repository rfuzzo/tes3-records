param(
    [string]$RootPath = $PSScriptRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-FieldValue {
    param(
        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [object]$Lines,

        [Parameter(Mandatory = $true)]
        [string]$FieldName
    )

    $pattern = '^\s*' + [regex]::Escape($FieldName) + '\s*:\s*(.*)$'
    foreach ($line in @($Lines)) {
        if ($null -eq $line) {
            continue
        }

        $match = [regex]::Match($line, $pattern)
        if ($match.Success) {
            $value = $match.Groups[1].Value.Trim()
            if (($value.StartsWith("'")) -and ($value.EndsWith("'")) -and ($value.Length -ge 2)) {
                return $value.Substring(1, $value.Length - 2)
            }
            if (($value.StartsWith('"')) -and ($value.EndsWith('"')) -and ($value.Length -ge 2)) {
                return $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }

    return ''
}

function Read-Row {
    param([System.IO.FileInfo]$YamlFile)

    $lines = Get-Content -LiteralPath $YamlFile.FullName
    $id = Get-FieldValue -Lines $lines -FieldName 'id'
    if ([string]::IsNullOrEmpty($id)) {
        $id = $YamlFile.BaseName
    }
    [PSCustomObject]@{
        id   = $id
        name = Get-FieldValue -Lines $lines -FieldName 'name'
        tags = ''
    }
}

# Expansion folders folded into their parent source rather than emitted as
# their own CSVs. Listed in load order: a later entry (DLC) overrides an
# earlier one when both define a record with the same id.
$NestedSources = @{
    'Morrowind' = @('Tribunal', 'Bloodmoon')
}

$root = Get-Item -LiteralPath $RootPath
$outDir = Join-Path $root.FullName '_out'
if (-not (Test-Path -LiteralPath $outDir -PathType Container)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

$mainFolders = Get-ChildItem -LiteralPath $root.FullName -Directory

foreach ($mainFolder in $mainFolders) {
    $nested = @()
    if ($NestedSources.ContainsKey($mainFolder.Name)) {
        $nested = $NestedSources[$mainFolder.Name]
    }

    # Record-type subfolders of this source, excluding the folded expansions.
    $typeNames = [System.Collections.Generic.List[string]]::new()
    Get-ChildItem -LiteralPath $mainFolder.FullName -Directory |
        Where-Object { $nested -notcontains $_.Name } |
        ForEach-Object { if (-not $typeNames.Contains($_.Name)) { $typeNames.Add($_.Name) } }
    foreach ($n in $nested) {
        $nestedDir = Join-Path $mainFolder.FullName $n
        if (Test-Path -LiteralPath $nestedDir -PathType Container) {
            Get-ChildItem -LiteralPath $nestedDir -Directory |
                ForEach-Object { if (-not $typeNames.Contains($_.Name)) { $typeNames.Add($_.Name) } }
        }
    }

    foreach ($typeName in $typeNames) {
        # Source dirs for this record type, in load order: base first, then each
        # expansion, so a later (DLC) record overrides an earlier one by id.
        $dirs = @()
        $baseTypeDir = Join-Path $mainFolder.FullName $typeName
        if (Test-Path -LiteralPath $baseTypeDir -PathType Container) { $dirs += $baseTypeDir }
        foreach ($n in $nested) {
            $nestedTypeDir = Join-Path (Join-Path $mainFolder.FullName $n) $typeName
            if (Test-Path -LiteralPath $nestedTypeDir -PathType Container) { $dirs += $nestedTypeDir }
        }

        $byId = [ordered]@{}
        foreach ($dir in $dirs) {
            foreach ($yamlFile in (Get-ChildItem -LiteralPath $dir -File -Filter '*.yaml')) {
                $row = Read-Row -YamlFile $yamlFile
                $byId[$row.id] = $row   # later dir (DLC) overrides an earlier one
            }
        }

        $rows = $byId.Values | Sort-Object { $_.id.ToLowerInvariant() }

        $csvName = '{0}_{1}.csv' -f $mainFolder.Name, $typeName
        $csvPath = Join-Path -Path $outDir -ChildPath $csvName
        @($rows) | Select-Object id, name, tags |
            Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8
        Write-Host ("Wrote {0} ({1} records)" -f $csvPath, @($rows).Count)
    }
}
