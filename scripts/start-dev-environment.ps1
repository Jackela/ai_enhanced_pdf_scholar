# ============================================================================
# AI Enhanced PDF Scholar - Development Environment Startup Script
# Comprehensive DevOps automation for local development setup
# ============================================================================

param(
    [switch]$Force,
    [switch]$SkipDocker,
    [int]$DockerTimeout = 120
)

Write-Host "🚀 AI Enhanced PDF Scholar - Development Environment Setup" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Function to check if Docker Desktop is running
function Test-DockerRunning {
    try {
        $result = docker ps 2>&1
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

# Function to start Docker Desktop
function Start-DockerDesktop {
    Write-Host "🐳 Starting Docker Desktop..." -ForegroundColor Yellow
    
    # Common Docker Desktop paths
    $dockerPaths = @(
        "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${env:LOCALAPPDATA}\Programs\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
    )
    
    $dockerExe = $null
    foreach ($path in $dockerPaths) {
        if (Test-Path $path) {
            $dockerExe = $path
            break
        }
    }
    
    if (-not $dockerExe) {
        Write-Host "❌ Docker Desktop not found. Please install Docker Desktop from https://docs.docker.com/desktop/install/windows/" -ForegroundColor Red
        return $false
    }
    
    # Start Docker Desktop
    Start-Process -FilePath $dockerExe -WindowStyle Hidden
    Write-Host "📍 Docker Desktop is starting. Please wait..." -ForegroundColor Yellow
    
    # Wait for Docker to be ready
    $timeout = $DockerTimeout
    $elapsed = 0
    
    while (-not (Test-DockerRunning) -and $elapsed -lt $timeout) {
        Start-Sleep -Seconds 5
        $elapsed += 5
        Write-Progress -Activity "Waiting for Docker Desktop" -Status "Elapsed: $elapsed seconds" -PercentComplete (($elapsed / $timeout) * 100)
    }
    
    Write-Progress -Activity "Waiting for Docker Desktop" -Completed
    
    if (Test-DockerRunning) {
        Write-Host "✅ Docker Desktop is running!" -ForegroundColor Green
        return $true
    } else {
        Write-Host "⚠️  Docker Desktop failed to start within $timeout seconds" -ForegroundColor Yellow
        Write-Host "   Please start Docker Desktop manually and try again" -ForegroundColor Yellow
        return $false
    }
}

# Function to install dependencies
function Install-Dependencies {
    Write-Host "📦 Installing Python dependencies..." -ForegroundColor Yellow
    
    try {
        pip install psycopg2-binary redis python-dotenv
        Write-Host "✅ Dependencies installed successfully!" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ Failed to install dependencies: $_" -ForegroundColor Red
        return $false
    }
}

# Function to start Docker services
function Start-DockerServices {
    Write-Host "🔄 Starting PostgreSQL and Redis services..." -ForegroundColor Yellow
    
    try {
        # Pull images first to show progress
        Write-Host "📥 Pulling PostgreSQL image..." -ForegroundColor Cyan
        docker pull postgres:15-alpine
        
        Write-Host "📥 Pulling Redis image..." -ForegroundColor Cyan  
        docker pull redis:7-alpine
        
        # Start services
        Write-Host "🚀 Starting services with docker-compose..." -ForegroundColor Cyan
        docker-compose up -d postgres redis
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Services started successfully!" -ForegroundColor Green
            
            # Wait for services to be healthy
            Write-Host "🏥 Waiting for services to be healthy..." -ForegroundColor Yellow
            Start-Sleep -Seconds 10
            
            # Check service health
            $postgresHealthy = (docker-compose exec postgres pg_isready -U postgres) 2>&1
            $redisHealthy = (docker-compose exec redis redis-cli ping) 2>&1
            
            Write-Host "📊 Service Status:" -ForegroundColor Cyan
            Write-Host "  PostgreSQL: $(if ($postgresHealthy -match 'accepting connections') { '✅ Healthy' } else { '❌ Not Ready' })" -ForegroundColor $(if ($postgresHealthy -match 'accepting connections') { 'Green' } else { 'Red' })
            Write-Host "  Redis: $(if ($redisHealthy -match 'PONG') { '✅ Healthy' } else { '❌ Not Ready' })" -ForegroundColor $(if ($redisHealthy -match 'PONG') { 'Green' } else { 'Red' })
            
            return $true
        } else {
            Write-Host "❌ Failed to start services" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "❌ Error starting services: $_" -ForegroundColor Red
        return $false
    }
}

# Function to validate environment
function Test-Environment {
    Write-Host "✅ Running environment validation..." -ForegroundColor Yellow
    
    try {
        $result = python verify_dependencies.py
        Write-Host $result -ForegroundColor White
        
        $success = $result -match "SUCCESS.*Database.*OK" -and $result -match "SUCCESS.*Redis.*OK"
        
        if ($success) {
            Write-Host "🎉 Environment validation PASSED!" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Environment validation FAILED!" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "❌ Error during validation: $_" -ForegroundColor Red
        return $false
    }
}

# Main execution
try {
    # Check if .env file exists
    if (-not (Test-Path ".env")) {
        Write-Host "❌ .env file not found. Please run the setup first." -ForegroundColor Red
        exit 1
    }
    
    # Install dependencies
    if (-not (Install-Dependencies)) {
        exit 1
    }
    
    # Check Docker status
    if (-not $SkipDocker) {
        if (-not (Test-DockerRunning)) {
            if (-not (Start-DockerDesktop)) {
                Write-Host "❌ Could not start Docker Desktop. Manual intervention required:" -ForegroundColor Red
                Write-Host "   1. Start Docker Desktop manually" -ForegroundColor Yellow
                Write-Host "   2. Run: docker-compose up -d postgres redis" -ForegroundColor Yellow
                Write-Host "   3. Run: python verify_dependencies.py" -ForegroundColor Yellow
                exit 1
            }
        } else {
            Write-Host "✅ Docker is already running!" -ForegroundColor Green
        }
        
        # Start services
        if (-not (Start-DockerServices)) {
            exit 1
        }
    }
    
    # Validate environment
    if (Test-Environment) {
        Write-Host ""
        Write-Host "🎉 SUCCESS! Development environment is fully configured and ready!" -ForegroundColor Green
        Write-Host ""
        Write-Host "📋 Quick Commands:" -ForegroundColor Cyan
        Write-Host "   • View services: docker-compose ps" -ForegroundColor White
        Write-Host "   • Stop services: docker-compose down" -ForegroundColor White
        Write-Host "   • View logs: docker-compose logs -f postgres redis" -ForegroundColor White
        Write-Host "   • Test connections: python verify_dependencies.py" -ForegroundColor White
    } else {
        Write-Host "❌ Setup completed but validation failed. Please check the services manually." -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "❌ Unexpected error: $_" -ForegroundColor Red
    exit 1
}