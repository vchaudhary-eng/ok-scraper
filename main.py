
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urlparse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="okru-scraper")
templates = Jinja2Templates(directory="templates")

class VideoDetails(BaseModel):
    video_url: Optional[str] = None
    duration: Optional[str] = None
    upload_date: Optional[str] = None
    profile_url: Optional[str] = None
    views: Optional[str] = None
    channel_name: Optional[str] = None
    subscriber_count: Optional[str] = None

def scrape_okru_video(url: str) -> VideoDetails:
    """Scrape video details from ok.ru URL using Google Sheets patterns"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        
        video_details = VideoDetails()
        video_details.video_url = url
        
        # Extract duration using Google Sheets pattern: class="vid-card_duration"
        duration_match = re.search(r'class="vid-card_duration">([\d:]+)<\/div>', html, re.IGNORECASE)
        if duration_match:
            duration_str = duration_match.group(1)
            time_parts = duration_str.split(":")
            if len(time_parts) == 3:  # HH:MM:SS
                video_details.duration = duration_str
            elif len(time_parts) == 2:  # MM:SS
                video_details.duration = f"00:{duration_str}"
            else:  # SS
                video_details.duration = f"00:00:{duration_str.zfill(2)}"
        else:
            video_details.duration = "N/A"
        
        # Extract upload date using Google Sheets pattern: vp-layer-info_i vp-layer-info_date
        upload_date_match = re.search(r'<span class="vp-layer-info_i vp-layer-info_date">([^<]+)<\/span>', html, re.IGNORECASE)
        if upload_date_match:
            date_text = upload_date_match.group(1).strip()
            
            # Handle Russian "вчера" (yesterday)
            if "вчера" in date_text.lower():
                from datetime import datetime, timedelta
                yesterday = datetime.now() - timedelta(days=1)
                time_part = date_text.split(" ")[-1] if " " in date_text else "00:00"
                video_details.upload_date = yesterday.strftime(f"%d/%m/%Y")
            else:
                # Handle DD-MM-YYYY or DD-MM format
                time_parts = date_text.split(" ")
                if len(time_parts) >= 1:
                    date_part = time_parts[0]
                    date_parts = date_part.split("-")
                    if len(date_parts) >= 2:
                        day = date_parts[0].zfill(2)
                        month = date_parts[1].zfill(2)
                        current_year = str(datetime.now().year)
                        year = date_parts[2] if len(date_parts) > 2 else current_year
                        video_details.upload_date = f"{day}/{month}/{year}"
                    else:
                        video_details.upload_date = date_text
                else:
                    video_details.upload_date = date_text
        else:
            video_details.upload_date = "N/A"
        
        # Extract views count using Google Sheets pattern: <div class="vp-layer-info_i"><span>
        views_match = re.search(r'<div class="vp-layer-info_i"><span>(.*?)<\/span>', html, re.IGNORECASE)
        if views_match:
            video_details.views = views_match.group(1).strip()
        else:
            video_details.views = "N/A"
        
        # Extract channel URL using Google Sheets pattern: /(group|profile)/([\w\d]+)
        channel_url_match = re.search(r'\/(group|profile)\/([\w\d]+)', html, re.IGNORECASE)
        if channel_url_match:
            video_details.profile_url = f"https://ok.ru/{channel_url_match.group(1)}/{channel_url_match.group(2)}"
        else:
            video_details.profile_url = "N/A"
        
        # Extract channel name using Google Sheets pattern: name="..." id="..."
        channel_name_match = re.search(r'name="([^"]+)" id="[\d]+"', html, re.IGNORECASE)
        if channel_name_match:
            video_details.channel_name = channel_name_match.group(1)
        else:
            video_details.channel_name = "N/A"
        
        # Extract subscriber count using Google Sheets pattern: subscriberscount="..."
        subscribers_match = re.search(r'subscriberscount="(\d+)"', html, re.IGNORECASE)
        if subscribers_match:
            video_details.subscriber_count = subscribers_match.group(1)
        else:
            video_details.subscriber_count = "N/A"
        
        return video_details
        
    except Exception as e:
        print(f"Scraping error for {url}: {str(e)}")
        # Return N/A values instead of raising exception
        video_details = VideoDetails()
        video_details.video_url = url
        video_details.duration = "N/A"
        video_details.upload_date = "N/A"
        video_details.profile_url = "N/A"
        video_details.views = "N/A"
        video_details.channel_name = "N/A"
        video_details.subscriber_count = "N/A"
        return video_details

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main page with form to input video URL"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/scrape", response_class=HTMLResponse)
async def scrape_video(request: Request, video_urls: str = Form(...)):
    """Scrape video details from provided URLs"""
    urls = [url.strip() for url in video_urls.split('\n') if url.strip()]
    
    if not urls:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Please provide at least one video URL"
        })
    
    results = []
    errors = []
    
    for url in urls:
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Validate if it's an ok.ru URL
            parsed_url = urlparse(url)
            if 'ok.ru' not in parsed_url.netloc:
                errors.append(f"Invalid URL: {url}")
                continue
            
            video_details = scrape_okru_video(url)
            results.append(video_details)
            
        except Exception as e:
            errors.append(f"Error scraping {url}: {str(e)}")
    
    return templates.TemplateResponse("result.html", {
        "request": request,
        "videos": results,
        "errors": errors
    })

@app.get("/api/scrape")
async def api_scrape_video(url: str):
    """API endpoint to scrape video details"""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    parsed_url = urlparse(url)
    if 'ok.ru' not in parsed_url.netloc:
        raise HTTPException(status_code=400, detail="Please provide a valid ok.ru video URL")
    
    return scrape_okru_video(url)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
