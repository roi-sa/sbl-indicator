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

# ==================== تعديل واجهة العرض التفاعلية فقط ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مؤشر الأسهم المقرضة التفاعلي</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f4f7f6; color: #333; }
        .container { max-width: 900px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #2c3e50; text-align: center; font-size: 24px; margin-bottom: 5px; }
        .status-bar { text-align: center; color: #7f8c8d; font-size: 13px; margin-bottom: 25px; }
        .control-panel { background: #ecf0f1; padding: 15px; border-radius: 8px; display: flex; gap: 15px; align-items: center; justify-content: center; flex-wrap: wrap; margin-bottom: 25px; }
        select, input { padding: 8px 12px; border: 1px solid #bdc3c7; border-radius: 5px; font-size: 14px; min-width: 180px; }
        .btn-execute { padding: 8px 20px; background-color: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .btn-execute:hover { background-color: #219653; }
        .chart-title { text-align: center; font-size: 18px; font-weight: bold; color: #2980b9; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>مؤشر حركة كميات الأسهم المقرضة</h1>
        <div class="status-bar">{{ status_message }}</div>
        
        <div class="control-panel">
            <label>قائمة الشركات:</label>
            <select id="companySelect">
                <option value="تاسي">كامل السوق - تاسي</option>
            </select>
            
            <label>بحث بالرمز:</label>
            <input type="text" id="searchInput" placeholder="اكتب رمز الشركة...">
            
            <button class="btn-execute" onclick="updateChart()">تنفيذ</button>
        </div>

        <div class="chart-title" id="displayTitle">المعروض الآن: كامل السوق - تاسي</div>
        <canvas id="sblChart" width="400" height="150"></canvas>
    </div>

    <script>
        const rawHistory = {{ history_data | tojson }};
        const labels = Object.keys(rawHistory).sort();
        
        // 1. تجميع قائمة ديناميكية بالشركات المتاحة من آخر تاريخ مسجل
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

        // 2. إعداد الشارت ككائن رئيسي قابل للتحديث
        const ctx = document.getElementById('sblChart').getContext('2d');
        let chartInstance = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [{ data: [] }] },
            options: { responsive: true, scales: { y: { beginAtZero: false } } }
        });

        // 3. دالة معالجة ورسم البيانات للشركة المحددة
        function drawChartFor(symbol) {
            let chartDataValues = [];
            let chartLabels = [];
            let companyName = "كامل السوق";

            labels.forEach(date => {
                if (rawHistory[date] && rawHistory[date][symbol]) {
                    chartLabels.push(date);
                    chartDataValues.push(rawHistory[date][symbol].volume);
                    companyName = rawHistory[date][symbol].name;
                }
            });

            // تحديث عنوان الشارت الظاهر للمستخدم
            document.getElementById('displayTitle').innerText = symbol === "تاسي" ? "المعروض الآن: كامل السوق - تاسي" : `المعروض الآن: ${symbol} - ${companyName}`;

            // تدمير الشارت القديم لمنع تداخل الرسوم عند اختيار شركة أخرى
            chartInstance.destroy();

            // رسم الخط البياني الجديد
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartLabels,
                    datasets: [{
                        label: symbol === "تاسي" ? "إجمالي السوق (سهم)" : `كمية الأسهم المقرضة لـ ${companyName}`,
                        data: chartDataValues,
                        borderColor: symbol === "تاسي" ? '#2980b9' : '#e67e22',
                        backgroundColor: symbol === "تاسي" ? 'rgba(41, 128, 185, 0.05)' : 'rgba(230, 126, 34, 0.05)',
                        borderWidth: 3,
                        tension: 0.1,
                        fill: true
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

        // 4. معالجة زر التنفيذ (دمج خانة البحث مع القائمة المنسدلة)
        function updateChart() {
            const searchVal = document.getElementById('searchInput').value.trim();
            const selectVal = document.getElementById('companySelect').value;

            if (searchVal !== "") {
                if (searchVal.toLowerCase() === "تاسي") {
                    drawChartFor("تاسي");
                    document.getElementById('companySelect').value = "تاسي";
                } else if (labels.length > 0 && rawHistory[labels[labels.length - 1]][searchVal]) {
                    drawChartFor(searchVal);
                    document.getElementById('companySelect').value = searchVal;
                } else {
                    alert("رمز الشركة غير موجود في قاعدة بيانات اليوم الحالية.");
                }
            } else {
                drawChartFor(selectVal);
            }
        }

        // تشغيل العرض التلقائي على تاسي عند فتح الصفحة لأول مرة
        drawChartFor("تاسي");
    </script>
</body>
</html>
"""
# =========================================================================

@app.route('/')
def index():
    chart_data, status_msg = fetch_and_save_data()
    return render_template_string(HTML_TEMPLATE, history_data=chart_data, status_message=status_msg)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))