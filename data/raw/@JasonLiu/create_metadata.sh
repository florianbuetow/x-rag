#!/bin/bash

# Script to create metadata JSON files for each transcript .txt file
# Processes all .txt files in the current directory and subdirectories

# Find all .txt files recursively
find . -type f -name "*.txt" | while read -r txt_file; do
    # Get the directory and filename
    dir=$(dirname "$txt_file")
    filename=$(basename "$txt_file")
    filename_no_ext="${filename%.txt}"

    # Create the corresponding .json filename
    json_file="${dir}/${filename_no_ext}.json"

    # Create the JSON metadata file
    cat > "$json_file" <<EOF
{
  "metadata": {
    "title": "$filename_no_ext",
    "source_file": "$filename",
    "type": "video transcript",
    "transcription_method": "whisper (medium, English)"
  }
}
EOF

    echo "Created: $json_file"
done

echo "Metadata generation complete!"
