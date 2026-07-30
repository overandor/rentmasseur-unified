#!/usr/bin/env Rscript
# RentMasseur Bio Analysis Dashboard
# Run this script in RStudio or with Rscript

# Install required packages if not already installed
required_packages <- c("flexdashboard", "ggplot2", "dplyr", "plotly", "jsonlite", "DT", "knitr", "scales")

for (pkg in required_packages) {
  if (!require(pkg, character.only = TRUE)) {
    install.packages(pkg)
    library(pkg, character.only = TRUE)
  }
}

# Load the dashboard
rmarkdown::render("rentmasseur_dashboard.Rmd", 
                  output_file = "rentmasseur_dashboard.html",
                  output_format = "html_document")

cat("Dashboard generated: rentmasseur_dashboard.html\n")
cat("Open this file in your browser to view the interactive dashboard.\n")
