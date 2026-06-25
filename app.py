import os
import json
from datetime import date
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, jsonify
import urllib3

# إيقاف تحذيرات شهادات الأمان المزعجة
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
DATA_FILE = "sbl_history.json"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # تحميل التاريخ الحالي أولاً لمنع الكتابة فوق البيانات القديمة
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
        total_volume = 0
        found_any_data = False
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                try:
                    vol_text = cols[3].text.strip().replace(',', '')
                    if vol_text.isdigit():
                        total_volume += int(vol_text)
                        found_any_data = True
                except ValueError:
                    continue
        
        # لا نحفظ أو نحدث إلا إذا جلبنا أرقاماً حقيقية وصحيحة من جدول تداول
        if found_any_data and total_volume > 0:
            today = str(date.today())
            history[today] = total_volume
            
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f4f7f6; }
        .container { max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; text-align: center; }
        .update-btn { display: block; margin: 20px auto; padding: 10px 20px; background-color: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        .update-btn:hover { background-color: #219653; }
    </style>
</head>
<body>
    <div class="container">
        <h2>مؤشر حركة كميات الأسهم المقرضة (تحديث يومي تلقائي)</h2>
        <button class="update-btn" onclick="window.location.reload()">تحديث البيانات الآن ↻</button>
        <canvas id="sblChart" width="400" height="200"></canvas>
    </div>

    <script>
        const historyData = {{ data | tojson }};
        const labels = Object.keys(historyData).sort();
        const dataValues = labels.map(date => historyData[date]);

        const ctx = document.getElementById('sblChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'إجمالي الأسهم المقرضة الحقيقية',
                    data: dataValues,
                    borderColor: '#2980b9',
                    backgroundColor: 'rgba(41, 128, 185, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 5,
                    pointBackgroundColor: '#2c3e50'
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