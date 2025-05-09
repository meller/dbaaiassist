import sys
import os

# Add parent directory to path to allow imports from dbaaiassist
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the actual page implementation
from dbaaiassist.pages.query_explain import show_query_explain

# Display the page
show_query_explain()
