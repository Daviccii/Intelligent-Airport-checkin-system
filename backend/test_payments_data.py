import requests
import json

# Test payments API data
try:
    response = requests.get('http://127.0.0.1:5000/api/activities/payments')
    if response.status_code == 200:
        data = response.json()
        print(f"✅ API returned {len(data.get('payments', []))} payment records")

        # Check if we have payment data
        payments = data.get('payments', [])
        if payments:
            print("✅ Payment data found:")
            for i, payment in enumerate(payments[:3]):  # Show first 3
                print(f"  {i+1}. {payment.get('type', 'N/A')} - {payment.get('amount', 'N/A')} - {payment.get('method', 'N/A')}")
        else:
            print("❌ No payment data in response")
    else:
        print(f"❌ API failed: {response.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")