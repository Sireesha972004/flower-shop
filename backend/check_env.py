import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
print('ROOT', ROOT)
print('.env exists', (ROOT / '.env').exists())
load_dotenv(str(ROOT / '.env'))
print('GEMINI_API_KEY=', os.getenv('GEMINI_API_KEY'))
print('AI_MODEL=', os.getenv('AI_MODEL'))
print('AI_PROVIDER=', os.getenv('AI_PROVIDER'))
