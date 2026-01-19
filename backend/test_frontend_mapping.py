import requests
import json

# Test if the payments page can access the API
response = requests.get('http://127.0.0.1:5000/api/activities/payments')
data = response.json()

print('✅ API is accessible')
print(f'✅ Found {len(data["payments"])} payment records')

# Check data structure
first_payment = data['payments'][0]
print('✅ First payment structure:')
print(json.dumps(first_payment, indent=2))

# Simulate what frontend does
mapped = []
for p in data['payments']:
    d = p.get('data', {})
    mapped.append({
        'amount': float(d.get('amount', 0)),
        'method': d.get('payment_method', 'N/A'),
        'status': d.get('status', 'N/A')
    })

print('✅ Frontend mapping test:')
print(f'  Total revenue: ${sum(p["amount"] for p in mapped):.2f}')
print(f'  Methods: {set(p["method"] for p in mapped)}')
print(f'  Statuses: {set(p["status"] for p in mapped)}')