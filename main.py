from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from bs4 import BeautifulSoup
import httpx
import asyncio

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/scrape")
async def scrape_api(
    request: Request,
    url: str = Form(...),
    platform: str = Form(default="okru")
):
    if platform == "okru":
        return await scrape_okru_url(url)
    elif platform == "dailymotion":
        return await scrape_dailymotion_url(url)
    else:
        return JSONResponse(content={"error": "Unsupported platform"}, status_code=400)


@app.post("/api/scrape-multiple")
async def scrape_multiple(request: Request):
    form = await request.form()
    urls = form.get("urls", "").strip().splitlines()
    platform = form.get("platform", "okru")

    tasks = []

    for url in urls:
        url = url.strip()
        if url:
            if platform == "okru":
                tasks.append(scrape_okru_url(url))
            elif platform == "dailymotion":
                tasks.append(scrape_dailymotion_url(url))

    results = await asyncio.gather(*tasks)
    return JSONResponse(content={"results": results})


# -----------------------
# OK.ru Scraper Function
# -----------------------
async def scrape_okru_url(url: str):
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

            title = soup.select_one("meta[property='og:title']")
            title = title["content"].strip() if title else "N/A"

            duration = soup.select_one("div.media-status-item_duration")
            duration = duration.text.strip() if duration else "N/A"

            profile_tag = soup.select_one("div.ucard-mini_cnt > a")
            profile_url = "https://ok.ru" + profile_tag["href"] if profile_tag else "N/A"

            return {
                "url": url,
                "title": title,
                "duration": duration,
                "profile_url": profile_url,
                "platform": "okru"
            }

    except Exception as e:
        return {"url": url, "error": str(e), "platform": "okru"}


# ----------------------------
# Dailymotion Scraper Function
# ----------------------------
async def scrape_dailymotion_url(url: str):
    try:
        video_id = url.strip().split("/")[-1].split("_")[0]
        api_url = f"https://www.dailymotion.com/player/metadata/video/{video_id}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(api_url)
            data = response.json()

            return {
                "url": url,
                "title": data.get("title", "N/A"),
                "duration": f"{int(data.get('duration', 0))}s",
                "profile_url": f"https://www.dailymotion.com/{data['owner']['username']}" if data.get("owner") else "N/A",
                "platform": "dailymotion"
            }

    except Exception as e:
        return {"url": url, "error": str(e), "platform": "dailymotion"}
