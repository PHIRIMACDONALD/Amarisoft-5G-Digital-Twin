#!/bin/bash
#
# This script automatically applies the necessary patches to the experiment files
# to allow for non-interactive execution in the automation script.
#

set -e # Exit immediately if any command fails

echo "▶️  Patching modified.digital_twin_setup.py to support --no-cli mode..."

# --- Patch 1: Add necessary imports to the Python script ---
# We use '1i' to insert these two lines at the very top (line 1) of the file.
sed -i '1i import sys\nimport time' modified.digital_twin_setup.py

# --- Patch 2: Replace the interactive CLI call in the Python script ---
# This 'sed' command finds the line containing 'CLI(net)' and replaces it ('c\')
# with a multi-line block of Python code. The new code checks for the --no-cli
# argument and waits indefinitely if it's present.
# Note the careful handling of indentation and single quotes ('\'').
sed -i '/^[[:space:]]*CLI(net)/c\
if '\''--no-cli'\'' in sys.argv:\
    while True:\
        time.sleep(1)\
else:\
    CLI(net)' modified.digital_twin_setup.py

echo "✅ Python script patched successfully."
echo ""
echo "▶️  Patching run_experiment.sh to use the --no-cli flag..."

# --- Patch 3: Update the automation script to use the new flag ---
# This is a simple search-and-replace ('s/.../.../') to add the flag.
sed -i "s/sudo python3 modified.digital_twin_setup.py >/sudo python3 modified.digital_twin_setup.py --no-cli >/" run_experiment.sh

echo "✅ Automation script patched successfully."
echo ""
echo "🎉 Patching complete! You can now run ./run_experiment.sh"
