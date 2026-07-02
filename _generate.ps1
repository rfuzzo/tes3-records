$root = $PSScriptRoot
$morrowindPath = Join-Path $root 'Morrowind'

function Move-FolderIntoMorrowind {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FolderName
    )

    $sourcePath = Join-Path $root $FolderName
    $destinationPath = Join-Path $morrowindPath $FolderName

    if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) {
        Write-Host "Skipping ${FolderName}: source folder not found."
        return
    }

    if (Test-Path -LiteralPath $destinationPath -PathType Container) {
        Write-Host "Skipping ${FolderName}: already present in Morrowind."
        return
    }

    Move-Item -LiteralPath $sourcePath -Destination $morrowindPath
    Write-Host "Moved $FolderName into Morrowind."
}

# tes3util dump .\ -o .\ -c -i ACTI, MISC, STAT, WEAP, CONT, LIGH, ARMO, CLOT, REPA, APPA, LOCK, PROB, INGR, BOOK, ALCH

# Merge classic DLC folders in the requested order.
Move-FolderIntoMorrowind -FolderName 'Tribunal'
Move-FolderIntoMorrowind -FolderName 'Bloodmoon'
