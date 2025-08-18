#!/bin/bash

echo "Starting Nutrition Analysis Services..."
echo "======================================"

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start Korean Food Recognition API (port 5001)
echo "Starting Korean Food Recognition API on port 5001..."
python "$DIR/app_korean.py" &
PID1=$!

# Start LogMeal Nutrition Integration Server (port 5003)
echo "Starting LogMeal Nutrition Server on port 5003..."
python "$DIR/logmeal_nutrition_server.py" &
PID2=$!

# Start Nutrition History Server (port 5004)
echo "Starting Nutrition History Server on port 5004..."
python "$DIR/nutrition_history_server.py" &
PID3=$!

echo ""
echo "All services are starting..."
echo "======================================"
echo "Services:"
echo "- Korean Food Recognition API: http://localhost:5001"
echo "- LogMeal Nutrition Analysis: http://localhost:5003"
echo "- Nutrition History Dashboard: http://localhost:5004"
echo "======================================"
echo ""

# Wait a moment for services to start
sleep 3

# Open dashboard in browser (works on Mac and Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open http://localhost:5004
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open http://localhost:5004 2>/dev/null || echo "Please open http://localhost:5004 in your browser"
fi

echo "Dashboard opened in browser!"
echo "Press Ctrl+C to stop all services..."

# Wait for Ctrl+C
trap "echo 'Stopping services...'; kill $PID1 $PID2 $PID3; exit" INT
wait