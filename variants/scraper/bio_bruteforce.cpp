#include <iostream>
#include <string>
#include <curl/curl.h>
#include <regex>
#include <fstream>
#include <vector>

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

void brute_force_bio_patterns(const std::string& html) {
    // Comprehensive list of bio patterns to try
    std::vector<std::string> pattern_strings = {
        // JSON field patterns for bio
        "\"aboutMe\":\\s*\\{[^}]*\"description\":\\s*\"([^\"]+)\"",
        "\"description\":\\s*\"([^\"]+)\"",
        "\"bio\":\\s*\"([^\"]+)\"",
        "\"about\":\\s*\"([^\"]+)\"",
        
        // UserCard patterns
        "\"userCard\":\\s*\\{[^}]*\"headline\":\\s*\"([^\"]+)\"",
        "\"headline\":\\s*\"([^\"]+)\"",
        
        // Blog/interview patterns
        "\"message\":\\s*\"([^\"]+)\"",
        "\"answer\":\\s*\"([^\"]+)\"",
        
        // Meta description patterns
        "<meta name=\"description\" content=\"([^\"]+)\"",
        "<meta property=\"og:description\" content=\"([^\"]+)\"",
        
        // Escaped JSON patterns
        "\\\\\"aboutMe\\\\\":\\\\s*\\\\{[^}]*\\\\\"description\\\\\":\\\\s*\\\\\"([^\\\\\"]+)\\\\\"",
        "\\\\\"description\\\\\":\\\\s*\\\\\"([^\\\\\"]+)\\\\\"",
        
        // Long text patterns (for multi-line bios)
        "\"description\":\\s*\"([^\"]{100,})\"",
        "\"aboutMe\":\\s*\\{[^}]*\"description\":\\s*\"([^\"]{100,})\"",
    };
    
    std::cout << "Brute-forcing " << pattern_strings.size() << " bio patterns..." << std::endl;
    std::cout << "=" << std::string(60, '=') << std::endl;
    
    int found_count = 0;
    std::vector<std::string> found_bios;
    
    for (size_t i = 0; i < pattern_strings.size(); ++i) {
        const std::string& pattern_str = pattern_strings[i];
        
        try {
            std::regex pattern(pattern_str);
            std::smatch match;
            bool found = false;
            std::string bio;
            
            if (std::regex_search(html, match, pattern)) {
                found = true;
                if (match.size() > 1) {
                    bio = match[1].str();
                } else {
                    bio = match[0].str();
                }
            }
            
            if (found && bio.length() > 20) { // Filter out very short matches
                found_count++;
                found_bios.push_back(bio);
                std::cout << "✓ Pattern " << (i+1) << " MATCHED" << std::endl;
                std::cout << "  Pattern: " << pattern_str << std::endl;
                std::cout << "  Bio length: " << bio.length() << " chars" << std::endl;
                std::cout << "  Bio preview: " << bio.substr(0, 100) << "..." << std::endl;
                std::cout << std::endl;
            }
        } catch (const std::regex_error& e) {
            std::cerr << "Pattern " << i << " error: " << e.what() << std::endl;
            continue;
        }
    }
    
    std::cout << "=" << std::string(60, '=') << std::endl;
    std::cout << "Total matches: " << found_count << " / " << pattern_strings.size() << std::endl;
    
    // Remove duplicates
    std::sort(found_bios.begin(), found_bios.end());
    found_bios.erase(std::unique(found_bios.begin(), found_bios.end()), found_bios.end());
    
    std::cout << "Unique bios found: " << found_bios.size() << std::endl;
    for (size_t i = 0; i < found_bios.size(); ++i) {
        std::cout << "Bio " << (i+1) << " (" << found_bios[i].length() << " chars):" << std::endl;
        std::cout << found_bios[i] << std::endl;
        std::cout << std::endl;
    }
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <username>" << std::endl;
        std::cout << "Example: " << argv[0] << " Karpathianwolf" << std::endl;
        return 1;
    }
    
    std::string username = argv[1];
    std::string url = "https://rentmasseur.com/" + username;
    
    curl_global_init(CURL_GLOBAL_DEFAULT);
    
    std::cout << "Fetching profile: " << url << std::endl;
    std::string html = fetch_url(url);
    
    if (!html.empty()) {
        std::cout << "Downloaded " << html.length() << " bytes" << std::endl;
        std::cout << std::endl;
        
        brute_force_bio_patterns(html);
    } else {
        std::cout << "Failed to fetch profile" << std::endl;
    }
    
    curl_global_cleanup();
    
    return 0;
}
