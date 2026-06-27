import os
import json
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string
import urllib3

# إيقاف تحذيرات شهادات الأمان
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
DATA_FILE = "sbl_history.json"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
        
        # 1. اقتناص التاريخ الحقيقي بالصيغة العربية للموقع (يوم-شهر-سنة)
        date_match = re.search(r'(\d{2})-(\d{2})-(\d{4})', response.text)
        
        # حماية صارمة: إذا لم نجد تاريخاً حقيقياً في الصفحة، ننسحب فوراً ولا نعتمد على تاريخ الخادم
        if not date_match:
            print("تنبيه أمني: لم يتم العثور على نمط التاريخ في الصفحة. تم إلغاء العملية لحماية قاعدة البيانات.")
            return history
            
        day, month, year = date_match.group(1), date_match.group(2), date_match.group(3)
        target_date = f"{year}-{month}-{day}" # تحويل آمن إلى الصيغة القياسية لترتيب الـ JSON (YYYY-MM-DD)

        # 2. شرط الأمان الصارم لمنع تكرار البيانات أو حجز أيام الإجازات
        if target_date in history and isinstance(history[target_date], dict) and "تاسي" in history[target_date]:
            print(f"البيانات الخاصة بالتاريخ الحقيقي {target_date} متواجدة مسبقاً. تم إيقاف الكشط تلقائياً.")
            return history

        # 3. تحليل الجدول في حال كان التاريخ جديداً تماماً صدر لأول مرة
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        
        day_data = {}
        total_volume = 0
        found_any_data = False
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                try:
                    code = cols[0].text.strip()
                    name = cols[1].text.strip()
                    vol_text = cols[3].text.strip().replace(',', '')
                    
                    if vol_text.isdigit() and code.isdigit():
                        vol_val = int(vol_text)
                        day_data[code] = {
                            "name": name,
                            "volume": vol_val
                        }
                        total_volume += vol_val
                        found_any_data = True
                except Exception:
                    continue
        
        # 4. الحفظ النهائي المنظم
        if found_any_data and total_volume > 0:
            day_data["تاسي"] = {
                "name": "كامل السوق - تاسي",
                "volume": total_volume
            }
            history[target_date] = day_data
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
                print(f"تم بنجاح تسجيل يوم مالي جديد وحقيقي: {target_date}")
                
    except Exception as e:
        print(f"حدث خطأ أثناء معالجة البيانات: {e}")
        
    return history

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مؤشر الأسهم المقرضة التفاعلي</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f4f7f6; text-align: right; }
        .container { max-width: 1100px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; text-align: center; margin-bottom: 25px; }
        .control-box { display: flex; justify-content: center; align-items: center; gap: 15px; margin-bottom: 25px; background: #eef2f3; padding: 15px; border-radius: 6px; }
        label { font-weight: bold; color: #34495e; }
        select { padding: 8px 15px; font-size: 15px; border-radius: 4px; border: 1px solid #bdc3c7; width: 350px; max-width: 100%; outline: none; }
        .update-btn { padding: 8px 15px; background-color: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 15px; }
        .update-btn:hover { background-color: #219653; }
        .chart-wrapper { position: relative; height: 55vh; width: 100%; }
    </style>
</head>
<body>
    <div class="container">
        <h2>مؤشر حركة كميات الأسهم المقرضة الحقيقية</h2>
        
        <div class="control-box">
            <label for="companySelector">اختر نطاق العرض الاستراتيجي:</label>
            <select id="companySelector" onchange="updateSBLChart()">
                <option value="تاسي">-- إجمالي السوق (تاسي) --</option>
            </select>
            <button class="update-btn" onclick="window.location.reload()">تحديث وفحص حركي الحين ↻</button>
        </div>

        <div class="chart-wrapper">
            <canvas id="sblChart"></canvas>
        </div>
    </div>

    <script>
        // حقن البيانات بشكل آمن لمنع تدمير الكود السطري في المتصفح
        const historyData = {{ data | tojson | safe }};
        const labels = Object.keys(historyData).sort();
        
        // 1. استخراج خريطة شاملة وموحدة لكل الشركات المتواجدة في الأرشيف التاريخي
        const globalCompaniesMap = new Map();
        labels.forEach(date => {
            const dayData = historyData[date];
            if (dayData && typeof dayData === 'object') {
                Object.keys(dayData).forEach(code => {
                    if (code !== "تاسي") {
                        globalCompaniesMap.set(code, dayData[code].name);
                    }
                });
            }
        });

        // 2. تغذية القائمة المنسدلة بالرموز والأسماء ديناميكياً مرتبة رقمياً
        const dropdown = document.getElementById('companySelector');
        const sortedCodes = Array.from(globalCompaniesMap.keys()).sort();
        sortedCodes.forEach(code => {
            const opt = document.createElement('option');
            opt.value = code;
            opt.text = `${code} - ${globalCompaniesMap.get(code)}`;
            dropdown.appendChild(opt);
        });

        let chartInstance = null;

        // 3. المحرك الحركي لرسم البيانات وتعويض النقص بالأصفار
        function updateSBLChart() {
            const selection = dropdown.value;
            let labelName = selection === "تاسي" ? "إجمالي السوق - تاسي" : globalCompaniesMap.get(selection);
            
            // بناء خط البيانات عبر فحص كل التواريخ زمنياً تعويضاً عن سقوط الشركات
            const dataValues = labels.map(date => {
                const entry = historyData[date];
                if (entry && typeof entry === 'object') {
                    // إذا كان التاريخ يحتوي على الكود المحدد
                    if (entry[selection]) {
                        return entry[selection].volume;
                    }
                } else if (selection === "تاسي" && typeof entry === 'number') {
                    // دعم هيكلية الأرقام الفردية القديمة احتياطياً
                    return entry;
                }
                return 0; // تعويض فوري بالصفر المتصل إذا غابت الشركة في هذا اليوم المالي
            });

            const ctx = document.getElementById('sblChart').getContext('2d');
            
            // تدمير الكائن الرسومي السابق لمنع تداخل الرسوم عند التغيير
            if (chartInstance) {
                chartInstance.destroy();
            }

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: labelName,
                        data: dataValues,
                        borderColor: selection === "تاسي" ? '#2980b9' : '#27ae60',
                        backgroundColor: selection === "تاسي" ? 'rgba(41, 128, 185, 0.08)' : 'rgba(39, 174, 96, 0.08)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.2,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#2c3e50'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { 
                            title: { display: true, text: 'الكمية (سهم)' },
                            beginAtZero: true 
                        },
                        x: { 
                            title: { display: true, text: 'التاريخ الفعلي للملف التاريخي' } 
                        }
                    }
                }
            });
        }

        // تشغيل البناء الأولي للمخطط فور تحميل الصفحة
        updateSBLChart();
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