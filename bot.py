import google.generativeai as genai
import telebot
from telebot import types
from config import TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, GEMINI_MODEL, MAX_MEMORY, VED_SYSTEM_PROMPT
import logging
from typing import Dict, List
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
chat_memory: Dict[int, List[Dict]] = {}
states = {}
STAVKI_FILE = 'stavki-china.txt'

def count_tokens(messages: List[Dict]) -> int:
    total = 0
    for msg in messages:
        total += len(msg["content"]) // 4 + 2
    return total

def get_gemini_response(chat_id: int, user_input: str) -> str:
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    # Формируем историю чата в текстовом формате для лучшей интерпретации
    history_text = VED_SYSTEM_PROMPT + "\n\n"
    if chat_id in chat_memory:
        for msg in chat_memory[chat_id]:
            role = "Пользователь" if msg["role"] == "user" else "Бот"
            history_text += f"{role}: {msg['parts'][0]['text']}\n"
    
    # Формируем полный запрос с учетом истории и текущего ввода
    full_prompt = f"{history_text}Пользователь: {user_input}\n\nОтветьте, учитывая контекст предыдущих сообщений и оставаясь в рамках темы ВЭД, сертификации или логистики. Предоставляйте только фактическую информацию без рекомендаций, советов или предложений действий."

    try:
        response = model.generate_content(full_prompt)
        answer = response.text
        
        # Сохраняем сообщение пользователя и ответ бота в историю
        if chat_id not in chat_memory:
            chat_memory[chat_id] = []
        chat_memory[chat_id].append({"role": "user", "parts": [{"text": user_input}]})
        chat_memory[chat_id].append({"role": "model", "parts": [{"text": answer}]})
        
        # Ограничиваем размер истории по MAX_MEMORY
        if len(chat_memory[chat_id]) > MAX_MEMORY:
            chat_memory[chat_id] = chat_memory[chat_id][-MAX_MEMORY:]
        
        logger.info(f"✅ Полный ответ на: {user_input[:50]}")
        return answer
    except Exception as e:
        return f"❌ Ошибка Gemini: {str(e)[:100]}"

def parse_number(text):
    return float(text.replace(',', '.'))

def load_stavki():
    with open(STAVKI_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return float(lines[0].strip()), float(lines[1].strip()), float(lines[2].strip())

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🚚 Расчет логистики")
    btn2 = types.KeyboardButton("🤖 Вопросы ВЭД")
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id,
        "🚚 **СУПЕР-БОТ Логистика + ВЭД**\n\n"
        "• *🚚 Расчет логистики* — Китай-Россия\n"
        "• *🤖 Вопросы ВЭД* — таможня, документы\n\n"
        "**✅ Отвечает на каждый вопрос ПОЛНОСТЬЮ!**",
        parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🚚 Расчет логистики")
def start_calc(message):
    chat_id = message.chat.id
    # Очищаем историю ВЭД при начале расчета логистики
    if chat_id in chat_memory:
        del chat_memory[chat_id]
    states[chat_id] = {'step': 0}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Назад"))
    bot.send_message(chat_id, "📍 *Откуда забирать груз?*", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🚚 Еще расчет")
def restart_calc(message):
    chat_id = message.chat.id
    # Очищаем историю ВЭД при повторном расчете
    if chat_id in chat_memory:
        del chat_memory[chat_id]
    states[chat_id] = {'step': 0}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Назад"))
    bot.send_message(chat_id, "📍 *Откуда забирать груз?*", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🤖 Вопросы ВЭД")
def start_ai(message):
    bot.send_message(message.chat.id,
        "✅ *Я готов ответить на любой вопрос!*\n\n"
        "Задайте вопрос по:\n"
        "• Импорт/экспорт\n"
        "• Таможня, код ТНВЭД\n"
        "• Документы, INCOTERMS\n"
        "• Сертификация продукции\n\n"
        "*Пример:* 'Нужен ли сертификат для текстиля из Китая?'",
        parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.chat.id in states)
def handle_calc(message):
    chat_id = message.chat.id
    if chat_id not in states:
        return
    state = states[chat_id]
    step = state['step']
    
    # Обработка кнопки "Назад"
    if message.text == "Назад":
        if step == 0:
            # Возвращаемся в главное меню и очищаем историю ВЭД
            if chat_id in chat_memory:
                del chat_memory[chat_id]
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add(types.KeyboardButton("🚚 Расчет логистики"), types.KeyboardButton("🤖 Вопросы ВЭД"))
            bot.send_message(chat_id, "↩️ Вернулся в главное меню", reply_markup=markup)
            del states[chat_id]
            return
        elif step == 1:
            state['step'] = 0
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "📍 *Откуда забирать груз?*", reply_markup=markup)
            return
        elif step == 2:
            state['step'] = 1
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "📍 *Куда везти?*", reply_markup=markup)
            return
        elif step == 3:
            state['step'] = 2
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "⚖️ *Вес (кг)?* Примеры: 150, 150,5", reply_markup=markup)
            return
        elif step == 4:
            state['step'] = 3
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "📦 *Объем (м³)?* Примеры: 0,5", reply_markup=markup)
            return
    
    # Обычная обработка шагов
    if step == 0:
        state['from_location'] = message.text
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Назад"))
        bot.send_message(chat_id, "📍 *Куда везти?*", reply_markup=markup)
        state['step'] = 1
    elif step == 1:
        state['to_location'] = message.text
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Назад"))
        bot.send_message(chat_id, "⚖️ *Вес (кг)?* Примеры: 150, 150,5", reply_markup=markup)
        state['step'] = 2
    elif step == 2:
        try:
            state['weight'] = parse_number(message.text)
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "📦 *Объем (м³)?* Примеры: 0,5", reply_markup=markup)
            state['step'] = 3
        except:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "❌ Число! Пример: 150,5", reply_markup=markup)
    elif step == 3:
        try:
            state['volume'] = parse_number(message.text)
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "🔢 *Количество мест?*", reply_markup=markup)
            state['step'] = 4
        except:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "❌ Число! Пример: 0,5", reply_markup=markup)
    elif step == 4:
        try:
            state['places'] = int(parse_number(message.text))
            
            rate_to, rate_from, kg_per_cub = load_stavki()
            effective_vol = max(state['volume'], state['weight'] / kg_per_cub)
            effective_vol = max(effective_vol, 1.0)
            cost_to = effective_vol * rate_to
            cost_from = effective_vol * rate_from
            total_cost = cost_to + cost_from
            
            response = (
                f"🚚 **РАСЧЕТ ЛОГИСТИКИ**\n\n"
                f"📍 {state['from_location']} → {state['to_location']}\n\n"
                f"⚖️ {state['weight']:.1f} кг | 📦 {state['volume']:.2f} м³ | 🔢 {state['places']} мест\n\n"
                f"🛕 *ДО МАНЧЖУРИИ:* {cost_to:.0f} USD\n"
                f"🇨🇳 *ИЗ МАНЧЖУРИИ:* {cost_from:.0f} USD\n\n"
                f"💎 **ИТОГО: {total_cost:.0f} USD**"
            )
            
            bot.send_message(chat_id, response, parse_mode='Markdown')
            del states[chat_id]
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add(types.KeyboardButton("🚚 Еще расчет"), types.KeyboardButton("🤖 Вопросы ВЭД"))
            bot.send_message(chat_id, "Для уточнения напиши @PrologMos", reply_markup=markup)
            
        except:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(chat_id, "❌ Целое число для мест!", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id not in states)
def handle_ai(message):
    chat_id = message.chat.id
    user_text = message.text.strip()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🚚 Расчет логистики"), types.KeyboardButton("🤖 Вопросы ВЭД"))
    
    bot.send_message(chat_id, "🤖 *Готовлю ответ...*", parse_mode='Markdown')
    answer = get_gemini_response(chat_id, user_text)
    bot.send_message(chat_id, answer, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['test'])
def test_api(message):
    bot.send_message(message.chat.id, "🧪 Тестирую...")
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content("Привет!")
        bot.send_message(message.chat.id, f"✅ **ИИ РАБОТАЕТ!**\n{response.text}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {str(e)}")

@bot.message_handler(commands=['clear'])
def clear(message):
    chat_id = message.chat.id
    # Очищаем историю чата и состояние
    if chat_id in chat_memory:
        del chat_memory[chat_id]
    if chat_id in states:
        del states[chat_id]
    bot.send_message(chat_id, "🧹 **Чат очищен!**")

@bot.message_handler(commands=['status'])
def status(message):
    bot.send_message(message.chat.id, "📊 **✅ Полные ответы на каждый вопрос!**")

if __name__ == "__main__":
    with open(STAVKI_FILE, 'w') as f:
        f.write("50\n110\n300")
    
    print("🚚🤖 СУПЕР-BOT ЗАПУЩЕН! ✅ ПОЛНЫЕ ОТВЕТЫ!")
    print("• /start — меню")
    print("• 🚚 Расчет логистики")
    print("• 🤖 Вопросы ВЭД")
    print("• /test — проверить ИИ")
    
    bot.polling(none_stop=True)

