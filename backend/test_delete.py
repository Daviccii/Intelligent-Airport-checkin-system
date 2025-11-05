import requests
import json

def test_delete_passengers():
    # Base URL of your Flask application
    base_url = "http://127.0.0.1:5000"
    
    # Test 1: Get current passengers
    print("Getting current passengers...")
    response = requests.get(f"{base_url}/api/passengers")
    if response.status_code == 200:
        current_passengers = response.json()
        print(f"Current number of passengers: {len(current_passengers)}")
    else:
        print("Failed to get passengers")
        return
    
    # Test 2: Delete all passengers
    print("\nDeleting all passengers...")
    response = requests.delete(f"{base_url}/api/passengers")
    if response.status_code == 200:
        print("Delete response:", response.json())
    else:
        print("Failed to delete passengers")
        print("Status code:", response.status_code)
        print("Response:", response.text)
        return
    
    # Test 3: Verify deletion
    print("\nVerifying deletion...")
    response = requests.get(f"{base_url}/api/passengers")
    if response.status_code == 200:
        passengers = response.json()
        print(f"Number of passengers after deletion: {len(passengers)}")
        if len(passengers) == 0:
            print("Success: All passengers were deleted!")
        else:
            print("Warning: Some passengers still exist in the system")
    else:
        print("Failed to verify deletion")

if __name__ == "__main__":
    test_delete_passengers()