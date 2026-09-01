import sys
sys.path.insert(0, r'C:\Users\khale\Downloads\SkillBridge-main2\SkillBridge\SkillBridge\backend')
import uvicorn
uvicorn.run('app.main:app', host='0.0.0.0', port=8000)