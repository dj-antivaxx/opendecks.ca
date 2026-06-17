import os
import sys

# Add 'src' directory to the path so nested imports work on Vercel
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.app import app
