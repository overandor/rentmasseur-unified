# RentMasseur Bio Watcher & Collector

Automated scraper for RentMasseur.com that collects masseur bios, tracks profile views, and calculates views per day based on registration dates. Built with C++, curl, and shell scripts.

## Features

- **Bio Collection**: Scrapes masseur profiles from known URLs
- **View Tracking**: Captures total view counts from profiles
- **Views Per Day Analysis**: Calculates daily view averages based on registration date
- **Data Export**: Exports to JSON, CSV, and generates markdown reports
- **C++ Implementation**: Fast, efficient scraping using libcurl
- **Shell Automation**: Easy-to-run automation script

## Installation

### Prerequisites

- macOS with Homebrew
- g++ compiler
- libcurl

```bash
# Install dependencies (if not already installed)
brew install gcc curl
```

### Build

```bash
cd rentmasseur_scraper
make
```

## Usage

### Quick Start

```bash
# Run the automation script
./run_scraper.sh
```

Or manually:

```bash
# Build
make

# Run
./rentmasseur_scraper
```

This will:
1. Scrape known profile URLs
2. Extract bio information, view counts, and registration dates
3. Calculate views per day for each profile
4. Save data to `data/masseur_profiles.json`
5. Save data to `data/masseur_profiles.csv`
6. Generate report in `data/views_report.md`

## Data Structure

### MasseurProfile
- `username`: Profile username
- `profile_url`: Full profile URL
- `location`: City/location
- `registration_date`: When the masseur joined
- `total_views`: Total profile views
- `bio`: Profile description/bio
- `views_per_day`: Calculated daily view average
- `last_updated`: Timestamp of last scrape

## Output Files

- `data/masseur_profiles.json`: Full profile data in JSON format
- `data/masseur_profiles.csv`: Tabular data for analysis
- `data/views_report.md`: Human-readable report with top profiles

## Current Limitations

- **CrowdSec Protection**: The site uses CrowdSec captcha protection on city pages, preventing automated discovery of all profiles
- **Known Profiles Only**: Currently scrapes a hardcoded list of 18 known profiles from the homepage
- **Data Availability**: View counts, registration dates, and bios may not be available on all profiles due to site protection
- **Manual Expansion**: To scrape more profiles, add their URLs to the `known_profiles` vector in `rentmasseur_scraper.cpp`

## Files

- `rentmasseur_scraper.cpp`: Main C++ scraper implementation
- `Makefile`: Build configuration
- `run_scraper.sh`: Automation script
- `requirements.txt`: Python dependencies (legacy, not used in C++ version)

## Notes

- The site uses CrowdSec protection which blocks automated scraping of city listing pages
- Individual profile pages may also be protected
- Current implementation uses known profile URLs as a workaround
- To expand coverage, manually add profile URLs to the source code
- Respect rate limits - the scraper includes 500ms delays between requests
