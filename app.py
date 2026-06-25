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
    """ضمان جلب التاريخ بدقة متناهية حسب توقيت الرياض لمنع تضارب الأيام في السيرفر"""
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
        return {}, None, f"تنبيه: لم يتم العثور على الملف التاريخي في جيت هاب (كود الاستجابة: {res.status_code}). سيتم إنشاء ملف جديد."
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
            return True, "تم حفظ وتثبيت البيانات الجديدة داخل مستودع جيت هاب للأبد بنجاح! 🎉"
        return False, f"فشل الحفظ في جيت هاب. كود الخطأ من الموقع: {res.status_code}"
    except Exception as e:
        return False, f"حدث خطأ أثناء إرسال البيانات إلى جيت هاب: {str(e)}"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 1. جلب التاريخ وقاعدة البيانات المستقرة
    history, sha, db_msg = get_github_file()
    status_msg = db_msg

    try:
        # 2. جلب وتفكيك جدول تداول المحدث
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
                    today_data[comp_code] = {
                        "name": comp_name,
                        "volume": volume
                    }
                    total_market_volume += volume
        
        if not today_data:
            status_msg += " | خطأ: تم الدخول لموقع تداول ولكن لم يتم العثور على أي بيانات داخل الجدول اليوم! قد يكون الرابط تحت الصيانة."
            return history, status_msg

        today_str = get_saudi_date()
        today_data["تاسي"] = {
            "name": "كامل السوق - تاسي",
            "volume": total_market_volume
        }
        
        # دمج وحفظ البيانات
        history[today_str] = today_data
        success, save_msg = save_github_file(history, sha)
        status_msg += " | " + save_msg
                
    except Exception as e:
        status_msg += f" | خطأ استثنائي أثناء معالجة سحب البيانات: {str(e)}"
        
    return history, status_msg

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مؤشر الأسهم المقرضة التفاعلي - المطور</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f4f7f6; }
        .container { max-width: 1000px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; text-align: center; margin-bottom: 5px; }
        .system-status { background: #e8f4fd; color: #1d6fa5; padding: 10px; border-radius: 6px; font-size: 13px; margin-bottom: 20px; border: 1px solid #bce1f5; font-weight: 500; text-align: center; }
        .control-panel { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; align-items: center; background: #ecf0f1; padding: 15px; border-radius: 6px; margin-bottom: 25px; }
        .control-panel label { font-weight: bold; color: #34495e; }
        .control-panel select, .control-panel input { padding: 8px 12px; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 14px; }
        #searchBar { width: 140px; }
        #companySelect { min-width: 240px; }
        .btn-search { padding: 8px 15px; background-color: #7f8c8d; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .btn-search:hover { background-color: #95a5a6; }
        .btn-execute { padding: 8px 30px; background-color: #2980b9; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 15px; font-weight: bold; }
        .btn-execute:hover { background-color: #3498db; }
        .update-btn { display: block; margin: 20px auto 10px auto; padding: 12px 30px; background-color: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 15px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .update-btn:hover { background-color: #219653; }
        #companyTitle { text-align: center; color: #16a085; font-size: 20px; font-weight: bold; margin-top: 15px; }
        .alert-msg { color: #c0392b; text-align: center; font-weight: bold; margin: 15px 0; display: none; background: #fdeaea; padding: 10px; border-radius: 4px; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <div class="container">
        <h2>مؤشر حركات كميات الأسهم المقرضة بالتفصيل</h2>
        <div style="text-align:center; color:#7f8c8d; margin-bottom:15px; font-size:13px;">نظام الحفظ المستقر والمراقب تلقائياً</div>
        
        <div class="system-status">
            <strong>حالة النظام اللحظية:</strong> {{ status_message }}
        </div>
        
        <div class="control-panel">
            <label>البحث بالرمز:</label>
            <input type="text" id="searchBar" placeholder="مثال: 3004" value="تاسي">
            <button class="btn-search" onclick="syncSearchToSelect()">بحث 🔍</button>
            
            <label>القائمة المنسدلة:</label>
            <select id="companySelect">
                </select>
            
            <button class="btn-execute" onclick="filterChart()">تنفيذ</button>
        </div>

        <div id="alertMessage" class="alert-msg"></div>
        <div id="companyTitle">كامل السوق - تاسي</div>
        <canvas id="sblChart" width="400" height="170"></canvas>
        
        <button class="update-btn" onclick="window.location.reload()">تحديث وجلب بيانات اليوم وحفظها في جيتهاب ↻</button>
    </div>

    <script>
        const rawHistory = {{ history_data | tojson }};
        let companiesMap = {"تاسي": "كامل السوق - تاسي"};
        
        for (let dateKey in rawHistory) {
            for (let code in rawHistory[dateKey]) {
                if(rawHistory[dateKey][code] && rawHistory[dateKey][code].name) {
                    companiesMap[code] = rawHistory[dateKey][code].name;
                }
            }
        }
        
        const selectEl = document.getElementById('companySelect');
        Object.keys(companiesMap).sort((a,b) => {
            if(a === "تاسي") return -1;
            if(b === "تاسي") return 1;
            return a.localeCompare(b);
        }).forEach(code => {
            let opt = document.createElement('option');
            opt.value = code;
            opt.textContent = `${code} - ${companiesMap[code]}`;
            selectEl.appendChild(opt);
        });

        function syncSearchToSelect() {
            let searchVal = document.getElementById('searchBar').value.trim();
            document.getElementById('alertMessage').style.display = "none";
            
            if (companiesMap[searchVal]) {
                selectEl.value = searchVal;
                generateChart(searchVal);
            } else {
                document.getElementById('alertMessage').textContent = "⚠️ الرمز غير مسجل في أي عمليات إقراض سابقة أو حالية.";
                document.getElementById('alertMessage').style.display = "block";
            }
        }
        
        function filterChart() { generateChart(selectEl.value); }

        let chartInstance = null;
        function generateChart(targetCode) {
            const labels = Object.keys(rawHistory).sort();
            const dataValues = [];
            
            labels.forEach(dateKey => {
                if (rawHistory[dateKey] && rawHistory[dateKey][targetCode]) {
                    dataValues.push(rawHistory[dateKey][targetCode].volume);
                } else {
                    dataValues.push(0);
                }
            });
            
            const compName = companiesMap[targetCode] || "شركة غير معروفة";
            document.getElementById('companyTitle').textContent = `${targetCode} - ${compName}`;
            
            const ctx = document.getElementById('sblChart').getContext('2d');
            if (chartInstance) { chartInstance.destroy(); }
            
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: `كمية الأسهم المقرضة لـ (${compName})`,
                        data: dataValues,
                        borderColor: targetCode === 'تاسي' ? '#2980b9' : '#e67e22',
                        backgroundColor: targetCode === 'تاسي' ? 'rgba(41, 128, 185, 0.1)' : 'rgba(230, 126, 34, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.1
                    }]
                },
                options: {
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
        }
        generateChart('تاسي');
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    chart_data, status_msg = fetch_and_save_data()
    return render_template_string(HTML_TEMPLATE, history_data=chart_data, status_message=status_msg)

if __name__ == '__main__':
    app.run(debug=True, port=5000)