CXX = g++
CXXFLAGS = -std=c++17 -Wall -O2
LDFLAGS = -lcurl

TARGETS = rentmasseur_scraper phone_extractor phone_bruteforce bio_bruteforce batch_bio_extractor fast_bio_extractor
SOURCES = rentmasseur_scraper.cpp phone_extractor.cpp phone_bruteforce.cpp bio_bruteforce.cpp batch_bio_extractor.cpp fast_bio_extractor.cpp

all: $(TARGETS)

rentmasseur_scraper: rentmasseur_scraper.cpp
	$(CXX) $(CXXFLAGS) -o rentmasseur_scraper rentmasseur_scraper.cpp $(LDFLAGS)

phone_extractor: phone_extractor.cpp
	$(CXX) $(CXXFLAGS) -o phone_extractor phone_extractor.cpp $(LDFLAGS)

phone_bruteforce: phone_bruteforce.cpp
	$(CXX) $(CXXFLAGS) -o phone_bruteforce phone_bruteforce.cpp $(LDFLAGS)

bio_bruteforce: bio_bruteforce.cpp
	$(CXX) $(CXXFLAGS) -o bio_bruteforce bio_bruteforce.cpp $(LDFLAGS)

batch_bio_extractor: batch_bio_extractor.cpp
	$(CXX) $(CXXFLAGS) -o batch_bio_extractor batch_bio_extractor.cpp $(LDFLAGS) -pthread

fast_bio_extractor: fast_bio_extractor.cpp
	$(CXX) $(CXXFLAGS) -o fast_bio_extractor fast_bio_extractor.cpp $(LDFLAGS) -pthread

clean:
	rm -f $(TARGETS)

run-scraper: rentmasseur_scraper
	./rentmasseur_scraper

run-phone: phone_extractor
	./phone_extractor Karpathianwolf

install-deps:
	brew install curl

.PHONY: all clean run-scraper run-phone install-deps
