# Snapchat Memories Backuper - Auto Setup Script
# This script downloads the repository and launches the web UI

Write-Host '==============================================' -ForegroundColor Cyan
Write-Host ' Snapchat Memories Backuper - Auto Setup' -ForegroundColor Cyan
Write-Host '==============================================' -ForegroundColor Cyan
Write-Host ''

$repoName = 'snapchat-memories-backuper'
$zipUrl = 'https://github.com/filipsjolanderr/snapchat-memories-backuper/archive/refs/heads/main.zip'
$zipFile = 'snapchat-memories-backuper.zip'

# Check if directory already exists
if (Test-Path $repoName) {
    Write-Host '[!] Directory already exists!' -ForegroundColor Yellow
    $overwrite = Read-Host 'Do you want to use the existing directory? (Y/n)'
    if ($overwrite -eq 'n' -or $overwrite -eq 'N') {
        Write-Host 'Exiting...' -ForegroundColor Red
        exit 1
    }
    Write-Host 'Using existing directory...' -ForegroundColor Green
} else {
    # Download ZIP file
    Write-Host 'Downloading repository...' -ForegroundColor Cyan
    Write-Host 'This may take a moment...' -ForegroundColor Yellow
    
    try {
        # Download ZIP file
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -ErrorAction Stop
        
        Write-Host '[OK] Download complete!' -ForegroundColor Green
        
        # Extract ZIP file
        Write-Host ''
        Write-Host 'Extracting files...' -ForegroundColor Cyan
        Expand-Archive -Path $zipFile -DestinationPath . -Force -ErrorAction Stop
        
        # Rename extracted folder (GitHub ZIP extracts to snapchat-memories-backuper-main)
        if (Test-Path 'snapchat-memories-backuper-main') {
            Rename-Item -Path 'snapchat-memories-backuper-main' -NewName $repoName -Force
        }
        
        # Clean up ZIP file
        Remove-Item -Path $zipFile -Force -ErrorAction SilentlyContinue
        
        Write-Host '[OK] Files extracted successfully!' -ForegroundColor Green
    } catch {
        Write-Host '[ERROR] Failed to download or extract repository!' -ForegroundColor Red
        Write-Host ('Error: ' + $_.Exception.Message) -ForegroundColor Red
        Write-Host ''
        Write-Host 'Please try downloading manually from:' -ForegroundColor Yellow
        Write-Host 'https://github.com/filipsjolanderr/snapchat-memories-backuper' -ForegroundColor Cyan
        pause
        exit 1
    }
}

# Change to repository directory
Set-Location $repoName

# Check if run_ui.bat exists
if (-not (Test-Path 'run_ui.bat')) {
    Write-Host '[ERROR] run_ui.bat not found in repository!' -ForegroundColor Red
    Write-Host 'The repository may not have downloaded correctly.' -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ''
Write-Host '==============================================' -ForegroundColor Cyan
Write-Host '[OK] Repository ready!' -ForegroundColor Green
Write-Host 'Launching setup script...' -ForegroundColor Cyan
Write-Host '==============================================' -ForegroundColor Cyan
Write-Host ''

# Run the batch file
& .\run_ui.bat
