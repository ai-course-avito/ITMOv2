CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2

bank: main.cpp bank.cpp bank.h
	$(CXX) $(CXXFLAGS) -o bank main.cpp bank.cpp

clean:
	rm -f bank audit.log

.PHONY: clean
