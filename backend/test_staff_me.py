import requests

login_url = 'http://127.0.0.1:5000/api/login'
me_url = 'http://127.0.0.1:5000/api/staff/me'
body = {'role': 'staff', 'staff_id': 'SF-2026-00001A', 'password': 'TestPassword123'}

print('POST', login_url)
r = requests.post(login_url, json=body)
print('login status', r.status_code)
try:
    print('login json:', r.json())
except Exception:
    print('login text:', r.text)

if r.status_code == 200:
    token = r.json().get('token')
    print('token:', token)
    headers = {'X-SESSION': token}
    r2 = requests.get(me_url, headers=headers)
    print('/api/staff/me status', r2.status_code)
    try:
        print('me json:', r2.json())
    except Exception:
        print('me text:', r2.text)
else:
    print('Login failed; skipping /api/staff/me')
