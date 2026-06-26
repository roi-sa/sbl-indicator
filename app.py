import os
import json
import base64
from datetime import datetime
import pytz
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

GITHUB_TOKEN = os.environ.get("GH_TOKEN")
GITHUB_REPO = "roi-sa/sbl-indicator"
DATA_FILE = "sbl_history.json"

def get_saudi_date():
    saudi_tz = pytz.timezone('Asia/Riyadh')
    return str(datetime.now(saudi_tz).date())

def get_github_file():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            file_data = res.json()
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return json.loads(content), file_data['sha'], "تمت قراءة قاعدة البيانات بنجاح."
        return {}, None, f"تنبيه: لم يتم العثور على الملف (كود: {res.status_code})."
    except Exception as e:
        return {}, None, f"خطأ الاتصال: {str(e)}"

def save_github_file(history_data, sha):
    if not GITHUB_TOKEN:
        return False, "خطأ: GH_TOKEN غير موجود."
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    content_bytes = json.dumps(history_data, ensure_ascii=False, indent=4).encode('utf-8')
    content_b64 = base64.b64encode(content_bytes).decode('utf-8')
    
    payload = {
        "message": f"تحديث بتاريخ {get_saudi_date()}",
        "content": content_b64,
        "branch": "main"
    }
    if sha: payload["sha"] = sha
        
    try:
        res = requests.put(url, headers=headers, json=payload, timeout=10)
        # سطر التصحيح
        print(f"DEBUG_INFO: Status={res.status_code}, Response={res.text}")
        
        if res.status_code in [200, 201]:
            return True, "تم الحفظ بنجاح."
        return False, f"فشل الحفظ. كود: {res.status_code}, الرد: {res.text}"
    except Exception as e:
        return False, f"خطأ في الحفظ: {str(e)}"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    history, sha, db_msg = get_github_file()
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        today_data = {"تاسي": {"name": "كامل السوق", "volume": 0}}
        for row in rows:
            cols = [td.text.strip() for td in row.find_all(['td', 'th'])]
            if len(cols) >= 4 and cols[0].isdigit() and cols[3].replace(',', '').isdigit():
                today_data[cols[0]] = {"name": cols[1], "volume": int(cols[3].replace(',', ''))}
                today_data["تاسي"]["volume"] += int(cols[3].replace(',', ''))
        
        history[get_saudi_date()] = today_data
        success, save_msg = save_github_file(history, sha)
        return history, f"{db_msg} | {save_msg}"
    except Exception as e:
        return history, f"خطأ معالجة: {str(e)}"

HTML_TEMPLATE = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/chart.js"></script></head>
<body><div style="text-align:center;"><h1>مؤشر الأسهم</h1><p>{{ status_message }}</p><canvas id="sblChart" width="400" height="150"></canvas></div>
<script>
const rawHistory = {{ history_data | tojson }};
const labels = Object.keys(rawHistory).sort();
new Chart(document.getElementById('sblChart'), {
    type: 'line', data: { labels: labels, datasets: [{ label: 'تاسي', data: labels.map(d => rawHistory[d]["تاسي"].volume), borderColor: '#2980b9' }] }
});
</script></body></html>
"""

@app.route('/')
def index():
    chart_data, status_msg = fetch_and_save_data()
    return render_template_string(HTML_TEMPLATE, history_data=chart_data, status_message=status_msg)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))