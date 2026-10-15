import asyncio
import logging
import base64
import json
import re
from io import BytesIO
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

PLATE_REGEX = re.compile(
    r'^[АВЕКМНОРСТУХABEKMHOPCTYX]\d{3}[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{2,3}$',
    re.IGNORECASE
)

SYSTEM_PROMPT = """
Ты — эксперт по автомобилям и российскому рынку (Auto.ru, Avito, Drom).

По фото автомобиля определи:
- Марку (brand) — на английском
- Модель (model) — на английском
- Примерный диапазон года выпуска (year_from и year_to)
- Тип кузова
- Примерное состояние
- Примерный диапазон рыночной цены в России в рублях

Ответь СТРОГО в формате JSON:

{
  "brand": "Toyota",
  "model": "Camry",
  "year_from": 2018,
  "year_to": 2020,
  "body": "седан",
  "condition": "хорошее",
  "price_from": 1800000,
  "price_to": 2300000,
  "comment": "Краткий комментарий"
}
"""

def slugify(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        "лада": "lada", "ваз": "lada",
        "mercedes-benz": "mercedes", "mercedes benz": "mercedes",
        "bmw": "bmw", "volkswagen": "volkswagen", "vw": "volkswagen",
    }
    for rus, eng in replacements.items():
        if rus in text:
            text = text.replace(rus, eng)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text

def make_search_links(brand: str, model: str, year_from=None, year_to=None) -> dict:
    brand_slug = slugify(brand)
    model_slug = slugify(model)

    autoru = f"https://auto.ru/cars/{brand_slug}/{model_slug}/all/"
    if year_from and year_to:
        autoru += f"?year_from={year_from}&year_to={year_to}"

    query = f"{brand} {model}"
    if year_from and year_to:
        query += f" {year_from}-{year_to}"
    avito = f"https://www.avito.ru/all/avtomobili?q={quote(query)}"

    drom = f"https://auto.drom.ru/{brand_slug}/{model_slug}/"
    if year_from and year_to:
        drom += f"?minyear={year_from}&maxyear={year_to}"

    return {"autoru": autoru, "avito": avito, "drom": drom}

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! 👋\n\n"
        "Пришли фото автомобиля или госномер (например А123ВС777).",
        parse_mode="HTML"
    )

@dp.message(F.text)
async def handle_text(message: Message):
    text = message.text.strip().replace(" ", "").upper()
    if PLATE_REGEX.match(text):
        await message.answer(
            f"✅ Госномер принят: <b>{text}</b>\n\nТеперь пришли фото автомобиля.",
            parse_mode="HTML"
        )
    else:
        await message.answer("Пришли фото автомобиля или госномер.")

@dp.message(F.photo)
async def handle_photo(message: Message):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)

    buffered = BytesIO()
    buffered.write(photo_bytes.read())
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    status = await message.answer("Анализирую фото... 🔍")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Определи автомобиль на фото:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]
                }
            ],
            max_tokens=600,
            temperature=0.2
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)

        brand = data.get("brand", "Неизвестно")
        model = data.get("model", "Неизвестно")
        year_from = data.get("year_from")
        year_to = data.get("year_to")
        body = data.get("body", "—")
        condition = data.get("condition", "—")
        price_from = data.get("price_from", 0)
        price_to = data.get("price_to", 0)
        comment = data.get("comment", "")

        links = make_search_links(brand, model, year_from, year_to)
        year_str = f"{year_from}–{year_to}" if year_from and year_to else "не определён"

        text = (
            f"🚗 <b>{brand} {model}</b>\n"
            f"📅 Год: {year_str}\n"
            f"🚙 Кузов: {body}\n"
            f"🔧 Состояние: {condition}\n\n"
            f"💰 <b>Примерная стоимость:</b>\n"
            f"от <b>{price_from:,} ₽</b> до <b>{price_to:,} ₽</b>\n\n"
            f"{comment}\n\n"
            f"🔗 <b>Объявления:</b>\n"
            f"• <a href=\"{links['autoru']}\">Auto.ru</a>\n"
            f"• <a href=\"{links['avito']}\">Avito</a>\n"
            f"• <a href=\"{links['drom']}\">Drom</a>"
        )

        await status.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logging.exception(e)
        await status.edit_text("Ошибка при анализе. Попробуй другое фото.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
