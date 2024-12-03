#!/usr/bin/env python3

import sys
import json
import urllib.request
import urllib.parse

def execute_command(hostname, command):
    # Define the API endpoint
    url = "http://localhost:8111/connections/mdcommand"  # Update with your actual API URL
    
    # Prepare the data to be sent
    data = {
        "hostname": hostname,
        "command": command,
        "enable_mode": True  # Assuming enable mode is not required
    }
    
    # Encode the data to JSON
    json_data = json.dumps(data).encode('utf-8')
    
    # Prepare the request
    req = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json'})
    
    try:
        # Send the request and get the response
        with urllib.request.urlopen(req) as response:
            response_data = response.read().decode('utf-8')
            results = json.loads(response_data)
            
            if type(results) is str:
                if results == 'Only supports show commands':
                    print(results)
                    exit()
            
            # Print the output from each device
            for result in results:
                print(f"Hostname: {result['hostname']}")
                print(f"Command: {result['command']}")
                if 'output' in result:
                    print(f"Output:\n{result['output']}")
                elif 'error' in result:
                    print(f"Error:\n{result['error']}")
                print("-" * 40)
    
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {str(e)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <hostname> <command>")
        sys.exit(1)
    
    hostname = sys.argv[1]
    command = sys.argv[2]
    
    execute_command(hostname, command)