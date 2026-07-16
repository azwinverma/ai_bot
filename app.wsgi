import sys
import os

# ALWAYS DATA PATH
path = '/home/decodereality/ai_bot'
if path not in sys.path:
    sys.path.append(path)

# Load env variables
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

# Import the WSGI application
from app import application
