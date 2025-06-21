#!/bin/bash

# Direct execution script for RAG Platform Frontend
# Runs Vite development server without Docker for debugging and development

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    echo -e "${1}${2}${NC}"
}

print_banner() {
    print_color $BLUE "🚀 RAG Platform Frontend - Direct Execution"
    print_color $BLUE "=============================================="
    echo
}

check_node_version() {
    if ! command -v node >/dev/null 2>&1; then
        print_color $RED "❌ Node.js is not installed"
        print_color $YELLOW "   Install Node.js from: https://nodejs.org/"
        return 1
    fi
    
    NODE_VERSION=$(node --version | cut -d'v' -f2)
    MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'.' -f1)
    
    if [ "$MAJOR_VERSION" -lt 18 ]; then
        print_color $RED "❌ Node.js 18+ is required"
        print_color $YELLOW "   Current version: $NODE_VERSION"
        return 1
    fi
    
    print_color $GREEN "✅ Node.js version: $NODE_VERSION"
    return 0
}

check_npm_version() {
    if ! command -v npm >/dev/null 2>&1; then
        print_color $RED "❌ npm is not installed"
        return 1
    fi
    
    NPM_VERSION=$(npm --version)
    print_color $GREEN "✅ npm version: $NPM_VERSION"
    return 0
}

setup_environment() {
    # Get script directory and project root
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    FRONTEND_DIR="$PROJECT_ROOT/src/frontend"
    
    print_color $BLUE "📁 Project paths:"
    echo "   Project root: $PROJECT_ROOT"
    echo "   Frontend dir: $FRONTEND_DIR"
    
    # Check if frontend directory exists
    if [ ! -d "$FRONTEND_DIR" ]; then
        print_color $RED "❌ Frontend directory not found: $FRONTEND_DIR"
        return 1
    fi
    
    # Change to frontend directory
    cd "$FRONTEND_DIR" || {
        print_color $RED "❌ Failed to change to frontend directory"
        return 1
    }
    
    print_color $GREEN "✅ Changed to frontend directory"
    return 0
}

check_package_json() {
    if [ ! -f "package.json" ]; then
        print_color $RED "❌ package.json not found in frontend directory"
        print_color $YELLOW "   This will be created in subsequent tasks"
        return 1
    fi
    
    print_color $GREEN "✅ package.json found"
    return 0
}

install_dependencies() {
    print_color $BLUE "📦 Checking dependencies..."
    
    if [ ! -d "node_modules" ]; then
        print_color $YELLOW "⚠️  node_modules not found, installing dependencies..."
        npm install
        if [ $? -ne 0 ]; then
            print_color $RED "❌ Failed to install dependencies"
            return 1
        fi
    else
        print_color $GREEN "✅ node_modules directory exists"
        
        # Check if package.json is newer than node_modules
        if [ "package.json" -nt "node_modules" ]; then
            print_color $YELLOW "⚠️  package.json is newer than node_modules, updating dependencies..."
            npm install
            if [ $? -ne 0 ]; then
                print_color $RED "❌ Failed to update dependencies"
                return 1
            fi
        fi
    fi
    
    print_color $GREEN "✅ Dependencies are up to date"
    return 0
}

set_environment_variables() {
    # Set development environment variables
    export NODE_ENV=development
    export VITE_API_BASE_URL=${VITE_API_BASE_URL:-"http://localhost:8000/api/v1"}
    export VITE_APP_TITLE=${VITE_APP_TITLE:-"Enterprise RAG Platform"}
    
    # Enable polling for file watching on some systems
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        export CHOKIDAR_USEPOLLING=true
        print_color $YELLOW "ℹ️  Enabled file watching polling for Windows"
    fi
    
    print_color $GREEN "✅ Environment variables set"
    echo "   VITE_API_BASE_URL: $VITE_API_BASE_URL"
    echo "   VITE_APP_TITLE: $VITE_APP_TITLE"
    echo "   NODE_ENV: $NODE_ENV"
}

run_frontend() {
    local PORT=${1:-3000}
    local HOST=${2:-"localhost"}
    
    print_color $BLUE "🚀 Starting frontend development server..."
    echo "   Host: $HOST"
    echo "   Port: $PORT"
    echo "   URL: http://$HOST:$PORT"
    echo
    print_color $YELLOW "Press Ctrl+C to stop the server"
    echo "----------------------------------------"
    
    # Run the development server
    npm run dev -- --host "$HOST" --port "$PORT"
    
    if [ $? -eq 0 ]; then
        print_color $GREEN "✅ Frontend server stopped gracefully"
        return 0
    else
        print_color $RED "❌ Frontend server encountered an error"
        return 1
    fi
}

show_help() {
    echo "RAG Platform Frontend - Direct Execution Script"
    echo
    echo "Usage: ./scripts/run_frontend.sh [options]"
    echo
    echo "Options:"
    echo "  --port PORT     Specify port (default: 3000)"
    echo "  --host HOST     Specify host (default: localhost)"
    echo "  --install       Force reinstall dependencies"
    echo "  --help, -h      Show this help message"
    echo
    echo "Examples:"
    echo "  ./scripts/run_frontend.sh"
    echo "  ./scripts/run_frontend.sh --port 4000"
    echo "  ./scripts/run_frontend.sh --host 0.0.0.0 --port 3000"
    echo "  ./scripts/run_frontend.sh --install"
    echo
    echo "Environment Variables:"
    echo "  VITE_API_BASE_URL    Backend API URL (default: http://localhost:8000/api/v1)"
    echo "  VITE_APP_TITLE       Application title (default: Enterprise RAG Platform)"
}

main() {
    # Parse command line arguments
    PORT=3000
    HOST="localhost"
    FORCE_INSTALL=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --port)
                PORT="$2"
                shift 2
                ;;
            --host)
                HOST="$2"
                shift 2
                ;;
            --install)
                FORCE_INSTALL=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_color $RED "❌ Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    print_banner
    
    # Pre-flight checks
    print_color $BLUE "🔍 Running pre-flight checks..."
    
    if ! check_node_version; then
        exit 1
    fi
    
    if ! check_npm_version; then
        exit 1
    fi
    
    if ! setup_environment; then
        exit 1
    fi
    
    if ! check_package_json; then
        print_color $YELLOW "ℹ️  Frontend application not yet implemented"
        print_color $YELLOW "   This script will work once the React app is created"
        exit 1
    fi
    
    # Force reinstall if requested
    if [ "$FORCE_INSTALL" = true ]; then
        print_color $YELLOW "🔄 Force reinstalling dependencies..."
        rm -rf node_modules package-lock.json
    fi
    
    if ! install_dependencies; then
        exit 1
    fi
    
    # Set up environment
    set_environment_variables
    
    # Display system information
    print_color $BLUE "🖥️  System information:"
    echo "   OS: $(uname -s) $(uname -r)"
    echo "   Node.js: $(which node)"
    echo "   npm: $(which npm)"
    echo "   Working directory: $(pwd)"
    
    # Start the frontend server
    print_color $BLUE "🚀 Starting RAG Platform Frontend..."
    run_frontend "$PORT" "$HOST"
    
    if [ $? -ne 0 ]; then
        exit 1
    fi
}

# Check if script is being sourced or executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 