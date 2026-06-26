<script>
        const rawHistory = {{ history_data | tojson }};
        // ترتيب التواريخ تصاعدياً
        const labels = Object.keys(rawHistory).sort();
        
        // مسح شامل لجمع الشركات من كل التواريخ
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

        // تعبئة القائمة المستدلة
        const selectDropdown = document.getElementById('companySelect');
        Object.keys(globalCompanies).sort((a, b) => parseInt(a) - parseInt(b)).forEach(sym => {
            let opt = document.createElement('option');
            opt.value = sym;
            opt.text = `${sym} - ${globalCompanies[sym]}`;
            selectDropdown.appendChild(opt);
        });

        // تجهيز مكان الرسم البياني
        const ctx = document.getElementById('sblChart').getContext('2d');
        let chartInstance = null;

        function drawChartFor(symbol) {
            let chartDataValues = [];
            let chartLabels = [];
            let companyName = symbol === "تاسي" ? "كامل السوق - تاسي" : (globalCompanies[symbol] || "");

            // بناء البيانات: نقوم بالمرور على التواريخ، وإذا لم توجد بيانات نضع 0 أو نتخطى
            labels.forEach(date => {
                if (rawHistory[date] && rawHistory[date][symbol] !== undefined) {
                    chartLabels.push(date); // إضافة التاريخ كنص صريح
                    chartDataValues.push(rawHistory[date][symbol].volume); // إضافة الكمية كعدد
                }
            });

            document.getElementById('displayTitle').innerText = `المعروض الآن: ${symbol === "تاسي" ? "" : symbol + " - "} ${companyName}`;
            
            // تدمير الرسم القديم لمنع تداخل الرسومات
            if (chartInstance) {
                chartInstance.destroy();
            }

            // إنشاء الرسم الجديد مع إجبار المحاور على القراءة النصية والعددية الصحيحة
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartLabels, // المحور X يحتوي على التواريخ نصوصاً
                    datasets: [{
                        label: symbol === "تاسي" ? "إجمالي الأسهم المقراضة بالسوق" : `حركة كميات الأسهم لـ ${companyName}`,
                        data: chartDataValues, // المحور Y يحتوي على الكميات الحقيقية
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
                        x: {
                            type: 'category', // إجبار المحور الأفقي على معاملة التواريخ كنصوص صريحة وعدم تخمينها كأرقام أو أوقات
                            title: { display: true, text: 'التاريخ' }
                        },
                        y: { 
                            beginAtZero: true, // إجبار المحور على البدء من الصفر صعوداً إلى الملايين
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

        // تشغيل افتراضي
        drawChartFor("تاسي");
    </script>