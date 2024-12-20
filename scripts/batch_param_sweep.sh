#!/bin/bash

# Define arrays for integration times (in milliseconds) and laser powers (in milliwatts)
integration_times=(500 1000 1500 2000)  # Example integration times
laser_powers=(50 100 150 200)          # Example laser powers

# Base command parameters
base_command="autoopenraman acq"
output_dir="testingdata"

# Loop through all combinations of integration times and laser powers
for integration_time in "${integration_times[@]}"; do
    for laser_power in "${laser_powers[@]}"; do
        # Generate the directory name based on parameters
        exp_dir="${output_dir}_power=${laser_power}_integration=${integration_time}"

        # Construct and print the command to execute
        echo "Running: ${base_command} --wasatch-integration-time-ms ${integration_time} --wasatch-laser-power-mw ${laser_power} --exp-dir ${exp_dir}"

        # Execute the command
        ${base_command} \
            --wasatch-integration-time-ms "${integration_time}" \
            --wasatch-laser-power-mw "${laser_power}" \
            --exp-dir "${exp_dir}"

        # Check if the command succeeded
        if [ $? -ne 0 ]; then
            echo "Command failed for integration=${integration_time} and power=${laser_power}. Exiting."
            exit 1
        fi
    done
done

echo "Batch sweep completed successfully!"
