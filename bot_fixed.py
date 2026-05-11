import os
import random
import asyncio
import json
from aiohttp import web
from google import genai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

# ==================== SOZLAMALAR ====================
TELEGRAM_TOKEN = "8792408068:AAHfw6zzx5b5Cj6UQ5JWZ-7E9hjbqq1DFi4"
GEMINI_API_KEY = "AIzaSyA10DJbzIEr4F8Ba2ucZkQGphA8XKH0hnI"

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# User ma'lumotlarini saqlash
user_data = {}

# ==================== DARAJANI ANIQLASH SAVOLLARI ====================
LEVEL_QUESTIONS = [
    {
        "question": "❓ Savol 1/5\n\nWhat is the correct sentence?\n\nA) I am go to school\nB) I go to school\nC) I going to school\nD) I goes to school",
        "answer": "B",
    },
    {
        "question": "❓ Savol 2/5\n\nChoose the correct word:\n'She ___ to music every day.'\n\nA) listen\nB) listening\nC) listens\nD) listened",
        "answer": "C",
    },
    {
        "question": "❓ Savol 3/5\n\nWhat does 'enormous' mean?\n\nA) Kichik\nB) Juda katta\nC) Chiroyli\nD) Tez",
        "answer": "B",
    },
    {
        "question": "❓ Savol 4/5\n\nChoose the correct tense:\n'By next year, she ___ in London for 5 years.'\n\nA) will live\nB) has lived\nC) will have lived\nD) is living",
        "answer": "C",
    },
    {
        "question": "❓ Savol 5/5\n\nWhat is the synonym of 'melancholy'?\n\nA) Happy\nB) Angry\nC) Sad\nD) Excited",
        "answer": "C",
    }
]

# ==================== O'YINLAR ====================
WORD_GAMES = {
    "beginner": [
        {"word": "apple", "hint": "🍎 Bu meva", "translation": "olma"},
        {"word": "book", "hint": "📚 O'qish uchun ishlatiladi", "translation": "kitob"},
        {"word": "water", "hint": "💧 Ichish uchun", "translation": "suv"},
        {"word": "house", "hint": "🏠 Yashaydigan joy", "translation": "uy"},
        {"word": "cat", "hint": "🐱 Uy hayvoni", "translation": "mushuk"},
        {"word": "sun", "hint": "☀️ Osmondagi yorug' narsa", "translation": "quyosh"},
        {"word": "food", "hint": "🍽️ Yeyiladigan narsa", "translation": "taom"},
        {"word": "friend", "hint": "🤝 Yaqin inson", "translation": "do'st"},
    ],
    "intermediate": [
        {"word": "knowledge", "hint": "💡 Bilim va tajriba", "translation": "bilim"},
        {"word": "adventure", "hint": "🗺️ Qiziqarli sayohat yoki tajriba", "translation": "sarguzasht"},
        {"word": "confident", "hint": "💪 O'ziga ishongan", "translation": "ishonchli"},
        {"word": "beautiful", "hint": "✨ Ko'rinishi yaxshi", "translation": "chiroyli"},
        {"word": "freedom", "hint": "🕊️ Erkin bo'lish holati", "translation": "erkinlik"},
        {"word": "journey", "hint": "🚂 Uzoq sayohat", "translation": "safar"},
        {"word": "grateful", "hint": "🙏 Minnatdor bo'lgan", "translation": "minnatdor"},
        {"word": "success", "hint": "🏆 Maqsadga erishish", "translation": "muvaffaqiyat"},
    ],
    "advanced": [
        {"word": "ephemeral", "hint": "⏳ Juda qisqa vaqt davom etadigan", "translation": "o'tkinchi"},
        {"word": "resilient", "hint": "🌊 Qiyinchiliklardan tez tiklanadigan", "translation": "bardoshli"},
        {"word": "eloquent", "hint": "🗣️ Juda yaxshi va ta'sirli gapiruvchi", "translation": "notiq"},
        {"word": "ambiguous", "hint": "🤔 Ikki ma'noli, noaniq", "translation": "noaniq"},
        {"word": "meticulous", "hint": "🔍 Har bir detalga e'tibor beradigan", "translation": "puxta"},
        {"word": "serendipity", "hint": "🍀 Tasodifan yoqimli narsa topish", "translation": "baxtli tasodif"},
        {"word": "tenacious", "hint": "🦾 O'z maqsadidan qaytmaydigan", "translation": "qat'iyatli"},
        {"word": "paradox", "hint": "♾️ O'ziga zid ko'rinadigan haqiqat", "translation": "paradoks"},
    ]
}

# ==================== ASOSIY FUNKSIYALAR ====================

def get_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "level": None,
            "correct_answers": 0,
            "level_test_answers": [],
            "current_question": 0,
            "conversation_history": [],
            "current_game": None,
            "word_queue": [],      # Navbat (bir xil so'z qayta chiqmasin)
            "words_played": 0,     # Jami o'ynalgan so'zlar
        }
    return user_data[user_id]

def determine_level(correct_count):
    if correct_count <= 1:
        return "beginner"
    elif correct_count <= 3:
        return "intermediate"
    else:
        return "advanced"

def get_level_emoji(level):
    emojis = {"beginner": "🌱", "intermediate": "🌿", "advanced": "🌳"}
    return emojis.get(level, "📚")

def get_main_keyboard(level=None):
    buttons = [
        [KeyboardButton("💬 AI bilan suhbat"), KeyboardButton("🎮 O'yin o'ynash")],
        [KeyboardButton("📖 So'z o'rganish"), KeyboardButton("✍️ Grammatika")],
        [KeyboardButton("📊 Mening darajam"), KeyboardButton("🔄 Darajani qayta aniqlash")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_next_word(user):
    """Navbatdagi so'zni oladi. Navbat tugasa — qayta aralashtiradi."""
    level = user["level"]
    words = WORD_GAMES[level]

    if not user["word_queue"]:
        shuffled = words.copy()
        random.shuffle(shuffled)
        user["word_queue"] = shuffled

    return user["word_queue"].pop(0)

def game_keyboard():
    """O'yin davomidagi inline tugmalar"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💡 Ishora", callback_data="game_hint"),
            InlineKeyboardButton("➡️ Keyingi so'z", callback_data="game_next"),
        ],
        [InlineKeyboardButton("🛑 To'xtatish", callback_data="game_stop")]
    ])

def after_round_keyboard():
    """To'g'ri topgandan / urinish tugaganidan keyin"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Keyingi so'z", callback_data="game_next")],
        [InlineKeyboardButton("🛑 To'xtatish", callback_data="game_stop")]
    ])

# ==================== GEMINI AI ====================

async def ask_gemini(user_id, user_message, system_prompt=None):
    user = get_user(user_id)
    level = user.get("level", "beginner")

    if system_prompt is None:
        system_prompt = f"""Sen ingliz tili o'qituvchisisisan. Foydalanuvchi darajasi: {level}.
Qoidalar:
- O'zbek tilida gaplashsa, inglizcha o'rgatib javob ber
- Qisqa va tushunarli bo'l (3-4 jumla)
- Xatolarni yaxshi niyat bilan tuzat
- Har javobda bitta yangi so'z yoki qoida o'rgat
- Javob oxirida bitta savol ber
- beginner=Present Simple, intermediate=Past/Future, advanced=idiomalar"""

    history = user["conversation_history"][-6:]
    history_text = ""
    for msg in history:
        role = "Foydalanuvchi" if msg["role"] == "user" else "O'qituvchi"
        history_text += f"{role}: {msg['content']}\n"

    full_prompt = f"{system_prompt}\n\n{history_text}Foydalanuvchi: {user_message}\nO'qituvchi:"

    def call_api():
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt
        )
        return response.text

    result = await asyncio.to_thread(call_api)

    user["conversation_history"].append({"role": "user", "content": user_message})
    user["conversation_history"].append({"role": "assistant", "content": result})

    return result

# ==================== WEB SERVER (GitHub Pages uchun) ====================

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

async def chat_endpoint(request):
    try:
        data = await request.json()
        user_message = data.get("message", "")

        if not user_message:
            return web.Response(
                text=json.dumps({"reply": "Xabar bo'sh!"}),
                content_type="application/json",
                headers=CORS_HEADERS
            )

        def call_gemini():
            system = """Sen ingliz tili o'qituvchisisisan. O'zbek tilida javob ber.
- Qisqa va tushunarli (3-4 jumla)
- Ingliz so'zlari va grammatikasini o'rgat
- Har javobda bitta yangi so'z yoki qoida
- Javob oxirida bitta savol ber"""
            full_prompt = f"{system}\n\nFoydalanuvchi: {user_message}\nO'qituvchi:"
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt
            )
            return response.text

        reply = await asyncio.to_thread(call_gemini)
        return web.Response(
            text=json.dumps({"reply": reply}),
            content_type="application/json",
            headers=CORS_HEADERS
        )
    except Exception as e:
        return web.Response(
            text=json.dumps({"reply": f"Xatolik: {str(e)}"}),
            content_type="application/json",
            headers=CORS_HEADERS
        )

async def options_endpoint(request):
    return web.Response(headers=CORS_HEADERS)

async def start_web_server():
    app_web = web.Application()
    app_web.router.add_post("/chat", chat_endpoint)
    app_web.router.add_route("OPTIONS", "/chat", options_endpoint)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("✅ Web server: http://0.0.0.0:8080/chat")

# ==================== KOMANDALAR ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    user["current_question"] = 0
    user["level_test_answers"] = []
    user["current_game"] = None
    context.user_data["mode"] = "menu"

    name = update.effective_user.first_name
    welcome_text = f"""🎉 Salom, {name}! Ingliz tili o'rganish botiga xush kelibsiz!

🤖 Men sizga ingliz tilini o'rganishda yordam beraman:
• 💬 AI bilan inglizcha suhbat
• 🎮 Qiziqarli o'yinlar
• 📖 Yangi so'zlar o'rganish
• ✍️ Grammatika mashqlari

Avval darajangizni aniqlab olaylik!
5 ta savol bo'ladi va bu 2-3 daqiqa vaqt oladi.

Tayyor bo'lsangiz, bosing! 👇"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Boshlash!", callback_data="start_test")]
    ])
    await update.message.reply_text(welcome_text, reply_markup=keyboard)

async def start_level_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    user["current_question"] = 0
    user["level_test_answers"] = []
    await send_level_question(query.message, user_id, edit=True)

async def send_level_question(message, user_id, edit=False):
    user = get_user(user_id)
    q_idx = user["current_question"]

    if q_idx >= len(LEVEL_QUESTIONS):
        await finish_level_test(message, user_id)
        return

    question = LEVEL_QUESTIONS[q_idx]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("A", callback_data="answer_A"),
         InlineKeyboardButton("B", callback_data="answer_B")],
        [InlineKeyboardButton("C", callback_data="answer_C"),
         InlineKeyboardButton("D", callback_data="answer_D")]
    ])
    text = f"📝 Daraja testi\n\n{question['question']}"

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.reply_text(text, reply_markup=keyboard)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)

    if not query.data.startswith("answer_"):
        return

    answer = query.data.split("_")[1]
    q_idx = user["current_question"]
    if q_idx >= len(LEVEL_QUESTIONS):
        return

    correct = LEVEL_QUESTIONS[q_idx]["answer"]
    is_correct = answer == correct
    user["level_test_answers"].append(is_correct)
    user["current_question"] += 1

    feedback = "✅ To'g'ri!" if is_correct else f"❌ Noto'g'ri. To'g'ri javob: {correct}"
    await query.message.edit_text(f"{feedback}\n\nKeyingi savol yuklanmoqda...")
    await send_level_question(query.message, user_id, edit=True)

async def finish_level_test(message, user_id):
    user = get_user(user_id)
    correct_count = sum(user["level_test_answers"])
    level = determine_level(correct_count)
    user["level"] = level
    emoji = get_level_emoji(level)
    level_names = {"beginner": "Boshlang'ich", "intermediate": "O'rta", "advanced": "Yuqori"}

    result_text = f"""🎊 Test tugadi!

📊 Natija: {correct_count}/5 to'g'ri javob

{emoji} Sizning darajangiz: {level_names[level]}

{'🌱 Asosiy so\'z va grammatikadan boshlaymiz!' if level == 'beginner' else '🌿 Qiziqarli mavzularni o\'rganamiz!' if level == 'intermediate' else '🌳 Murakkab mavzular va idiomalar bilan ishlaylik!'}

Endi o'rganishni boshlashingiz mumkin! 👇"""

    await message.edit_text(result_text, reply_markup=None)
    await message.reply_text(
        "📚 Asosiy menyu - kerakli bo'limni tanlang:",
        reply_markup=get_main_keyboard(level)
    )

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user["level"]:
        await update.message.reply_text("⚠️ Avval /start buyrug'i bilan darajangizni aniqlang!")
        return

    level = user["level"]
    level_names = {"beginner": "Boshlang'ich", "intermediate": "O'rta", "advanced": "Yuqori"}
    emoji = get_level_emoji(level)

    context.user_data["mode"] = "conversation"
    await update.message.reply_text(
        f"{emoji} AI o'qituvchi bilan suhbat rejimi!\n\n"
        f"Daraja: {level_names[level]}\n\n"
        f"Ingliz yoki o'zbek tilida yozing — xatolaringizni tuzataman, yangi so'zlar o'rgataman!\n\n"
        f"Boshlang! ✍️\n(Orqaga: /menu)"
    )

# ==================== O'YIN ====================

async def _send_game_word(message, user, context, edit_msg=None):
    """Yangi so'zni yuboradi (yangi xabar yoki edit)"""
    word_data = get_next_word(user)
    user["words_played"] = user.get("words_played", 0) + 1
    user["current_game"] = {
        "word": word_data["word"],
        "translation": word_data["translation"],
        "hint": word_data["hint"],
        "attempts": 0
    }
    context.user_data["mode"] = "game"

    text = (
        f"🎮 SO'Z TOPISH O'YINI!\n\n"
        f"{word_data['hint']}\n\n"
        f"Bu so'zni ingliz tilida toping!\n"
        f"O'zbek tarjimasi: {word_data['translation']}\n\n"
        f"So'zni yozing... 💭"
    )

    if edit_msg:
        await edit_msg.edit_text(text, reply_markup=game_keyboard())
    else:
        await message.reply_text(text, reply_markup=game_keyboard())

async def start_word_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user["level"]:
        await update.message.reply_text("⚠️ Avval /start buyrug'i bilan darajangizni aniqlang!")
        return

    await _send_game_word(update.message, user, context)

async def handle_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """💡 Ishora | ➡️ Keyingi | 🛑 To'xtatish"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user = get_user(user_id)

    if query.data == "game_hint":
        game = user.get("current_game")
        if not game:
            await query.answer("O'yin topilmadi!", show_alert=True)
            return
        word = game["word"]
        if len(word) <= 2:
            hint_str = word[0] + "_"
        else:
            hint_str = word[0] + " _ " * (len(word) - 2) + word[-1]
        await query.answer(f"💡 {hint_str}  ({len(word)} harf)", show_alert=True)

    elif query.data == "game_next":
        await _send_game_word(None, user, context, edit_msg=query.message)

    elif query.data == "game_stop":
        user["current_game"] = None
        context.user_data["mode"] = "menu"
        score = user.get("correct_answers", 0)
        played = user.get("words_played", 0)
        await query.message.edit_text(
            f"🛑 O'yin to'xtatildi!\n\n"
            f"📊 Sizning natijangiz:\n"
            f"✅ To'g'ri topilgan so'zlar: {score}\n"
            f"🎮 Jami o'ynalgan: {played}\n\n"
            f"Davom etish uchun 🎮 O'yin o'ynash tugmasini bosing!",
            reply_markup=None
        )

async def give_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    game = user.get("current_game")
    if not game:
        await update.message.reply_text("⚠️ Hozir o'yin yo'q. 🎮 O'yin o'ynash tugmasini bosing!")
        return
    word = game["word"]
    if len(word) == 1:
        hint_word = word
    elif len(word) == 2:
        hint_word = word[0] + "_"
    else:
        hint_word = f"{word[0]}{'_ ' * (len(word) - 2)}{word[-1]}"
    await update.message.reply_text(f"💡 Ishora: {hint_word}\n({len(word)} harf)")

async def vocabulary_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user["level"]:
        await update.message.reply_text("⚠️ Avval /start buyrug'i bilan darajangizni aniqlang!")
        return
    await update.message.reply_text("📖 So'zlar yuklanmoqda...")
    try:
        prompt = f"Daraja {user['level']} uchun 5 ta muhim ingliz so'zini o'rgatgin. Har birini o'zbek tarjimasi va misol gap bilan. Emoji ishlatib chiroyli qil."
        system = "Sen ingliz tili lug'at o'qituvchisisisan. So'z, tarjima va misol gap ber. O'zbek tilida tushuntir."
        response = await ask_gemini(user_id, prompt, system_prompt=system)
        await update.message.reply_text(response)
    except Exception:
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.\n/menu")

async def grammar_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user["level"]:
        await update.message.reply_text("⚠️ Avval /start buyrug'i bilan darajangizni aniqlang!")
        return
    level_topics = {
        "beginner": "Present Simple grammatikasi - qoidalar va misollar",
        "intermediate": "Past Perfect vs Past Simple - farqi va ishlatilishi",
        "advanced": "Subjunctive Mood - murakkab grammatika qoidasi"
    }
    await update.message.reply_text("✍️ Grammatika dars yuklanmoqda...")
    try:
        topic = level_topics[user["level"]]
        prompt = f"Bu mavzuni o'rgatgin: {topic}. Qisqa, tushunarli va misollar bilan."
        system = "Sen grammatika o'qituvchisisisan. O'zbek tilida tushuntir, inglizcha misollar ber."
        response = await ask_gemini(user_id, prompt, system_prompt=system)
        await update.message.reply_text(response)
    except Exception:
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.\n/menu")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user["level"]:
        await update.message.reply_text("⚠️ Avval /start buyrug'i bilan darajangizni aniqlang!")
        return
    level_names = {"beginner": "Boshlang'ich 🌱", "intermediate": "O'rta 🌿", "advanced": "Yuqori 🌳"}
    test_answers = user.get("level_test_answers", [])
    text = (
        f"📊 SIZNING STATISTIKANGIZ\n\n"
        f"👤 Daraja: {level_names[user['level']]}\n"
        f"💬 Suhbat xabarlari: {len(user['conversation_history']) // 2}\n"
        f"✅ Test natijalari: {sum(test_answers)} / {len(test_answers)}\n"
        f"🎮 To'g'ri topilgan so'zlar: {user.get('correct_answers', 0)}\n"
        f"🃏 Jami o'ynalgan so'zlar: {user.get('words_played', 0)}\n\n"
        f"{'🔥 Zo\'r ketayapsiz! Davom eting!' if len(user['conversation_history']) > 10 else '💪 Yangi boshlagan! Har kuni mashq qiling!'}"
    )
    await update.message.reply_text(text)

async def reset_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ha, qayta test qilaman", callback_data="start_test")],
        [InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data="cancel")]
    ])
    await update.message.reply_text("🔄 Darajangizni qayta aniqlashni xohlaysizmi?", reply_markup=keyboard)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    context.user_data["mode"] = "menu"
    user["current_game"] = None
    await update.message.reply_text("📚 Asosiy menyu:", reply_markup=get_main_keyboard(user.get("level")))

# ==================== XABAR HANDLER ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    text = update.message.text
    mode = context.user_data.get("mode", "menu")

    # Menyu tugmalari
    if text == "💬 AI bilan suhbat":
        await start_conversation(update, context)
        return
    elif text == "🎮 O'yin o'ynash":
        await start_word_game(update, context)
        return
    elif text == "📖 So'z o'rganish":
        await vocabulary_lesson(update, context)
        return
    elif text == "✍️ Grammatika":
        await grammar_lesson(update, context)
        return
    elif text == "📊 Mening darajam":
        await show_stats(update, context)
        return
    elif text == "🔄 Darajani qayta aniqlash":
        await reset_test(update, context)
        return

    # O'yin rejimi — foydalanuvchi javob yozdi
    if mode == "game" and user.get("current_game"):
        game = user["current_game"]
        game["attempts"] += 1

        if text.lower().strip() == game["word"].lower():
            user["correct_answers"] = user.get("correct_answers", 0) + 1
            user["current_game"] = None
            await update.message.reply_text(
                f"🎉 BARAKALLA! To'g'ri!\n\n"
                f"✅ So'z: {game['word']}\n"
                f"📝 Tarjima: {game['translation']}\n\n"
                f"Nima qilasiz?",
                reply_markup=after_round_keyboard()
            )
        else:
            hints_left = 3 - game["attempts"]
            if hints_left <= 0:
                user["current_game"] = None
                await update.message.reply_text(
                    f"❌ Urinishlar tugadi!\n\n"
                    f"💡 Javob: {game['word']} ({game['translation']})\n\n"
                    f"Nima qilasiz?",
                    reply_markup=after_round_keyboard()
                )
            else:
                await update.message.reply_text(
                    f"❌ Noto'g'ri! Yana {hints_left} urinish qoldi.\n"
                    f"💭 Qayta urinib ko'ring...",
                    reply_markup=game_keyboard()
                )
        return

    # AI suhbat rejimi
    if mode == "conversation" or (user.get("level") and mode != "game"):
        if not user.get("level"):
            await update.message.reply_text("⚠️ Avval /start buyrug'i bilan darajangizni aniqlang!")
            return
        await update.message.chat.send_action("typing")
        try:
            response = await ask_gemini(user_id, text)
            await update.message.reply_text(response)
        except Exception:
            await update.message.reply_text("⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.\n/menu - Asosiy menyu")
    else:
        await update.message.reply_text("👇 Quyidagi tugmalardan birini tanlang:", reply_markup=get_main_keyboard(user.get("level")))

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("✅ Bekor qilindi.")

# ==================== BOTNI ISHGA TUSHIRISH ====================

async def main():
    print("🤖 English Learning Bot ishga tushmoqda...")

    await start_web_server()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("hint", give_hint))
    app.add_handler(CommandHandler("next", start_word_game))
    app.add_handler(CommandHandler("stats", show_stats))

    app.add_handler(CallbackQueryHandler(start_level_test, pattern="^start_test$"))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern="^answer_"))
    app.add_handler(CallbackQueryHandler(handle_game_callback, pattern="^game_"))
    app.add_handler(CallbackQueryHandler(handle_cancel, pattern="^cancel$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot tayyor! Telegram'da /start bosing.")
    print("✅ Web API: http://0.0.0.0:8080/chat")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
