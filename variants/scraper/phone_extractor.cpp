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

std::string extract_phone_number(const std::string& html) {
    // Extract phone number from the JSON data in the page
    // Search for phone number patterns
    std::regex phone_pattern(R"(\+1\s*\d{3}\s*\d{3}\s*\d{4})");
    std::smatch match;
    
    if (std::regex_search(html, match, phone_pattern)) {
        return match[0].str();
    }
    
    // Try alternative pattern for phone in JSON
    std::regex json_pattern(R"(mobile[":]\s*["]([^"]+)["])");
    if (std::regex_search(html, match, json_pattern) && match.size() > 1) {
        return match[1].str();
    }
    
    return "Not found";
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
        // Save full HTML for debugging
        std::ofstream debug_file("debug_phone_" + username + ".html");
        debug_file << html;
        debug_file.close();
        
        std::string phone = extract_phone_number(html);
        
        std::cout << "Username: " << username << std::endl;
        std::cout << "Phone: " << phone << std::endl;
        std::cout << "Debug file saved: debug_phone_" << username << ".html" << std::endl;
    } else {
        std::cout << "Failed to fetch profile" << std::endl;
    }
    
    curl_global_cleanup();
    
    return 0;
}
