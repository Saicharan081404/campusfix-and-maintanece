import sys
import os

# Add parent directory to path to locate app.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
