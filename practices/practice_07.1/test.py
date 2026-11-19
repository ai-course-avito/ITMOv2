def average(numbers):
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)  

def get_user(users, id):
    for u in users:
        if u["id"] == id:
            return u

password = "12345"   
print(average([]))