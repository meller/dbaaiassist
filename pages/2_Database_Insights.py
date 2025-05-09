import sys
import os

# Add parent directory to path to allow imports from dbaaiassist
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the actual page implementation
from dbaaiassist.pages.database_insights import show_database_insights

# Display the page
show_database_insights()