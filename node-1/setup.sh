#!/bin/bash
WORK_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(dirname "$WORK_DIR")"

# Create data directories
mkdir -p "$PARENT_DIR"/{uploads,outputs,logs,models}

# Copy Biomni if not present
if [ ! -d "$PARENT_DIR/Biomni" ]; then
    echo "Warning: Biomni not found at $PARENT_DIR/Biomni"
    echo "Please clone: git clone https://github.com/JHK-DEV-Star/Biomni.git $PARENT_DIR/Biomni"
fi

# Create .env from example if not present
if [ ! -f "$WORK_DIR/.env" ]; then
    cp "$WORK_DIR/.env.example" "$WORK_DIR/.env"
    echo ".env file created. Please configure API keys and service URLs."
fi

echo "Setup complete. Run ./start_server.sh to start the server."
echo "(First run will take time for Docker build)"
