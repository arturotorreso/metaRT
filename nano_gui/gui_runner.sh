#!/bin/bash

# Get the directory where this script is located (e.g., .../metaRT/nano_gui)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Define a log file to capture all output and errors
LOG_FILE="$SCRIPT_DIR/nanort_gui.log"
exec >> "$LOG_FILE" 2>&1

echo "--- Starting NanoRT GUI at $(date) ---"

# --- Setup Bundled Java ---
BUNDLED_JAVA_HOME="$SCRIPT_DIR/../nextflow_pipeline/bin/java-17"
if [ -d "$BUNDLED_JAVA_HOME" ]; then
    echo "Found bundled Java at: $BUNDLED_JAVA_HOME"
    export JAVA_HOME="$BUNDLED_JAVA_HOME"
    export PATH="$JAVA_HOME/bin:$PATH"
else
    echo "ERROR: Bundled Java not found at $BUNDLED_JAVA_HOME"
fi
echo "Using Java version:"
java -version

# --- Setup Bundled Conda Environment ---
BUNDLED_CONDA_ENV="$SCRIPT_DIR/../nextflow_pipeline/bin/conda-env"
if [ -d "$BUNDLED_CONDA_ENV" ]; then
    echo "Found bundled Conda environment at: $BUNDLED_CONDA_ENV"
    # Add the environment's bin directory to the front of the PATH
    export PATH="$BUNDLED_CONDA_ENV/bin:$PATH"
    echo "Updated PATH to include Conda binaries."
else
    echo "ERROR: Bundled Conda environment not found at $BUNDLED_CONDA_ENV"
fi

# Define the Python executable from the bundled environment
PYTHON_EXEC="$BUNDLED_CONDA_ENV/bin/python"

echo "Using Python executable: $PYTHON_EXEC"
echo "Executing python script..."

# Execute the GUI script with the correct python interpreter
"$PYTHON_EXEC" nanort_gui.py

EXIT_CODE=$?
echo "--- Python script finished with exit code: $EXIT_CODE ---"
exit $EXIT_CODE