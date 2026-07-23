use reqwest::Client;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::time::Instant;
use tokio::time::{timeout, Duration};

#[derive(Serialize, Deserialize, Debug)]
struct Location {
    location_id: i32,
    search_city: String,
    city: String,
    state: String,
    country: String,
    url: String,
}

async fn fetch_locations(client: &Client) -> Vec<Location> {
    // Use the API endpoint that the Python script found
    let api_url = "https://rentmasseur.com/api/locations";
    
    match timeout(Duration::from_secs(30), client.get(api_url).send()).await {
        Ok(Ok(response)) => {
            if let Ok(text) = response.text().await {
                if let Ok(locations) = serde_json::from_str::<Vec<Location>>(&text) {
                    return locations;
                }
            }
        }
        _ => {}
    }
    
    Vec::new()
}

async fn fetch_usernames_from_city(client: &Client, location: &Location) -> HashSet<String> {
    let url = format!("https://rentmasseur.com/gay-massage/{}/", location.search_city);
    
    let result = timeout(Duration::from_secs(15), client.get(&url).send()).await;
    
    match result {
        Ok(Ok(response)) => {
            if let Ok(html) = response.text().await {
                let username_pattern = Regex::new(r#""username":"([^"]+)""#).unwrap();
                let mut usernames = HashSet::new();
                
                for caps in username_pattern.captures_iter(&html) {
                    if let Some(username) = caps.get(1) {
                        usernames.insert(username.as_str().to_string());
                    }
                }
                
                return usernames;
            }
        }
        _ => {}
    }
    
    HashSet::new()
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::builder()
        .user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        .timeout(Duration::from_secs(15))
        .build()?;
    
    println!("Fetching locations from API...");
    let locations = fetch_locations(&client).await;
    println!("Found {} locations", locations.len());
    
    let start = Instant::now();
    let mut all_usernames: HashSet<String> = HashSet::new();
    
    // Process locations in batches
    let batch_size = 10;
    for (i, location) in locations.iter().enumerate() {
        let batch_start = i / batch_size;
        
        println!("[{}/{}] Processing: {} ({})", i + 1, locations.len(), location.city, location.country);
        
        let usernames = fetch_usernames_from_city(&client, location).await;
        println!("  Found {} usernames", usernames.len());
        
        all_usernames.extend(usernames);
        
        // Small delay between batches
        if (i + 1) % batch_size == 0 {
            tokio::time::sleep(Duration::from_millis(500)).await;
        }
    }
    
    let duration = start.elapsed();
    
    // Save usernames to file
    let usernames_vec: Vec<_> = all_usernames.iter().cloned().collect();
    let json_output = serde_json::to_string_pretty(&usernames_vec)?;
    std::fs::write("all_discovered_usernames.json", json_output)?;
    
    println!("\n{}", "=".repeat(60));
    println!("Username discovery complete!");
    println!("Time taken: {:.2} seconds", duration.as_secs_f64());
    println!("Total unique usernames discovered: {}", all_usernames.len());
    println!("Output saved to: all_discovered_usernames.json");
    
    Ok(())
}
