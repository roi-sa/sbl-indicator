import os
import json
import re
from datetime import date
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, jsonify
import urllib3

# إيقاف تحذيرات شهادات الأمان المزعجة من تداول
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
DATA_FILE = "sbl_history.json"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 1. تحميل ملف البيانات الحالي التاريخي لمنع الفقدان
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
        
        # 2. اقتناص تاريخ التحديث الحقيقي من نص الصفحة (وليس تاريخ الساعة في الخادم)
        target_date = str(date.today())  # قيمة احتياطية في حال فشل العثور على النص
        
        # البحث عن نمط التاريخ المرافق لعبارة "تاريخ آخر تحديث"
        text_match = re.search(r'تاريخ آخر تحديث\s*:\s*(\d{4}-\d{2}-\d{2})', response.text)
        if text_match:
            target_date = text_match.group(1)
        else:
            # محاولة بحث أوسع عن أي تاريخ يطابق تنسيق السنة-الشهر-اليوم داخل الصفحة
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', response.text)
            if date_match:
                target_date = date_match.group(1)

        # 3. شرط الأمان الصارم لمنع التكرار وتدمير البيانات:
        # إذا كان التاريخ الحقيقي مستخرجاً ومخزناً مسبقاً بهيكلية الكائن الصحيحة، يتوقف الكاشط فوراً.
        if target_date in history and isinstance(history[target_date], dict) and "تاسي" in history[target_date]:
            print(f"بيانات التاريخ الحقيقي {target_date} مسجلة مسبقاً وبنيتها سليمة. تم إنهاء العملية بأمان منعاً للتكرار.")
            return history

        # 4. بدء كشط وتحليل الجدول في حال كان التاريخ جديداً
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
                    
                    if vol_text.isdigit():
                        vol_val = int(vol_text)
                        
                        # نتحقق أن الرمز عبارة عن رقم (أي شركة مدرجة وليس عنواناً أو سطراً شكلياً)
                        if code.isdigit():
                            day_data[code] = {
                                "name": name,
                                "volume": vol_val
                            }
                            total_volume += vol_val
                            found_any_data = True
                except Exception:
                    continue
        
        # 5. حفظ إجمالي السوق تحت مفتاح مخصص وتخزين اليوم
        if found_any_data and total_volume > 0:
            # إضافة كائن إجمالي السوق "تاسي" في بداية أو نهاية قائمة الشركات لليوم
            day_data["تاسي"] = {
                "name": "كامل السوق - تاسي",
                "volume": total_volume
            }
            
            # ربط تفاصيل اليوم بالتاريخ الحقيقي المستخرج من الصفحة
            history[target_date] = day_data
            
            # حفظ الملف بصيغة JSON منظمة وتدعم اللغة العربية
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
                print(f"تم بنجاح تحديث قاعدة البيانات وإدراج يوم جديد: {target_date}")
                
    except Exception as e:
        print(f"حدث خطأ أثناء جلب البيانات أو تحليلها: {e}")
        
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
        // استقبال البيانات القادمة من الباك إند
        const historyData = {{ data | tojson }};
        
        // فرز التواريخ تصاعدياً لضمان الترتيب الزمني الصحيح على المنحنى
        const labels = Object.keys(historyData).sort();
        
        // 6. هندسة قراءة الرسم البياني ليتوافق مع بنية البيانات المتفرعة للشركات
        const dataValues = labels.map(date => {
            const entry = historyData[date];
            
            // إذا كان الكائن متفرعاً ويحتوي على مفتاح "تاسي"، استخرج منه الكمية الإجمالية
            if (entry && typeof entry === 'object' && entry["تاسي"]) {
                return entry["تاسي"].volume;
            }
            
            // دعم توافقي مؤقت في حال وجود تواريخ قديمة مسجلة كأرقام مجردة
            return typeof entry === 'number' ? entry : 0;
        });

        const ctx = document.getElementById('sblChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'إجمالي الأسهم المقرضة الحقيقية (تاسي)',
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
                    y: { 
                        title: { display: true, text: 'الكمية (سهم)' } 
                    },
                    x: { 
                        title: { display: true, text: 'التاريخ' },
                        // 7. تفعيل الفراغ الشكلي التصميمي في أطراف المحور الأفقي لراحة العين دون تواريخ وهمية
                        offset: true 
                    }
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