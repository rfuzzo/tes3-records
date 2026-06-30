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

$root = Get-Item -LiteralPath $RootPath
$mainFolders = Get-ChildItem -LiteralPath $root.FullName -Directory

foreach ($mainFolder in $mainFolders) {
    $subFolders = Get-ChildItem -LiteralPath $mainFolder.FullName -Directory

    foreach ($subFolder in $subFolders) {
        $yamlFiles = Get-ChildItem -LiteralPath $subFolder.FullName -File -Filter '*.yaml'
        $rows = foreach ($yamlFile in $yamlFiles) {
            $lines = Get-Content -LiteralPath $yamlFile.FullName
            [PSCustomObject]@{
                id   = Get-FieldValue -Lines $lines -FieldName 'id'
                name = Get-FieldValue -Lines $lines -FieldName 'name'
                tags = ''
            }
        }

        $csvName = '{0}_{1}.csv' -f $mainFolder.Name, $subFolder.Name
        $csvPath = Join-Path -Path $subFolder.FullName -ChildPath $csvName

        # Always produce a CSV for each subfolder, even when no YAML files are present.
        @($rows) | Select-Object id, name, tags | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8
        Write-Host ("Wrote {0}" -f $csvPath)
    }
}
