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

async fn fetch_locations(client: &Client) -> Vec<Location> {
    let url = "https://rentmasseur.com/api/locations";
    
    match timeout(Duration::from_secs(30), client.get(url).send()).await {
        Ok(Ok(response)) => {
            if let Ok(text) = response.text().await {
                if let Ok(locations) = serde_json::from_str::<Vec<Location>>(&text) {
                    println!("Successfully fetched {} locations from API", locations.len());
                    return locations;
                }
            }
        }
        _ => {}
    }
    
    println!("API failed, using hardcoded major cities as fallback");
    // Fallback to hardcoded major cities - expanded list
    vec![
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
        Location {
            location_id: 4,
            search_city: "chicago".to_string(),
            city: "Chicago".to_string(),
            state: "IL".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/chicago/".to_string(),
        },
        Location {
            location_id: 5,
            search_city: "saopaulo".to_string(),
            city: "Sao Paulo".to_string(),
            state: "São Paulo".to_string(),
            country: "Brazil".to_string(),
            url: "https://rentmasseur.com/gay-massage/saopaulo/".to_string(),
        },
        Location {
            location_id: 6,
            search_city: "miami".to_string(),
            city: "Miami".to_string(),
            state: "FL".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/miami/".to_string(),
        },
        Location {
            location_id: 7,
            search_city: "sanfrancisco".to_string(),
            city: "San Francisco".to_string(),
            state: "CA".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/sanfrancisco/".to_string(),
        },
        Location {
            location_id: 8,
            search_city: "london".to_string(),
            city: "London".to_string(),
            state: "".to_string(),
            country: "UK".to_string(),
            url: "https://rentmasseur.com/gay-massage/london/".to_string(),
        },
        Location {
            location_id: 9,
            search_city: "toronto".to_string(),
            city: "Toronto".to_string(),
            state: "ON".to_string(),
            country: "Canada".to_string(),
            url: "https://rentmasseur.com/gay-massage/toronto/".to_string(),
        },
        Location {
            location_id: 10,
            search_city: "sydney".to_string(),
            city: "Sydney".to_string(),
            state: "".to_string(),
            country: "Australia".to_string(),
            url: "https://rentmasseur.com/gay-massage/sydney/".to_string(),
        },
        Location {
            location_id: 11,
            search_city: "bogota".to_string(),
            city: "Bogota".to_string(),
            state: "".to_string(),
            country: "Colombia".to_string(),
            url: "https://rentmasseur.com/gay-massage/bogota/".to_string(),
        },
        Location {
            location_id: 12,
            search_city: "lima".to_string(),
            city: "Lima".to_string(),
            state: "".to_string(),
            country: "Peru".to_string(),
            url: "https://rentmasseur.com/gay-massage/lima/".to_string(),
        },
        Location {
            location_id: 13,
            search_city: "buenosaires".to_string(),
            city: "Buenos Aires".to_string(),
            state: "".to_string(),
            country: "Argentina".to_string(),
            url: "https://rentmasseur.com/gay-massage/buenosaires/".to_string(),
        },
        Location {
            location_id: 14,
            search_city: "madrid".to_string(),
            city: "Madrid".to_string(),
            state: "".to_string(),
            country: "Spain".to_string(),
            url: "https://rentmasseur.com/gay-massage/madrid/".to_string(),
        },
        Location {
            location_id: 15,
            search_city: "barcelona".to_string(),
            city: "Barcelona".to_string(),
            state: "".to_string(),
            country: "Spain".to_string(),
            url: "https://rentmasseur.com/gay-massage/barcelona/".to_string(),
        },
        Location {
            location_id: 16,
            search_city: "houston".to_string(),
            city: "Houston".to_string(),
            state: "TX".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/houston/".to_string(),
        },
        Location {
            location_id: 17,
            search_city: "dallas".to_string(),
            city: "Dallas".to_string(),
            state: "TX".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/dallas/".to_string(),
        },
        Location {
            location_id: 18,
            search_city: "atlanta".to_string(),
            city: "Atlanta".to_string(),
            state: "GA".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/atlanta/".to_string(),
        },
        Location {
            location_id: 19,
            search_city: "phoenix".to_string(),
            city: "Phoenix".to_string(),
            state: "AZ".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/phoenix/".to_string(),
        },
        Location {
            location_id: 20,
            search_city: "seattle".to_string(),
            city: "Seattle".to_string(),
            state: "WA".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/seattle/".to_string(),
        },
        Location {
            location_id: 21,
            search_city: "denver".to_string(),
            city: "Denver".to_string(),
            state: "CO".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/denver/".to_string(),
        },
        Location {
            location_id: 22,
            search_city: "boston".to_string(),
            city: "Boston".to_string(),
            state: "MA".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/boston/".to_string(),
        },
        Location {
            location_id: 23,
            search_city: "washingtondc".to_string(),
            city: "Washington DC".to_string(),
            state: "DC".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/washingtondc/".to_string(),
        },
        Location {
            location_id: 24,
            search_city: "orlando".to_string(),
            city: "Orlando".to_string(),
            state: "FL".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/orlando/".to_string(),
        },
        Location {
            location_id: 25,
            search_city: "lasvegas".to_string(),
            city: "Las Vegas".to_string(),
            state: "NV".to_string(),
            country: "USA".to_string(),
            url: "https://rentmasseur.com/gay-massage/lasvegas/".to_string(),
        },
        Location {
            location_id: 26,
            search_city: "amsterdam".to_string(),
            city: "Amsterdam".to_string(),
            state: "".to_string(),
            country: "Netherlands".to_string(),
            url: "https://rentmasseur.com/gay-massage/amsterdam/".to_string(),
        },
        Location {
            location_id: 27,
            search_city: "berlin".to_string(),
            city: "Berlin".to_string(),
            state: "".to_string(),
            country: "Germany".to_string(),
            url: "https://rentmasseur.com/gay-massage/berlin/".to_string(),
        },
        Location {
            location_id: 28,
            search_city: "paris".to_string(),
            city: "Paris".to_string(),
            state: "".to_string(),
            country: "France".to_string(),
            url: "https://rentmasseur.com/gay-massage/paris/".to_string(),
        },
        Location {
            location_id: 29,
            search_city: "rome".to_string(),
            city: "Rome".to_string(),
            state: "".to_string(),
            country: "Italy".to_string(),
            url: "https://rentmasseur.com/gay-massage/rome/".to_string(),
        },
        Location {
            location_id: 30,
            search_city: "mexicocity".to_string(),
            city: "Mexico City".to_string(),
            state: "".to_string(),
            country: "Mexico".to_string(),
            url: "https://rentmasseur.com/gay-massage/mexicocity/".to_string(),
        },
    ]
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
                    let profiles = extract_profiles_from_html(&html);
                    
                    if profiles.is_empty() {
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
                    has_more = false;
                }
            }
            _ => {
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
    let services_pattern = Regex::new(r#""services":\s*\[([^\]]+)\]"#).unwrap();
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
    
    println!("Fetching locations from API...");
    let locations = fetch_locations(&client).await;
    println!("Found {} locations", locations.len());
    
    if locations.is_empty() {
        println!("No locations found. Exiting.");
        return Ok(());
    }
    
    let start = Instant::now();
    let mut all_profiles: Vec<Profile> = Vec::new();
    let mut all_usernames: HashSet<String> = HashSet::new();
    
    // Process locations
    for (i, location) in locations.iter().enumerate() {
        println!("[{}/{}] Processing: {} ({})", i + 1, locations.len(), location.city, location.country);
        
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
    std::fs::write("all_city_profiles.json", json_output)?;
    
    // Save just usernames
    let usernames_vec: Vec<_> = all_usernames.iter().cloned().collect();
    let usernames_json = serde_json::to_string_pretty(&usernames_vec)?;
    std::fs::write("all_city_usernames.json", usernames_json)?;
    
    println!("\n{}", "=".repeat(60));
    println!("Profile discovery complete!");
    println!("Time taken: {:.2} seconds", duration.as_secs_f64());
    println!("Total unique profiles discovered: {}", all_profiles.len());
    println!("Total cities processed: {}", locations.len());
    println!("Output saved to: all_city_profiles.json");
    println!("Usernames saved to: all_city_usernames.json");
    
    Ok(())
}
