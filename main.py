from fastapi.staticfiles import StaticFiles
import os
import yfinance as yf
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

# ---------------------------------------------------------------------------
# Initialization & Setup
# ---------------------------------------------------------------------------
# Load environment variables from .env
load_dotenv()

# Initialize Gemini client
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please check your .env file.")

client = genai.Client(api_key=api_key)

# Initialize FastAPI app
app = FastAPI(
    title="Investment Thesis API (Gemini Edition)",
    description="API for fetching financial data and streaming an AI-generated investment thesis.",
    version="1.0.0"
)

# Setup CORS middleware for local frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend's exact URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class ThesisRequest(BaseModel):
    ticker: str
    risk_tolerance: str = "moderate" # Allowed: "low", "moderate", "high"

# ---------------------------------------------------------------------------
# Data Helpers
# ---------------------------------------------------------------------------
def fetch_stock_data(ticker: str):
    """Fetches P/E ratio, revenue growth, and 12-mo historical data."""
    stock = yf.Ticker(ticker)
    info = stock.info
    
    trailing_pe = info.get("trailingPE", "N/A")
    revenue_growth = info.get("revenueGrowth", "N/A")
    
    if revenue_growth != "N/A" and revenue_growth is not None:
        revenue_growth = f"{revenue_growth * 100:.2f}%"
        
    hist = stock.history(period="1y")
    if hist.empty:
        return None, None, None
        
    return trailing_pe, revenue_growth, hist

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/generate-thesis")
async def generate_thesis(request: ThesisRequest):
    """
    Accepts a ticker and risk tolerance, fetches yfinance data, 
    and streams back a generated thesis via SSE using Gemini.
    """
    ticker = request.ticker.upper()
    
    # Fetch financial data
    pe, rev_growth, hist = fetch_stock_data(ticker)
    if hist is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch data for ticker {ticker}.")

    # Format recent history to save tokens
    recent_hist = hist[['Close', 'Volume']].resample('ME').last().tail(12)
    hist_str = recent_hist.to_string()

    # Construct the prompt
    prompt = f"""You are a strict, professional financial analyst. Evaluate the high-growth potential of {ticker}. 
The user's stated risk tolerance is: {request.risk_tolerance}.

Financial data for {ticker}:
- Trailing P/E Ratio: {pe}
- Revenue Growth: {rev_growth}

Last 12 months end-of-month price and volume data:
{hist_str}

STRICT FORMATTING RULES — you must follow these exactly:
1. Do NOT write large paragraphs. Every point must be a concise bullet point.
2. Structure your response using exactly these three markdown H3 headers, in this order:
   ### The Bull Case
   ### The Bear Case
   ### The Verdict
3. Under each header, use 3-5 bullet points. Each bullet must be one or two sentences maximum.
4. Focus on the growth narrative, market opportunity, and whether the P/E and revenue growth justify expectations given the {request.risk_tolerance} risk profile.
5. Do NOT add any text before the first header or after the last bullet point.
"""

    def event_generator():
        """Generator function to yield Gemini chunks as SSE format."""
        try:
            # We use gemini-2.5-flash as it was in your original script
            response = client.models.generate_content_stream(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            
            for chunk in response:
                if chunk.text:
                    # Replace newlines to ensure SSE format doesn't break
                    safe_content = chunk.text.replace('\n', '\\n')
                    yield f"data: {safe_content}\n\n"
                    
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    # Return the generator as a StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")
@app.get("/api/chart-data/{ticker}")
async def get_chart_data(ticker: str):
    """
    Fetches the 12-month historical date and closing price data 
    for the frontend charting library.
    """
    ticker = ticker.upper()
    _, _, hist = fetch_stock_data(ticker)
    
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail=f"Could not fetch chart data for {ticker}.")

    # Extract dates as strings and closing prices as rounded floats
    dates = hist.index.strftime('%Y-%m-%d').tolist()
    prices = hist['Close'].round(2).tolist()

    return {"dates": dates, "prices": prices}

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)