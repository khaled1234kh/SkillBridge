import sys
sys.path.insert(0, r'C:\Users\khale\Downloads\SkillBridge-main2\SkillBridge\SkillBridge\backend')
import uvicorn
import threading
import time
import requests

def test_api():
    time.sleep(3)
    base = 'http://localhost:8000'
    try:
        r = requests.post(base + '/api/auth/login', json={'email': 'aisha@student.edu', 'password': 'demo1234'}, timeout=5)
        tok = r.json()['token']
        roles = requests.get(base + '/api/roles', headers={'Authorization': 'Bearer ' + tok}, timeout=5).json()
        print('location:', roles.get('location'))
        print('roles count:', len(roles.get('roles', [])))
        print('catalog count:', len(roles.get('catalog', [])))
        for role in roles.get('roles', []):
            print('  {}: {} - {} - {}'.format(role['id'], role['title'], role['company_name'], role.get('company_location', '')))
    except Exception as e:
        print('Test error:', e)

t = threading.Thread(target=test_api, daemon=True)
t.start()
uvicorn.run('app.main:app', host='0.0.0.0', port=8000, log_level='info')