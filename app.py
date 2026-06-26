import os
import json
import base64
from datetime import datetime
import pytz
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string
import urllib3

# إيقاف تحذيرات شهادات الأمان المزعجة
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# إعدادات الاتصال بمستودع GitHub الخاص بك لحفظ الملف التراكمي
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
        
        # هيكلة تخزين اليوم: نضع "تاسي" كعنصر رئيسي لحساب الإجمالي تلقائياً
        today_data = {"تاسي": {"name": "كامل الأسهم - تاسي", "volume": 0}}
        
        for row in rows:
            cols = [td.text.strip() for td in row.find_all(['td', 'th'])]
            if len(cols) >= 4 and cols[0].isdigit() and cols[3].replace(',', '').isdigit():
                symbol = cols[0]
                name = cols[1]
                volume = int(cols[3].replace(',', ''))
                
                # تخزين كل شركة بشكل منفصل برمزها واسمها وعدد أسهمها
                today_data[symbol] = {"name": name, "volume": volume}
                # جمع التراكمي لإجمالي السوق في تاسي
                today_data["تاسي"]["volume"] += volume
        
        # حفظ التحديث التراكمي لليوم في مستودع GitHub
        history[get_saudi_date()] = today_data
        success, save_msg = save_github_file(history, sha)
        return history, f"{db_msg} | {save_msg}"
    except Exception as e:
        return history, f"خطأ معالجة: {str(e)}"

# واجهة العرض التفاعلية الكاملة بالأدوات المطلوبة
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
        
        // 1. بناء خيارات القائمة المنسدلة تلقائياً من آخر بيانات مسجلة في الملف
        if (labels.length > 0) {
            const lastDate = labels[labels.length - 1];
            const lastDayData = rawHistory[lastDate];
            const selectDropdown = document.getElementById('companySelect');
            
            Object.keys(lastDayData).forEach(symbol => {
                if (symbol !== "تاسي") {
                    let opt = document.createElement('option');
                    opt.value = symbol;
                    opt.text = `${symbol} - ${lastDayData[symbol].name}`;
                    selectDropdown.appendChild(opt);
                }
            });
        }

        // 2. تهيئة مساحة الرسم البياني الأساسية
        const ctx = document.getElementById('sblChart').getContext('2d');
        let chartInstance = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [{ data: [] }] },
            options: { responsive: true, scales: { y: { beginAtZero: false } } }
        });

        // 3. وظيفة زر البحث: التحقق من الرمز وتثبيته داخل القائمة المنسدلة
        function searchAndSelectCompany() {
            const searchVal = document.getElementById('searchInput').value.trim();
            const selectDropdown = document.getElementById('companySelect');
            
            if (searchVal === "") {
                alert("الرجاء كتابة رمز الشركة أولاً.");
                return;
            }
            
            if (searchVal === "تاسي") {
                selectDropdown.value = "تاسي";
                return;
            }
            
            // البحث داخل خيارات القائمة للتأكد من مطابقة الرمز
            let found = false;
            for (let i = 0; i < selectDropdown.options.length; i++) {
                if (selectDropdown.options[i].value === searchVal) {
                    selectDropdown.value = searchVal; // تثبيت الشركة المحددة في القائمة المنسدلة
                    found = true;
                    break;
                }
            }
            
            if (!found) {
                alert("رمز الشركة غير موجود في القائمة الحالية المحدثة.");
            }
        }

        // 4. وظيفة زر التنفيذ: رسم حركة إقراض الأسهم للشركة المثبتة حالياً في القائمة المنسدلة
        function drawChartFor(symbol) {
            let chartDataValues = [];
            let chartLabels = [];
            let companyName = "كامل السوق";

            // قراءة السلسلة التاريخية للرمز المحدد وتثبيت النقاط التاريخية السابقة
            labels.forEach(date => {
                if (rawHistory[date] && rawHistory[date][symbol]) {
                    chartLabels.push(date);
                    chartDataValues.push(rawHistory[date][symbol].volume);
                    companyName = rawHistory[date][symbol].name;
                }
            });

            document.getElementById('displayTitle').innerText = symbol === "تاسي" ? "المعروض الآن: كل الأسهم - تاسي" : `المعروض الآن: ${symbol} - ${companyName}`;
            
            // تدمير الكائن السابق للشارت لمنع التداخل والوميض عند الانتقال لشركة أخرى
            chartInstance.destroy();

            // رسم الخط البياني بالنقاط التراكمية التاريخية الثابتة
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartLabels,
                    datasets: [{
                        label: symbol === "تاسي" ? "إجمالي الأسهم المقراضة لكل شركات السوق" : `حركة كميات الأسهم المقراضة لـ ${companyName}`,
                        data: chartDataValues,
                        borderColor: symbol === "تاسي" ? '#2980b9' : '#e67e22',
                        backgroundColor: symbol === "تاسي" ? 'rgba(41, 128, 185, 0.05)' : 'rgba(230, 126, 34, 0.05)',
                        borderWidth: 3,
                        tension: 0.1,
                        fill: true,
                        pointRadius: 5,
                        pointHoverRadius: 7
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { title: { display: true, text: 'الكمية (سهم)' } },
                        x: { title: { display: true, text: 'التاريخ' } }
                    }
                }
            });
        }

        function updateChart() {
            const selectVal = document.getElementById('companySelect').value;
            drawChartFor(selectVal);
        }

        // تشغيل الرسم الافتراضي الأولي لكامل السوق (تاسي) عند فتح الصفحة لأول مرة
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