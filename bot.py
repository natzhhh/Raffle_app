import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
# Import your existing database setup from app.py
from app import db, User, Post, Ticket, app 

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Check if this Telegram user is already in our DB
    with app.app_context():
        user = User.query.filter_by(phone_number=str(message.from_user.id)).first()
        
        if not user:
            await message.answer("Welcome to Harar Raffle! 🎟\nIt looks like you're new. Use /register to join.")
        else:
            await message.answer(f"Welcome back, {user.full_name}! Use /raffles to see active draws.")

@dp.message(Command("raffles"))
async def list_raffles(message: types.Message):
    with app.app_context():
        # Get all active raffles from your existing Post table
        active_raffles = Post.query.filter(Post.winner_id == None).all()
        
        if not active_raffles:
            await message.answer("No active raffles at the moment. Check back later!")
            return

        for raffle in active_raffles:
            text = f"🎁 **{raffle.raffle_name}**\n" \
                   f"💰 Ticket: {raffle.raffle_value} ETB\n" \
                   f"🏆 Prize: {raffle.prize_1} ETB"
            # We can add an 'Enter' button here
            await message.answer(text, parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())