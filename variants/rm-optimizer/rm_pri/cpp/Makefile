CXX = g++
CXXFLAGS = -O3 -march=native -std=c++17 -Wall

TARGET = rm_pri

.PHONY: all clean

all: $(TARGET)

$(TARGET): rm_pri.cpp
	$(CXX) $(CXXFLAGS) rm_pri.cpp -o $(TARGET)

clean:
	rm -f $(TARGET)
