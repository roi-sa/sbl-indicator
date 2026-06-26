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

# الإعدادات المعتمدة
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
            return json.loads(content), file_data['sha'], "تمت قراءة قاعدة البيانات التاريخية بنجاح."
        return {}, None, f"تنبيه: لم يتم العثور على الملف التاريخي (كود: {res.status_code}). سيتم إنشاء ملف جديد."
    except Exception as e:
        return {}, None, f"خطأ أثناء الاتصال بجيت هاب: {str(e)}"

def save_github_file(history_data, sha):
    if not GITHUB_TOKEN:
        return False, "خطأ: الرمز السري GH_TOKEN غير معرف في بيئة Render!"
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    content_bytes = json.dumps(history_data, ensure_ascii=False, indent=4).encode('utf-8')
    content_b64 = base64.b64encode(content_bytes).decode('utf-8')
    
    today_str = get_saudi_date()
    payload = {
        "message": f"تحديث تلقائي مستقر لبيانات الإقراض بتاريخ {today_str}",
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
        
    try:
        res = requests.put(url, headers=headers, json=payload, timeout=10)
        if res.status_code in [200, 201]:
            return True, "تم حفظ وتثبيت البيانات الجديدة بنجاح! 🎉"
        return False, f"فشل الحفظ في جيت هاب. كود الخطأ: {res.status_code}"
    except Exception as e:
        return False, f"حدث خطأ أثناء إرسال البيانات: {str(e)}"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    history, sha, db_msg = get_github_file()
    status_msg = db_msg

    try:
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        rows = soup.find_all('tr')
        today_data = {}
        total_market_volume = 0
        
        for row in rows:
            cols = [td.text.strip() for td in row.find_all(['td', 'th'])]
            if len(cols) >= 4:
                comp_code = cols[0].replace(' ', '')
                comp_name = cols[1]
                vol_text = cols[3].replace(',', '').replace(' ', '')
                
                if comp_code.isdigit() and vol_text.isdigit():
                    volume = int(vol_text)
                    today_data[comp_code] = {"name": comp_name, "volume": volume}
                    total_market_volume += volume
        
        today_str = get_saudi_date()
        today_data["تاسي"] = {"name": "كامل السوق - تاسي", "volume": total_market_volume}
        
        history[today_str] = today_data
        success, save_msg = save_github_file(history, sha)
        status_msg += " | " + save_msg
    except Exception as e:
        status_msg += f" | خطأ أثناء معالجة البيانات: {str(e)}"
        
    return history, status_msg

# بقية الكود (التصميم والواجهة)
@app.route('/')
def index():
    chart_data, status_msg = fetch_and_save_data()
    # هنا يمكنك إكمال الـ HTML_TEMPLATE الذي كنا نستخدمه
    return f"<h1>النظام يعمل</h1><p>{status_msg}</p>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)