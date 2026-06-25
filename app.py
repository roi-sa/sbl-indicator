import os
import json
from datetime import date
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
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
        
        rows = soup.find_all('tr')
        today_data = {}
        total_market_volume = 0
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                try:
                    comp_code = cols[0].text.strip()
                    comp_name = cols[1].text.strip()
                    vol_text = cols[3].text.strip().replace(',', '')
                    
                    if comp_code.isdigit() and vol_text.isdigit():
                        volume = int(vol_text)
                        today_data[comp_code] = {
                            "name": comp_name,
                            "volume": volume
                        }
                        total_market_volume += volume
                except ValueError:
                    continue
        
        if today_data and total_market_volume > 0:
            today = str(date.today())
            
            today_data["تاسي"] = {
                "name": "كامل السوق - تاسي",
                "volume": total_market_volume
            }
            
            history[today] = today_data
            
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
    <title>مؤشر الأسهم المقرضة التفاعلي - تداول</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f4f7f6; }
        .container { max-width: 950px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; text-align: center; margin-bottom: 25px; }
        
        .control-panel { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; align-items: center; background: #ecf0f1; padding: 15px; border-radius: 6px; margin-bottom: 25px; }
        .control-panel label { font-weight: bold; color: #34495e; }
        .control-panel select, .control-panel input { padding: 8px 12px; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 14px; }
        #searchBar { width: 140px; }
        #companySelect { min-width: 220px; }
        
        .btn-search { padding: 8px 15px; background-color: #7f8c8d; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .btn-search:hover { background-color: #95a5a6; }
        
        .btn-execute { padding: 8px 30px; background-color: #2980b9; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 15px; font-weight: bold; }
        .btn-execute:hover { background-color: #3498db; }
        
        .update-btn { display: block; margin: 10px auto; padding: 6px 15px; background-color: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
        .update-btn:hover { background-color: #219653; }
        
        #companyTitle { text-align: center; color: #16a085; font-size: 18px; font-weight: bold; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>مؤشر حركة كميات الأسهم المقرضة بالتفصيل</h2>
        
        <div class="control-panel">
            <label>البحث بالرمز:</label>
            <input type="text" id="searchBar" placeholder="مثال: 1120 أو تاسي" value="تاسي">
            <button class="btn-search" onclick="syncSearchToSelect()">بحث 🔍</button>
            
            <label>القائمة المنسدلة:</label>
            <select id="companySelect">
                </select>
            
            <button class="btn-execute" onclick="filterChart()">تنفيذ</button>
        </div>

        <div id="companyTitle">كامل السوق - تاسي</div>
        <canvas id="sblChart" width="400" height="180"></canvas>
        
        <button class="update-btn" onclick="window.location.reload()">تحديث وجلب بيانات اليوم ↻</button>
    </div>

    <script>
        const rawHistory = {{ history_data | tojson }};
        
        let companiesMap = {"تاسي": "كامل السوق - تاسي"};
        for (let dateKey in rawHistory) {
            for (let code in rawHistory[dateKey]) {
                companiesMap[code] = rawHistory[dateKey][code].name;
            }
        }
        
        const selectEl = document.getElementById('companySelect');
        const sortedCodes = Object.keys(companiesMap).sort((a,b) => {
            if(a === "تاسي") return -1;
            if(b === "تاسي") return 1;
            return a.localeCompare(b);
        });
        
        sortedCodes.forEach(code => {
            let opt = document.createElement('option');
            opt.value = code;
            opt.textContent = `${code} - ${companiesMap[code]}`;
            selectEl.appendChild(opt);
        });

        // 1. وظيفة زر البحث: تقوم بمطابقة النص وتغيير الاختيار في القائمة المنسدلة فوراً
        function syncSearchToSelect() {
            let searchVal = document.getElementById('searchBar').value.trim();
            if (companiesMap[searchVal]) {
                selectEl.value = searchVal;
            } else {
                alert("رمز الشركة غير موجود في البيانات الحالية، يرجى التأكد من الرمز.");
            }
        }
        
        // عند تغيير الاختيار يدوياً من القائمة المنسدلة، يتحدث صندوق البحث تلقائياً لراحة المستخدم
        selectEl.addEventListener('change', function(e) {
            document.getElementById('searchBar').value = e.target.value;
        });

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
            
            if (chartInstance) {
                chartInstance.destroy();
            }
            
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
                        tension: 0.2,
                        pointRadius: 5,
                        pointBackgroundColor: '#2c3e50'
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { title: { display: true, text: 'الكمية (سهم)' }, beginAtZero: true },
                        x: { title: { display: true, text: 'التاريخ' } }
                    }
                }
            });
        }

        // 2. عند الضغط على تنفيذ، يتم أخذ الخيار المستقر في القائمة المنسدلة وتحديث الشارت
        function filterChart() {
            let selectedCode = selectEl.value;
            generateChart(selectedCode);
        }

        generateChart('تاسي');
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    chart_data = fetch_and_save_data()
    return render_template_string(HTML_TEMPLATE, history_data=chart_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)