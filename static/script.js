document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("thesis-form");
    const submitBtn = document.getElementById("submit-btn");
    const resultContainer = document.getElementById("result-container");
    const thesisOutput = document.getElementById("thesis-output");
    
    let priceChartInstance = null;

    async function renderChart(ticker) {
        try {
            const response = await fetch(`http://localhost:8000/api/chart-data/${ticker}`);
            if (!response.ok) throw new Error("Chart data not found");
            const data = await response.json();

            const ctx = document.getElementById('priceChart').getContext('2d');

            if (priceChartInstance) {
                priceChartInstance.destroy();
            }

            priceChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: `${ticker} Closing Price (1Y)`,
                        data: data.prices,
                        borderColor: '#8c52ff',
                        backgroundColor: 'rgba(140, 82, 255, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: true,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { display: false },
                        y: {
                            ticks: { color: '#a0a6b5' },
                            grid: { color: '#2d3446' }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#ffffff' } }
                    }
                }
            });
        } catch (error) {
            console.error("Failed to load chart:", error);
        }
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const ticker = document.getElementById("ticker").value.trim().toUpperCase();
        const risk = document.getElementById("risk").value;
        const horizon = document.getElementById("horizon").value; 

        if (!ticker) return;

        submitBtn.disabled = true;
        submitBtn.textContent = "Analyzing Market Data & Generating...";
        resultContainer.style.display = "block";
        thesisOutput.textContent = ""; 

        renderChart(ticker);

        try {
            const response = await fetch("http://localhost:8000/api/generate-thesis", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticker: ticker, risk_tolerance: risk, horizon: horizon })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Failed to generate thesis.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let done = false;
            let fullMarkdown = "";

            while (!done) {
                const { value, done: readerDone } = await reader.read();
                done = readerDone;
                
                if (value) {
                    const chunk = decoder.decode(value, { stream: true });
                    const lines = chunk.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const dataContent = line.replace('data: ', '');
                            
                            if (dataContent.trim() === '[DONE]') {
                                done = true;
                                break;
                            }
                            if (dataContent.startsWith('[ERROR]')) {
                                throw new Error(dataContent);
                            }

                            const formattedText = dataContent.replace(/\\n/g, '\n');
                            fullMarkdown += formattedText;
                            thesisOutput.innerHTML = marked.parse(fullMarkdown);
                        }
                    }
                }
            }
        } catch (error) {
            // This is the part that got cut off!
            thesisOutput.textContent = `Error: ${error.message}`;
            thesisOutput.style.color = "#ff6b6b";
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = "Generate Thesis";
        }
    });
});