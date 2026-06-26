import os
import json
import base64
from datetime import datetime
import pytz
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string
import urllib3

# إيقاف تحذيرات شهادات الأمان
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
        if res.status_code in [200, 201]:
            return True, "تم الحفظ بنجاح."
        return False, f"فشل الحفظ. كود: {res.status_code}"
    except Exception as e:
        return False, f"خطأ في الحفظ: {str(e)}"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    history, sha, db_msg = get_github_file()
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        
        today_data = {"تاسي": {"name": "كامل السوق - تاسي", "volume": 0}}
        found_any_data = False
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                try:
                    sym_text = cols[0].text.strip()
                    name_text = cols[1].text.strip()
                    vol_text = cols[3].text.strip().replace(',', '')
                    
                    if sym_text.isdigit() and vol_text.isdigit():
                        vol_val = int(vol_text)
                        today_data[sym_text] = {"name": name_text, "volume": vol_val}
                        today_data["تاسي"]["volume"] += vol_val
                        found_any_data = True
                except Exception:
                    continue
        
        if found_any_data and today_data["تاسي"]["volume"] > 0:
            history[get_saudi_date()] = today_data
            success, save_msg = save_github_file(history, sha)
            return history, f"{db_msg} | {save_msg}"
        else:
            return history, f"{db_msg} | تنبيه: لم يتم جلب بيانات جديدة من الجدول."
    except Exception as e:
        return history, f"خطأ معالجة: {str(e)}"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مؤشر حركة الأسهم المقرضة</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f4f7f6; color: #333; }
        .container { max-width: 950px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #2c3e50; text-align: center; font-size: 22px; margin-bottom: 5px; }
        .status-bar { text-align: center; color: #7f8c8d; font-size: 13px; margin-bottom: 25px; }
        .control-panel { background: #ecf0f1; padding: 15px; border-radius: 8px; display: flex; gap: 15px; align-items: center; justify-content: center; flex-wrap: wrap; margin-bottom: 25px; }
        .search-group, .select-group { display: flex; align-items: center; gap: 8px; }
        select, input { padding: 8px 12px; border: 1px solid #bdc3c7; border-radius: 5px; font-size: 14px; }
        input { width: 140px; }
        select { min-width: 220px; max-width: 300px; }
        button { padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .btn-search { background-color: #34495e; color: white; }
        .btn-search:hover { background-color: #2c3e50; }
        .btn-execute { background-color: #27ae60; color: white; padding: 8px 25px; }
        .btn-execute:hover { background-color: #219653; }
        .chart-title { text-align: center; font-size: 18px; font-weight: bold; color: #2980b9; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>مؤشر حركة كميات الأسهم المقرضة الحية</h1>
        <div class="status-bar">{{ status_message }}</div>
        
        <div class="control-panel">
            <div class="search-group">
                <label>بحث بالرمز:</label>
                <input type="text" id="searchInput" placeholder="مثال: 3004">
                <button class="btn-search" onclick="searchAndSelectCompany()">بحث</button>
            </div>
            
            <div class="select-group">
                <label>قائمة الشركات:</label>
                <select id="companySelect">
                    <option value="تاسي">كل الأسهم - تاسي</option>
                </select>
            </div>
            
            <button class="btn-execute" onclick="updateChart()">تنفيذ</button>
        </div>

        <div class="chart-title" id="displayTitle">المعروض الآن: كل الأسهم - تاسي</div>
        <canvas id="sblChart" width="400" height="150"></canvas>
    </div>

    <script>
        const rawHistory = {{ history_data | tojson }};
        const labels = Object.keys(rawHistory).sort();
        
        // بناء قائمة الشركات بناءً على آخر تاريخ متوفر (لأنه يحتوي على القائمة الكاملة)
        if (labels.length > 0) {
            const lastDate = labels[labels.length - 1];
            const lastDayData = rawHistory[lastDate];
            const selectDropdown = document.getElementById('companySelect');
            
            // استخراج الأكواد وترتيبها عددياً
            const symbols = Object.keys(lastDayData).filter(s => s !== "تاسي").sort((a, b) => parseInt(a) - parseInt(b));
            
            symbols.forEach(symbol => {
                let opt = document.createElement('option');
                opt.value = symbol;
                opt.text = `${symbol} - ${lastDayData[symbol].name}`;
                selectDropdown.appendChild(opt);
            });
        }

        const ctx = document.getElementById('sblChart').getContext('2d');
        let chartInstance = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [{ data: [] }] },
            options: { responsive: true }
        });

        // وظيفة البحث ونقل المؤشر إلى الخيار المطلوب داخل القائمة المنسدلة
        function searchAndSelectCompany() {
            const searchVal = document.getElementById('searchInput').value.trim();
            const selectDropdown = document.getElementById('companySelect');
            
            if (searchVal === "") {
                alert("الرجاء كتابة رمز الشركة أولاً.");
                return;
            }
            if (searchVal === "تاسي" || searchVal === "كل الأسهم - تاسي") {
                selectDropdown.value = "تاسي";
                return;
            }
            
            let found = false;
            for (let i = 0; i < selectDropdown.options.length; i++) {
                if (selectDropdown.options[i].value === searchVal) {
                    selectDropdown.value = searchVal;
                    found = true;
                    break;
                }
            }
            if (!found) {
                alert("رمز الشركة غير موجود في القائمة الحالية المحدثة.");
            }
        }

        // رسم المنحنى البياني مع التوافقية الكاملة لبيانات تاسي القديمة والجديدة
        function drawChartFor(symbol) {
            let chartDataValues = [];
            let chartLabels = [];
            let companyName = "";

            labels.forEach(date => {
                if (rawHistory[date] && rawHistory[date][symbol]) {
                    chartLabels.push(date);
                    chartDataValues.push(rawHistory[date][symbol].volume);
                    if (!companyName) {
                        companyName = rawHistory[date][symbol].name;
                    }
                }
            });

            if (symbol === "تاسي") {
                companyName = "كل الأسهم - تاسي";
            }

            document.getElementById('displayTitle').innerText = `المعروض الآن: ${symbol === "تاسي" ? "" : symbol + " - "} ${companyName}`;
            chartInstance.destroy();

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartLabels,
                    datasets: [{
                        label: symbol === "تاسي" ? "إجمالي الأسهم المقرضة بالسوق" : `حركة كميات الأسهم لـ ${companyName}`,
                        data: chartDataValues,
                        borderColor: symbol === "تاسي" ? '#2980b9' : '#e67e22',
                        backgroundColor: symbol === "تاسي" ? 'rgba(41, 128, 185, 0.05)' : 'rgba(230, 126, 34, 0.05)',
                        borderWidth: 3,
                        tension: 0.1,
                        fill: true,
                        pointRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { 
                            title: { display: true, text: 'الكمية (سهم)' },
                            beginAtZero: false 
                        },
                        x: { title: { display: true, text: 'التاريخ' } }
                    }
                }
            });
        }

        function updateChart() {
            const selectVal = document.getElementById('companySelect').value;
            drawChartFor(selectVal);
        }

        // التشغيل التلقائي الأولي على مؤشر تاسي عند فتح الصفحة
        drawChartFor("تاسي");
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    chart_data, status_msg = fetch_and_save_data()
    return render_template_string(HTML_TEMPLATE, history_data=chart_data, status_message=status_msg)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))