#pragma once

#include <string>
#include <vector>

// Простая модель банковского счёта. Деньги хранятся в копейках.
struct Account {
    int id;
    std::string owner;
    long long balance_cents;
    int overdraft_limit_cents;  // допустимый уход в минус
};

class Bank {
public:
    Account* open(const std::string& owner);
    Account* find(int id);

    bool deposit(int id, long long cents);
    bool withdraw(int id, long long cents);
    bool transfer(int from, int to, long long cents);

    void print_report() const;

private:
    std::vector<Account> accounts_;
    int next_id_ = 1;
};

// Записывает событие в audit.log
void log_event(const std::string& note);
