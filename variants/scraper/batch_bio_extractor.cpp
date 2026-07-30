#include <iostream>
#include <string>
#include <curl/curl.h>
#include <regex>
#include <fstream>
#include <vector>
#include <thread>
#include <chrono>

size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

std::string fetch_url(const std::string& url) {
    CURL* curl;
    CURLcode res;
    std::string readBuffer;
    
    curl = curl_easy_init();
    if(curl) {
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36");
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
        
        res = curl_easy_perform(curl);
        if(res != CURLE_OK) {
            std::cerr << "curl_easy_perform() failed: " << curl_easy_strerror(res) << std::endl;
        }
        curl_easy_cleanup(curl);
    }
    return readBuffer;
}

std::string extract_bio(const std::string& html) {
    // Try the most reliable pattern first
    std::regex pattern("\"aboutMe\":\\s*\\{[^}]*\"description\":\\s*\"([^\"]+)\"");
    std::smatch match;
    
    if (std::regex_search(html, match, pattern) && match.size() > 1) {
        return match[1].str();
    }
    
    // Fallback to other patterns
    std::vector<std::string> fallback_patterns = {
        "\"description\":\\s*\"([^\"]{100,})\"",
        "\"bio\":\\s*\"([^\"]{50,})\"",
        "\"about\":\\s*\"([^\"]{50,})\"",
    };
    
    for (const auto& pattern_str : fallback_patterns) {
        try {
            std::regex fallback_pattern(pattern_str);
            if (std::regex_search(html, match, fallback_pattern) && match.size() > 1) {
                std::string bio = match[1].str();
                if (bio.length() > 50) {
                    return bio;
                }
            }
        } catch (const std::regex_error& e) {
            continue;
        }
    }
    
    return "";
}

int main() {
    std::vector<std::string> usernames = {
        "AARONBLAZE", "AlexandrMuscles", "andrewUS", "AntinousAquila", "AronHotBoy",
        "Asian_greathands", "BigHandsHK", "BrownBoyy", "BrunoMathias", "DaddyMelt",
        "EdsBlissfulHands", "EIMARLATINN", "ExoticYoungGuy", "FemboyFey", "Fredericodedeus",
        "GiovanniSF", "HOLLYHOODONLYGEN", "HungMasseurNYC", "Iggyfieryone", "InosukeTopXL",
        "JaceHawkins", "Jacobthejock", "JayMassive", "Jessiepo", "JonnasLatino",
        "karpathianwolf", "LiamGoodBoy", "LustAndRelief", "LVM", "MagicHandsPro",
        "MalikXL", "MarkoMassuer", "Muscltomuscl", "OloSilver", "OscarRubDown",
        "Ritual", "ricardomasseurx", "SamTOPbodywork", "SirIvan", "softsenses",
        "STEPHANOXL", "Steff", "TantraHandsNYC", "TonyAsian", "Will_Xavier",
        "YULIAN", "aTensionGetter", "izzytantra"
    };
    
    curl_global_init(CURL_GLOBAL_DEFAULT);
    
    std::ofstream output_file("all_bios.json");
    output_file << "{\n";
    
    int success_count = 0;
    int fail_count = 0;
    
    for (size_t i = 0; i < usernames.size(); ++i) {
        const std::string& username = usernames[i];
        std::string url = "https://rentmasseur.com/" + username;
        
        std::cout << "[" << (i+1) << "/" << usernames.size() << "] Extracting bio for: " << username << std::endl;
        
        std::string html = fetch_url(url);
        
        if (!html.empty()) {
            std::string bio = extract_bio(html);
            
            if (!bio.empty()) {
                success_count++;
                std::cout << "  ✓ Bio found (" << bio.length() << " chars)" << std::endl;
                
                // Escape JSON special characters
                std::string escaped_bio;
                for (char c : bio) {
                    switch(c) {
                        case '"': escaped_bio += "\\\""; break;
                        case '\\': escaped_bio += "\\\\"; break;
                        case '\n': escaped_bio += "\\n"; break;
                        case '\r': escaped_bio += "\\r"; break;
                        case '\t': escaped_bio += "\\t"; break;
                        default: escaped_bio += c;
                    }
                }
                
                output_file << "  \"" << username << "\": \"" << escaped_bio << "\"";
                if (i < usernames.size() - 1) {
                    output_file << ",";
                }
                output_file << "\n";
            } else {
                fail_count++;
                std::cout << "  ✗ No bio found" << std::endl;
                output_file << "  \"" << username << "\": \"\"";
                if (i < usernames.size() - 1) {
                    output_file << ",";
                }
                output_file << "\n";
            }
        } else {
            fail_count++;
            std::cout << "  ✗ Failed to fetch profile" << std::endl;
            output_file << "  \"" << username << "\": \"ERROR\"";
            if (i < usernames.size() - 1) {
                output_file << ",";
            }
            output_file << "\n";
        }
        
        // Rate limiting - wait 1 second between requests
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    
    output_file << "}\n";
    output_file.close();
    
    curl_global_cleanup();
    
    std::cout << "\n" << std::string(60, '=') << std::endl;
    std::cout << "Bio extraction complete!" << std::endl;
    std::cout << "Success: " << success_count << " / " << usernames.size() << std::endl;
    std::cout << "Failed: " << fail_count << " / " << usernames.size() << std::endl;
    std::cout << "Output saved to: all_bios.json" << std::endl;
    
    return 0;
}
