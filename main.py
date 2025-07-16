from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse
import requests, re
from bs4 import BeautifulSoup

app = FastAPI(title="Video Scraper")
templates = Jinja2Templates(directory="templates")

class VideoDetails(BaseModel):
    video_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[str] = None
    upload_date: Optional[str] = None
    profile_url: Optional[str] = None
    views: Optional[str] = None
    channel_name: Optional[str] = None
    subscriber_count: Optional[str] = None

def convert_to_ddmmyyyy(date_str: str) -> str:
    month_map = {
        'янв': '01', 'фев': '02', 'мар': '03', 'апр': '04', 'май': '05', 'мая': '05',
        'июн': '06', 'июл': '07', 'авг': '08', 'сен': '09', 'окт': '10', 'ноя': '11', 'дек': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }

    date_str = date_str.strip().replace('.', '').replace(',', '').lower()
    parts = date_str.split()

    try:
        if "вчера" in date_str:
            return (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y")
        elif len(parts) == 3:
            day = parts[0].zfill(2)
            month = month_map.get(parts[1][:3], '??')
            year = parts[2]
        elif len(parts) == 2:
            day = parts[0].zfill(2)
            month = month_map.get(parts[1][:3], '??')
            year = str(datetime.now().year)
        elif re.match(r"\d{1,2}-\w{3,}", date_str):
            sub_parts = date_str.split('-')
            day = sub_parts[0].zfill(2)
            month = month_map.get(sub_parts[1][:3], '??')
            year = sub_parts[2] if len(sub_parts) > 2 else str(datetime.now().year)
        else:
            return date_str
        return f"{day}-{month}-{year}"
    except:
        return date_str

def scrape_okru_video(url: str) -> VideoDetails:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        html = res.text
        soup = BeautifulSoup(html, 'html.parser')
        data = VideoDetails(video_url=url)

        data.title = soup.find("meta", property="og:title")['content'].strip() if soup.find("meta", property="og:title") else "N/A"

        duration_match = re.search(r'class="vid-card_duration">([\d:]+)</div>', html)
        if duration_match:
            duration = duration_match.group(1)
            parts = duration.split(":")
            data.duration = duration if len(parts) == 3 else f"00:{duration}" if len(parts) == 2 else f"00:00:{duration.zfill(2)}"
        else:
            data.duration = "N/A"

        upload_match = re.search(r'<span class="vp-layer-info_i vp-layer-info_date">([^<]+)</span>', html)
        data.upload_date = convert_to_ddmmyyyy(upload_match.group(1)) if upload_match else "N/A"

        views_match = re.search(r'<div class="vp-layer-info_i"><span>(.*?)</span>', html)
        data.views = views_match.group(1).strip() if views_match else "N/A"

        channel_match = re.search(r'name="([^"]+)" id="[\d]+"', html)
        data.channel_name = channel_match.group(1) if channel_match else "N/A"

        subs_match = re.search(r'subscriberscount="(\d+)"', html)
        data.subscriber_count = subs_match.group(1) if subs_match else "N/A"

        # Profile URL
        profile_url = None
        hovercard = soup.find(attrs={"data-entity-hovercard-url": True})
        if hovercard:
            rel = hovercard["data-entity-hovercard-url"]
            profile_url = f"https://ok.ru{rel}" if rel.startswith("/") else rel
        if not profile_url:
            match = re.search(r'"authorLink":"(\\/profile\\/[^"]+)"', html)
            if match:
                profile_url = "https://ok.ru" + match.group(1).replace("\\/", "/")
        if not profile_url:
            match = re.search(r'/(group|profile)/([\w\d]+)', html)
            if match:
                profile_url = f"https://ok.ru/{match.group(1)}/{match.group(2)}"
        data.profile_url = profile_url or "N/A"

        return data

    except Exception as e:
        print(f"Error scraping OK.ru: {e}")
        return VideoDetails(video_url=url, title="N/A", duration="N/A", upload_date="N/A",
                            profile_url="N/A", views="N/A", channel_name="N/A", subscriber_count="N/A")

def scrape_dailymotion_video(url: str) -> VideoDetails:
    try:
        video_id = url.strip().split("/")[-1].split("?")[0]
        base = f"https://api.dailymotion.com/video/{video_id}?fields=id,title,duration,created_time,views_total,likes_total,owner"
        resp = requests.get(base, timeout=10)
        video_json = resp.json()

        owner_id = video_json.get("owner", "")
        owner_resp = requests.get(f"https://api.dailymotion.com/user/{owner_id}?fields=username,followers_total")
        owner_json = owner_resp.json()

        return VideoDetails(
            video_url=url,
            title=video_json.get("title", "N/A"),
            duration=str(video_json.get("duration", "N/A")),
            upload_date=datetime.utcfromtimestamp(video_json.get("created_time")).strftime("%d-%m-%Y") if video_json.get("created_time") else "N/A",
            views=str(video_json.get("views_total", "N/A")),
            profile_url=f"https://www.dailymotion.com/{owner_id}",
            channel_name=owner_json.get("username", "N/A"),
            subscriber_count=str(owner_json.get("followers_total", "N/A"))
        )

    except Exception as e:
        print(f"Error scraping Dailymotion: {e}")
        return VideoDetails(video_url=url, title="N/A", duration="N/A", upload_date="N/A",
                            profile_url="N/A", views="N/A", channel_name="N/A", subscriber_count="N/A")

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/scrape")
async def scrape_endpoint(url: str, platform: str = "okru"):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)

    if platform == "okru" and "ok.ru" in parsed.netloc:
        return scrape_okru_video(url)
    elif platform == "dailymotion" and "dailymotion.com" in parsed.netloc:
        return scrape_dailymotion_video(url)
    else:
        raise HTTPException(status_code=400, detail="Unsupported platform or invalid URL.")

# For local/Render
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
