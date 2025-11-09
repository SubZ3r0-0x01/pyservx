#!/usr/bin/env python3

from pyservx import server

if __name__ == "__main__":
    # Get the shared folder (automatically creates in Downloads/PyServeX-Shared)
    base_dir = server.get_shared_folder()
    
    # Run the server with QR codes enabled
    server.run(base_dir, no_qr=False)
