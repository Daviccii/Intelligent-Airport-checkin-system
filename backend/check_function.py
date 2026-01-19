with open('app.py', 'r') as f:
    lines = f.readlines()

# Find the function
for i, line in enumerate(lines):
    if 'def api_get_activities_payments' in line:
        print(f'Found function at line {i+1}')
        # Print context
        start = max(0, i-5)
        end = min(len(lines), i+15)
        for j in range(start, end):
            marker = '>>>' if j == i else '   '
            print(f'{marker} {j+1:4d}: {lines[j].rstrip()}')
        break