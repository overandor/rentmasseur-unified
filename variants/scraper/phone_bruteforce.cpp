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

void brute_force_phone_patterns(const std::string& html) {
    // Comprehensive list of phone number patterns to try
    std::vector<std::string> pattern_strings = {
        // Basic US phone patterns
        "\\+1\\s*\\d{3}\\s*\\d{3}\\s*\\d{4}",
        "\\+1\\d{10}",
        "\\d{3}[-.\\s]\\d{3}[-.\\s]\\d{4}",
        "\\d{10}",
        
        // JSON field patterns
        "\"mobile\":\\s*\"([^\"]+)\"",
        "mobile\":\\s*\"([^\"]+)\"",
        "mobile\\\\\":\\s*\\\\\"([^\\\\\"]+)\\\\\"",
        "mobile[\":]\\s*[\"']([^\"]+)[\"']",
        
        // Phone field patterns
        "\"phone\":\\s*\"([^\"]+)\"",
        "phone\":\\s*\"([^\"]+)\"",
        "phone[\":]\\s*[\"']([^\"]+)[\"']",
        
        // Contact field patterns
        "\"contact\":\\s*\"([^\"]+)\"",
        "contact\":\\s*\"([^\"]+)\"",
        
        // Tel patterns
        "\"tel\":\\s*\"([^\"]+)\"",
        "tel\":\\s*\"([^\"]+)\"",
        
        // Various phone number formats
        "\\(\\d{3}\\)\\s*\\d{3}-\\d{4}",
        "\\d{3}-\\d{3}-\\d{4}",
        "\\d{3}\\.\\d{3}\\.\\d{4}",
        "\\d{3}\\s\\d{3}\\s\\d{4}",
        
        // International patterns
        "\\+\\d{1,3}\\s*\\d{3,14}",
        "\\+\\d{11,15}",
        
        // Escaped JSON patterns
        "\\\\\"mobile\\\\\":\\\\s*\\\\\"([^\\\\\"]+)\\\\\"",
        "\\\\\"phone\\\\\":\\\\s*\\\\\"([^\\\\\"]+)\\\\\"",
        
        // ContactMe patterns
        "\"contactMe\":\\s*\\{[^}]*\"phones\":\\s*\\{[^}]*\"mobile\":\\s*\"([^\"]+)\"",
    };
    
    std::cout << "Brute-forcing " << pattern_strings.size() << " phone patterns..." << std::endl;
    std::cout << "=" << std::string(60, '=') << std::endl;
    
    int found_count = 0;
    std::vector<std::string> found_phones;
    
    for (size_t i = 0; i < pattern_strings.size(); ++i) {
        const std::string& pattern_str = pattern_strings[i];
        
        try {
            std::regex pattern(pattern_str);
            std::smatch match;
            bool found = false;
            std::string phone;
            
            if (std::regex_search(html, match, pattern)) {
                found = true;
                if (match.size() > 1) {
                    phone = match[1].str();
                } else {
                    phone = match[0].str();
                }
            }
            
            if (found) {
                found_count++;
                found_phones.push_back(phone);
                std::cout << "✓ Pattern " << (i+1) << " MATCHED" << std::endl;
                std::cout << "  Pattern: " << pattern_str << std::endl;
                std::cout << "  Phone: " << phone << std::endl;
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
    std::sort(found_phones.begin(), found_phones.end());
    found_phones.erase(std::unique(found_phones.begin(), found_phones.end()), found_phones.end());
    
    std::cout << "Unique phone numbers found: " << found_phones.size() << std::endl;
    for (const auto& phone : found_phones) {
        std::cout << "  - " << phone << std::endl;
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
        
        brute_force_phone_patterns(html);
    } else {
        std::cout << "Failed to fetch profile" << std::endl;
    }
    
    curl_global_cleanup();
    
    return 0;
}
