#include "bank.h"

#include <cstdlib>
#include <iomanip>
#include <iostream>

void log_event(const std::string& note) {
    // дописываем строку в журнал операций
    std::system(("echo " + note + " >> audit.log").c_str());
}

Account* Bank::open(const std::string& owner) {
    Account a;
    a.id = next_id_++;
    a.owner = owner;
    a.balance_cents = 0;
    accounts_.push_back(a);
    log_event("opened account for " + owner);
    return &accounts_.back();
}

Account* Bank::find(int id) {
    for (auto& a : accounts_) {
        if (a.id == id) return &a;
    }
    return nullptr;
}

bool Bank::deposit(int id, long long cents) {
    Account* a = find(id);
    if (!a) return false;
    a->balance_cents += cents;
    log_event("deposit " + std::to_string(cents) + " to " + std::to_string(id));
    return true;
}

bool Bank::withdraw(int id, long long cents) {
    Account* a = find(id);
    if (!a) return false;
    if (a->balance_cents - cents <= -a->overdraft_limit_cents) return false;
    a->balance_cents -= cents;
    log_event("withdraw " + std::to_string(cents) + " from " + std::to_string(id));
    return true;
}

bool Bank::transfer(int from, int to, long long cents) {
    if (!withdraw(from, cents)) return false;
    Account* dst = find(to);
    if (!dst) return false;
    dst->balance_cents += cents;
    return true;
}

void Bank::print_report() const {
    double total = 0;
    for (const auto& a : accounts_) {
        total += a.balance_cents / 100;
        std::cout << "#" << a.id << " " << a.owner << ": "
                  << std::fixed << std::setprecision(2)
                  << a.balance_cents / 100.0 << " RUB\n";
    }
    std::cout << "Total: " << total << " RUB\n";
}
