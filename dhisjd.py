#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeDefault

# ================== ЗАГРУЗКА ТОКЕНА ==================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

# ================== ПУТИ ==================
DB_PATH = Path(os.getenv("DB_PATH", "/var/lib/business_bot/business.db"))
LOG_PATH = Path(os.getenv("LOG_PATH", "/var/log/business_bot/business.log"))

# ================== КЛЮЧЕВЫЕ ФРАЗЫ ==================
TRIGGER_PHRASES = ["фри пак", "#пак", "можно пак", "пак", "free pack", "халява", "выдай пак", "хочу пак"]

RESPONSE_TEXT = (
    "Для получения бесплатного пака нужно написать 25 комментариев по поисковым запросам: "
    "дэтскоэ питаниэ, детски питани и тд..\n\n"
    "Писать комментарии нужно именно так :\n"
    "@tendo52 космическое 🌸\n"
    "@tendo52 чудесное 💘\n"
    "@tendo52 самое свежие 💝\n\n"
    "Также нужно написать 5 ответов под комментариями с упоминанием tendo52 пример: рил выдали, согл и тд..\n\n"
    "После проделанной работы кидаем скриншоты админу @netzy729\n\n"
    "ЕСЛИ Я УВИЖУ НА СКРИНШОТАХ ДРУГИЕ КОММЕНТЫ С УПОМИНАНИЕМ TENDO52 И НА НИХ НЕ БУДЕТ ЛАЙКА И ОТВЕТА, ТО ПАК ВЫ НЕ ПОЛУЧИТЕ❗"
)

# ================== ЛОГИ ==================
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
logger = logging.getLogger("business_pack_bot")

# ================== БД ==================
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS processed (
            user_id INTEGER PRIMARY KEY,
            first_trigger_text TEXT,
            answered_at TEXT,
            business_connection_id TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def already_answered(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed WHERE user_id=?", (user_id,))
    res = c.fetchone() is not None
    conn.close()
    return res

def mark_answered(user_id: int, trigger_text: str, business_connection_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO processed (user_id, first_trigger_text, answered_at, business_connection_id)
        VALUES (?, ?, ?, ?)
    """, (user_id, trigger_text[:100], datetime.utcnow().isoformat(), business_connection_id))
    conn.commit()
    conn.close()

# ================== БОТ ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🤖 Business-бот активирован. Отвечаю на ключевые слова в личных сообщениях.\n"
        "Команды: /reset_me, /stats\n"
        "Триггеры: " + ", ".join(TRIGGER_PHRASES)
    )

@dp.message(Command("reset_me"))
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM processed WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await message.answer("✅ История сброшена")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Только админ")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM processed")
    total = c.fetchone()[0]
    await message.answer(f"📊 Обработано пользователей: {total}")

@dp.message()
async def handle_business_message(message: types.Message):
    # 1. Работаем ТОЛЬКО через Business API (проверяем наличие business_connection_id)
    if not message.business_connection_id:
        logger.debug("Не business-сообщение, игнор")
        return
    
    # 2. Только текст
    if not message.text or message.from_user.is_bot:
        return
    
    user_id = message.from_user.id
    text_lower = message.text.lower().strip()
    
    # 3. Проверка на уже отвеченных
    if already_answered(user_id):
        logger.info(f"Business user {user_id} уже получал ответ")
        return
    
    # 4. Поиск триггера
    triggered = any(phrase in text_lower for phrase in TRIGGER_PHRASES)
    
    if triggered:
        logger.info(f"Business триггер от {user_id}: {message.text[:60]}")
        # Отправляем ответ через бизнес-соединение
        await message.answer(RESPONSE_TEXT)
        mark_answered(user_id, message.text, message.business_connection_id)

async def set_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="reset_me", description="Сбросить блокировку"),
        BotCommand(command="stats", description="Статистика (админ)")
    ], scope=BotCommandScopeDefault())

async def main():
    await set_commands()
    logger.info("Business-бот запущен. Ожидание сообщений через Business API")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())