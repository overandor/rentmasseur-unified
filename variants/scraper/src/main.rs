use reqwest::Client;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Instant;
use tokio::time::{timeout, Duration};
use futures::future::join_all;

#[derive(Serialize, Deserialize)]
struct BioResult {
    username: String,
    bio: String,
    success: bool,
}

async fn fetch_bio(client: &Client, username: &str) -> BioResult {
    let url = format!("https://rentmasseur.com/{}", username);
    
    let result = timeout(Duration::from_secs(15), client.get(&url).send()).await;
    
    match result {
        Ok(Ok(response)) => {
            if let Ok(html) = response.text().await {
                let bio = extract_bio(&html);
                BioResult {
                    username: username.to_string(),
                    bio,
                    success: true,
                }
            } else {
                BioResult {
                    username: username.to_string(),
                    bio: String::new(),
                    success: false,
                }
            }
        }
        _ => BioResult {
            username: username.to_string(),
            bio: String::new(),
            success: false,
        },
    }
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

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let usernames = vec![
        "AARONBLAZE", "AlexandrMuscles", "andrewUS", "AntinousAquila", "AronHotBoy",
        "Asian_greathands", "BigHandsHK", "BrownBoyy", "BrunoMathias", "DaddyMelt",
        "EdsBlissfulHands", "EIMARLATINN", "ExoticYoungGuy", "FemboyFey", "Fredericodedeus",
        "GiovanniSF", "HOLLYHOODONLYGEN", "HungMasseurNYC", "Iggyfieryone", "InosukeTopXL",
        "JaceHawkins", "Jacobthejock", "JayMassive", "Jessiepo", "JonnasLatino",
        "karpathianwolf", "LiamGoodBoy", "LustAndRelief", "LVM", "MagicHandsPro",
        "MalikXL", "MarkoMassuer", "Muscltomuscl", "OloSilver", "OscarRubDown",
        "Ritual", "ricardomasseurx", "SamTOPbodywork", "SirIvan", "softsenses",
        "STEPHANOXL", "Steff", "TantraHandsNYC", "TonyAsian", "Will_Xavier",
        "YULIAN", "aTensionGetter", "izzytantra",
    ];
    
    let client = Client::builder()
        .user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        .timeout(Duration::from_secs(15))
        .build()?;
    
    println!("Starting async Rust bio extraction...");
    println!("Total profiles: {}", usernames.len());
    println!("{}", "=".repeat(60));
    
    let start = Instant::now();
    
    // Process all usernames concurrently
    let tasks: Vec<_> = usernames
        .iter()
        .map(|username| fetch_bio(&client, username))
        .collect();
    
    let results = join_all(tasks).await;
    
    let duration = start.elapsed();
    
    // Convert to HashMap for JSON output
    let mut bios_map: HashMap<String, String> = HashMap::new();
    let mut success_count = 0;
    
    for result in results {
        if result.success {
            success_count += 1;
            bios_map.insert(result.username, result.bio);
        } else {
            bios_map.insert(result.username, String::new());
        }
    }
    
    // Write to JSON
    let json_output = serde_json::to_string_pretty(&bios_map)?;
    std::fs::write("all_bios_rust.json", json_output)?;
    
    println!("{}", "=".repeat(60));
    println!("Bio extraction complete!");
    println!("Time taken: {:.2} seconds", duration.as_secs_f64());
    println!("Success: {} / {}", success_count, usernames.len());
    println!("Failed: {} / {}", usernames.len() - success_count, usernames.len());
    println!("Output saved to: all_bios_rust.json");
    
    Ok(())
}
