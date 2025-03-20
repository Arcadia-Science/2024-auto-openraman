#!/bin/bash

# Define arrays for integration times (in milliseconds) and laser powers (in milliwatts)
integration_times=(200 600 1000 1400 1800)  # Example integration times
laser_powers=(5 10 15 20 25)          # Example laser powers
averages=(5 10 15 20 25)          # Averages

# Base command parameters
base_command="autoopenraman acq"
output_dir="attempt2"

# Loop through all combinations of integration times and laser powers
for integration_time in "${integration_times[@]}"; do
    for laser_power in "${laser_powers[@]}"; do
        for average in "${averages[@]}"; do
            # Generate the directory name based on parameters
            exp_dir="${output_dir}_power=${laser_power}_integration=${integration_time}_average=${average}"

            # Construct and print the command to execute
            echo "Running: ${base_command} --n-averages ${average} --wasatch-integration-time-ms ${integration_time} --wasatch-laser-power-mw ${laser_power} --exp-dir ${exp_dir}"

            # Execute the command
            ${base_command} \
                --wasatch-integration-time-ms "${integration_time}" \
                --wasatch-laser-power-mw "${laser_power}" \
                --n-averages ${average} \
                --exp-dir "${exp_dir}"

            # Check if the command succeeded
            if [ $? -ne 0 ]; then
                echo "Command failed for integration=${integration_time} and power=${laser_power} and n averages=${average}. Exiting."
                exit 1
            fi
        done
    done
done

echo "Batch sweep completed successfully!"
