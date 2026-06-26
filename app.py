import os
import json
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
DATA_FILE = "sbl_history.json"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 1. تحميل التاريخ الحالي المخزن لعدم الكتابة فوق القديم
    history = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = {}

    try:
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 2. استخراج تاريخ التقرير الحقيقي المنشور في الصفحة (مثال: 2026-06-25)
        page_text = soup.get_text()
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', page_text)
        report_date = date_match.group(1) if date_match else "unknown"
        
        rows = soup.find_all('tr')
        today_data = {"تاسي": {"name": "كامل السوق - تاسي", "volume": 0}}
        found_any_data = False
        
        # 3. استخدام نفس منطق التنظيف الخاص بك والناجح في قراءة الأعمدة
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                try:
                    sym_text = cols[0].text.strip()
                    name_text = cols[1].text.strip()
                    vol_text = cols[3].text.strip().replace(',', '')
                    
                    if vol_text.isdigit():
                        vol_val = int(vol_text)
                        if vol_val > 0:
                            # حفظ إجمالي تاسي وحفظ الشركات الفردية بشكل مستقل
                            today_data["تاسي"]["volume"] += vol_val
                            if sym_text.isdigit() and len(sym_text) == 4:
                                today_data[sym_text] = {"name": name_text, "volume": vol_val}
                            found_any_data = True
                except ValueError:
                    continue
        
        # 4. الحفظ في الملف بالهيكل الجديد المنسق فقط إذا كانت البيانات حقيقية وبكامل الشركات
        if found_any_data and today_data["تاسي"]["volume"] > 0 and report_date != "unknown":
            history[report_date] = today_data
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
                
    except Exception as e:
        print(f"حدث خطأ أثناء جلب البيانات: {e}")
        
    return history

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مؤشر الأسهم المقرضة التفاعلي</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f4f7f6; color: #333; }
        .container { max-width: 950px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h2 { color: #2c3e50; text-align: center; font-size: 20px; margin-bottom: 20px; }
        .control-panel { background: #ecf0f1; padding: 15px; border-radius: 8px; display: flex; gap: 15px; align-items: center; justify-content: center; flex-wrap: wrap; margin-bottom: 25px; }
        .search-group, .select-group { display: flex; align-items: center; gap: 8px; }
        select, input { padding: 8px 12px; border: 1px solid #bdc3c7; border-radius: 5px; font-size: 14px; }
        input { width: 120px; }
        select { min-width: 250px; }
        button { padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .btn-search { background-color: #34495e; color: white; }
        .btn-execute { background-color: #27ae60; color: white; }
        .chart-title { text-align: center; font-size: 18px; font-weight: bold; color: #2980b9; margin-top: 15px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>مؤشر حركة كميات الأسهم المقرضة (تحديث تلقائي)</h2>
        
        <div class="control-panel">
            <div class="search-group">
                <label>بحث بالرمز:</label>
                <input type="text" id="searchInput" placeholder="مثال: 1010">
                <button class="btn-search" onclick="searchCompany()">بحث</button>
            </div>
            
            <div class="select-group">
                <label>قائمة الشركات:</label>
                <select id="companySelect" onchange="updateChart()">
                    <option value="تاسي">كل الأسهم - تاسي</option>
                </select>
            </div>
        </div>

        <div class="chart-title" id="displayTitle">المعروض الآن: كل الأسهم - تاسي</div>
        <canvas id="sblChart" width="400" height="180"></canvas>
    </div>

    <script>
        const rawHistory = {{ data | tojson }};
        
        // تنظيف التواريخ ودعم التوافقية مع الملف القديم (سواء كان رقم مباشر أو كائن معقد)
        const labels = Object.keys(rawHistory).sort();
        
        // استخراج قائمة أسماء الشركات ديناميكياً من كافة التواريخ المتوفرة لتعبئة المنسدلة
        const globalCompanies = {};
        labels.forEach(date => {
            const dayData = rawHistory[date];
            if (dayData && typeof dayData === 'object') {
                Object.keys(dayData).forEach(sym => {
                    if (sym !== "تاسي" && dayData[sym].name) {
                        globalCompanies[sym] = dayData[sym].name;
                    }
                });
            }
        });

        // تعبئة القائمة المنسدلة بالشركات المكتشفة مرتبة بالرمز
        const selectDropdown = document.getElementById('companySelect');
        Object.keys(globalCompanies).sort((a, b) => parseInt(a) - parseInt(b)).forEach(sym => {
            let opt = document.createElement('option');
            opt.value = sym;
            opt.text = `${sym} - ${globalCompanies[sym]}`;
            selectDropdown.appendChild(opt);
        });

        const ctx = document.getElementById('sblChart').getContext('2d');
        let chartInstance = null;

        function drawChartFor(symbol) {
            let chartDataValues = [];
            let chartLabels = [];
            let companyName = symbol === "تاسي" ? "كامل السوق - تاسي" : (globalCompanies[symbol] || "");

            labels.forEach(date => {
                const dayData = rawHistory[date];
                if (dayData !== undefined && dayData !== null) {
                    chartLabels.push(date);
                    
                    // دعم التوافق التام: إذا كان التاريخ القديم يحمل الرقم الإجمالي مباشرة أو كائن حديث
                    if (typeof dayData === 'object') {
                        if (dayData[symbol] !== undefined) {
                            chartDataValues.push(dayData[symbol].volume);
                        } else {
                            chartDataValues.push(0); // صفر للأيام التي لم تكن الشركة مدرجة بالتقرير فيها
                        }
                    } else {
                        // البيانات القديمة المسطحة تذهب لتاسي تلقائياً
                        chartDataValues.push(symbol === "تاسي" ? dayData : 0);
                    }
                }
            });

            document.getElementById('displayTitle').innerText = `المعروض الآن: ${symbol === "تاسي" ? "" : symbol + " - "} ${companyName}`;
            
            if (chartInstance) { chartInstance.destroy(); }

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartLabels,
                    datasets: [{
                        label: symbol === "تاسي" ? "إجمالي الأسهم المقرضة بالسوق" : `حركة الكميات لـ ${companyName}`,
                        data: chartDataValues,
                        borderColor: symbol === "تاسي" ? '#2980b9' : '#e67e22',
                        backgroundColor: symbol === "تاسي" ? 'rgba(41, 128, 185, 0.05)' : 'rgba(230, 126, 34, 0.05)',
                        borderWidth: 3,
                        tension: 0.2,
                        fill: true,
                        pointRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { beginAtZero: true, title: { display: true, text: 'الكمية (سهم)' } },
                        x: { title: { display: true, text: 'التاريخ' } }
                    }
                }
            });
        }

        function searchCompany() {
            const searchVal = document.getElementById('searchInput').value.trim();
            if (searchVal === "") return;
            if (searchVal === "تاسي") { selectDropdown.value = "تاسي"; updateChart(); return; }
            
            if (globalCompanies[searchVal]) {
                selectDropdown.value = searchVal;
                updateChart();
            } else {
                alert("الرمز غير موجود في البيانات التاريخية الحالية.");
            }
        }

        function updateChart() {
            drawChartFor(selectDropdown.value);
        }

        // تشغيل الرسم البياني الافتراضي لتاسي فور تحميل الصفحة
        drawChartFor("تاسي");
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    chart_data = fetch_and_save_data()
    return render_template_string(HTML_TEMPLATE, data=chart_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)