import os
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def index():
    # كود بسيط للتأكد من عمل السيرفر
    return """
    <h1>النظام يعمل!</h1>
    <p>تم الربط بنجاح، والسيرفر الآن في حالة استقرار.</p>
    <p>بمجرد ظهور هذه الرسالة، سنقوم بإضافة منطق جلب البيانات من تداول.</p>
    """

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)