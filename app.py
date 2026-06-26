import os
import json
import base64
import re
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

def get_github_file():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            file_data = res.json()
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return json.loads(content), file_data['sha'], "success"
        return {}, None, "not_found"
    except Exception as e:
        return {}, None, str(e)

def save_github_file(history_data, target_date, sha):
    if not GITHUB_TOKEN:
        return False, "missing_token"
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    content_bytes = json.dumps(history_data, ensure_ascii=False, indent=4).encode('utf-8')
    content_b64 = base64.b64encode(content_bytes).decode('utf-8')
    
    payload = {
        "message": f"automated-update-{target_date}",
        "content": content_b64,
        "branch": "main"
    }
    if sha: 
        payload["sha"] = sha
        
    try:
        res = requests.put(url, headers=headers, json=payload, timeout=12)
        if res.status_code in [200, 201]:
            return True, "saved"
        return False, f"status_{res.status_code}"
    except Exception as e:
        return False, str(e)

def fetch_and_save_data():
    url = "https://www.saudiexchange.sa/Resources/Reports-v2/SBLReport_ar.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    history, sha, db_msg = get_github_file()
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. استخراج تاريخ التقرير الفعلي المكتوب داخل الصفحة قسراً لربطه بالبيانات
        page_text = soup.get_text()
        date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})|(\d{2}[-/]\d{2}[-/]\d{4})', page_text)
        
        if date_match:
            report_date = date_match.group(0).replace('/', '-')
        else:
            saudi_tz = pytz.timezone('Asia/Riyadh')
            report_date = str(datetime.now(saudi_tz).date())
        
        rows = soup.find_all('tr')
        today_data = {"تاسي": {"name": "كامل السوق - تاسي", "volume": 0}}
        companies_count = 0
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                try:
                    sym_text = cols[0].text.strip()
                    name_text = cols[1].text.strip()
                    vol_text = cols[3].text.strip().replace(',', '').replace(' ', '')
                    
                    if sym_text.isdigit() and vol_text.isdigit():
                        vol_val = int(vol_text)
                        if vol_val > 0:
                            today_data[sym_text] = {"name": name_text, "volume": vol_val}
                            today_data["تاسي"]["volume"] += vol_val
                            companies_count += 1
                except Exception:
                    continue
        
        # إذا وجدنا كميات حقيقية نعتمد التحديث بالتاريخ الفعلي للتقرير
        if companies_count > 0 and today_data["تاسي"]["volume"] > 0:
            history[report_date] = today_data
            success, save_msg = save_github_file(history, report_date, sha)
            return history, f"تمت قراءة وتحديث التقرير الفعلي لتاريخ {report_date} بنجاح (الشركات: {companies_count} | الكمية: {today_data['تاسي']['volume']:,})"
        else:
            # محاولة قراءة كمية السوق العام إذا كان هيكل الصفحة مختلفاً (صيانة للمستقبل)
            full_text = soup.get_text().replace(',', '')
            totals = [int(s) for s in re.findall(r'\b\d{6,12}\b', full_text)]
            if totals and today_data["تاسي"]["volume"] == 0:
                today_data["تاسي"]["volume"] = max(totals)
                history[report_date] = today_data
                save_github_file(history, report_date, sha)
                return history, f"تم تحديث إجمالي تاسي التقريبي لتاريخ {report_date} (الكمية: {today_data['تاسي']['volume']:,})"
            
            return history, f"تم عرض قاعدة البيانات التاريخية بنجاح | تاريخ آخر تحديث بالملف هو: {max(history.keys()) if history else 'لا يوجد'}"
            
    except Exception as e:
        return history, f"تم عرض البيانات التاريخية بأمان | خطأ اتصال: {str(e)}"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مؤشر حركة الأسهم المقرضة</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f4f7f6; color: #333; }
        .container { max-width: 1000px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #2c3e50; text-align: center; font-size: 22px; margin-bottom: 5px; }
        .status-bar { text-align: center; color: #27ae60; font-size: 14px; font-weight: bold; margin-bottom: 25px; }
        .control-panel { background: #ecf0f1; padding: 15px; border-radius: 8px; display: flex; gap: 15px; align-items: center; justify-content: center; flex-wrap: wrap; margin-bottom: 25px; }
        .search-group, .select-group { display: flex; align-items: center; gap: 8px; }
        select, input { padding: 8px 12px; border: 1px solid #bdc3c7; border-radius: 5px; font-size: 14px; }
        input { width: 140px; }
        select { min-width: 240px; max-width: 320px; }
        button { padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .btn-search { background-color: #34495e; color: white; }
        .btn-execute { background-color: #27ae60; color: white; padding: 8px 25px; }
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
                <input type="text" id="searchInput" placeholder="مثال: 1010">
                <button class="btn-search" onclick="searchAndSelectCompany()">بحث</button>
            </div>
            
            <div class="select-group">
                <label>قائمة الشركات:</label>
                <select id="companySelect">
                    <option value="تاسي">كل الأسهم - تاسي</option>
                </select>
            </div>
            
            <button class="btn-execute" onclick="updateChart()">عرض المؤشر</button>
        </div>

        <div class="chart-title" id="displayTitle">المعروض الآن: كل الأسهم - تاسي</div>
        <canvas id="sblChart" width="400" height="160"></canvas>
    </div>

    <script>
        const rawHistory = {{ history_data | tojson }};
        const labels = Object.keys(rawHistory).sort();
        
        const globalCompanies = {};
        labels.forEach(date => {
            const dayData = rawHistory[date];
            if (dayData) {
                Object.keys(dayData).forEach(sym => {
                    if (sym !== "تاسي" && dayData[sym].name) {
                        globalCompanies[sym] = dayData[sym].name;
                    }
                });
            }
        });

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
                if (rawHistory[date] && rawHistory[date][symbol] !== undefined) {
                    chartLabels.push(date);
                    
                    let origVolume = rawHistory[date][symbol].volume;
                    let cleanVolume = 0;
                    
                    if (origVolume !== undefined && origVolume !== null) {
                        let volString = origVolume.toString().replace(/,/g, '');
                        cleanVolume = parseInt(volString, 10) || 0;
                    }
                    
                    chartDataValues.push(cleanVolume);
                }
            });

            document.getElementById('displayTitle').innerText = `المعروض الآن: ${symbol === "تاسي" ? "" : symbol + " - "} ${companyName}`;
            
            if (chartInstance) {
                chartInstance.destroy();
            }

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
                        pointRadius: 6,
                        pointHoverRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        x: {
                            type: 'category',
                            title: { display: true, text: 'التاريخ' }
                        },
                        y: { 
                            beginAtZero: true,
                            title: { display: true, text: 'الكمية (سهم)' }
                        }
                    }
                }
            });
        }

        function searchAndSelectCompany() {
            const searchVal = document.getElementById('searchInput').value.trim();
            const selectDropdown = document.getElementById('companySelect');
            if (searchVal === "") return;
            if (searchVal === "تاسي") { selectDropdown.value = "تاسي"; updateChart(); return; }
            
            for (let i = 0; i < selectDropdown.options.length; i++) {
                if (selectDropdown.options[i].value === searchVal) {
                    selectDropdown.value = searchVal;
                    updateChart();
                    return;
                }
            }
            alert("الرمز غير موجود تاريخياً.");
        }

        function updateChart() {
            const selectVal = document.getElementById('companySelect').value;
            drawChartFor(selectVal);
        }

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