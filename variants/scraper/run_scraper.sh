#!/bin/bash

# RentMasseur Scraper Automation Script
# This script builds and runs the C++ scraper

set -e

echo "=== RentMasseur Scraper Automation ==="
echo ""

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    echo "Error: curl is not installed"
    echo "Install with: brew install curl"
    exit 1
fi

# Check if g++ is installed
if ! command -v g++ &> /dev/null; then
    echo "Error: g++ is not installed"
    echo "Install with: brew install gcc"
    exit 1
fi

# Create data directory
mkdir -p data

echo "Building scraper..."
make clean
make

echo ""
echo "Running scraper..."
./rentmasseur_scraper

echo ""
echo "=== Scraping Complete ==="
echo "Data saved to data/ directory:"
echo "  - masseur_profiles.json"
echo "  - masseur_profiles.csv"
echo "  - views_report.md"
