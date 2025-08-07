#!/usr/bin/env python3

import os
from pyservx import server

if __name__ == "__main__":
    # Create a 'shared' directory if it doesn't exist
    if not os.path.exists("shared"):
        os.makedirs("shared")
    
    # Set the base directory for the server
    server.base_dir = os.path.abspath("shared")
    
    # Run the server
    server.run(server.base_dir)
