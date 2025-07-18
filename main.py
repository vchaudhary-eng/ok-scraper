from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import requests
from bs4 import BeautifulSoup

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def scrape_okru(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:title")
        title = title_tag["content"] if title_tag else "N/A"

        duration_tag = soup.find("meta", property="video:duration")
        duration = duration_tag["content"] if duration_tag else "N/A"

        profile_tag = soup.select_one("div.user-info_name a")
        profile_url = "https://ok.ru" + profile_tag["href"] if profile_tag else "N/A"

        return {
            "url": url,
            "title": title,
            "duration": duration,
            "profile_url": profile_url
        }
    except Exception:
        return {
            "url": url,
            "title": "N/A",
            "duration": "N/A",
            "profile_url": "N/A"
        }

def scrape_dailymotion(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("meta", property="og:title")
        title = title_tag["content"] if title_tag else "N/A"

        duration_tag = soup.find("meta", property="video:duration")
        duration = duration_tag["content"] if duration_tag else "N/A"

        profile_tag = soup.find("a", {"class": "VideoOwnerCard-ownerLink"})
        profile_url = "https://www.dailymotion.com" + profile_tag["href"] if profile_tag else "N/A"

        return {
            "url": url,
            "title": title,
            "duration": duration,
            "profile_url": profile_url
        }
    except Exception:
        return {
            "url": url,
            "title": "N/A",
            "duration": "N/A",
            "profile_url": "N/A"
        }

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/scrape")
async def scrape(request: Request, urls: str = Form(...), platform: str = Form(...)):
    url_list = [url.strip() for url in urls.strip().split("\n") if url.strip()]
    results = []

    for url in url_list:
        if platform == "okru":
            result = scrape_okru(url)
        elif platform == "dailymotion":
            result = scrape_dailymotion(url)
        else:
            result = {
                "url": url,
                "title": "Invalid platform",
                "duration": "N/A",
                "profile_url": "N/A"
            }
        results.append(result)

    return {"results": results}
