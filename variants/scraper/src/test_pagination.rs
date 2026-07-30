use reqwest::Client;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::time::Instant;
use tokio::time::{timeout, Duration};

#[derive(Serialize, Deserialize, Debug)]
struct Location {
    #[serde(rename = "locationId")]
    location_id: i32,
    #[serde(rename = "searchCity")]
    search_city: String,
    city: String,
    state: String,
    country: String,
    url: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct Profile {
    username: String,
    description: String,
    headline: String,
    location: String,
    services: Vec<String>,
    rating: String,
    reviews: i32,
}

async fn fetch_profiles_from_city(client: &Client, location: &Location) -> Vec<Profile> {
    let mut all_profiles: Vec<Profile> = Vec::new();
    let mut page = 1;
    let mut has_more = true;
    
    while has_more {
        let url = if page == 1 {
            format!("https://rentmasseur.com/gay-massage/{}/", location.search_city)
        } else {
            format!("https://rentmasseur.com/gay-massage/{}/?page={}", location.search_city, page)
        };
        
        let result = timeout(Duration::from_secs(20), client.get(&url).send()).await;
        
        match result {
            Ok(Ok(response)) => {
                if let Ok(html) = response.text().await {
                    println!("    Page {}: HTML length = {}", page, html.len());
                    
                    // Debug: save first page HTML for inspection
                    if page == 1 {
                        std::fs::write(format!("debug_{}_page1.html", location.search_city), &html).ok();
                    }
                    
                    let profiles = extract_profiles_from_html(&html);
                    
                    if profiles.is_empty() {
                        println!("    Page {}: No profiles found, stopping", page);
                        has_more = false;
                    } else {
                        println!("    Page {}: {} profiles", page, profiles.len());
                        all_profiles.extend(profiles);
                        page += 1;
                        
                        // Safety limit to prevent infinite loops
                        if page > 50 {
                            println!("    Reached page limit (50), stopping");
                            has_more = false;
                        }
                    }
                } else {
                    println!("    Page {}: Failed to read HTML", page);
                    has_more = false;
                }
            }
            Ok(Err(e)) => {
                println!("    Page {}: HTTP error: {:?}", page, e);
                has_more = false;
            }
            Err(e) => {
                println!("    Page {}: Request timeout: {:?}", page, e);
                has_more = false;
            }
        }
        
        // Small delay between pages
        tokio::time::sleep(Duration::from_millis(300)).await;
    }
    
    all_profiles
}

fn extract_profiles_from_html(html: &str) -> Vec<Profile> {
    let mut profiles = Vec::new();
    
    // Extract profile data from the JSON embedded in HTML
    let username_pattern = Regex::new(r#""username":"([^"]+)""#).unwrap();
    let description_pattern = Regex::new(r#""description":"([^"]+)""#).unwrap();
    let headline_pattern = Regex::new(r#""headline":"([^"]+)""#).unwrap();
    let location_pattern = Regex::new(r#""location":"([^"]+)""#).unwrap();
    let rating_pattern = Regex::new(r#""ratingAverage":"([^"]+)""#).unwrap();
    let reviews_pattern = Regex::new(r#""reviewsCount":(\d+)"#).unwrap();
    
    let usernames: Vec<String> = username_pattern.captures_iter(html)
        .filter_map(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .collect();
    
    let descriptions: Vec<String> = description_pattern.captures_iter(html)
        .filter_map(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .collect();
    
    let headlines: Vec<String> = headline_pattern.captures_iter(html)
        .filter_map(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .collect();
    
    let locations: Vec<String> = location_pattern.captures_iter(html)
        .filter_map(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .collect();
    
    let ratings: Vec<String> = rating_pattern.captures_iter(html)
        .filter_map(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .collect();
    
    let reviews: Vec<i32> = reviews_pattern.captures_iter(html)
        .filter_map(|c| c.get(1))
        .filter_map(|m| m.as_str().parse().ok())
        .collect();
    
    let min_len = usernames.len().min(descriptions.len()).min(headlines.len()).min(locations.len());
    
    for i in 0..min_len {
        let services = if i < descriptions.len() {
            extract_services(&descriptions[i])
        } else {
            Vec::new()
        };
        
        profiles.push(Profile {
            username: usernames[i].clone(),
            description: descriptions[i].clone(),
            headline: headlines[i].clone(),
            location: locations[i].clone(),
            services,
            rating: ratings.get(i).cloned().unwrap_or("0".to_string()),
            reviews: reviews.get(i).copied().unwrap_or(0),
        });
    }
    
    profiles
}

fn extract_services(text: &str) -> Vec<String> {
    let mut services = Vec::new();
    let service_keywords = vec![
        "therapeutic", "sensual", "swedish", "deep tissue", 
        "hot stone", "sports", "shiatsu", "thai", "reflexology",
        "four hands", "tantric", "nuru"
    ];
    
    let lower_text = text.to_lowercase();
    for keyword in service_keywords {
        if lower_text.contains(keyword) {
            services.push(keyword.to_string());
        }
    }
    
    services
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::builder()
        .user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        .timeout(Duration::from_secs(20))
        .build()?;
    
    // Test with just 3 cities to verify pagination works
    let test_locations = vec![
        Location {
            location_id: 1,
            search_city: "newyork".to_string(),
            city: "New York City".to_string(),
            state: "NY".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/newyork/".to_string(),
        },
        Location {
            location_id: 2,
            search_city: "manhattan-ny".to_string(),
            city: "Manhattan".to_string(),
            state: "NY".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/manhattan-ny/".to_string(),
        },
        Location {
            location_id: 3,
            search_city: "losangeles".to_string(),
            city: "Los Angeles".to_string(),
            state: "CA".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/losangeles/".to_string(),
        },
    ];
    
    println!("Testing pagination on {} cities...", test_locations.len());
    
    let start = Instant::now();
    let mut all_profiles: Vec<Profile> = Vec::new();
    let mut all_usernames: HashSet<String> = HashSet::new();
    
    // Process locations
    for (i, location) in test_locations.iter().enumerate() {
        println!("[{}/{}] Processing: {} ({})", i + 1, test_locations.len(), location.city, location.country);
        
        let profiles = fetch_profiles_from_city(&client, location).await;
        println!("  Total profiles from {}: {}", location.city, profiles.len());
        
        for profile in profiles {
            if all_usernames.insert(profile.username.clone()) {
                all_profiles.push(profile);
            }
        }
        
        // Small delay between cities
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    
    let duration = start.elapsed();
    
    // Save results
    let json_output = serde_json::to_string_pretty(&all_profiles)?;
    std::fs::write("test_pagination_profiles.json", json_output)?;
    
    // Save just usernames
    let usernames_vec: Vec<_> = all_usernames.iter().cloned().collect();
    let usernames_json = serde_json::to_string_pretty(&usernames_vec)?;
    std::fs::write("test_pagination_usernames.json", usernames_json)?;
    
    println!("\n{}", "=".repeat(60));
    println!("Pagination test complete!");
    println!("Time taken: {:.2} seconds", duration.as_secs_f64());
    println!("Total unique profiles discovered: {}", all_profiles.len());
    println!("Total cities processed: {}", test_locations.len());
    println!("Output saved to: test_pagination_profiles.json");
    println!("Usernames saved to: test_pagination_usernames.json");
    
    Ok(())
}
