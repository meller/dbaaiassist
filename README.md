# DB AI Assist

A powerful AI-assisted database management and optimization tool that provides database insights, performance recommendations, and log analysis.

## Features

- **Database Connection Management**: Securely connect to and manage PostgreSQL databases
- **Log Analysis**: Analyze database logs to identify issues and performance bottlenecks
  - Supported log formats:
    - PostgreSQL logs
    - SQLAlchemy logs
- **Database Insights**: View comprehensive statistics and information about your database structure
- **Performance Recommendations**: Receive AI-powered recommendations for database optimization
- **Index Recommendations**: Identify missing indexes and get suggestions for performance improvement

## Installation

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the Streamlit application:
   ```
   streamlit run streamlit_app.py
   ```

## Usage

1. Navigate to the application in your web browser
2. Connect to your PostgreSQL database by providing connection details
3. Explore the different pages:
   - Log Analysis
   - Database Insights
   - Recommendations
   - Settings

## Project Structure

```
dbaaiassist/
├── components/         # UI components
├── data/               # Data connectors and exporters
│   ├── connectors/     # Database connectors
│   ├── exporters/      # Data export utilities
│   └── log_parser/     # Log parsing modules
├── models/             # Data models
├── pages/              # Application pages
├── services/           # Business logic services
│   ├── analyzer/       # Data analysis
│   └── recommender/    # Recommendation engines
└── utils/              # Utility functions
```

## Requirements

- Python 3.8+
- PostgreSQL
- Dependencies listed in requirements.txt

## License

This project uses a dual license model:

- **Free for non-commercial use** under the Mozilla Public License 2.0
- **Commercial license required** for any commercial applications

For commercial use, please contact the author to arrange licensing terms.

See the [LICENSE](LICENSE) file for complete details.

## Documentation

Additional documentation can be found in the [docs](docs/) directory:
- [Design Document](docs/DESIGN.md)
- [Product Requirements Document](docs/PRD.md)
- [Project Priorities](docs/PRIORITIES.md)
- [User Stories](docs/USER_STORIES.md)