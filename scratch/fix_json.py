import re
import json

with open('service_account.json', 'r') as f:
    content = f.read()

# Replace any \ followed by a base64 character with just that character
# Except for \n which we want to keep
fixed = re.sub(r'\\(?![n"\\/])([A-Za-z0-9+/=])', r'\1', content)

# Also ensure it's valid JSON
try:
    json.loads(fixed)
    print("Fixed content is valid JSON")
    with open('service_account.json', 'w') as f:
        f.write(fixed)
except Exception as e:
    print(f"Still invalid: {e}")
