use reqwest::Client;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::time::Instant;
use tokio::time::{timeout, Duration};
use futures::future::join_all;

#[derive(Serialize, Deserialize, Debug)]
struct CompleteProfile {
    username: String,
    bio: String,
    phone: String,
    location: String,
    headline: String,
    services: Vec<String>,
    rating: String,
    reviews: i32,
    views: i32,
}

async fn fetch_profile_data(client: &Client, username: &str) -> (String, String, i32) {
    let url = format!("https://rentmasseur.com/{}", username);
    
    let result = timeout(Duration::from_secs(15), client.get(&url).send()).await;
    
    match result {
        Ok(Ok(response)) => {
            if let Ok(html) = response.text().await {
                let bio = extract_bio(&html);
                let phone = extract_phone(&html);
                let views = extract_views(&html);
                return (bio, phone, views);
            }
        }
        _ => {}
    }
    
    (String::new(), String::new(), 0)
}

fn extract_bio(html: &str) -> String {
    let pattern = Regex::new(r#""aboutMe":\s*\{[^}]*"description":\s*"([^"]+)""#).unwrap();
    
    if let Some(caps) = pattern.captures(html) {
        if let Some(bio) = caps.get(1) {
            return bio.as_str().to_string();
        }
    }
    
    let fallback_patterns = vec![
        r#""description":\s*"([^"]{100,})""#,
        r#""bio":\s*"([^"]{50,})""#,
        r#""about":\s*"([^"]{50,})""#,
    ];
    
    for pattern_str in fallback_patterns {
        if let Ok(pattern) = Regex::new(pattern_str) {
            if let Some(caps) = pattern.captures(html) {
                if let Some(bio) = caps.get(1) {
                    if bio.as_str().len() > 50 {
                        return bio.as_str().to_string();
                    }
                }
            }
        }
    }
    
    String::new()
}

fn extract_phone(html: &str) -> String {
    let phone_pattern = Regex::new(r"\+1\s*\d{3}\s*\d{3}\s*\d{4}").unwrap();
    
    if let Some(caps) = phone_pattern.captures(html) {
        return caps[0].to_string();
    }
    
    let json_pattern = Regex::new(r#""mobile":\s*"([^"]+)""#).unwrap();
    if let Some(caps) = json_pattern.captures(html) {
        return caps[1].to_string();
    }
    
    String::new()
}

fn extract_views(html: &str) -> i32 {
    let patterns = vec![
        r#""totalViews":\s*(\d+)"#,
        r#""views":\s*(\d+)"#,
        r#""viewCount":\s*(\d+)"#,
        r#""profileViews":\s*(\d+)"#,
        r#""total_views":\s*(\d+)"#,
        r#""view_count":\s*(\d+)"#,
    ];
    
    for pattern_str in patterns {
        if let Ok(pattern) = Regex::new(pattern_str) {
            if let Some(caps) = pattern.captures(html) {
                if let Some(views) = caps.get(1) {
                    if let Ok(count) = views.as_str().parse::<i32>() {
                        if count > 0 {
                            return count;
                        }
                    }
                }
            }
        }
    }
    
    0
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Load discovered usernames
    let usernames_json = std::fs::read_to_string("all_city_usernames.json")?;
    let usernames: Vec<String> = serde_json::from_str(&usernames_json)?;
    
    println!("Processing {} discovered profiles...", usernames.len());
    
    let client = Client::builder()
        .user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        .timeout(Duration::from_secs(15))
        .build()?;
    
    let start = Instant::now();
    let mut complete_profiles: Vec<CompleteProfile> = Vec::new();
    
    // Process concurrently in batches
    let batch_size = 50;
    let mut processed = 0;
    
    for chunk in usernames.chunks(batch_size) {
        println!("[{}/{}] Processing batch of {} profiles...", processed + 1, usernames.len(), chunk.len());
        
        let tasks: Vec<_> = chunk.iter().map(|username| {
            let client = client.clone();
            let username = username.clone();
            async move {
                let (bio, phone, views) = fetch_profile_data(&client, &username).await;
                CompleteProfile {
                    username,
                    bio,
                    phone,
                    location: String::new(),
                    headline: String::new(),
                    services: Vec::new(),
                    rating: "0".to_string(),
                    reviews: 0,
                    views,
                }
            }
        }).collect();
        
        let results = join_all(tasks).await;
        complete_profiles.extend(results);
        processed += chunk.len();
        
        // Small delay between batches
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
    
    let duration = start.elapsed();
    
    // Save results
    let json_output = serde_json::to_string_pretty(&complete_profiles)?;
    std::fs::write("complete_profiles_with_bios_phones.json", json_output)?;
    
    // Count stats
    let with_bio = complete_profiles.iter().filter(|p| !p.bio.is_empty()).count();
    let with_phone = complete_profiles.iter().filter(|p| !p.phone.is_empty()).count();
    let with_views = complete_profiles.iter().filter(|p| p.views > 0).count();
    let total_views: i32 = complete_profiles.iter().map(|p| p.views).sum();
    
    println!("\n{}", "=".repeat(60));
    println!("Bulk extraction complete!");
    println!("Time taken: {:.2} seconds", duration.as_secs_f64());
    println!("Total profiles processed: {}", complete_profiles.len());
    println!("Profiles with bio: {}", with_bio);
    println!("Profiles with phone: {}", with_phone);
    println!("Profiles with view count: {}", with_views);
    println!("Total views across all profiles: {}", total_views);
    println!("Output saved to: complete_profiles_with_bios_phones.json");
    
    Ok(())
}
