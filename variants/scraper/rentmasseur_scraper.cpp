#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <fstream>
#include <sstream>
#include <regex>
#include <ctime>
#include <cmath>
#include <thread>
#include <chrono>
#include <algorithm>
#include <curl/curl.h>

struct MasseurProfile {
    std::string username;
    std::string profile_url;
    std::string location;
    std::string registration_date;
    int total_views;
    std::string bio;
    std::vector<std::string> massage_types;
    std::vector<std::string> travel_schedule;
    double views_per_day;
    std::string last_updated;
    
    MasseurProfile() : total_views(0), views_per_day(0.0) {}
};

size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

size_t HeaderCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    std::string* header_string = (std::string*)userp;
    header_string->append((char*)contents, size * nmemb);
    return size * nmemb;
}

std::string cookie_file = "cookies.txt";

std::string login(const std::string& username, const std::string& password) {
    CURL* curl;
    CURLcode res;
    std::string readBuffer;
    
    curl = curl_easy_init();
    if(curl) {
        // Login URL
        std::string login_url = "https://rentmasseur.com/login";
        
        // Post data
        std::string post_fields = "username=" + username + "&password=" + password;
        
        curl_easy_setopt(curl, CURLOPT_URL, login_url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_fields.c_str());
        curl_easy_setopt(curl, CURLOPT_COOKIEJAR, cookie_file.c_str());
        curl_easy_setopt(curl, CURLOPT_COOKIEFILE, cookie_file.c_str());
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36");
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
        
        res = curl_easy_perform(curl);
        if(res != CURLE_OK) {
            std::cerr << "Login failed: " << curl_easy_strerror(res) << std::endl;
        } else {
            std::cout << "Login attempt completed" << std::endl;
        }
        curl_easy_cleanup(curl);
    }
    return readBuffer;
}

std::string fetch_url(const std::string& url, bool use_cookies = true) {
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
        
        if(use_cookies) {
            curl_easy_setopt(curl, CURLOPT_COOKIEFILE, cookie_file.c_str());
            curl_easy_setopt(curl, CURLOPT_COOKIEJAR, cookie_file.c_str());
        }
        
        res = curl_easy_perform(curl);
        if(res != CURLE_OK) {
            std::cerr << "curl_easy_perform() failed: " << curl_easy_strerror(res) << std::endl;
        }
        curl_easy_cleanup(curl);
    }
    return readBuffer;
}

std::vector<std::string> extract_profile_links(const std::string& html) {
    std::vector<std::string> links;
    std::regex profile_regex(R"(https://rentmasseur\.com/([a-zA-Z0-9_-]+))");
    std::sregex_iterator it(html.begin(), html.end(), profile_regex);
    std::sregex_iterator end;
    
    std::set<std::string> unique_links;
    for(; it != end; ++it) {
        std::string link = it->str();
        if(link.find("gay-massage") == std::string::npos && 
           link.find("massages/") == std::string::npos &&
           link.length() > 25) {
            unique_links.insert(link);
        }
    }
    
    for(const auto& link : unique_links) {
        links.push_back(link);
    }
    
    return links;
}

std::string extract_text(const std::string& html, const std::string& pattern) {
    std::regex regex(pattern);
    std::smatch match;
    if(std::regex_search(html, match, regex) && match.size() > 1) {
        return match[1].str();
    }
    return "";
}

int extract_views(const std::string& html) {
    std::regex view_regex(R"((\d{1,3}(,\d{3})*))");
    std::sregex_iterator it(html.begin(), html.end(), view_regex);
    std::sregex_iterator end;
    
    int max_views = 0;
    for(; it != end; ++it) {
        std::string num_str = (*it)[1].str();
        // Remove commas
        num_str.erase(std::remove(num_str.begin(), num_str.end(), ','), num_str.end());
        try {
            int num = std::stoi(num_str);
            if(num > max_views && num < 1000000) { // Reasonable view count range
                max_views = num;
            }
        } catch(...) {}
    }
    return max_views;
}

std::string extract_registration_date(const std::string& html) {
    std::vector<std::string> patterns = {
        R"(since\s+([A-Za-z]+\s+\d{4}))",
        R"(joined\s+([A-Za-z]+\s+\d{4}))",
        R"(member\s+since\s+([A-Za-z]+\s+\d{4}))",
        R"((\d{4}-\d{2}-\d{2}))",
        R"((\d{2}/\d{2}/\d{4}))"
    };
    
    for(const auto& pattern : patterns) {
        std::string result = extract_text(html, pattern);
        if(!result.empty()) {
            return result;
        }
    }
    return "";
}

double calculate_views_per_day(int total_views, const std::string& reg_date_str) {
    if(total_views == 0 || reg_date_str.empty()) return 0.0;
    
    // Try to parse the date
    std::tm tm = {};
    std::istringstream iss(reg_date_str);
    
    // Try different formats
    const char* formats[] = {"%Y-%m-%d", "%m/%d/%Y", "%B %Y", "%b %Y", "%Y"};
    for(const auto& fmt : formats) {
        iss.clear();
        iss.str(reg_date_str);
        if(iss >> std::get_time(&tm, fmt)) {
            std::time_t reg_time = std::mktime(&tm);
            std::time_t now = std::time(nullptr);
            double days = difftime(now, reg_time) / (60 * 60 * 24);
            if(days > 0) {
                return round((total_views / days) * 100.0) / 100.0;
            }
        }
    }
    
    return 0.0;
}

std::string get_current_timestamp() {
    std::time_t now = std::time(nullptr);
    char buf[80];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", std::localtime(&now));
    return std::string(buf);
}

void save_to_json(const std::map<std::string, MasseurProfile>& profiles, const std::string& filename) {
    std::ofstream file(filename);
    file << "{\n";
    
    auto it = profiles.begin();
    while(it != profiles.end()) {
        const auto& profile = it->second;
        file << "  \"" << profile.username << "\": {\n";
        file << "    \"username\": \"" << profile.username << "\",\n";
        file << "    \"profile_url\": \"" << profile.profile_url << "\",\n";
        file << "    \"location\": \"" << profile.location << "\",\n";
        file << "    \"registration_date\": \"" << profile.registration_date << "\",\n";
        file << "    \"total_views\": " << profile.total_views << ",\n";
        file << "    \"views_per_day\": " << profile.views_per_day << ",\n";
        file << "    \"bio\": \"" << profile.bio << "\",\n";
        file << "    \"last_updated\": \"" << profile.last_updated << "\"\n";
        file << "  }";
        
        if(++it != profiles.end()) {
            file << ",\n";
        } else {
            file << "\n";
        }
    }
    
    file << "}\n";
    file.close();
    std::cout << "Saved " << profiles.size() << " profiles to " << filename << std::endl;
}

void save_to_csv(const std::map<std::string, MasseurProfile>& profiles, const std::string& filename) {
    std::ofstream file(filename);
    file << "username,profile_url,location,registration_date,total_views,views_per_day,bio,last_updated\n";
    
    for(const auto& pair : profiles) {
        const auto& profile = pair.second;
        file << "\"" << profile.username << "\","
             << "\"" << profile.profile_url << "\","
             << "\"" << profile.location << "\","
             << "\"" << profile.registration_date << "\","
             << profile.total_views << ","
             << profile.views_per_day << ","
             << "\"" << profile.bio << "\","
             << "\"" << profile.last_updated << "\"\n";
    }
    
    file.close();
    std::cout << "Saved " << profiles.size() << " profiles to " << filename << std::endl;
}

void generate_report(const std::map<std::string, MasseurProfile>& profiles, const std::string& filename) {
    std::ofstream file(filename);
    
    file << "# RentMasseur Views Analysis Report\n\n";
    file << "Generated: " << get_current_timestamp() << "\n";
    file << "Total Profiles: " << profiles.size() << "\n\n";
    
    // Sort by views per day
    std::vector<MasseurProfile> sorted_profiles;
    for(const auto& pair : profiles) {
        sorted_profiles.push_back(pair.second);
    }
    std::sort(sorted_profiles.begin(), sorted_profiles.end(), 
              [](const MasseurProfile& a, const MasseurProfile& b) {
                  return a.views_per_day > b.views_per_day;
              });
    
    file << "## Top Profiles by Views Per Day\n\n";
    file << "| Username | Location | Total Views | Views/Day | Registered |\n";
    file << "|----------|----------|-------------|-----------|------------|\n";
    
    size_t count = 0;
    for(const auto& profile : sorted_profiles) {
        if(count++ >= 50) break;
        file << "| " << profile.username << " | " << profile.location << " | "
             << profile.total_views << " | " << profile.views_per_day << " | "
             << profile.registration_date << " |\n";
    }
    
    file.close();
    std::cout << "Generated report: " << filename << std::endl;
}

int main() {
    curl_global_init(CURL_GLOBAL_DEFAULT);
    
    // First, fetch login page to see form structure
    std::cout << "Fetching login page..." << std::endl;
    std::string login_page = fetch_url("https://rentmasseur.com/login", false);
    std::ofstream login_debug("login_page.html");
    login_debug << login_page;
    login_debug.close();
    std::cout << "Login page saved to login_page.html" << std::endl;
    
    // Login first
    std::cout << "Logging in as karpathianwolf..." << std::endl;
    std::string login_response = login("karpathianwolf", "Lola369!");
    
    std::ofstream login_response_debug("login_response.html");
    login_response_debug << login_response;
    login_response_debug.close();
    std::cout << "Login response saved to login_response.html" << std::endl;
    
    std::map<std::string, MasseurProfile> profiles;
    
    std::vector<std::string> cities = {
        "newyork", "losangeles", "manhattan-ny", "atlanta", "miami",
        "london", "west-hollywood-ca", "palmsprings", "chicago", "dallas",
        "sanfrancisco", "ftlauderdale", "sandiego", "houston", "lasvegas-nv",
        "toronto", "washingtondc", "orangecounty-ca", "orlando", "philadelphia"
    };
    
    std::set<std::string> all_profile_urls;
    
    // First, try scraping the homepage for featured profiles
    std::string homepage_url = "https://rentmasseur.com/";
    std::cout << "Scraping homepage for featured profiles..." << std::endl;
    
    std::string homepage_html = fetch_url(homepage_url);
    if(!homepage_html.empty()) {
        std::ofstream debug_file("debug_homepage.html");
        debug_file << homepage_html;
        debug_file.close();
        
        std::cout << "Downloaded " << homepage_html.length() << " bytes from homepage" << std::endl;
        
        std::vector<std::string> homepage_links = extract_profile_links(homepage_html);
        for(const auto& link : homepage_links) {
            all_profile_urls.insert(link);
        }
        
        std::cout << "Found " << homepage_links.size() << " profiles on homepage" << std::endl;
    }
    
    // Also add known profiles from the homepage we saw earlier
    std::vector<std::string> known_profiles = {
        "https://rentmasseur.com/Ritual",
        "https://rentmasseur.com/JonnasLatino",
        "https://rentmasseur.com/LiamGoodBoy",
        "https://rentmasseur.com/BrunoMathias",
        "https://rentmasseur.com/HOLLYHOODONLYGEN",
        "https://rentmasseur.com/YULIAN",
        "https://rentmasseur.com/MalikXL",
        "https://rentmasseur.com/BigHandsHK",
        "https://rentmasseur.com/HungMasseurNYC",
        "https://rentmasseur.com/InosukeTopXL",
        "https://rentmasseur.com/Muscltomuscl",
        "https://rentmasseur.com/FemboyFey",
        "https://rentmasseur.com/LVM",
        "https://rentmasseur.com/JayMassive",
        "https://rentmasseur.com/MagicHandsPro",
        "https://rentmasseur.com/ExoticYoungGuy",
        "https://rentmasseur.com/Will_Xavier",
        "https://rentmasseur.com/TonyAsian",
        "https://rentmasseur.com/karpathianwolf"
    };
    
    for(const auto& profile : known_profiles) {
        all_profile_urls.insert(profile);
    }
    
    std::cout << "Total unique profiles to scrape: " << all_profile_urls.size() << std::endl;
    
    // Scrape each profile
    for(const auto& profile_url : all_profile_urls) {
        std::string username = profile_url.substr(profile_url.find_last_of('/') + 1);
        std::cout << "Scraping profile: " << username << std::endl;
        
        std::string html = fetch_url(profile_url);
        if(html.empty()) {
            std::cout << "Failed to fetch " << profile_url << std::endl;
            continue;
        }
        
        MasseurProfile profile;
        profile.username = username;
        profile.profile_url = profile_url;
        profile.location = extract_text(html, R"(Gay Massage in ([^<]+))");
        profile.registration_date = extract_registration_date(html);
        profile.total_views = extract_views(html);
        profile.bio = extract_text(html, R"(<meta name=\"description\" content=\"([^\"]+)\")");
        profile.last_updated = get_current_timestamp();
        profile.views_per_day = calculate_views_per_day(profile.total_views, profile.registration_date);
        
        profiles[username] = profile;
        
        // Small delay to be respectful
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    
    // Save data
    std::string data_dir = "data";
    system(("mkdir -p " + data_dir).c_str());
    
    save_to_json(profiles, data_dir + "/masseur_profiles.json");
    save_to_csv(profiles, data_dir + "/masseur_profiles.csv");
    generate_report(profiles, data_dir + "/views_report.md");
    
    std::cout << "\nScraping complete! Total profiles collected: " << profiles.size() << std::endl;
    
    curl_global_cleanup();
    return 0;
}
