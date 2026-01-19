import json

with open('flights.json', 'r') as f:
    flights = json.load(f)

routes = {}
for f in flights:
    key = f['origin'] + '-' + f['destination']
    if key not in routes:
        routes[key] = {'count': 0, 'dates': set()}
    routes[key]['count'] += 1
    routes[key]['dates'].add(f['departure_time'].split('T')[0])

print('Current Routes:')
for route, data in sorted(routes.items()):
    dates = sorted(data['dates'])
    print(f'{route}: {data["count"]} flights on {dates}')
print(f'\nTotal: {len(routes)} routes, {len(flights)} flights')