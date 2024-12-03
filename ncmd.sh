#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <hostname> <command>"
  exit 1
fi

# Assign arguments to variables
hostname=$1
command=$2

# Make the API call and capture the response
response=$(curl -s -X 'POST' \
  'http://127.0.0.1:8111/connections/command' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "hostname": "'"$hostname"'",
  "command": "'"$command"'",
  "enable_mode": false
}')

# Extract the response body using jq
output=$(echo "$response" | jq -r '.')

# Print the output with proper formatting
echo "$output" | sed 's/\\n/\n/g' | sed 's/\\"/"/g' | sed 's/\\t/\t/g'