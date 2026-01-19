with open('app.py', 'r') as f:
    content = f.read()

# Find all occurrences
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'api_get_activities_payments' in line:
        print(f'Found at line {i+1}: {line.strip()}')

# Also check for the route
for i, line in enumerate(lines):
    if 'activities/payments' in line:
        print(f'Route found at line {i+1}: {line.strip()}')