import os
import json
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string
import urllib3
from datetime import datetime

# إيقاف تحذيرات شهادات الأمان لضمان استقرار الاتصال بالسيرفر
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
DATA_FILE = "sbl_history.json"

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 1. قراءة قاعِدة البيانات (التي تبدأ الآن نظيفة {})
    history = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = {}

    try:
        # الاتصال بالرابط وسحب الصفحة
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 2. فحص واقتناص تاريخ التقرير الحقيقي من داخل نص الصفحة (يدعم - أو /)
        page_text = soup.get_text()
        date_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})|(\d{4}[-/]\d{2}[-/]\d{2})', page_text)
        
        if date_match:
            raw_date = date_match.group(0).replace('/', '-')
            parts = raw_date.split('-')
            # إذا كان التاريخ يبدأ باليوم (صيغة تداول العربية DD-MM-YYYY)، نعيد ترتيبه لـ YYYY-MM-DD
            if len(parts[0]) == 2:
                scraped_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
            else:
                scraped_date = raw_date
        else:
            # احتياط صلب في حال غيّر تداول مكان التاريخ أو صيغته
            scraped_date = datetime.now().strftime('%Y-%m-%d')

        current_day_data = {}
        total_volume = 0
        
        # 3. تشريح الجدول واقتناص الشركات بدقة
        table = soup.find('table')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
                if len(cols) >= 3:
                    code = cols[0]       # رمز الشركة (مثل 1010)
                    name = cols[1]       # اسم الشركة
                    volume_str = re.sub(r'[^\d]', '', cols[2]) # تنظيف الكمية من الفواصل والأحرف
                    
                    # التحقق من أن السطر يحتوي على بيانات شركة حقيقية وليس عناوين جانبية
                    if code.isdigit() and volume_str.isdigit():
                        vol = int(volume_str)
                        current_day_data[code] = {
                            "name": name,
                            "volume": vol
                        }
                        total_volume += vol

        # 4. إذا نجحت عملية القراءة ولم يكن الجدول فارغاً، نحدث الملف التاريخي
        if current_day_data:
            # حقن إجمالي السوق المحسوب ديناميكياً تحت مفتاح خاص وثابت
            current_day_data["TOTAL"] = {
                "name": "إجمالي السوق - تاسي",
                "volume": total_volume
            }
            
            # حفظ البيانات تحت مفتاح التاريخ الموحد
            history[scraped_date] = current_day_data
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
                
    except Exception as e:
        print(f"خطأ أثناء تحديث البيانات: {e}")
        
    return history

# واجهة المستخدم الديناميكية المستقلة عن عشوائية البيانات القديمة
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مؤشر الأسهم المقرضة (SBL)</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; margin: 0; padding: 20px; text-align: right; }
        .container { max-width: 1200px; margin: auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; text-align: center; margin-bottom: 30px; font-size: 24px; border-bottom: 2px solid #ecf0f1; padding-bottom: 15px; }
        .selector-box { display: flex; justify-content: center; align-items: center; gap: 15px; margin-bottom: 30px; background: #f1f2f6; padding: 15px; border-radius: 6px; }
        label { font-weight: bold; color: #2c3e50; }
        select { padding: 10px; font-size: 16px; border-radius: 4px; border: 1px solid #ced4da; width: 400px; max-width: 100%; outline: none; }
        .chart-wrapper { position: relative; height: 60vh; width: 100%; }
    </style>
</head>
<body>

    <div class="container">
        <h1>مؤشر حركة تغيير الأسهم المقرضة الحقيقية</h1>
        
        <div class="selector-box">
            <label for="companySelector">اختر نطاق العرض الاستراتيجي:</label>
            <select id="companySelector" onchange="updateSBLChart()">
                <option value="TOTAL">-- إجمالي السوق (تاسي) --</option>
            </select>
        </div>

        <div class="chart-wrapper">
            <canvas id="sblChart"></canvas>
        </div>
    </div>

    <script>
        // استقبال البيانات الحية القادمة من السيرفر
        const rawHistory = {{ history_json | safe }};
        
        // 1. فرز التواريخ المتاحة تصاعدياً بشكل تلقائي لحل مشكلة قفزات التحديثات الزمنية
        const chronDates = Object.keys(rawHistory).sort();
        
        // 2. مسح شامل لبناء دليل الشركات الفريد الشامل (حتى لو اختفت لاحقاً)
        const globalCompaniesMap = new Map();
        chronDates.forEach(date => {
            const dayData = rawHistory[date];
            Object.keys(dayData).forEach(code => {
                if (code !== "TOTAL") {
                    globalCompaniesMap.set(code, dayData[code].name);
                }
            });
        });

        // 3. تغذية القائمة المنسدلة بالشركات المرصودة مرتبة حسب رموزها
        const dropdown = document.getElementById('companySelector');
        const sortedCodes = Array.from(globalCompaniesMap.keys()).sort();
        sortedCodes.forEach(code => {
            const opt = document.createElement('option');
            opt.value = code;
            opt.text = `${code} - ${globalCompaniesMap.get(code)}`;
            dropdown.appendChild(opt);
        });

        let chartInstance = null;

        // 4. محرك معالجة اختفاء الشركات والربط الصِفري المتصل
        function updateSBLChart() {
            const currentSelection = dropdown.value;
            let labelName = currentSelection === "TOTAL" ? "إجمالي السوق - تاسي" : globalCompaniesMap.get(currentSelection);

            // المرور على كافة التواريخ لتعويض النقص بالأصفار
            const datasetPoints = chronDates.map(date => {
                const dayData = rawHistory[date];
                if (dayData && dayData[currentSelection]) {
                    return dayData[currentSelection].volume; // كمية حقيقية
                } else {
                    return 0; // تعويض ذكي بالصفر إذا سقطت من الجدول أو لم تكن قد دخلت بعد لضمان اتصال الخط
                }
            });

            const ctx = document.getElementById('sblChart').getContext('2d');
            if (chartInstance) {
                chartInstance.destroy(); // تدمير الهيكل القديم لبناء الجديد بنظافة وثبات
            }

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chronDates,
                    datasets: [{
                        label: labelName,
                        data: datasetPoints,
                        borderColor: currentSelection === "TOTAL" ? '#2980b9' : '#27ae60',
                        backgroundColor: currentSelection === "TOTAL" ? 'rgba(41, 128, 185, 0.05)' : 'rgba(39, 174, 96, 0.05)',
                        borderWidth: 3,
                        tension: 0.1,
                        fill: true,
                        pointRadius: 5,
                        pointHoverRadius: 7
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { title: { display: true, text: 'حجم الأسهم المقرضة' }, beginAtZero: true },
                        x: { title: { display: true, text: 'التواريخ المسجلة بالتحديث الفعلي' } }
                    }
                }
            });
        }

        // تشغيل العرض الافتراضي (الإجمالي) عند تحميل الصفحة لأول مرة
        updateSBLChart();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    # جلب وحفظ التحديث الجديد تلقائياً بمجرد زيارة أي مستخدم للموقع
    latest_history = fetch_and_save_data()
    return render_template_string(HTML_TEMPLATE, history_json=json.dumps(latest_history, ensure_ascii=False))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)