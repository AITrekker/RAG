# Direct execution script for RAG Platform Frontend (PowerShell)
# Runs Vite development server without Docker for debugging and development

param(
    [int]$Port = 3000,
    [string]$HostAddress = "localhost",
    [switch]$Install,
    [switch]$Help
)

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Banner {
    Write-ColorOutput "[RAG] Platform Frontend - Direct Execution" "Cyan"
    Write-ColorOutput "============================================" "Cyan"
    Write-Host ""
}

function Test-NodeVersion {
    try {
        $nodeVersion = node --version
        if (-not $nodeVersion) {
            Write-ColorOutput "[ERROR] Node.js is not installed" "Red"
            Write-ColorOutput "        Install Node.js from: https://nodejs.org/" "Yellow"
            return $false
        }
        
        $version = $nodeVersion -replace "v", ""
        $majorVersion = [int]($version.Split(".")[0])
        
        if ($majorVersion -lt 18) {
            Write-ColorOutput "[ERROR] Node.js 18+ is required" "Red"
            Write-ColorOutput "        Current version: $version" "Yellow"
            return $false
        }
        
        Write-ColorOutput "[OK] Node.js version: $version" "Green"
        return $true
    }
    catch {
        Write-ColorOutput "[ERROR] Node.js is not installed or not in PATH" "Red"
        return $false
    }
}

function Test-NpmVersion {
    try {
        $npmVersion = npm --version
        if (-not $npmVersion) {
            Write-ColorOutput "[ERROR] npm is not installed" "Red"
            return $false
        }
        
        Write-ColorOutput "[OK] npm version: $npmVersion" "Green"
        return $true
    }
    catch {
        Write-ColorOutput "[ERROR] npm is not installed or not in PATH" "Red"
        return $false
    }
}

function Get-ScriptDirectory {
    try {
        if ($PSScriptRoot) {
            return $PSScriptRoot
        }
        # Fallback for older PowerShell or different execution contexts
        return Split-Path -Parent $MyInvocation.MyCommand.Path
    } catch {
        Write-Error "Could not determine script directory."
        exit 1
    }
}

function Initialize-Environment {
    # Get script directory and project root
    $scriptDir = Get-ScriptDirectory
    $projectRoot = Split-Path -Parent $scriptDir
    $frontendDir = Join-Path $projectRoot "src\frontend"
    
    Write-ColorOutput "[INFO] Project paths:" "Cyan"
    Write-Host "       Project root: $projectRoot"
    Write-Host "       Frontend dir: $frontendDir"
    
    # Check if frontend directory exists
    if (-not (Test-Path $frontendDir)) {
        Write-ColorOutput "[ERROR] Frontend directory not found: $frontendDir" "Red"
        return $null
    }
    
    # Change to frontend directory
    try {
        Set-Location $frontendDir
        Write-ColorOutput "[OK] Changed to frontend directory" "Green"
        return $frontendDir
    }
    catch {
        Write-ColorOutput "[ERROR] Failed to change to frontend directory" "Red"
        return $null
    }
}

function Test-PackageJson {
    if (-not (Test-Path "package.json")) {
        Write-ColorOutput "[ERROR] package.json not found in frontend directory" "Red"
        Write-ColorOutput "        This will be created in subsequent tasks" "Yellow"
        return $false
    }
    
    Write-ColorOutput "[OK] package.json found" "Green"
    return $true
}

function Install-Dependencies {
    param([bool]$ForceInstall = $false)
    
    Write-ColorOutput "[INFO] Checking dependencies..." "Cyan"
    
    if ($ForceInstall) {
        Write-ColorOutput "[WARN] Force reinstalling dependencies..." "Yellow"
        if (Test-Path "node_modules") { Remove-Item -Recurse -Force "node_modules" }
        if (Test-Path "package-lock.json") { Remove-Item -Force "package-lock.json" }
        if (Test-Path "yarn.lock") { Remove-Item -Force "yarn.lock" }
    }
    
    if (-not (Test-Path "node_modules")) {
        Write-ColorOutput "[WARN] node_modules not found, installing dependencies..." "Yellow"
        
        # Try yarn first on Windows (better for Windows-specific npm issues)
        try {
            $yarnVersion = yarn --version
            Write-ColorOutput "[OK] Using yarn $yarnVersion" "Green"
            yarn install
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "[OK] Dependencies installed with yarn" "Green"
                return $true
            }
            else {
                Write-ColorOutput "[WARN] yarn install failed, trying npm" "Yellow"
            }
        }
        catch {
            Write-ColorOutput "[INFO] yarn not available, using npm" "Yellow"
        }
        
        # Fall back to npm
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-ColorOutput "[ERROR] Failed to install dependencies" "Red"
            return $false
        }
    }
    else {
        Write-ColorOutput "[OK] node_modules directory exists" "Green"
        
        # Check if package.json is newer than node_modules
        $packageJsonTime = (Get-Item "package.json").LastWriteTime
        $nodeModulesTime = (Get-Item "node_modules").LastWriteTime
        
        if ($packageJsonTime -gt $nodeModulesTime) {
            Write-ColorOutput "[WARN] package.json is newer than node_modules, updating dependencies..." "Yellow"
            
            # Try yarn first
            try {
                $yarnVersion = yarn --version
                Write-ColorOutput "[OK] Using yarn $yarnVersion" "Green"
                yarn install
                if ($LASTEXITCODE -eq 0) {
                    Write-ColorOutput "[OK] Dependencies updated with yarn" "Green"
                    return $true
                }
                else {
                    Write-ColorOutput "[WARN] yarn install failed, trying npm" "Yellow"
                }
            }
            catch {
                Write-ColorOutput "[INFO] yarn not available, using npm" "Yellow"
            }
            
            # Fall back to npm
            npm install
            if ($LASTEXITCODE -ne 0) {
                Write-ColorOutput "[ERROR] Failed to update dependencies" "Red"
                return $false
            }
        }
    }
    
    Write-ColorOutput "[OK] Dependencies are up to date" "Green"
    return $true
}

function Set-EnvironmentVariables {
    # Set development environment variables
    $env:NODE_ENV = "development"
    $env:VITE_API_BASE_URL = if ($env:VITE_API_BASE_URL) { $env:VITE_API_BASE_URL } else { "http://localhost:8000/api/v1" }
    $env:VITE_APP_TITLE = if ($env:VITE_APP_TITLE) { $env:VITE_APP_TITLE } else { "Enterprise RAG Platform" }
    $env:CHOKIDAR_USEPOLLING = "true"  # Enable polling for Windows
    
    Write-ColorOutput "[OK] Environment variables set" "Green"
    Write-Host "     VITE_API_BASE_URL: $($env:VITE_API_BASE_URL)"
    Write-Host "     VITE_APP_TITLE: $($env:VITE_APP_TITLE)"
    Write-Host "     NODE_ENV: $($env:NODE_ENV)"
    Write-ColorOutput "[INFO] Enabled file watching polling for Windows" "Yellow"
}

function Start-Frontend {
    param(
        [int]$Port,
        [string]$HostAddress
    )
    
    Write-ColorOutput "[START] Starting frontend development server..." "Cyan"
    Write-Host "        Host: $HostAddress"
    Write-Host "        Port: $Port"
    Write-Host "        URL: http://$HostAddress`:$Port"
    Write-Host ""
    Write-ColorOutput "[INFO] Press Ctrl+C to stop the server" "Yellow"
    Write-Host "----------------------------------------"
    
    # Run the development server - try yarn first, then npm
    try {
        # Try yarn first (better for Windows)
        try {
            $yarnVersion = yarn --version
            Write-ColorOutput "[OK] Using yarn $yarnVersion for development server" "Green"
            yarn dev --host $HostAddress --port $Port
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "[OK] Frontend server stopped gracefully" "Green"
                return $true
            }
            else {
                Write-ColorOutput "[WARN] yarn dev failed, trying npm" "Yellow"
            }
        }
        catch {
            Write-ColorOutput "[INFO] yarn not available, using npm" "Yellow"
        }
        
        # Fall back to npm
        npm run dev -- --host $HostAddress --port $Port
        Write-ColorOutput "[OK] Frontend server stopped gracefully" "Green"
        return $true
    }
    catch {
        Write-ColorOutput "[ERROR] Frontend server encountered an error" "Red"
        return $false
    }
}

function Show-Help {
    Write-Host "RAG Platform Frontend - Direct Execution Script (PowerShell)"
    Write-Host ""
    Write-Host "Usage: .\scripts\run_frontend.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Port PORT          Specify port (default: 3000)"
    Write-Host "  -HostAddress HOST   Specify host (default: localhost)"
    Write-Host "  -Install            Force reinstall dependencies"
    Write-Host "  -Help               Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\scripts\run_frontend.ps1"
    Write-Host "  .\scripts\run_frontend.ps1 -Port 4000"
    Write-Host "  .\scripts\run_frontend.ps1 -HostAddress 0.0.0.0 -Port 3000"
    Write-Host "  .\scripts\run_frontend.ps1 -Install"
    Write-Host ""
    Write-Host "Environment Variables:"
    Write-Host "  VITE_API_BASE_URL    Backend API URL (default: http://localhost:8000/api/v1)"
    Write-Host "  VITE_APP_TITLE       Application title (default: Enterprise RAG Platform)"
}

function Main {
    if ($Help) {
        Show-Help
        return
    }
    
    Write-Banner
    
    # Pre-flight checks
    Write-ColorOutput "[CHECK] Running pre-flight checks..." "Cyan"
    
    if (-not (Test-NodeVersion)) {
        exit 1
    }
    
    if (-not (Test-NpmVersion)) {
        exit 1
    }
    
    $frontendDir = Initialize-Environment
    if (-not $frontendDir) {
        exit 1
    }
    
    if (-not (Test-PackageJson)) {
        Write-ColorOutput "[INFO] Frontend application not yet implemented" "Yellow"
        Write-ColorOutput "       This script will work once the React app is created" "Yellow"
        exit 1
    }
    
    if (-not (Install-Dependencies -ForceInstall $Install)) {
        exit 1
    }
    
    # Set up environment
    Set-EnvironmentVariables
    
    # Display system information
    Write-ColorOutput "[SYS] System information:" "Cyan"
    Write-Host "      OS: $($env:OS) $([System.Environment]::OSVersion.Version)"
    Write-Host "      PowerShell: $($PSVersionTable.PSVersion)"
    Write-Host "      Node.js: $(Get-Command node | Select-Object -ExpandProperty Source)"
    Write-Host "      npm: $(Get-Command npm | Select-Object -ExpandProperty Source)"
    Write-Host "      Working directory: $(Get-Location)"
    
    # Start the frontend server
    Write-ColorOutput "[START] Starting RAG Platform Frontend..." "Cyan"
    $success = Start-Frontend -Port $Port -HostAddress $HostAddress
    
    if (-not $success) {
        exit 1
    }
}

# Execute main function
Main 