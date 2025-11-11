import os
from app import app, passengers, save_passengers

def run_smoke():
    # Ensure master access set for admin operations if needed
    os.environ['MASTER_ACCESS'] = 'testmaster'
    client = app.test_client()

    # 1) Create/login passenger
    r = client.post('/api/login', json={'role':'passenger','passport':'SMOKE999','name':'Smoke Tester'})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.data}"
    token = r.get_json().get('token')
    print('token:', bool(token))

    headers = {'X-SESSION': token}

    # 2) Checkin
    payload = {'flight':'SMK200','passengers':[{'name':'Smoke Tester','passport':'SMOKE999','seat':'1','baggage_count':1}]}
    r2 = client.post('/api/checkin', json=payload, headers=headers)
    print('checkin status:', r2.status_code, r2.get_json())
    assert r2.status_code == 200

    # 3) Fetch boarding pass
    r3 = client.get('/api/boardingpass?passport=SMOKE999', headers=headers)
    print('boardingpass status:', r3.status_code, 'content-type:', r3.content_type)
    if r3.status_code == 200 and r3.content_type == 'image/png':
        out = '/tmp/boarding_smoke_client.png'
        with open(out, 'wb') as f:
            f.write(r3.data)
        print('wrote boarding pass to', out, 'size', os.path.getsize(out))
    else:
        print('boarding pass not generated, body:', r3.get_data()[:200])

if __name__ == '__main__':
    run_smoke()
