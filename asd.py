from config import token
from typing import List
from aiogram import types, executor, Bot, Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.storage import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import sqlite3

bot = Bot(token)
dp = Dispatcher(bot, storage=MemoryStorage())
database = sqlite3.connect("bot.db")
cursor = database.cursor()

"""cursor.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, numb TEXT)')
cursor.execute('CREATE TABLE IF NOT EXISTS gifts(id INTEGER PRIMARY KEY, text TEXT, url TEXT, user_id INTEGER,'
               ' FOREIGN KEY (user_id) REFERENCES users(id))')
database.commit()"""


def add_user(message: types.Message):
    user_id = message.chat.id
    cursor.execute("SELECT id FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    if user is None:
        cursor.execute("INSERT INTO users(id, name, numb) VALUES(?,?,?)",(user_id,"name","numb"))
        database.commit()


def add_user_name(message):
    cursor.execute("UPDATE users SET name=? WHERE id=?", (message.text, message.chat.id))
    database.commit()


def add_user_numb(message):
    phone_number = message.text
    if phone_number.startswith("+38"):
        phone_number = phone_number[3:]  # Видаляємо "+38" з початку номера
    cursor.execute("UPDATE users SET numb=? WHERE id=?", (phone_number, message.chat.id))
    database.commit()


def get_gifts(user_id: int) -> List[str]:
    cursor.execute("SELECT id, text, url FROM gifts WHERE user_id=?", (user_id,))
    gifts = cursor.fetchall()
    gift_list = []
    for gift in gifts:
        gift_id, gift_text, gift_url = gift
        gift_str = f"ID: {gift_id}, Текст: {gift_text}"
        if gift_url:
            gift_str += f", URL: {gift_url}"
        gift_list.append(gift_str)
    return gift_list


def get_gifts_by_phone(phone_number: str) -> List[str]:
    if phone_number.startswith("+38"):
        phone_number = phone_number[3:]
    cursor.execute("SELECT id FROM users WHERE numb=?", (phone_number,))
    user = cursor.fetchone()
    if user is None:
        return []
    else:
        user_id = user[0]
        cursor.execute("SELECT id, text, url FROM gifts WHERE user_id=?", (user_id,))
        gifts = cursor.fetchall()
        gift_list = []
        for gift in gifts:
            gift_id, gift_text, gift_url = gift
            gift_str = f"ID: {gift_id}, Текст: {gift_text}"
            if gift_url:
                gift_str += f", URL: {gift_url}"
            gift_list.append(gift_str)
        return gift_list


async def get_phone_number(message: types.Message, state=FSMContext):
    await bot.send_message(message.chat.id, "Введіть номер телефону користувача:")
    await User.get_phone_number.set()


def delete_gift(gift_id: int):
    cursor.execute("DELETE FROM gifts WHERE id=?", (gift_id,))
    database.commit()


def edit_gift(gift_id: int, new_text: str, new_url: str = None):
    cursor.execute("UPDATE gifts SET text=?, url=? WHERE id=?", (new_text, new_url, gift_id))
    database.commit()


class User(StatesGroup):
    get_phone_number = State()
    delete_gift = State()
    edit_gift_url_input = State()
    edit_gift = State()
    edit_gift_text = State()
    edit_gift_url = State()
    name = State()
    numb = State()
    add_gift_text = State()
    add_gift_url = State()
    add_gift_url_input = State()
    main_menu = State()
    confirm_gifts_by_phone = State()


@dp.message_handler(commands=['skip'], state='*')
async def skip_handler(message: types.Message, state=FSMContext):
    await state.finish()
    await User.main_menu.set()
    await start_message(message)


@dp.message_handler(state=User.main_menu)
async def main_menu_handler(message: types.Message):
    chat_id = message.chat.id
    if message.text == '/add_gift':
        await add_gift_handler(message)
    elif message.text == '/gifts':
        await show_gifts(message)
    elif message.text == '/gifts_by_phone':
        await handle_gifts_by_phone(message)
    elif message.text == '/edit_gift':
        await edit_gift_handler(message)
    else:
        await bot.send_message(chat_id, "Невідома команда. Виберіть доступну команду або введіть текст повідомлення.")


@dp.message_handler(state=User.name)
async def add_name_(message: types.Message, state=FSMContext):
    chat_id = message.chat.id
    await state.finish()
    add_user_name(message)
    await bot.send_message(chat_id, "Введіть ваш номер телефону: ")
    await User.numb.set()


@dp.message_handler(state=User.numb)
async def add_numb_(message: types.Message, state=FSMContext):
    chat_id = message.chat.id
    await state.finish()
    add_user_numb(message)
    await bot.send_message(chat_id, "Реєстрацію завершено! Для перегляду команд скористайтеся меню")


@dp.message_handler(commands=['start'])
async def start_message(message: types.Message):
    chat_id = message.chat.id
    cursor.execute("SELECT id FROM users WHERE id=?", (chat_id,))
    user = cursor.fetchone()
    if user is None:
        add_user(message)
        await bot.send_message(chat_id, f"Привіт {message.chat.first_name},"
                                        f" я бот, створений для роботи із списком побажань щодо подарунків! !\n "
                                        f"Для продовження введи своє ім'я: ")
        await User.name.set()
    else:
        await bot.send_message(chat_id, f"Привіт {message.chat.first_name}, що бажаєш зробити?")


@dp.message_handler(state=User.add_gift_text)
async def add_gift_text(message: types.Message, state=FSMContext):
    await state.update_data(gift_text=message.text)
    await bot.send_message(message.chat.id, "Ви хочете додати URL-адресу до подарунку? (так/ні)")
    await User.add_gift_url.set()


@dp.message_handler(state=User.add_gift_url)
async def add_gift_url(message: types.Message, state=FSMContext):
    user_data = await state.get_data()
    gift_text = user_data.get("gift_text")
    if message.text.lower() == "так":
        await bot.send_message(message.chat.id, "Введіть URL-адресу подарунку:")
        await state.update_data(gift_text=gift_text, gift_url=True)
        await User.add_gift_url_input.set()
    elif message.text.lower() == "ні":
        user_id = message.chat.id
        cursor.execute("SELECT id FROM users WHERE id=?", (user_id,))
        user = cursor.fetchone()
        if user is None:
            await bot.send_message(user_id, "Спочатку потрібно зареєструватися!")
            return
        else:
            cursor.execute("INSERT INTO gifts(text, url, user_id) VALUES (?,?,?)", (gift_text, None, user_id))
            database.commit()
            await bot.send_message(user_id, "Подарунок додано до списку!")
            await state.finish()
    else:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        yes_btn = KeyboardButton('Так')
        no_btn = KeyboardButton('Ні')
        keyboard.add(yes_btn, no_btn)
        await bot.send_message(message.chat.id,
                               "Невідповідна відповідь. Ви хочете додати URL-адресу до подарунку?",
                               reply_markup=keyboard)


@dp.message_handler(state=User.add_gift_url_input)
async def add_gift_url_input(message: types.Message, state=FSMContext):
    user_data = await state.get_data()
    gift_text = user_data.get("gift_text")
    user_id = message.chat.id
    cursor.execute("SELECT id FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    if user is None:
        await bot.send_message(user_id, "Спочатку потрібно зареєструватися!")
        return
    else:
        cursor.execute("INSERT INTO gifts(text, url, user_id) VALUES (?,?,?)", (gift_text, message.text, user_id))
        database.commit()
        await bot.send_message(user_id, "Подарунок додано до списку!")
        await state.finish()


@dp.message_handler(commands=['add_gift'])
async def add_gift_handler(message: types.Message, state=FSMContext):
    await bot.send_message(message.chat.id, "Введіть текст подарунку: ")
    await User.add_gift_text.set()


@dp.message_handler(commands=['gifts'])
async def show_gifts(message: types.Message):
    user_id = message.chat.id
    cursor.execute("SELECT id FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    if user is None:
        await bot.send_message(user_id, "Спочатку потрібно зареєструватися!")
        return
    else:
        gift_list = get_gifts(user_id)
        if not gift_list:
            await bot.send_message(user_id, "Ваш список подарунків порожній.")
        else:
            gifts_str = "\n".join(gift_list)
            await bot.send_message(user_id, f"Ваші подарунки:\n{gifts_str}")


@dp.message_handler(state=User.get_phone_number)
async def process_phone_number(message: types.Message, state=FSMContext):
    phone_number = message.text.strip()
    gift_list = get_gifts_by_phone(phone_number)
    if not gift_list:
        await bot.send_message(message.chat.id, f"Користувач з номером телефону {phone_number} не знайдений")
    else:
        await bot.send_message(message.chat.id, "\n".join(gift_list))
    await state.finish()


@dp.message_handler(commands=['gifts_by_phone'])
async def handle_gifts_by_phone(message: types.Message):
    await get_phone_number(message)
    await User.confirm_gifts_by_phone.set()  # Встановлюємо новий стан для підтвердження запиту

@dp.message_handler(state=User.confirm_gifts_by_phone)  # Обробник повідомлень у стані підтвердження запиту
async def confirm_gifts_by_phone_handler(message: types.Message, state=FSMContext):
    if message.text.lower() == "так":
        await process_phone_number(message, state)  # Викликаємо обробник, який виводить список подарунків
    elif message.text.lower() == "ні":
        await bot.send_message(message.chat.id, "Запит на список подарунків скасовано.")
        await state.finish()
    else:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        yes_btn = KeyboardButton('Так')
        no_btn = KeyboardButton('Ні')
        keyboard.add(yes_btn, no_btn)
        await bot.send_message(message.chat.id, "Ви дійсно хочете отримати список подарунків?", reply_markup=keyboard)


@dp.message_handler(commands=['edit_gift'])
async def edit_gift_handler(message: types.Message, state=FSMContext):
    chat_id = message.chat.id
    gift_list = get_gifts(chat_id)
    if not gift_list:
        await bot.send_message(chat_id, "Ваш список подарунків порожній.")
        return

    await bot.send_message(chat_id, "Оберіть ID подарунку, який ви хочете змінити:")
    gift_ids = [gift.split(":")[1].split(",")[0].strip() for gift in gift_list]
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(*gift_ids)
    await bot.send_message(chat_id, "Виберіть ID подарунку:", reply_markup=keyboard)
    await User.edit_gift.set()


@dp.message_handler(state=User.edit_gift)
async def process_edit_gift(message: types.Message, state=FSMContext):
    gift_id = int(message.text)
    gift_list = get_gifts(message.chat.id)
    gift_ids = [gift.split(",")[0].split(":")[1].strip() for gift in gift_list]
    if str(gift_id) in gift_ids:
        for gift in gift_list:
            if gift_id == int(gift.split(",")[0].split(":")[1].strip()):
                gift_text: str = gift.split(",")[1].split(":")[1].strip()
                gift_url = gift.split(",")[2].split(":")[1].strip() if len(gift.split(",")) > 2 else None
                break
        await state.update_data(gift_id=gift_id, gift_text=gift_text, gift_url=gift_url)
        await bot.send_message(message.chat.id, f"Вибраний подарунок:\nID: {gift_id}\nТекст: {gift_text}\nURL:"
                                                f" {gift_url or 'Немає'}\n\nВведіть новий текст для подарунку "
                                                f"або натисніть /skip, щоб залишити без змін:")
        await User.edit_gift_text.set()
    else:
        await bot.send_message(message.chat.id, "Введено некоректний ID подарунку. Спробуйте ще раз.")


@dp.message_handler(state=User.edit_gift_text)
async def process_edit_gift_text(message: types.Message, state=FSMContext):
    user_data = await state.get_data()
    gift_text = message.text.strip()
    await state.update_data(gift_text=gift_text)
    await bot.send_message(message.chat.id, "Чи бажаєте ви змінити URL адресу подарунку? (так/ні)")
    await User.edit_gift_url.set()


@dp.message_handler(state=User.edit_gift_url)
async def process_edit_gift_url(message: types.Message, state=FSMContext):
    user_data = await state.get_data()
    gift_id = user_data.get("gift_id")
    gift_text = user_data.get("gift_text")

    if message.text.lower() == "так":
        await bot.send_message(message.chat.id, "Введіть новий URL-адресу для подарунку:")
        await User.edit_gift_url_input.set()
        await state.update_data(editing_url=True)

    elif message.text.lower() == "ні":
        user_id = message.chat.id
        new_url = user_data.get("gift_url")
        edit_gift(gift_id, gift_text, new_url)
        await bot.send_message(user_id, "Текст подарунку змінено!")
        await state.finish()

    else:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        yes_btn = KeyboardButton('Так')
        no_btn = KeyboardButton('Ні')
        keyboard.add(yes_btn, no_btn)
        await bot.send_message(message.chat.id, "Введено некоректну відповідь. Будь ласка, виберіть 'так' або 'ні'.",
                               reply_markup=keyboard)


@dp.message_handler(state=User.edit_gift_url_input)
async def process_edit_gift_url_input(message: types.Message, state=FSMContext):
    user_data = await state.get_data()
    gift_id = user_data.get("gift_id")
    gift_text = user_data.get("gift_text")

    if "editing_url" in user_data and user_data["editing_url"]:
        new_url = message.text
        edit_gift(gift_id, gift_text, new_url)
        await bot.send_message(message.chat.id, "URL-адресу змінено!")
        await state.finish()
    else:
        await bot.send_message(message.chat.id, "Неочікувана помилка. Будь ласка, спробуйте знову.")


@dp.message_handler(commands=['delete_gift'])
async def delete_gift_handler(message: types.Message, state=FSMContext):
    chat_id = message.chat.id
    gift_list = get_gifts(chat_id)
    if not gift_list:
        await bot.send_message(chat_id, "Ваш список подарунків порожній.")
        return

    await bot.send_message(chat_id, "Оберіть ID подарунку, який ви хочете видалити:")
    gift_ids = [gift.split(":")[1].split(",")[0].strip() for gift in gift_list]
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(*gift_ids)
    await bot.send_message(chat_id, "Виберіть ID подарунку:", reply_markup=keyboard)
    await User.delete_gift.set()


@dp.message_handler(state=User.delete_gift)
async def process_delete_gift(message: types.Message, state=FSMContext):
    gift_id = int(message.text)
    gift_list = get_gifts(message.chat.id)
    gift_ids = [gift.split(",")[0].split(":")[1].strip() for gift in gift_list]
    if str(gift_id) in gift_ids:
        delete_gift(gift_id)
        await bot.send_message(message.chat.id, f"Подарунок з ID {gift_id} видалено.")
    else:
        await bot.send_message(message.chat.id, "Введено некоректний ID подарунку. Спробуйте ще раз.")
    await state.finish()


if __name__ == '__main__':
    executor.start_polling(dp)
