#include <iostream>
#include <string>
#include <curl/curl.h>
#include <regex>
#include <fstream>
#include <vector>
#include <thread>
#include <mutex>
#include <atomic>
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
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
        curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 10L);
        
        res = curl_easy_perform(curl);
        if(res != CURLE_OK) {
            std::cerr << "curl_easy_perform() failed: " << curl_easy_strerror(res) << std::endl;
        }
        curl_easy_cleanup(curl);
    }
    return readBuffer;
}

std::string extract_bio(const std::string& html) {
    std::regex pattern("\"aboutMe\":\\s*\\{[^}]*\"description\":\\s*\"([^\"]+)\"");
    std::smatch match;
    
    if (std::regex_search(html, match, pattern) && match.size() > 1) {
        return match[1].str();
    }
    
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

struct BioResult {
    std::string username;
    std::string bio;
    bool success;
};

void extract_single_bio(const std::string& username, std::vector<BioResult>& results, std::mutex& mtx) {
    std::string url = "https://rentmasseur.com/" + username;
    std::string html = fetch_url(url);
    
    BioResult result;
    result.username = username;
    
    if (!html.empty()) {
        result.bio = extract_bio(html);
        result.success = !result.bio.empty();
    } else {
        result.success = false;
    }
    
    std::lock_guard<std::mutex> lock(mtx);
    results.push_back(result);
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
    
    const int num_threads = 8; // Parallel threads
    std::vector<std::thread> threads;
    std::vector<BioResult> results;
    std::mutex results_mutex;
    std::atomic<int> completed(0);
    
    curl_global_init(CURL_GLOBAL_ALL);
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    std::cout << "Starting parallel bio extraction with " << num_threads << " threads..." << std::endl;
    std::cout << "Total profiles: " << usernames.size() << std::endl;
    std::cout << std::string(60, '=') << std::endl;
    
    // Process in batches
    for (size_t i = 0; i < usernames.size(); i += num_threads) {
        size_t batch_end = std::min(i + num_threads, usernames.size());
        
        for (size_t j = i; j < batch_end; ++j) {
            threads.emplace_back(extract_single_bio, std::ref(usernames[j]), std::ref(results), std::ref(results_mutex));
        }
        
        for (auto& thread : threads) {
            if (thread.joinable()) {
                thread.join();
            }
        }
        
        threads.clear();
        
        completed += (batch_end - i);
        std::cout << "Progress: " << completed << "/" << usernames.size() << " profiles processed" << std::endl;
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::seconds>(end_time - start_time);
    
    curl_global_cleanup();
    
    // Write results to JSON
    std::ofstream output_file("all_bios.json");
    output_file << "{\n";
    
    for (size_t i = 0; i < results.size(); ++i) {
        const auto& result = results[i];
        
        std::string escaped_bio;
        for (char c : result.bio) {
            switch(c) {
                case '"': escaped_bio += "\\\""; break;
                case '\\': escaped_bio += "\\\\"; break;
                case '\n': escaped_bio += "\\n"; break;
                case '\r': escaped_bio += "\\r"; break;
                case '\t': escaped_bio += "\\t"; break;
                default: escaped_bio += c;
            }
        }
        
        output_file << "  \"" << result.username << "\": \"" << escaped_bio << "\"";
        if (i < results.size() - 1) {
            output_file << ",";
        }
        output_file << "\n";
    }
    
    output_file << "}\n";
    output_file.close();
    
    // Statistics
    int success_count = 0;
    for (const auto& result : results) {
        if (result.success) success_count++;
    }
    
    std::cout << std::string(60, '=') << std::endl;
    std::cout << "Bio extraction complete!" << std::endl;
    std::cout << "Time taken: " << duration.count() << " seconds" << std::endl;
    std::cout << "Success: " << success_count << " / " << usernames.size() << std::endl;
    std::cout << "Failed: " << (usernames.size() - success_count) << " / " << usernames.size() << std::endl;
    std::cout << "Output saved to: all_bios.json" << std::endl;
    
    return 0;
}
