# Makefile — Native HDAR build (pure C++ on Apple Silicon)
# Requires: Apple Container CLI (brew install container), OpenSSL 3.x (brew install openssl)

CXX = clang++
CXXFLAGS = -std=c++17 -stdlib=libc++ \
           -I/opt/homebrew/include -I/opt/homebrew/opt/openssl@3/include \
           -Wall -Wno-unused-parameter -Wno-unused-variable \
           -O2

LDFLAGS = -L/opt/homebrew/opt/openssl@3/lib -lcrypto -lsqlite3

SRCS = main.cpp hdar_crypto.cpp hdar_store.cpp hdar_provider.cpp hdar_lease.cpp hdar_continuity.cpp hdar_gateway.cpp
OBJS = $(SRCS:.cpp=.o)
TARGET = hdar_native

.PHONY: all clean test battle

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(OBJS) -o $(TARGET) $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Headers
hdar_crypto.o: hdar_crypto.h
hdar_store.o: hdar_store.h hdar_crypto.h
hdar_provider.o: hdar_provider.h
hdar_lease.o: hdar_lease.h hdar_crypto.h
hdar_continuity.o: hdar_continuity.h hdar_crypto.h hdar_store.h hdar_lease.h hdar_provider.h
hdar_gateway.o: hdar_gateway.h hdar_continuity.h hdar_crypto.h hdar_store.h hdar_lease.h hdar_provider.h
main.o: hdar_crypto.h hdar_store.h hdar_lease.h hdar_provider.h hdar_continuity.h hdar_gateway.h

clean:
	rm -f $(OBJS) $(TARGET)

test: $(TARGET)
	./$(TARGET)

battle: $(TARGET)
	./$(TARGET) && echo "NATIVE DECISIVE LOOP: PASS"
