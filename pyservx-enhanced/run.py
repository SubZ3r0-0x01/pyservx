#!/usr/bin/env python3
# PyServeX Enhanced - Run Script

from pyservx import server

if __name__ == "__main__":
    # Get the enhanced shared folder (automatically creates in Downloads/PyServeX-Enhanced-Shared)
    base_dir = server.get_shared_folder()
    
    # Run the enhanced server with QR codes enabled
    server.run(base_dir, no_qr=False)