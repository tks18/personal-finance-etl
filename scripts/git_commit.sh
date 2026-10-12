#!/bin/bash

# Target folder (change to your folder path)
TARGET_DIR="/home/tksudharshan/personal-finance-etl/docs/finance"

# Loop through each file in the folder
for file in "$TARGET_DIR"/*; do
    # Check if it's a file (not a subdirectory)
    if [ -f "$file" ]; then
        # Get just the file name without the directory path
        file_name=$(basename "$file")
        
        # Stage the file
        git add "$file"
        
        # Commit the file
        git commit -m "docs: update $file_name"
    fi
done
