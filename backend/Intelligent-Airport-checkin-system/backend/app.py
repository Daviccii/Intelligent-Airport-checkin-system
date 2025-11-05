import json
import os

PASSENGER_FILE = "passengers.json"

# Load passengers if file exists
if os.path.exists(PASSENGER_FILE):
    with open(PASSENGER_FILE, "r") as file:
        passengers = json.load(file)
else:
    passengers = []

def save_passengers():
    with open(PASSENGER_FILE, "w") as file:
        json.dump(passengers, file, indent=4)

def register_passenger():
    name = input("Enter passenger name: ")
    passport = input("Enter passport/ID number: ")
    flight = input("Enter flight number: ")
    
    for p in passengers:
        if p["passport"] == passport and p["flight"] == flight:
            print("Passenger already registered!")
            return

    seat = len(passengers) + 1
    passenger = {"name": name, "passport": passport, "flight": flight, "seat": seat}
    passengers.append(passenger)
    save_passengers()
    print(f"\nPassenger {name} registered successfully!")
    print(f"Flight: {flight} | Seat: {seat}\n")

def view_passengers():
    if not passengers:
        print("\nNo passengers registered yet.\n")
        return
    print("\n--- Registered Passengers ---")
    for p in passengers:
        print(f"{p['name']} - Passport: {p['passport']} - Flight: {p['flight']} - Seat: {p['seat']}")
    print("-----------------------------\n")

def main():
    while True:
        print("\n1. Register Passenger")
        print("2. View Passengers")
        print("3. Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            register_passenger()
        elif choice == "2":
            view_passengers()
        elif choice == "3":
            print("Exiting system...")
            break
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    main()