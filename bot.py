import asyncio
import json
import random
import os
import logging
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ========== КОНФІГУРАЦІЯ ==========
TOKEN = "8730827649:AAFKh0RFHMAslNxsHbTDIaa-JFt1XJm_d2w"
ADMIN_ID = 8037254540
logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# ========== ГЛОБАЛЬНІ БЛОКУВАННЯ ==========
user_locks = {}
gangs_lock = asyncio.Lock()
market_lock = asyncio.Lock()
events_lock = asyncio.Lock()
stock_lock = asyncio.Lock()
file_lock = asyncio.Lock()

admin_config = {
    "global_freeze_until": 0,
    "locked_commands": [],
    "event_chances": {},
    "admin_godmode": False
}
pending_trades = {}
pending_fights = {}
FIGHT_TIMEOUT = 60

def get_user_lock(uid: str) -> asyncio.Lock:
    if uid not in user_locks:
        user_locks[uid] = asyncio.Lock()
    return user_locks[uid]

# ========== ЗАВАНТАЖЕННЯ ДАНИХ ==========
def load_data():
    if os.path.exists("users.json"):
        try:
            with open("users.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

async def save_data():
    async with file_lock:
        with open("users.json", "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)

user_data = load_data()

GANGS_FILE, MARKET_FILE, EVENTS_FILE = "gangs.json", "market.json", "events.json"

def load_gangs():
    if os.path.exists(GANGS_FILE):
        try:
            with open(GANGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"gangs": {}, "user_gang": {}}

async def save_gangs():
    async with file_lock:
        with open(GANGS_FILE, "w", encoding="utf-8") as f:
            json.dump(gangs_data, f, ensure_ascii=False, indent=4)

def load_market():
    if os.path.exists(MARKET_FILE):
        try:
            with open(MARKET_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"lots": []}

async def save_market():
    async with file_lock:
        with open(MARKET_FILE, "w", encoding="utf-8") as f:
            json.dump(market_data, f, ensure_ascii=False, indent=4)

def load_events():
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"active_event": None, "event_end": 0, "last_random_event": 0}

async def save_events():
    async with file_lock:
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)

gangs_data = load_gangs()
market_data = load_market()
events_data = load_events()
event_multipliers = {"work": 1.0, "crime": 1.0, "farm": 1.0, "rob": 1.0, "fish": 1.0, "mine": 1.0}

async def apply_event_effects():
    now = time.time()
    if events_data["active_event"] and now < events_data["event_end"]:
        etype = events_data["active_event"]
        if etype == "double_work":
            event_multipliers["work"] = event_multipliers["farm"] = 2.0
        elif etype == "double_crime":
            event_multipliers["crime"] = event_multipliers["rob"] = 2.0
        elif etype == "bonus_money":
            for k in event_multipliers:
                event_multipliers[k] = 2.0
        elif etype == "crisis":
            for k in event_multipliers:
                event_multipliers[k] = 0.5
        else:
            for k in event_multipliers:
                event_multipliers[k] = 1.0
    else:
        if events_data["active_event"]:
            events_data["active_event"] = None
            events_data["event_end"] = 0
            await save_events()
        for k in event_multipliers:
            event_multipliers[k] = 1.0

def is_newbie(d: dict) -> bool:
    return d.get('xp', 0) < 500

def get_user(uid, name="Гравець"):
    uid = str(uid)
    if uid not in user_data:
        user_data[uid] = {
            "nickname": f"temp_{uid[-4:]}", "coins": 0, "bank": 0, "xp": 0,
            "level": "Вуличний 🧢",
            "equipped": {"head": "Без шапки 🧢", "body": "Футболка 👕", "pants": "Труси 🩲", "shoes": "Босі ноги 🦶"},
            "equipped_weapon": "Кулаки 👊", "armor_stats": {"head": 0, "body": 0, "pants": 0, "shoes": 0},
            "weapon_damage": 5, "last_work": 0, "last_rob": 0, "last_crime": 0, "last_daily": 0,
            "work_boost_until": 0, "age": None, "registered": False, "cheat_status": None,
            "stocks": {}, "achievements": [], "quest": None, "inventory": {},
            "fish_level": 0, "mine_level": 0, "last_fish": 0, "last_mine": 0,
            "crafting_materials": {}, "crafting_count": 0, "rob_count": 0, "jackpot_win": False,
            "stats": {"work_count": 0, "rob_count": 0, "crime_count": 0, "games_won": 0, "games_lost": 0, "fish_count": 0, "mine_count": 0},
            "hp": 100, "max_hp": 100, "mp": 50, "max_mp": 50, "class": None, "energy": 100, "level_fight": 1, "fight_xp": 0,
            "pvp_wins": 0, "pvp_losses": 0, "pve_wins": 0, "pve_losses": 0, "elo": 1200,
            "premium_until": 0, "diamonds": 0, "pet": None, "pet_hunger": 100, "profession": None, "profession_level": 1,
            "daily_tasks": [], "last_daily_task_reset": 0, "streak_daily": 0,
            "blacksmith_level": 0, "alchemist_level": 0, "cook_level": 0, "fishing_level": 0, "mining_level": 0,
            "bank_deposit": 0, "bank_deposit_time": 0,
            "referrer": None, "referrals": [],
            "cases_opened": 0,
            "last_fight": 0,
            "title": None,
            "last_wheel": 0
        }
    d = user_data[uid]
    defaults = {
        "equipped_weapon": "Кулаки 👊", "armor_stats": {"head": 0, "body": 0, "pants": 0, "shoes": 0},
        "weapon_damage": 5, "last_work": 0, "last_rob": 0, "last_crime": 0, "last_daily": 0,
        "work_boost_until": 0, "bank": 0, "age": None, "registered": False, "cheat_status": None,
        "stocks": {}, "achievements": [],
        "equipped": {"head": "Без шапки 🧢", "body": "Футболка 👕", "pants": "Труси 🩲", "shoes": "Босі ноги 🦶"},
        "quest": None, "inventory": {}, "fish_level": 0, "mine_level": 0,
        "last_fish": 0, "last_mine": 0, "crafting_materials": {},
        "crafting_count": 0, "rob_count": 0, "jackpot_win": False,
        "stats": {"work_count": 0, "rob_count": 0, "crime_count": 0, "games_won": 0, "games_lost": 0, "fish_count": 0, "mine_count": 0},
        "hp": 100, "max_hp": 100, "mp": 50, "max_mp": 50, "class": None, "energy": 100, "level_fight": 1, "fight_xp": 0,
        "pvp_wins": 0, "pvp_losses": 0, "pve_wins": 0, "pve_losses": 0, "elo": 1200,
        "premium_until": 0, "diamonds": 0, "pet": None, "pet_hunger": 100, "profession": None, "profession_level": 1,
        "daily_tasks": [], "last_daily_task_reset": 0, "streak_daily": 0,
        "blacksmith_level": 0, "alchemist_level": 0, "cook_level": 0, "fishing_level": 0, "mining_level": 0,
        "bank_deposit": 0, "bank_deposit_time": 0,
        "referrer": None, "referrals": [],
        "cases_opened": 0,
        "last_fight": 0,
        "title": None,
        "last_wheel": 0
    }
    for k, v in defaults.items():
        d.setdefault(k, v)
    return d

def find_user_by_nick(nickname: str):
    for uid, data in user_data.items():
        if data.get("nickname", "").lower() == nickname.lower():
            return uid, data
    return None, None

def get_all_players_except(uid: str, limit=10):
    others = [(u, d["nickname"]) for u, d in user_data.items() if u != uid and d.get("registered")]
    return random.sample(others, min(len(others), limit)) if len(others) > limit else others

def get_status(uid: str) -> str:
    d = get_user(uid)
    if d.get("cheat_status"):
        return d["cheat_status"]
    if int(uid) == ADMIN_ID:
        return "📓 Власник"
    return ""

def cooldown_left(last_time: float, seconds: int) -> int:
    return max(0, seconds - int(time.time() - last_time))

def fmt_time(s: int) -> str:
    if s >= 3600:
        return f"{s//3600}г {(s%3600)//60}хв"
    if s >= 60:
        return f"{s//60}хв {s%60}с"
    return f"{s}с"

# ========== РАНГИ ТА ДОСЯГНЕННЯ ==========
RANKS = [
    (0, "Вуличний 🧢"), (500, "Бандит 🔪"), (2000, "Гангстер 🕶"),
    (6000, "Кримінал 🔫"), (15000, "Дон 🤵"), (40000, "Легенда 👑")
]

def get_rank(xp: int) -> str:
    rank = RANKS[0][1]
    for req, title in RANKS:
        if xp >= req:
            rank = title
    return rank

def check_rank_up(d: dict) -> str | None:
    old = d.get("level", RANKS[0][1])
    new = get_rank(d["xp"])
    if new != old:
        d["level"] = new
        return new
    return None

ACHIEVEMENTS_DESC = {
    "first_million": ("💰 Перший мільйон", "Накопичити 1,000,000 💰"),
    "billionaire": ("💎 Мільярдер", "Накопичити 1,000,000,000 💰"),
    "farm_tycoon": ("🌾 Ферма 10 рівня", "Прокачати ферму до 10 рівня"),
    "legend": ("👑 Легенда", "Досягти рангу Легенда"),
    "stylish": ("👕 Стильний бандит", "Змінити хоча б один предмет одягу"),
    "fish_master": ("🎣 Майстер риболовлі", "Риболовля 10 рівня"),
    "mine_master": ("⛏ Майстер шахти", "Шахта 10 рівня"),
    "craft_master": ("🛠 Майстер крафту", "Створити 10 предметів"),
    "jackpot_winner": ("🎰 Джекпот", "Виграти джекпот у слотах"),
    "top_robber": ("💰 Професійний грабіжник", "Пограбувати 10 разів"),
    "pvp_champion": ("⚔️ Чемпіон арени", "Виграти 50 PvP боїв"),
    "pve_hero": ("🐉 Герой підземель", "Перемогти 10 босів"),
    "million_xp": ("⭐ Мільйон XP", "Накопичити 1,000,000 XP"),
    "premium": ("💎 Преміум", "Купити преміум статус"),
    "pet_lover": ("🐕 Любитель тварин", "Отримати домашню тварину"),
    "gambler": ("🎲 Азартний гравець", "Виграти в казино 100 разів"),
    "blacksmith": ("🔨 Майстер-коваль", "Досягти 10 рівня коваля"),
    "alchemist": ("🧪 Майстер-алхімік", "Досягти 10 рівня алхіміка"),
    "cook": ("🍳 Шеф-кухар", "Досягти 10 рівня кухаря"),
    "referral_king": ("👑 Король рефералів", "Запросити 10 друзів"),
}

def check_achievements(d: dict, uid: str):
    total = d["coins"] + d["bank"]
    farm = get_user_farm(uid) if "get_user_farm" in dir() else {"level": 0}
    farm_level = farm["level"] if farm else 0
    conditions = [
        ("first_million", total >= 1_000_000),
        ("billionaire", total >= 1_000_000_000),
        ("farm_tycoon", farm_level >= 10),
        ("legend", d["level"] == "Легенда 👑"),
        ("stylish", any(d["equipped"][s] not in ["Футболка 👕", "Труси 🩲", "Босі ноги 🦶", "Без шапки 🧢"] for s in ["head", "body", "pants", "shoes"])),
        ("fish_master", d.get("fish_level", 0) >= 10),
        ("mine_master", d.get("mine_level", 0) >= 10),
        ("craft_master", d.get("crafting_count", 0) >= 10),
        ("jackpot_winner", d.get("jackpot_win", False)),
        ("top_robber", d.get("rob_count", 0) >= 10),
        ("pvp_champion", d.get("pvp_wins", 0) >= 50),
        ("pve_hero", d.get("pve_wins", 0) >= 10),
        ("million_xp", d.get("xp", 0) >= 1_000_000),
        ("premium", d.get("premium_until", 0) > time.time()),
        ("pet_lover", d.get("pet") is not None),
        ("gambler", d.get("stats", {}).get("casino_wins", 0) >= 100),
        ("blacksmith", d.get("blacksmith_level", 0) >= 10),
        ("alchemist", d.get("alchemist_level", 0) >= 10),
        ("cook", d.get("cook_level", 0) >= 10),
        ("referral_king", len(d.get("referrals", [])) >= 10),
    ]
    changed = False
    for ach_id, cond in conditions:
        if cond and ach_id not in d["achievements"]:
            d["achievements"].append(ach_id)
            changed = True
    if changed:
        asyncio.ensure_future(save_data())

# ========== КВЕСТИ ==========
QUEST_TYPES = ["work", "crime", "rob", "farm", "dice_win", "flip_win", "slots_win", "buy_item", "fish", "mine", "craft", "pvp_win", "pve_win", "casino_win"]

def generate_quest(d: dict):
    qtype = random.choice(QUEST_TYPES)
    target = random.randint(1, 5) if qtype in ["pvp_win", "pve_win", "casino_win"] else random.randint(1, 3)
    reward_coins = random.randint(10000, 50000)
    reward_xp = random.randint(100, 500)
    d["quest"] = {"type": qtype, "target": target, "progress": 0, "reward_coins": reward_coins, "reward_xp": reward_xp}

async def update_quest_progress(uid: str, qtype: str):
    async with get_user_lock(uid):
        d = get_user(uid)
        if not d.get("quest"):
            generate_quest(d)
        quest = d["quest"]
        if quest["type"] == qtype:
            quest["progress"] += 1
            if quest["progress"] >= quest["target"]:
                d["coins"] += quest["reward_coins"]
                d["xp"] += quest["reward_xp"]
                await save_data()
                try:
                    await bot.send_message(uid, f"🎯 *Квест виконано!*\nОтримано: `{quest['reward_coins']:,} 💰` та `{quest['reward_xp']} XP`", parse_mode="Markdown")
                except:
                    pass
                generate_quest(d)
                check_rank_up(d)
                check_achievements(d, uid)
                await save_data()
            else:
                await save_data()

# ========== КЛАВІАТУРИ ==========
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    buttons = [
        "👤 Профіль", "🔨 Робота", "🛒 Ринок",
        "📦 Інвентар", "🛍 Магазин", "🏦 Банк",
        "📈 Біржа", "🎲 Ігри", "⚔️ Бій",
        "🏴 Банда", "👔 Професії", "Далі ➡️"
    ]
    for b in buttons:
        builder.button(text=b)
    builder.adjust(3, 3, 3, 3)
    return builder.as_markup(resize_keyboard=True)

def get_second_kb():
    builder = ReplyKeyboardBuilder()
    buttons = [
        "🏭 Ферми", "🏅 Досягнення",
        "🎰 Казино", "🐾 Тварина", "💎 Преміум",
        "👥 Запросити", "💰 Баланс", "📊 Статистика",
        "🌦 Погода", "🎁 Кейси", "⬅️ Назад"
    ]
    for b in buttons:
        builder.button(text=b)
    builder.adjust(3, 3, 3, 2)
    return builder.as_markup(resize_keyboard=True)

def get_professions_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎣 Рибалка", callback_data="prof_fish")
    builder.button(text="⛏ Шахтар", callback_data="prof_mine")
    builder.button(text="🛠 Коваль", callback_data="prof_blacksmith")
    builder.button(text="🧪 Алхімік", callback_data="prof_alchemist")
    builder.button(text="🍳 Кухар", callback_data="prof_cook")
    builder.button(text="🏆 Рейтинг професій", callback_data="prof_rating")
    builder.adjust(1)
    return builder.as_markup()

# ========== FSM РЕЄСТРАЦІЇ ==========
class RegForm(StatesGroup):
    waiting_nickname = State()
    waiting_age = State()
    waiting_referral = State()

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = args[1]
    async with get_user_lock(uid):
        d = get_user(uid)
        if message.from_user.id == ADMIN_ID and not d.get("registered"):
            d["nickname"] = "Admin"; d["age"] = 30; d["registered"] = True; d["coins"] = 1000000; d["diamonds"] = 1000
            d["bank"] = 0; d["xp"] = 0; d["level"] = "Вуличний 🧢"
            d["equipped"] = {"head": "Корона 👑", "body": "Піджак 🕴️", "pants": "Штани 👖", "shoes": "Черевики 👞"}
            d["equipped_weapon"] = "Кулаки 👊"; d["weapon_damage"] = 5
            d["armor_stats"] = {"head": 0, "body": 0, "pants": 0, "shoes": 0}
            for t in ["last_work", "last_rob", "last_crime", "last_daily", "work_boost_until"]:
                d[t] = 0
            await save_data()
            await message.answer(
                "👑 *Вітаємо у вашому власному боті, Володарю!* 👑\n\n🦾 *Bandit Ultimate* готовий.\nКеруйте економікою: `/give`, `/take`, `/give_xp`, `/take_xp`\nВаш адмінський профіль створено автоматично.",
                reply_markup=get_main_kb(), parse_mode="Markdown"
            )
            return
        if message.from_user.id == ADMIN_ID:
            await message.answer(
                "👑 *Ласкаво просимо, Володарю!* 👑\nКеруйте економікою командами `/give`, `/take`, `/give_xp`, `/take_xp`",
                reply_markup=get_main_kb(), parse_mode="Markdown"
            )
            return
        if d.get("registered"):
            if d["nickname"].startswith("temp_"):
                d["registered"] = False
                await save_data()
            else:
                if referrer_id and referrer_id != uid and not d.get("referrer"):
                    ref_uid = referrer_id
                    if ref_uid in user_data and user_data[ref_uid].get("registered"):
                        d["referrer"] = ref_uid
                        user_data[ref_uid]["referrals"] = user_data[ref_uid].get("referrals", [])
                        if uid not in user_data[ref_uid]["referrals"]:
                            user_data[ref_uid]["referrals"].append(uid)
                            user_data[ref_uid]["coins"] += 5000
                            user_data[ref_uid]["diamonds"] = user_data[ref_uid].get("diamonds", 0) + 10
                            await save_data()
                            try:
                                await bot.send_message(ref_uid, f"🎉 Новий реферал! {d['nickname']} зареєструвався за вашим посиланням. Отримано +5000💰 та +10💎")
                            except: pass
                            await message.answer("✨ Ви були запрошені іншим гравцем! Отримано стартовий бонус +1000💰")
                            d["coins"] += 1000
                            await save_data()
                await message.answer(f"🦾 З поверненням, *{d['nickname']}*!", reply_markup=get_main_kb(), parse_mode="Markdown")
                return
    await state.set_state(RegForm.waiting_nickname)
    await message.answer(
        "🎭 *Ласкаво просимо до Bandit Ultimate!*\n\nПридумайте свій *нікнейм*:\n• Від 1 до 5 символів\n• Тільки англійські літери (A-Z a-z)\n• Без пробілів та розділових знаків\n\nНапишіть ваш нікнейм:",
        parse_mode="Markdown"
    )

@dp.message(RegForm.waiting_nickname)
async def register_nickname(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    nick = message.text.strip()
    if not (1 <= len(nick) <= 5) or not nick.isalpha() or not nick.isascii():
        await message.answer("❌ Нікнейм має бути від 1 до 5 англійських літер!")
        return
    existing_uid, _ = find_user_by_nick(nick)
    if existing_uid and existing_uid != uid:
        await message.answer(f"❌ Нікнейм `{nick}` вже зайнятий!")
        return
    await state.update_data(nickname=nick)
    await state.set_state(RegForm.waiting_age)
    await message.answer(f"✅ Гарний нікнейм, *{nick}*!\nТепер вкажіть ваш *вік* (число від 1 до 60):", parse_mode="Markdown")

@dp.message(RegForm.waiting_age)
async def register_age(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    try:
        age = int(message.text.strip())
    except:
        await message.answer("❌ Вік має бути числом!")
        return
    if not (1 <= age <= 60):
        await message.answer("❌ Вік має бути від 1 до 60!")
        return
    data = await state.get_data()
    nickname = data["nickname"]
    async with get_user_lock(uid):
        d = get_user(uid)
        d["nickname"] = nickname
        d["age"] = age
        d["registered"] = True
        d["coins"] = 500
        d["bank"] = 0
        d["xp"] = 0
        d["level"] = "Вуличний 🧢"
        d["equipped"] = {"head": "Без шапки 🧢", "body": "Футболка 👕", "pants": "Труси 🩲", "shoes": "Босі ноги 🦶"}
        d["equipped_weapon"] = "Кулаки 👊"
        d["weapon_damage"] = 5
        d["armor_stats"] = {"head": 0, "body": 0, "pants": 0, "shoes": 0}
        for t in ["last_work", "last_rob", "last_crime", "last_daily", "work_boost_until"]:
            d[t] = 0
        if not d.get("quest"):
            generate_quest(d)
        d["daily_tasks"] = []
        d["last_daily_task_reset"] = time.time()
        await save_data()
    await state.clear()
    await message.answer(
        f"🎉 *Вітаємо, {nickname}!*\n\nВи успішно зареєструвались у Bandit Ultimate.\nВаш вік: {age} років.\nОтримано стартовий капітал: `500 💰`\n\n🦾 Використовуйте кнопки нижче, щоб заробляти та ставати багатшим!",
        reply_markup=get_main_kb(), parse_mode="Markdown"
    )

# ========== ЧІТ-КОДИ ==========
CHEAT_CODES = {
    "storm44": (10_000_000, "💸 +10,000,000 💰", "Шторм грошей!"), "neon21": (10_000_000, "🌈 +10,000,000 💰", "Неонові бабки!"),
    "cash77": (100_000, "💵 +100,000 💰", "Кеш в кишені!"), "drop13": (100_000, "🎯 +100,000 💰", "Дроп активовано!"),
    "king99": (999_000_000_000, "👑 +999 млрд 💰", "Ти КОРОЛЬ!"), "boss52": (999_000_000_000, "😈 +999 млрд 💰", "Бос прийшов!"),
    "blaze88": (1_000_000_000, "🔥 +1 млрд 💰", "Вогонь!"), "fire36": (1_000_000_000, "🚒 +1 млрд 💰", "Пожежа грошей!"),
    "ultra55": (100_000_000, "⚡️ +100 млн 💰", "Ультра-заряд!"), "ghost11": (100_000_000, "👻 +100 млн 💰", "Привид багатства!"),
    "godmode": (999_999_999_999_999, "👼 +999 трлн 💰", "БОГ"), "immortal": (888_888_888_888_888, "🧛 +888 трлн 💰", "Безсмертний"),
    "infinity": (777_777_777_777_777, "♾️ +777 трлн 💰", "Нескінченний"), "matrix": (666_666_666_666_666, "🌀 +666 трлн 💰", "Обраний"),
    "celestial": (555_555_555_555_555, "🌌 +555 трлн 💰", "Небесний"), "golden56": (500_000_000_000_000, "💰 +500 трлн 💰", "Золотий запас"),
    "platinum": (300_000_000_000_000, "💎 +300 трлн 💰", "Платиновий"), "titan": (200_000_000_000_000, "🗿 +200 трлн 💰", "Титан"),
    "diamond": (100_000_000_000_000, "💠 +100 трлн 💰", "Діамант"), "legend77": (50_000_000_000_000, "🏆 +50 трлн 💰", "Легенда"),
    "shadow": (25_000_000_000_000, "🌑 +25 трлн 💰", "Тінь"), "vortex": (12_000_000_000_000, "🌀 +12 трлн 💰", "Вихор"),
    "phoenix": (6_000_000_000_000, "🦅 +6 трлн 💰", "Фенікс"), "nova": (3_000_000_000_000, "💥 +3 трлн 💰", "Наднова"),
    "omega": (1_000_000_000_000, "🅾️ +1 трлн 💰", "Омега"), "hyper": (900_000_000_000, "⚡ +900 млрд 💰", "Гіпер"),
    "storm99": (800_000_000_000, "🌪️ +800 млрд 💰", "Шторм 99"), "blizzard": (700_000_000_000, "❄️ +700 млрд 💰", "Завірюха"),
    "thunder": (600_000_000_000, "⛈️ +600 млрд 💰", "Грім"), "typhoon": (400_000_000_000, "🌀 +400 млрд 💰", "Тайфун")
}

async def handle_cheat(message: types.Message, code: str):
    amount, text, status = CHEAT_CODES[code]
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            await message.answer("❌ Спочатку зареєструйтесь через /start!")
            return
        d["coins"] += amount
        d["cheat_status"] = status
        check_achievements(d, uid)
        await save_data()
    await message.answer(f"🎮 *Чіт-код активовано!*\n{text}\n🏷 Ваш новий статус: *{status}*", parse_mode="Markdown")

for code in CHEAT_CODES:
    @dp.message(Command(code))
    async def cheat_handler(message: types.Message, cmd_code=code):
        await handle_cheat(message, cmd_code)

@dp.message(Command("myid"))
async def show_my_id(message: types.Message):
    await message.answer(f"Твій Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")

# ========== АДМІН КОМАНДИ ==========
def parse_nickname_and_amount(args: str):
    if not args:
        return None, None
    parts = args.strip().split()
    if len(parts) < 2:
        return None, None
    try:
        amount = int(parts[-1])
    except ValueError:
        return None, None
    nick = " ".join(parts[:-1])
    return nick, amount

@dp.message(Command("give"))
async def give_money(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick, amount = parse_nickname_and_amount(command.args)
    if not nick or amount <= 0:
        return await message.answer("⚠️ `/give [нікнейм] [сума]`", parse_mode="Markdown")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["coins"] += amount
        await save_data()
    await message.answer(f"✅ `{nick}` отримав `{amount:,} 💰`", parse_mode="Markdown")

@dp.message(Command("take"))
async def take_money(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick, amount = parse_nickname_and_amount(command.args)
    if not nick or amount <= 0:
        return await message.answer("⚠️ `/take [нікнейм] [сума]`", parse_mode="Markdown")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["coins"] = max(0, td["coins"] - amount)
        await save_data()
    await message.answer(f"✅ Знято `{amount:,} 💰` у `{nick}`", parse_mode="Markdown")

@dp.message(Command("give_xp"))
async def give_xp(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick, amount = parse_nickname_and_amount(command.args)
    if not nick or amount <= 0:
        return await message.answer("⚠️ `/give_xp [нікнейм] [кількість]`", parse_mode="Markdown")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["xp"] += amount
        rank_up = check_rank_up(td)
        await save_data()
    text = f"✅ `{nick}` отримав `{amount:,} XP`"
    if rank_up:
        text += f"\n🎉 *Новий ранг: {rank_up}!*"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("take_xp"))
async def take_xp(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick, amount = parse_nickname_and_amount(command.args)
    if not nick or amount <= 0:
        return await message.answer("⚠️ `/take_xp [нікнейм] [кількість]`", parse_mode="Markdown")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["xp"] = max(0, td["xp"] - amount)
        new_level = get_rank(td["xp"])
        if new_level != td["level"]:
            td["level"] = new_level
        await save_data()
    await message.answer(f"✅ У `{nick}` забрано `{amount} XP`. Тепер `{td['xp']} XP`.", parse_mode="Markdown")

@dp.message(Command("profile"))
async def admin_profile(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Тільки адмін!")
    if not command.args:
        regs = [(uid, data) for uid, data in user_data.items() if data.get("registered")]
        if not regs:
            return await message.answer("❌ Немає гравців.")
        text = "👥 *Зареєстровані гравці:*\n"
        for uid, data in regs[:20]:
            text += f"• `{data['nickname']}` (ID: `{uid}`)\n"
        if len(regs) > 20:
            text += f"... і ще {len(regs)-20}"
        return await message.answer(text, parse_mode="Markdown")
    nick = command.args.strip()
    uid, td = find_user_by_nick(nick)
    if not td or not td.get("registered"):
        return await message.answer("❌ Не знайдено!")
    eq = td["equipped"]
    status = get_status(uid)
    age = td.get('age')
    total = td["coins"] + td["bank"]
    text = (
        f"👤 *{td['nickname']}* (ID: `{uid}`) | {td['level']}\n"
        f"🏷 {status}\n🎂 Вік: {age}\n"
        f"💰 Готівка: {td['coins']:,}\n🏦 Банк: {td['bank']:,}\n💎 Всього: {total:,}\n⭐ Досвід: {td['xp']} XP\n"
        f"👕 Екіпіровка:\n🧢 {eq['head']}\n🛡 {eq['body']}\n👖 {eq['pants']}\n👟 {eq['shoes']}\n⚔️ {td['equipped_weapon']} (шкода {td['weapon_damage']})"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("write"))
async def write_message(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Тільки адмін!")
    if not command.args:
        return await message.answer("⚠️ `/write [нікнейм] [повідомлення]`")
    parts = command.args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("⚠️ Потрібен нікнейм та повідомлення!")
    nick, msg_text = parts[0], parts[1]
    uid, td = find_user_by_nick(nick)
    if not td or not td.get("registered"):
        return await message.answer("❌ Не знайдено!")
    try:
        await bot.send_message(uid, f"📨 *Повідомлення від адміністратора:*\n\n{msg_text}", parse_mode="Markdown")
        await message.answer(f"✅ Надіслано `{nick}`.")
    except:
        await message.answer("❌ Не вдалось надіслати.")

@dp.message(Command("writeall"))
async def write_all(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Тільки адмін!")
    if not command.args:
        return await message.answer("⚠️ `/writeall [повідомлення]`")
    msg_text = command.args.strip()
    registered = [uid for uid, data in user_data.items() if data.get("registered")]
    sent = 0
    for uid in registered:
        try:
            await bot.send_message(uid, f"📢 *Оголошення від адміністратора:*\n\n{msg_text}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"✅ Розсилка: доставлено {sent}/{len(registered)}.")

@dp.message(Command("resetcooldowns"))
async def reset_cooldowns(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick = command.args.strip() if command.args else None
    if not nick:
        return await message.answer("⚠️ `/resetcooldowns [нікнейм]`")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["last_work"] = 0
        td["last_rob"] = 0
        td["last_crime"] = 0
        td["last_daily"] = 0
        td["work_boost_until"] = 0
        td["last_fight"] = 0
        if "farm" in td:
            td["farm"]["last_harvest"] = 0
        await save_data()
    await message.answer(f"✅ Усі кулдауни для `{nick}` скинуто!", parse_mode="Markdown")

@dp.message(Command("boost"))
async def give_boost(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    args = command.args.split() if command.args else []
    if len(args) < 2:
        return await message.answer("⚠️ `/boost [нікнейм] [хвилини]`")
    nick, minutes = args[0], args[1]
    try:
        minutes = int(minutes)
    except:
        return await message.answer("❌ Хвилини мають бути числом!")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["work_boost_until"] = time.time() + minutes * 60
        await save_data()
    await message.answer(f"✅ `{nick}` отримав x2 на роботу на {minutes} хв!", parse_mode="Markdown")

@dp.message(Command("resetquest"))
async def reset_quest(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick = command.args.strip() if command.args else None
    if not nick:
        return await message.answer("⚠️ `/resetquest [нікнейм]`")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        generate_quest(td)
        await save_data()
    await message.answer(f"✅ Квест для `{nick}` оновлено!", parse_mode="Markdown")

@dp.message(Command("additem"))
async def add_item(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    args = command.args.split(maxsplit=2) if command.args else []
    if len(args) < 2:
        return await message.answer("⚠️ `/additem [нікнейм] [назва_предмета] [кількість?]`")
    nick = args[0]
    item_name = args[1]
    count = int(args[2]) if len(args) > 2 else 1
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["inventory"][item_name] = td["inventory"].get(item_name, 0) + count
        await save_data()
    await message.answer(f"✅ `{nick}` отримав {count} x `{item_name}`!", parse_mode="Markdown")

@dp.message(Command("removeitem"))
async def remove_item(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    args = command.args.split(maxsplit=2) if command.args else []
    if len(args) < 2:
        return await message.answer("⚠️ `/removeitem [нікнейм] [назва_предмета] [кількість?]`")
    nick = args[0]
    item_name = args[1]
    count = int(args[2]) if len(args) > 2 else 1
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        current = td["inventory"].get(item_name, 0)
        if current < count:
            return await message.answer(f"❌ У `{nick}` лише {current} x `{item_name}`!")
        if current == count:
            del td["inventory"][item_name]
        else:
            td["inventory"][item_name] = current - count
        await save_data()
    await message.answer(f"✅ У `{nick}` забрано {count} x `{item_name}`!", parse_mode="Markdown")

@dp.message(Command("setlevel"))
async def set_level(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    args = command.args.split() if command.args else []
    if len(args) < 2:
        return await message.answer("⚠️ `/setlevel [нікнейм] [рівень_ферми]`")
    nick, level_str = args[0], args[1]
    try:
        level = int(level_str)
        level = max(0, min(level, 30))
    except:
        return await message.answer("❌ Рівень має бути числом (0-30)!")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        farm = get_user_farm(target_uid)
        farm["level"] = level
        farm["last_harvest"] = 0
        await save_data()
    await message.answer(f"✅ Ферма `{nick}` встановлена на рівень {level}!", parse_mode="Markdown")

@dp.message(Command("resetfarm"))
async def reset_farm(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick = command.args.strip() if command.args else None
    if not nick:
        return await message.answer("⚠️ `/resetfarm [нікнейм]`")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["farm"] = {"level": 0, "last_harvest": 0}
        await save_data()
    await message.answer(f"✅ Ферма `{nick}` повністю скинута!", parse_mode="Markdown")

@dp.message(Command("resetbank"))
async def reset_bank(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick = command.args.strip() if command.args else None
    if not nick:
        return await message.answer("⚠️ `/resetbank [нікнейм]`")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["bank"] = 0
        await save_data()
    await message.answer(f"✅ Банківський рахунок `{nick}` обнулений!", parse_mode="Markdown")

@dp.message(Command("resetstocks"))
async def reset_stocks(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick = command.args.strip() if command.args else None
    if not nick:
        return await message.answer("⚠️ `/resetstocks [нікнейм]`")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["stocks"] = {}
        await save_data()
    await message.answer(f"✅ Усі акції `{nick}` видалені!", parse_mode="Markdown")

@dp.message(Command("freeze"))
async def freeze_player(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    nick = command.args.strip() if command.args else None
    if not nick:
        return await message.answer("⚠️ `/freeze [нікнейм]`")
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ `{nick}` не знайдено!")
    async with get_user_lock(target_uid):
        td["frozen"] = not td.get("frozen", False)
        status = "заморожений" if td["frozen"] else "розморожений"
        await save_data()
    await message.answer(f"✅ Гравець `{nick}` {status}!", parse_mode="Markdown")

@dp.message(Command("sellall"))
async def admin_sell_item(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Тільки адмін!")
    if not command.args:
        return await message.answer("⚠️ `/sellall [назва] [категорія] [ціна]`")
    parts = command.args.strip().split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("⚠️ Потрібно: назва, категорія, ціна")
    name, cat, price_str = parts
    try:
        price = int(price_str)
    except:
        return await message.answer("❌ Ціна має бути числом!")
    valid_cats = ["Голова", "Торс", "Штани", "Взуття", "Зброя", "Інше"]
    if cat not in valid_cats:
        return await message.answer(f"❌ Категорії: {', '.join(valid_cats)}")
    async with market_lock:
        lot = {"name": name, "category": cat, "price": price, "seller_uid": str(message.from_user.id), "id": int(time.time()*1000)}
        market_data["lots"].append(lot)
        await save_market()
    await message.answer(f"✅ *{name}* ({cat}) виставлено за `{price:,} 💰`", parse_mode="Markdown")

# ---------- НОВІ АДМІН КОМАНДИ ----------
@dp.message(Command("freeze_global"))
async def global_freeze(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    if not command.args:
        return await message.answer("⚠️ `/freeze_global [секунди]`")
    try:
        seconds = int(command.args)
    except:
        return await message.answer("❌ Введіть число секунд!")
    admin_config["global_freeze_until"] = time.time() + seconds
    await message.answer(f"🌍 *Світ заморожено на {seconds} секунд!* Жодна дія не працюватиме.", parse_mode="Markdown")

@dp.message(Command("unfreeze_global"))
async def global_unfreeze(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    admin_config["global_freeze_until"] = 0
    await message.answer("🌍 *Світ розморожено!*", parse_mode="Markdown")

@dp.message(Command("lockcmd"))
async def lock_command(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    if not command.args:
        return await message.answer("⚠️ `/lockcmd [команда]` (наприклад /work або work)")
    cmd = command.args.strip().lstrip('/')
    if cmd not in admin_config["locked_commands"]:
        admin_config["locked_commands"].append(cmd)
    await message.answer(f"🔒 Команда `/{cmd}` заблокована для всіх (крім адміна).", parse_mode="Markdown")

@dp.message(Command("unlockcmd"))
async def unlock_command(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Немає прав!")
    if not command.args:
        return await message.answer("⚠️ `/unlockcmd [команда]`")
    cmd = command.args.strip().lstrip('/')
    if cmd in admin_config["locked_commands"]:
        admin_config["locked_commands"].remove(cmd)
    await message.answer(f"🔓 Команда `/{cmd}` розблокована.", parse_mode="Markdown")

# ========== РИНОК ==========
@dp.message(F.text == "🛒 Ринок")
async def market_menu(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    if not market_data["lots"]:
        return await message.answer("🛒 Ринок порожній.")
    text = "🛒 *Підпільний ринок*\n"
    builder = InlineKeyboardBuilder()
    for lot in market_data["lots"][:10]:
        text += f"• {lot['name']} ({lot['category']}) — `{lot['price']:,} 💰`\n"
        builder.button(text=f"Купити {lot['name']}", callback_data=f"mktbuy_{lot['id']}")
    builder.adjust(1)
    text += f"\n💰 Ваш баланс: `{d['coins']:,} 💰`"
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("mktbuy_"))
async def market_buy(callback: types.CallbackQuery):
    lot_id = int(callback.data.split("_")[1])
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await callback.answer("❌ Акаунт заморожено або світ на паузі!", show_alert=True)
        if not d.get("registered") and callback.from_user.id != ADMIN_ID:
            return await callback.answer("❌ Зареєструйтесь!")
        async with market_lock:
            lot = next((l for l in market_data["lots"] if l["id"] == lot_id), None)
            if not lot:
                return await callback.answer("❌ Продано!")
            if d["coins"] < lot["price"]:
                return await callback.answer("❌ Недостатньо грошей!")
            d["coins"] -= lot["price"]
            d["inventory"][lot["name"]] = d["inventory"].get(lot["name"], 0) + 1
            market_data["lots"].remove(lot)
            await save_market()
            await save_data()
    await callback.message.edit_text(f"✅ Ви купили *{lot['name']}* за `{lot['price']:,} 💰`!", parse_mode="Markdown")
    await callback.answer()

# ========== ПОДІЇ ==========
EVENT_TYPES = ["double_work", "double_crime", "bonus_money", "crisis"]

@dp.message(Command("event"))
async def admin_event(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Тільки адмін!")
    if not command.args:
        return await message.answer("⚠️ `/event [тип] [хвилини]`\nТипи: " + ", ".join(EVENT_TYPES))
    parts = command.args.split()
    if len(parts) < 2:
        return await message.answer("⚠️ Потрібен тип та тривалість")
    etype, duration_str = parts[0], parts[1]
    try:
        duration = int(duration_str)
    except:
        return await message.answer("❌ Тривалість числом (хвилини)")
    if etype not in EVENT_TYPES:
        return await message.answer("❌ Невідомий тип")
    if duration <= 0:
        return await message.answer("❌ Тривалість має бути більшою за 0!")
    async with events_lock:
        events_data["active_event"] = etype
        events_data["event_end"] = time.time() + duration*60
        await save_events()
    await apply_event_effects()
    registered = [uid for uid, data in user_data.items() if data.get("registered")]
    for uid in registered:
        try:
            await bot.send_message(uid, f"🌍 *Глобальна подія!* {etype} діє {duration} хв.", parse_mode="Markdown")
        except:
            pass
    await message.answer(f"✅ Подія *{etype}* активована на {duration} хв.", parse_mode="Markdown")

# ========== РОБОТА ==========
WORK_COOLDOWN = 1800
JOBS = [
    ("🚗 Таксував цілу ніч", 400, 900),
    ("🍕 Розвозив піцу", 300, 700),
    ("🔧 Ремонтував машини", 500, 1000),
    ("📦 Вантажив ящики", 350, 750),
    ("🛒 Працював касиром", 300, 600),
    ("🏗 Будував стіни", 600, 1200),
]

def get_gang_bonus(uid):
    gang_name = gangs_data["user_gang"].get(uid)
    if not gang_name or gang_name not in gangs_data["gangs"]:
        return 1.0
    return 1.0 + (gangs_data["gangs"][gang_name]["level"] - 1) * 0.05

@dp.message(F.text == "🔨 Робота")
async def work_h(message: types.Message):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return await message.answer("❌ Зареєструйтесь!")
        left = cooldown_left(d["last_work"], WORK_COOLDOWN)
        if left > 0:
            return await message.answer(f"😴 Відпочиньте ще *{fmt_time(left)}*", parse_mode="Markdown")
        job_name, min_rew, max_rew = random.choice(JOBS)
        await apply_event_effects()
        reward = random.randint(min_rew, max_rew) * event_multipliers["work"]
        if time.time() < d.get("work_boost_until", 0):
            reward *= 2
        if d.get("premium_until", 0) > time.time():
            reward *= 2
        gang_bonus = get_gang_bonus(uid)
        reward = int(reward * gang_bonus)
        d["coins"] += reward
        d["xp"] += 15
        d["last_work"] = time.time()
        d.setdefault("stats", {})["work_count"] = d["stats"].get("work_count", 0) + 1
        rank_up = check_rank_up(d)
        await save_data()
    await update_quest_progress(uid, "work")
    async with get_user_lock(uid):
        d = get_user(uid)
        check_achievements(d, uid)
        await save_data()
    boost_line = " ⚡️ x2" if time.time() < d.get("work_boost_until", 0) else ""
    premium_line = " 💎 x2 (преміум)" if d.get("premium_until", 0) > time.time() else ""
    gang_line = f" (+{int((gang_bonus-1)*100)}% від банди)" if gang_bonus > 1 else ""
    rank_line = f"\n\n🎉 *Новий ранг: {rank_up}!*" if rank_up else ""
    text = f"🔨 *Робота виконана!*{boost_line}{premium_line}{gang_line}\n{job_name}\nОтримано: `{reward:,} 💰` та `15 XP`{rank_line}\n\n⏳ Наступна через `{fmt_time(WORK_COOLDOWN)}`"
    await message.answer(text, parse_mode="Markdown")

# ========== БАНК ==========
@dp.message(F.text == "🏦 Банк")
async def bank_h(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    if d.get("bank_deposit", 0) > 0 and d.get("bank_deposit_time", 0) > 0:
        elapsed = time.time() - d["bank_deposit_time"]
        hours = elapsed // 3600
        if hours >= 1:
            interest = int(d["bank_deposit"] * 0.005 * hours)
            d["bank_deposit"] += interest
            d["bank_deposit_time"] = time.time()
            await save_data()
            await message.answer(f"🏦 *Відсотки нараховано!* +{interest:,} 💰 до депозиту.")
    await message.answer(
        f"🏦 *Банк Bandit*\n━━━━━━━━━━━━━━━━\n"
        f"💰 Готівка: `{d['coins']:,} 💰`\n🏦 На рахунку: `{d['bank']:,} 💰`\n"
        f"📈 *Депозит під 0.5% щогодини:*\n   Вкладено: `{d.get('bank_deposit', 0):,} 💰`\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💸 `/dep [сума]` — покласти\n"
        f"💸 `/with [сума]` — зняти\n"
        f"📈 `/deposit_invest [сума]` — вкласти під %\n"
        f"📈 `/deposit_withdraw` — зняти депозит\n\n"
        f"🔒 Гроші у банку *захищені* від пограбування!",
        parse_mode="Markdown"
    )

@dp.message(Command("dep"))
async def deposit(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return
        try:
            amount = int(command.args)
        except:
            return await message.answer("❌ Введіть суму!")
        if amount <= 0 or amount > d["coins"]:
            return await message.answer(f"❌ Недостатньо! У вас `{d['coins']:,} 💰`", parse_mode="Markdown")
        d["coins"] -= amount
        d["bank"] += amount
        await save_data()
    await message.answer(f"✅ Покладено `{amount:,} 💰` до банку!\n🏦 Баланс: `{d['bank']:,} 💰`", parse_mode="Markdown")

@dp.message(Command("with"))
async def withdraw(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return
        try:
            amount = int(command.args)
        except:
            return await message.answer("❌ Введіть суму!")
        if amount <= 0 or amount > d["bank"]:
            return await message.answer(f"❌ У банку лише `{d['bank']:,} 💰`", parse_mode="Markdown")
        d["bank"] -= amount
        d["coins"] += amount
        await save_data()
    await message.answer(f"✅ Знято `{amount:,} 💰` з банку!\n💰 Готівка: `{d['coins']:,} 💰`", parse_mode="Markdown")

@dp.message(Command("deposit_invest"))
async def deposit_invest(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return
        try:
            amount = int(command.args)
        except:
            return await message.answer("❌ Введіть суму!")
        if amount <= 0 or amount > d["coins"]:
            return await message.answer(f"❌ Недостатньо! У вас `{d['coins']:,} 💰`", parse_mode="Markdown")
        d["coins"] -= amount
        d["bank_deposit"] = d.get("bank_deposit", 0) + amount
        d["bank_deposit_time"] = time.time()
        await save_data()
    await message.answer(f"✅ Ви вклали `{amount:,} 💰` на депозит під 0.5% щогодини!", parse_mode="Markdown")

@dp.message(Command("deposit_withdraw"))
async def deposit_withdraw(message: types.Message):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return
        amount = d.get("bank_deposit", 0)
        if amount <= 0:
            return await message.answer("❌ У вас немає активного депозиту!")
        d["coins"] += amount
        d["bank_deposit"] = 0
        d["bank_deposit_time"] = 0
        await save_data()
    await message.answer(f"✅ Ви зняли депозит: `{amount:,} 💰`!", parse_mode="Markdown")

# ========== ТОП ==========
MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

@dp.message(F.text == "🏆 ТОП")
async def top_h(message: types.Message):
    registered = [(uid, data) for uid, data in user_data.items() if data.get("registered") and not data.get("frozen")]
    top = sorted(registered, key=lambda x: x[1].get("coins", 0) + x[1].get("bank", 0), reverse=True)[:5]
    text = "🏆 *ТОП-5 БАГАТІЇВ:*\n━━━━━━━━━━━━━━━━\n"
    for i, (_, u) in enumerate(top):
        total = u.get("coins", 0) + u.get("bank", 0)
        text += f"{MEDALS[i]} `{u['nickname']}` — `{total:,} 💰`\n"
    await message.answer(text, parse_mode="Markdown")

# ========== ПОГРАБУВАННЯ ==========
ROB_COOLDOWN = 2700

@dp.message(Command("rob"))
async def rob_command(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    left = cooldown_left(d["last_rob"], ROB_COOLDOWN)
    if left > 0:
        return await message.answer(f"😅 Зачекайте *{fmt_time(left)}*", parse_mode="Markdown")
    players = get_all_players_except(uid, 10)
    if not players:
        return await message.answer("❌ Немає жертв!")
    builder = InlineKeyboardBuilder()
    for p_uid, p_nick in players:
        builder.button(text=p_nick, callback_data=f"rob_{p_uid}_{p_nick}")
    builder.adjust(2)
    await message.answer("🔫 *Оберіть жертву для пограбування:*\n(у жертви має бути ≥200💰 на руках)", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("rob_"))
async def execute_rob(callback: types.CallbackQuery):
    _, target_uid, target_nick = callback.data.split("_", 2)
    robber_uid = str(callback.from_user.id)
    if robber_uid == target_uid:
        return await callback.answer("❌ Не можна себе!")
    async with get_user_lock(robber_uid), get_user_lock(target_uid):
        robber = get_user(robber_uid)
        if robber.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await callback.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not robber.get("registered") and callback.from_user.id != ADMIN_ID:
            return await callback.answer("❌ Зареєструйтесь!")
        target = user_data.get(target_uid)
        if not target or not target.get("registered") or target.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await callback.answer("❌ Не існує або заморожений!")
        if target["coins"] < 200:
            return await callback.answer(f"💸 У {target_nick} немає грошей!", show_alert=True)
        await apply_event_effects()
        if random.random() < 0.5:
            stolen = random.randint(100, min(2000, target["coins"] // 2)) * event_multipliers["rob"]
            stolen = int(stolen)
            target["coins"] -= stolen
            robber["coins"] += stolen
            robber["xp"] += 20
            robber["last_rob"] = time.time()
            robber["rob_count"] = robber.get("rob_count", 0) + 1
            robber.setdefault("stats", {})["rob_count"] = robber["stats"].get("rob_count", 0) + 1
            rank_up = check_rank_up(robber)
            await save_data()
            await update_quest_progress(robber_uid, "rob")
            rank_line = f"\n🎉 *Новий ранг: {rank_up}!*" if rank_up else ""
            await callback.message.edit_text(f"✅ *Пограбування вдалося!*\nВи вкрали `{stolen:,} 💰` у `{target_nick}`\n+20 XP{rank_line}", parse_mode="Markdown")
        else:
            fine = random.randint(150, 400)
            robber["coins"] = max(0, robber["coins"] - fine)
            await save_data()
            await callback.message.edit_text(f"🚔 *Спіймала поліція!*\nСпроба пограбувати `{target_nick}` провалилась!\nШтраф: `{fine:,} 💰`", parse_mode="Markdown")
    await callback.answer()

# ========== ІГРИ ==========
@dp.message(F.text == "🎲 Ігри")
async def games_h(message: types.Message):
    await message.answer(
        "🎰 *Ігровий зал:*\n━━━━━━━━━━━━━━━━\n"
        "🎲 `/dice [ставка]` — гра в кості\n"
        "🪙 `/flip [ставка]` — орел чи решка\n"
        "🎰 `/slots [ставка]` — однорукий бандит\n\n"
        "⚠️ Мінімальна ставка: `100 💰`\n"
        "⚠️ Для новачків (XP < 500) максимальна ставка — 30% від готівки.",
        parse_mode="Markdown"
    )

async def check_bet_newbie(message, command, d):
    try:
        bet = int(command.args)
    except:
        await message.answer("❌ Ставка числом!")
        return None
    if bet < 100:
        await message.answer("❌ Мінімальна ставка 100 💰!")
        return None
    if bet > d["coins"]:
        await message.answer(f"❌ Недостатньо грошей! У вас {d['coins']:,} 💰")
        return None
    if is_newbie(d):
        max_bet = int(d["coins"] * 0.3)
        if bet > max_bet:
            await message.answer(f"⚠️ Ви новачок (XP < 500). Максимальна ставка для вас — 30% від готівки = {max_bet} 💰")
            return None
    return bet

@dp.message(Command("dice"))
async def dice_game(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return
        bet = await check_bet_newbie(message, command, d)
        if not bet:
            return
        pr, br = random.randint(1, 6), random.randint(1, 6)
        if pr > br:
            d["coins"] += bet
            d["xp"] += 10
            d.setdefault("stats", {})["games_won"] = d["stats"].get("games_won", 0) + 1
            res = f"✅ Виграли `{bet:,} 💰`! +10 XP"
            await update_quest_progress(uid, "dice_win")
        elif pr < br:
            d["coins"] -= bet
            d.setdefault("stats", {})["games_lost"] = d["stats"].get("games_lost", 0) + 1
            res = f"❌ Програли `{bet:,} 💰`!"
        else:
            res = "🤝 Нічия! Ставка повернута."
        check_achievements(d, uid)
        await save_data()
    await message.answer(f"🎲 *Гра в кості*\nВи: `{pr}` 🎲 | Бот: `{br}` 🎲\n{res}", parse_mode="Markdown")

@dp.message(Command("flip"))
async def flip_game(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return
        bet = await check_bet_newbie(message, command, d)
        if not bet:
            return
        if random.choice([True, False]):
            d["coins"] += bet
            d["xp"] += 5
            d.setdefault("stats", {})["games_won"] = d["stats"].get("games_won", 0) + 1
            res = f"🦅 Орел! Виграли `{bet:,} 💰`! +5 XP"
            await update_quest_progress(uid, "flip_win")
        else:
            d["coins"] -= bet
            d.setdefault("stats", {})["games_lost"] = d["stats"].get("games_lost", 0) + 1
            res = f"🔵 Решка! Програли `{bet:,} 💰`!"
        await save_data()
    await message.answer(f"🪙 *Орел чи решка*\n{res}", parse_mode="Markdown")

SLOT_SYMBOLS = ["🍋", "🍊", "🍇", "💎", "7️⃣", "🔔"]

@dp.message(Command("slots"))
async def slots_game(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return
        bet = await check_bet_newbie(message, command, d)
        if not bet:
            return
        s1, s2, s3 = random.choices(SLOT_SYMBOLS, k=3)
        if s1 == s2 == s3 == "7️⃣":
            mult = 10
            res = "🎉 ДЖЕКПОТ! x10"
            d["jackpot_win"] = True
        elif s1 == s2 == s3 == "💎":
            mult = 7
            res = "💎 ТРІПЛ ДІАМАНТ! x7"
        elif s1 == s2 == s3:
            mult = 4
            res = "🔥 Тріпл! x4"
        elif s1 == s2 or s2 == s3 or s1 == s3:
            mult = 2
            res = "✅ Пара! x2"
        else:
            mult = 0
            res = "❌ Не повезло!"
        if mult > 0:
            win = bet * mult - bet
            d["coins"] += win
            d["xp"] += mult * 3
            d.setdefault("stats", {})["games_won"] = d["stats"].get("games_won", 0) + 1
            res += f"\nВиграш: `{win:,} 💰` +{mult*3} XP"
            await update_quest_progress(uid, "slots_win")
        else:
            d["coins"] -= bet
            d.setdefault("stats", {})["games_lost"] = d["stats"].get("games_lost", 0) + 1
            res += f"\nПрограш: `{bet:,} 💰`"
        await save_data()
    await message.answer(f"🎰 *Слоти*\n[ {s1} | {s2} | {s3} ]\n{res}", parse_mode="Markdown")

# ========== ПРОФІЛЬ ==========
@dp.message(F.text == "👤 Профіль")
async def profile_h(message: types.Message):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return await message.answer("❌ Зареєструйтесь!")
        check_achievements(d, uid)
        await save_data()
        eq = d["equipped"]
        status = get_status(uid)
        age = d.get('age')
        total = d["coins"] + d["bank"]
        title = f" [{d.get('title', '')}]" if d.get('title') else ""
        status_line = f"\n🏷 Статус: {status}" if status else ""
        age_line = f"\n🎂 Вік: {age} років" if age else ""
        premium_line = f"\n💎 Преміум до: {fmt_time(max(0, int(d.get('premium_until', 0) - time.time())))}" if d.get('premium_until', 0) > time.time() else ""
        text = (
            f"👤 *{d['nickname']}{title}* | {d['level']}{status_line}{age_line}{premium_line}\n"
            f"┌─────────────────┐\n"
            f"│ 💰 Готівка:  `{d['coins']:,} 💰`\n"
            f"│ 🏦 Банк:     `{d['bank']:,} 💰`\n"
            f"│ 💎 Всього:   `{total:,} 💰`\n"
            f"│ ⭐️ Досвід:   `{d['xp']} XP`\n"
            f"│ 💎 Діаманти: `{d.get('diamonds', 0)}`\n"
            f"├─────────────────┤\n"
            f"│ 👕 *Екіпіровка:*\n"
            f"│   🧢 Голова: {eq['head']}\n"
            f"│   🛡 Торс:   {eq['body']}\n"
            f"│   👖 Штани:  {eq['pants']}\n"
            f"│   👟 Взуття: {eq['shoes']}\n"
            f"│   ⚔️ Зброя:   {d['equipped_weapon']} (шкода {d['weapon_damage']})\n"
            f"└─────────────────┘"
        )
    await message.answer(text, parse_mode="Markdown")

# ========== МАГАЗИН (НОВИЙ ПОВНОЦІННИЙ) ==========
SHOP_CATEGORIES = ["Голова", "Торс", "Штани", "Взуття", "Зброя"]
CAT_KEY = {"Голова": "head", "Торс": "body", "Штани": "pants", "Взуття": "shoes", "Зброя": "weapon"}
BASE_ITEM_NAMES = {
    "head": ["Бейсболка", "Шапка", "Кепка", "Бандана", "Каска", "Шолом", "Корона", "Тіара", "Шапка-вушанка", "Берет", "Капелюх", "Ковпак", "Тюрбан", "Шапка з козирком", "Панама", "Циліндр", "Балаклава", "Військова каска", "Золотий шолом"],
    "body": ["Футболка", "Светр", "Куртка", "Бронежилет", "Кольчуга", "Кіраса", "Золотий костюм", "Плащ", "Мантія", "Тельняшка", "Дублянка", "Шкіряна куртка", "Пончо", "Халат", "Військовий мундир", "Лицарські лати", "Роба мага", "Кімоно", "Піджак"],
    "pants": ["Шорти", "Джинси", "Спортивки", "Штани", "Кюлоти", "Легінси", "Шкіряні штани", "Броньовані штани", "Штани-кльош", "Бермуди", "Карго", "Парашутні штани", "Лосини", "Бриджі", "Гольфи", "Спідниця-штани", "Військові штани", "Штани з лампасами", "Піжамні штани"],
    "shoes": ["Сандалі", "Кросівки", "Туфлі", "Босоніжки", "Черевики", "Уггі", "Ковбойські чоботи", "Ботфорти", "Лабутени", "Балетки", "Мокасини", "Кеди", "Сліпони", "Трекінгові черевики", "Шльопанці", "Берці", "Туфлі-човники", "Чоботи-панчохи", "Золоті кросівки"],
    "weapon": ["Кулаки 👊", "Ніж 🔪", "Пістолет 🔫", "Автомат 🎯", "Гвинтівка", "Дробовик", "Снайперка", "Гранатомет", "Лазер", "Меч", "Бойова сокира", "Спис", "Лук", "Арбалет", "Вогнемет", "Електрошокер", "Бойовий молот", "Катана", "Плазмова гармата"]
}

def get_item_price_shop(level: int) -> int:
    """Ціна предмета рівня level (level 1..20)"""
    return 100 * (10 ** (level - 1))

def get_item_bonus(cat_key: str, level: int) -> int:
    if cat_key == "weapon":
        return 5 + level * 45   # шкода
    else:
        return level * 100      # захист

@dp.message(F.text == "🛍 Магазин")
async def shop_main(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    builder = InlineKeyboardBuilder()
    for cat in SHOP_CATEGORIES:
        builder.button(text=cat, callback_data=f"shop_cat_{cat}")
    builder.button(text="💎 Магазин за діаманти", callback_data="shop_diamonds")
    builder.adjust(2)
    await message.answer(f"🛍 *Магазин Bandit*\n💰 Ваш баланс: `{d['coins']:,} 💰`\n💎 Діаманти: `{d.get('diamonds', 0)}`\n\nОберіть категорію:", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("shop_cat_"))
async def shop_category(callback: types.CallbackQuery):
    cat = callback.data.split("_")[2]   # "Голова" etc.
    uid = str(callback.from_user.id)
    d = get_user(uid)
    cat_key = CAT_KEY.get(cat)
    if not cat_key:
        return await callback.answer("❌ Невідома категорія!")
    # Показуємо предмети 1..20 рівня
    text = f"🛍 *{cat}*\nОберіть рівень предмета (1-20):\n"
    builder = InlineKeyboardBuilder()
    for lvl in range(1, 21):
        price = get_item_price_shop(lvl)
        bonus = get_item_bonus(cat_key, lvl)
        if cat_key == "weapon":
            bonus_text = f"шкода +{bonus}"
        else:
            bonus_text = f"захист +{bonus}"
        builder.button(text=f"{lvl} рівень — {price:,}💰 ({bonus_text})", callback_data=f"shop_buy_{cat_key}_{lvl}")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("shop_buy_"))
async def shop_buy_item(callback: types.CallbackQuery):
    _, cat_key, level_str = callback.data.split("_")
    level = int(level_str)
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await callback.answer("❌ Акаунт заморожено або світ на паузі!", show_alert=True)
        if not d.get("registered") and callback.from_user.id != ADMIN_ID:
            return await callback.answer("❌ Зареєструйтесь!")
        price = get_item_price_shop(level)
        if d["coins"] < price:
            return await callback.answer(f"❌ Не вистачає {price - d['coins']:,}💰", show_alert=True)
        # Генеруємо назву предмета
        names = BASE_ITEM_NAMES.get(cat_key, ["Річ"])
        item_name = f"{random.choice(names)} {level}р"
        d["inventory"][item_name] = d["inventory"].get(item_name, 0) + 1
        d["coins"] -= price
        await save_data()
    await callback.message.edit_text(f"✅ Ви придбали *{item_name}* за `{price:,} 💰`! Використайте `/wear {item_name}` щоб надіти.", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "shop_diamonds")
async def shop_diamonds(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    d = get_user(uid)
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Преміум (30 днів) - 100💎", callback_data="buy_premium_30")
    builder.button(text="🐉 Дракончик (домашній улюбленець) - 50💎", callback_data="buy_pet_dragon")
    builder.button(text="🎁 Кейс зі скіном - 20💎", callback_data="buy_case_skin")
    builder.button(text="⚡️ Подвоєння досвіду (1 год) - 10💎", callback_data="buy_xp_boost")
    builder.adjust(1)
    await callback.message.edit_text(
        f"💎 *Магазин за діаманти*\nВаші діаманти: {d.get('diamonds', 0)}\n\n"
        "• Преміум (30 днів) – x2 до всіх доходів\n"
        "• Дракончик – дає +10% до шкоди в бою\n"
        "• Кейс зі скіном – випадковий унікальний скін зброї\n"
        "• Подвоєння досвіду на 1 годину",
        reply_markup=builder.as_markup(), parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def handle_diamond_purchase(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    action = callback.data.split("_")[1]
    async with get_user_lock(uid):
        d = get_user(uid)
        diamonds = d.get("diamonds", 0)
        if action == "premium":
            if diamonds < 100:
                return await callback.answer("❌ Не вистачає діамантів!", show_alert=True)
            d["diamonds"] -= 100
            d["premium_until"] = time.time() + 30*86400
            await save_data()
            await callback.message.edit_text("✅ Ви купили Преміум на 30 днів!")
        elif action == "pet":
            if diamonds < 50:
                return await callback.answer("❌ Не вистачає діамантів!", show_alert=True)
            d["diamonds"] -= 50
            d["pet"] = "Дракончик 🐉"
            await save_data()
            await callback.message.edit_text("✅ Ви отримали дракончика! Він дає +10% до шкоди в бою.")
        elif action == "case":
            if diamonds < 20:
                return await callback.answer("❌ Не вистачає діамантів!", show_alert=True)
            d["diamonds"] -= 20
            skins = ["Вогняний меч 🔥", "Льодяна сокира ❄️", "Блискавка ⚡️", "Демонічний ніж 😈"]
            skin = random.choice(skins)
            d["inventory"][skin] = d["inventory"].get(skin, 0) + 1
            await save_data()
            await callback.message.edit_text(f"✅ Ви відкрили кейс і отримали скін: {skin}!")
        elif action == "xp":
            if diamonds < 10:
                return await callback.answer("❌ Не вистачає діамантів!", show_alert=True)
            d["diamonds"] -= 10
            d["work_boost_until"] = time.time() + 3600
            await save_data()
            await callback.message.edit_text("✅ Подвоєння досвіду активовано на 1 годину!")
    await callback.answer()

# ========== КОМАНДА /wear ==========
@dp.message(Command("wear"))
async def wear_item(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    if not command.args:
        return await message.answer("⚠️ `/wear [назва предмета з інвентаря]`")
    item_name = command.args.strip()
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return await message.answer("❌ Зареєструйтесь!")
        count = d["inventory"].get(item_name, 0)
        if count == 0:
            return await message.answer(f"❌ У вас немає предмета `{item_name}` в інвентарі!", parse_mode="Markdown")
        # Визначити тип предмета (зброя чи броня) за назвою або за категорією з магазину
        # Спрощено: якщо в назві є "меч", "ніж", "пістолет", то зброя, інакше – броня.
        # Але краще зберігати категорію при покупці. Для простоти зробимо за ключовими словами.
        weapon_keywords = ["меч", "ніж", "пістолет", "автомат", "гвинтівка", "дробовик", "снайперка", "гранатомет", "лазер", "сокира", "спис", "лук", "арбалет", "вогнемет", "електрошокер", "молот", "катана", "гармата", "кулаки"]
        armor_keywords = ["шапка", "каска", "шолом", "корона", "тіара", "берет", "капелюх", "ковпак", "тюрбан", "панама", "циліндр", "балаклава", "футболка", "светр", "куртка", "бронежилет", "кольчуга", "кіраса", "костюм", "плащ", "мантія", "тельняшка", "дублянка", "пончо", "халат", "мундир", "лати", "роба", "кімоно", "піджак", "шорти", "джинси", "спортивки", "штани", "кюлоти", "леґінси", "шкіряні штани", "бермуди", "карго", "лосини", "бриджі", "гольфи", "піжамні штани", "сандалі", "кросівки", "туфлі", "босоніжки", "черевики", "уггі", "чоботи", "ботфорти", "лабутени", "балетки", "мокасини", "кеди", "сліпони", "шльопанці", "берці"]
        is_weapon = any(kw in item_name.lower() for kw in weapon_keywords)
        is_armor = any(kw in item_name.lower() for kw in armor_keywords)
        if not is_weapon and not is_armor:
            return await message.answer("❌ Не вдалося визначити тип предмета. Для зброї використовуйте слова зі списку, для броні – відповідні назви.")
        if is_weapon:
            # Отримуємо бонус шкоди: пробуємо витягти число з назви (наприклад "Меч 5р" -> 5)
            import re
            match = re.search(r'(\d+)р', item_name)
            if match:
                level = int(match.group(1))
                damage_bonus = get_item_bonus("weapon", level)
                d["weapon_damage"] = damage_bonus
                d["equipped_weapon"] = item_name
                await save_data()
                await message.answer(f"✅ Ви екіпірували зброю *{item_name}*! Шкода зброї тепер {damage_bonus}.", parse_mode="Markdown")
            else:
                # Скін або особливий предмет – дає фіксований бонус
                special_bonus = random.randint(50, 200)
                d["weapon_damage"] = special_bonus
                d["equipped_weapon"] = item_name
                await save_data()
                await message.answer(f"✅ Ви екіпірували скін *{item_name}*! Шкода +{special_bonus}.", parse_mode="Markdown")
        else:
            # Броня – визначаємо частину тіла за ключовими словами
            head_words = ["шапка", "каска", "шолом", "корона", "тіара", "берет", "капелюх", "ковпак", "тюрбан", "панама", "циліндр", "балаклава"]
            body_words = ["футболка", "светр", "куртка", "бронежилет", "кольчуга", "кіраса", "костюм", "плащ", "мантія", "тельняшка", "дублянка", "пончо", "халат", "мундир", "лати", "роба", "кімоно", "піджак"]
            pants_words = ["шорти", "джинси", "спортивки", "штани", "кюлоти", "леґінси", "шкіряні штани", "бермуди", "карго", "лосини", "бриджі", "гольфи", "піжамні штани"]
            shoes_words = ["сандалі", "кросівки", "туфлі", "босоніжки", "черевики", "уггі", "чоботи", "ботфорти", "лабутени", "балетки", "мокасини", "кеди", "сліпони", "шльопанці", "берці"]
            slot = None
            if any(w in item_name.lower() for w in head_words):
                slot = "head"
            elif any(w in item_name.lower() for w in body_words):
                slot = "body"
            elif any(w in item_name.lower() for w in pants_words):
                slot = "pants"
            elif any(w in item_name.lower() for w in shoes_words):
                slot = "shoes"
            if not slot:
                return await message.answer("❌ Не вдалося визначити слот для броні (голова/торс/штани/взуття).")
            match = re.search(r'(\d+)р', item_name)
            if match:
                level = int(match.group(1))
                protection = get_item_bonus(slot, level)  # для броні той самий розрахунок
                d["equipped"][slot] = item_name
                d["armor_stats"][slot] = protection
                await save_data()
                await message.answer(f"✅ Ви наділи *{item_name}* на слот {slot}. Захист +{protection}.", parse_mode="Markdown")
            else:
                # Скін броні
                protection = random.randint(50, 200)
                d["equipped"][slot] = item_name
                d["armor_stats"][slot] = protection
                await save_data()
                await message.answer(f"✅ Ви наділи скін *{item_name}* на слот {slot}. Захист +{protection}.", parse_mode="Markdown")

# ========== ІНВЕНТАР ==========
@dp.message(F.text == "📦 Інвентар")
async def inventory_menu(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    inv = d.get("inventory", {})
    if not inv:
        await message.answer("📦 *Ваш інвентар порожній.*", parse_mode="Markdown")
        return
    text = "📦 *Ваш інвентар:*\n"
    for item, count in inv.items():
        text += f"• {item} — {count} шт.\n"
    await message.answer(text, parse_mode="Markdown")

# ========== ФЕРМИ ==========
MAX_FARM_LEVEL = 30
BASE_FARM_PRICE = 10000
BASE_FARM_INCOME_MIN = 300
PRICE_MULT = 2.2
INC_MULT = 1.8
FARM_CD = 1800

def get_farm_price(level):
    if level <= 0:
        return 0
    if level > MAX_FARM_LEVEL:
        level = MAX_FARM_LEVEL
    return int(BASE_FARM_PRICE * (PRICE_MULT ** (level - 1)))

def get_farm_income_range(level):
    if level <= 0:
        return 0, 0
    if level > MAX_FARM_LEVEL:
        level = MAX_FARM_LEVEL
    min_inc = int(BASE_FARM_INCOME_MIN * (INC_MULT ** (level - 1)))
    return min_inc, min_inc * 2

def get_user_farm(uid):
    d = get_user(uid)
    if "farm" not in d:
        d["farm"] = {"level": 0, "last_harvest": 0}
        asyncio.ensure_future(save_data())
    else:
        if d["farm"].get("level", 0) > MAX_FARM_LEVEL:
            d["farm"]["level"] = MAX_FARM_LEVEL
            asyncio.ensure_future(save_data())
    return d["farm"]

@dp.message(F.text == "🏭 Ферми")
async def farms_menu(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return
    farm = get_user_farm(uid)
    if farm["level"] == 0:
        price = get_farm_price(1)
        inc_min, inc_max = get_farm_income_range(1)
        builder = InlineKeyboardBuilder()
        builder.button(text=f"Купити ферму ({price:,}💰)", callback_data="buy_farm_1")
        await message.answer(
            f"🏭 *Ферми*\n━━━━━━━━━━━━━━━━\n🌱 У вас ще немає ферми. Перший рівень:\n💰 Ціна: `{price:,} 💰`\n🌾 Дохід: `{inc_min}-{inc_max} 💰`\n⏳ Кулдаун: `{fmt_time(FARM_CD)}`\n\nНатисніть кнопку, щоб купити.",
            reply_markup=builder.as_markup(), parse_mode="Markdown"
        )
        return
    lvl = farm["level"]
    last = farm.get("last_harvest", 0)
    left = cooldown_left(last, FARM_CD)
    inc_min, inc_max = get_farm_income_range(lvl)
    can = left == 0
    text = f"🏭 *Ваша ферма* (рівень {lvl})\n━━━━━━━━━━━━━━━━\n🌾 Дохід: `{inc_min}-{inc_max} 💰`\n⏳ Кулдаун: `{fmt_time(FARM_CD)}`\n💎 Статус: {'✅ Готово до збору' if can else f'⏳ Чекайте {fmt_time(left)}'}\n\n"
    if lvl < MAX_FARM_LEVEL:
        nxt_lvl = lvl + 1
        nxt_price = get_farm_price(nxt_lvl)
        nxt_min, nxt_max = get_farm_income_range(nxt_lvl)
        builder = InlineKeyboardBuilder()
        if can:
            builder.button(text="🌾 Зібрати врожай", callback_data="harvest_farm")
        builder.button(text=f"⬆ Покращити до {nxt_lvl} ({nxt_price:,}💰)", callback_data=f"buy_farm_{nxt_lvl}")
        builder.button(text="⏫ Прокачати на максимум", callback_data="upgrade_max_farm")
        builder.adjust(1)
        text += f"⬆ *Наступний рівень:*\n   Ціна: `{nxt_price:,} 💰`\n   Дохід: `{nxt_min}-{nxt_max} 💰`\n\n⏫ Натисніть «Прокачати на максимум», щоб купити всі можливі рівні одразу."
    else:
        builder = InlineKeyboardBuilder()
        if can:
            builder.button(text="🌾 Зібрати врожай", callback_data="harvest_farm")
        builder.adjust(1)
        text += "🏁 *Максимальний рівень! (30)*"
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "upgrade_max_farm")
async def upgrade_max_farm(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await callback.answer("❌ Акаунт заморожено або світ на паузі!", show_alert=True)
        farm = get_user_farm(uid)
        if farm["level"] == 0:
            return
        lvl = farm["level"]
        total_spent = 0
        total_tax = 0
        bought = 0
        while lvl < MAX_FARM_LEVEL:
            nxt = lvl + 1
            price = get_farm_price(nxt)
            if d["coins"] < price:
                break
            d["coins"] -= price
            tax = int(price * 0.05)
            d["coins"] -= tax
            total_spent += price
            total_tax += tax
            lvl = nxt
            bought += 1
        if bought == 0:
            return await callback.answer("❌ У вас недостатньо грошей навіть на один рівень!", show_alert=True)
        farm["level"] = lvl
        farm["last_harvest"] = 0
        await save_data()
    inc_min, inc_max = get_farm_income_range(lvl)
    await callback.message.answer(
        f"⏫ *Ферму прокачано на максимум!*\n🆙 Куплено рівнів: {bought}\n🏆 Новий рівень: {lvl}\n💰 Витрачено: `{total_spent:,} 💰`\n👑 5% податку: `{total_tax:,} 💰` (згорів)\n🌾 Тепер дохід: `{inc_min}-{inc_max} 💰` за збір.",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_farm_"))
async def buy_farm(callback: types.CallbackQuery):
    level = int(callback.data.split("_")[2])
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await callback.answer("❌ Акаунт заморожено або світ на паузі!", show_alert=True)
        farm = get_user_farm(uid)
        if level <= farm["level"] or level > MAX_FARM_LEVEL:
            return await callback.answer("❌ Неможливо!")
        price = get_farm_price(level)
        if d["coins"] < price:
            return await callback.answer(f"❌ Не вистачає {price - d['coins']:,} 💰", show_alert=True)
        d["coins"] -= price
        tax = int(price * 0.05)
        d["coins"] -= tax
        farm["level"] = level
        farm["last_harvest"] = 0
        await save_data()
    await callback.message.answer(f"✅ Ферма рівня {level} куплена!\n👑 Податок (5%): `{tax:,} 💰` (згорів)", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "harvest_farm")
async def harvest_farm(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await callback.answer("❌ Акаунт заморожено або світ на паузі!", show_alert=True)
        farm = get_user_farm(uid)
        if farm["level"] == 0:
            return
        left = cooldown_left(farm.get("last_harvest", 0), FARM_CD)
        if left > 0:
            return await callback.answer(f"⏳ Зачекайте ще {fmt_time(left)}", show_alert=True)
        await apply_event_effects()
        inc_min, inc_max = get_farm_income_range(farm["level"])
        income = int(random.randint(inc_min, inc_max) * event_multipliers["farm"])
        if d.get("premium_until", 0) > time.time():
            income *= 2
        gang_bonus = get_gang_bonus(uid)
        income = int(income * gang_bonus)
        d["coins"] += income
        d["xp"] += 10
        farm["last_harvest"] = time.time()
        d.setdefault("stats", {})["farm_count"] = d["stats"].get("farm_count", 0) + 1
        await save_data()
    await update_quest_progress(uid, "farm")
    gang_line = f" (+{int((gang_bonus-1)*100)}% від банди)" if gang_bonus > 1 else ""
    premium_line = " 💎 x2 (преміум)" if d.get("premium_until", 0) > time.time() else ""
    await callback.message.edit_text(f"🌾 *Ви зібрали врожай!*{gang_line}{premium_line}\nОтримано: `{income:,} 💰` +10 XP", parse_mode="Markdown")
    await callback.answer()

# ========== БІРЖА ==========
STOCK_FILE = "stock_data.json"
def load_stock_data():
    if os.path.exists(STOCK_FILE):
        try:
            with open(STOCK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"prices": {"Крипта": 5000, "Нафта": 3000, "Зброя": 8000, "Нерухомість": 12000}, "last_update": 0}

stock_data = load_stock_data()

async def save_stock_data():
    async with file_lock:
        with open(STOCK_FILE, "w", encoding="utf-8") as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=4)

def update_stock_prices():
    now = time.time()
    if now - stock_data["last_update"] >= 1800:
        for sym in stock_data["prices"]:
            change = random.uniform(-0.1, 0.1)
            stock_data["prices"][sym] = max(1, int(stock_data["prices"][sym] * (1 + change)))
        stock_data["last_update"] = now
        asyncio.ensure_future(save_stock_data())

@dp.message(F.text == "📈 Біржа")
async def stock_exchange(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return
    update_stock_prices()
    text = "📈 *Біржа Bandit*\n━━━━━━━━━━━━━━━━\n"
    builder = InlineKeyboardBuilder()
    for sym, price in stock_data["prices"].items():
        owned = d["stocks"].get(sym, 0)
        text += f"*{sym}* — `{price:,} 💰` (у вас: {owned})\n"
        builder.button(text=f"Купити {sym}", callback_data=f"stock_buy_{sym}")
        builder.button(text=f"Продати {sym}", callback_data=f"stock_sell_{sym}")
        builder.button(text=f"Макс {sym}", callback_data=f"stock_max_{sym}")
    builder.adjust(2)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("stock_"))
async def stock_operation(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await callback.answer("❌ Акаунт заморожено або світ на паузі!", show_alert=True)
        if not d.get("registered") and callback.from_user.id != ADMIN_ID:
            return await callback.answer("❌ Зареєструйтесь!")
        _, action, symbol = callback.data.split("_")
        update_stock_prices()
        price = stock_data["prices"][symbol]
        if action == "buy":
            if d["coins"] < price:
                return await callback.answer("❌ Недостатньо грошей!", show_alert=True)
            d["coins"] -= price
            tax = int(price * 0.05)
            d["coins"] -= tax
            d["stocks"][symbol] = d["stocks"].get(symbol, 0) + 1
            await save_data()
            await callback.answer(f"✅ Куплено 1 {symbol} за {price:,} 💰 (комісія {tax:,} згоріла)")
        elif action == "sell":
            owned = d["stocks"].get(symbol, 0)
            if owned <= 0:
                return await callback.answer("❌ У вас немає цієї акції!", show_alert=True)
            d["coins"] += price
            tax = int(price * 0.05)
            d["coins"] -= tax
            d["stocks"][symbol] = owned - 1
            if d["stocks"][symbol] == 0:
                del d["stocks"][symbol]
            await save_data()
            await callback.answer(f"✅ Продано 1 {symbol} за {price:,} 💰 (комісія {tax:,} згоріла)")
        elif action == "max":
            if price <= 0:
                return
            max_qty = d["coins"] // price
            if max_qty == 0:
                return await callback.answer("❌ Недостатньо грошей!", show_alert=True)
            total = max_qty * price
            d["coins"] -= total
            tax = int(total * 0.05)
            d["coins"] -= tax
            d["stocks"][symbol] = d["stocks"].get(symbol, 0) + max_qty
            await save_data()
            await callback.answer(f"✅ Куплено {max_qty} {symbol} за {total:,} 💰 (комісія {tax:,} згоріла)")
    await callback.message.edit_reply_markup(reply_markup=None)

# ========== БОЙОВА СИСТЕМА (виправлено тренувальний бій + автовідновлення) ==========
CLASSES = {
    "warrior": {"name": "Воїн ⚔️", "hp_bonus": 1.2, "dmg_bonus": 1.15, "mp_bonus": 0.8, "skill": "berserk", "skill_desc": "Подвоює шкоду на 1 хід (20 мани)"},
    "mage": {"name": "Маг 🔮", "hp_bonus": 0.8, "dmg_bonus": 1.3, "mp_bonus": 1.5, "skill": "fireball", "skill_desc": "Атакує зі шкодою x3, витрачає 30 мани"},
    "rogue": {"name": "Злодій 🗡️", "hp_bonus": 0.9, "dmg_bonus": 1.2, "mp_bonus": 1.0, "skill": "crit", "skill_desc": "100% критичний удар (x2 шкода), 15 мани"},
    "healer": {"name": "Лікар 💊", "hp_bonus": 0.9, "dmg_bonus": 0.7, "mp_bonus": 1.4, "skill": "heal", "skill_desc": "Відновлює 30% HP, 25 мани"},
}

BOSSES = {
    "Гоблін 🏹": {"hp": 150, "dmg": 15, "reward_coins": 5000, "reward_xp": 100, "reward_diamonds": 1},
    "Троль 🗿": {"hp": 300, "dmg": 25, "reward_coins": 15000, "reward_xp": 300, "reward_diamonds": 3},
    "Дракон 🐉": {"hp": 600, "dmg": 40, "reward_coins": 50000, "reward_xp": 800, "reward_diamonds": 10},
    "Ліч 💀": {"hp": 1000, "dmg": 60, "reward_coins": 100000, "reward_xp": 1500, "reward_diamonds": 20},
}

FIGHT_CD = 300

@dp.message(Command("setclass"))
async def set_class(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    args = command.args.split() if command.args else []
    if not args:
        kb = InlineKeyboardBuilder()
        for key, val in CLASSES.items():
            kb.button(text=val["name"], callback_data=f"setclass_{key}")
        kb.adjust(2)
        return await message.answer("🎭 *Оберіть свій клас:*", reply_markup=kb.as_markup(), parse_mode="Markdown")
    class_key = args[0].lower()
    if class_key not in CLASSES:
        return await message.answer("❌ Невірний клас! Доступні: warrior, mage, rogue, healer")
    async with get_user_lock(uid):
        d = get_user(uid)
        d["class"] = class_key
        base_hp = 100
        base_mp = 50
        d["max_hp"] = int(base_hp * CLASSES[class_key]["hp_bonus"])
        d["hp"] = d["max_hp"]
        d["max_mp"] = int(base_mp * CLASSES[class_key]["mp_bonus"])
        d["mp"] = d["max_mp"]
        await save_data()
    await message.answer(f"✅ Ваш клас: {CLASSES[class_key]['name']}!\n❤️ HP: {d['max_hp']}\n💙 MP: {d['max_mp']}\n✨ Навичка: {CLASSES[class_key]['skill_desc']}")

@dp.callback_query(lambda c: c.data.startswith("setclass_"))
async def setclass_callback(callback: types.CallbackQuery):
    class_key = callback.data.split("_")[1]
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        d["class"] = class_key
        base_hp = 100
        base_mp = 50
        d["max_hp"] = int(base_hp * CLASSES[class_key]["hp_bonus"])
        d["hp"] = d["max_hp"]
        d["max_mp"] = int(base_mp * CLASSES[class_key]["mp_bonus"])
        d["mp"] = d["max_mp"]
        await save_data()
    await callback.message.edit_text(f"✅ Ваш клас: {CLASSES[class_key]['name']}!\n❤️ HP: {d['max_hp']}\n💙 MP: {d['max_mp']}\n✨ Навичка: {CLASSES[class_key]['skill_desc']}")
    await callback.answer()

@dp.message(F.text == "⚔️ Бій")
async def fight_main(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    if not d.get("class"):
        return await message.answer("❌ Спочатку оберіть клас: `/setclass`")
    left = cooldown_left(d.get("last_fight", 0), FIGHT_CD)
    if left > 0:
        return await message.answer(f"⏳ Ви втомилися після бою. Відпочиньте ще {fmt_time(left)}")
    builder = InlineKeyboardBuilder()
    builder.button(text="⚔️ PvP (арена)", callback_data="fight_mode_pvp")
    builder.button(text="🐉 PvE (бос)", callback_data="fight_mode_pve")
    builder.button(text="🤖 Тренувальний бій", callback_data="fight_mode_train")
    builder.button(text="📊 Моя статистика боїв", callback_data="fight_stats")
    builder.adjust(1)
    await message.answer(
        "⚔️ *Виберіть режим бою:*\n"
        "• PvP – бій з іншим гравцем. Впливає на Elo рейтинг.\n"
        "• PvE – бій з босом. Нагороди: монети, XP, діаманти.\n"
        "• Тренувальний – без ризику, але менше нагороди.\n\n"
        f"❤️ Ваше HP: {d['hp']}/{d['max_hp']}\n💙 MP: {d['mp']}/{d['max_mp']}\n🏆 Elo: {d.get('elo', 1200)}",
        reply_markup=builder.as_markup(), parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "fight_stats")
async def fight_stats(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    d = get_user(uid)
    text = (
        f"📊 *Статистика боїв {d['nickname']}:*\n"
        f"⚔️ PvP перемог: {d.get('pvp_wins', 0)}\n"
        f"⚔️ PvP поразок: {d.get('pvp_losses', 0)}\n"
        f"🐉 PvE перемог: {d.get('pve_wins', 0)}\n"
        f"🐉 PvE поразок: {d.get('pve_losses', 0)}\n"
        f"🏆 Elo рейтинг: {d.get('elo', 1200)}\n"
        f"❤️ Поточне HP: {d.get('hp', 0)}/{d.get('max_hp', 0)}\n"
        f"💙 MP: {d.get('mp', 0)}/{d.get('max_mp', 0)}\n"
        f"🗡 Клас: {CLASSES.get(d.get('class'), {}).get('name', 'Не обрано')}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("fight_mode_"))
async def fight_mode_choice(callback: types.CallbackQuery):
    mode = callback.data.split("_")[2]
    uid = str(callback.from_user.id)
    d = get_user(uid)
    if d.get("hp", 0) <= 0:
        d["hp"] = d["max_hp"]
        d["mp"] = d["max_mp"]
        asyncio.ensure_future(save_data())
    if mode == "pvp":
        players = get_all_players_except(uid, 10)
        if not players:
            return await callback.answer("❌ Немає суперників для PvP!", show_alert=True)
        builder = InlineKeyboardBuilder()
        for p_uid, p_nick in players:
            p_data = get_user(p_uid)
            if p_data.get("class") and p_data.get("hp", 0) > 0:
                builder.button(text=f"{p_nick} (Elo: {p_data.get('elo',1200)})", callback_data=f"pvp_challenge_{p_uid}")
        builder.adjust(1)
        await callback.message.edit_text("⚔️ *Оберіть суперника для PvP:*", reply_markup=builder.as_markup(), parse_mode="Markdown")
    elif mode == "pve":
        builder = InlineKeyboardBuilder()
        for boss_name, boss_data in BOSSES.items():
            builder.button(text=f"{boss_name} (❤️{boss_data['hp']} ⚔️{boss_data['dmg']})", callback_data=f"pve_boss_{boss_name}")
        builder.adjust(1)
        await callback.message.edit_text("🐉 *Оберіть боса:*", reply_markup=builder.as_markup(), parse_mode="Markdown")
    elif mode == "train":
        await start_fight(uid, None, mode="train", callback=callback)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("pvp_challenge_"))
async def pvp_challenge(callback: types.CallbackQuery):
    target_uid = callback.data.split("_")[2]
    attacker_uid = str(callback.from_user.id)
    if attacker_uid == target_uid:
        return await callback.answer("❌ Не можна битися з собою!", show_alert=True)
    attacker = get_user(attacker_uid)
    defender = get_user(target_uid)
    if not defender.get("class") or defender.get("hp", 0) <= 0:
        return await callback.answer("❌ Суперник не готовий до бою (немає класу або HP = 0)", show_alert=True)
    if defender.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await callback.answer("❌ Суперник заморожений!", show_alert=True)
    fight_id = f"pvp_{int(time.time())}_{attacker_uid}_{target_uid}"
    pending_fights[fight_id] = {
        "attacker": attacker_uid,
        "defender": target_uid,
        "mode": "pvp",
        "status": "pending",
        "time": time.time()
    }
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Прийняти бій", callback_data=f"pvp_accept_{fight_id}")
    builder.button(text="❌ Відхилити", callback_data=f"pvp_decline_{fight_id}")
    try:
        await bot.send_message(target_uid, 
            f"⚔️ *Виклик на бій!*\n{attacker['nickname']} (Elo: {attacker.get('elo',1200)}) хоче битися з вами!\nЧас на відповідь: 60 секунд.",
            reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.message.edit_text(f"⏳ Запит на бій надіслано {defender['nickname']}. Очікуйте відповіді...")
    except:
        pending_fights.pop(fight_id, None)
        await callback.answer("❌ Не вдалося сповістити суперника.", show_alert=True)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("pvp_accept_"))
async def pvp_accept(callback: types.CallbackQuery):
    fight_id = callback.data.split("_")[2]
    if fight_id not in pending_fights:
        return await callback.answer("❌ Запит застарів або скасований!", show_alert=True)
    fight = pending_fights[fight_id]
    if str(callback.from_user.id) != fight["defender"]:
        return await callback.answer("❌ Не ваш бій!", show_alert=True)
    fight["status"] = "active"
    await start_fight(fight["attacker"], fight["defender"], mode="pvp", fight_id=fight_id, callback=callback)

@dp.callback_query(lambda c: c.data.startswith("pvp_decline_"))
async def pvp_decline(callback: types.CallbackQuery):
    fight_id = callback.data.split("_")[2]
    if fight_id in pending_fights:
        fight = pending_fights.pop(fight_id)
        try:
            await bot.send_message(fight["attacker"], f"❌ {callback.from_user.first_name} відхилив ваш виклик на бій.")
        except: pass
    await callback.message.edit_text("❌ Ви відхилили бій.")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("pve_boss_"))
async def pve_boss_selected(callback: types.CallbackQuery):
    boss_name = callback.data.split("_", 2)[2]
    uid = str(callback.from_user.id)
    await start_fight(uid, None, mode="pve", boss_name=boss_name, callback=callback)

async def start_fight(attacker_uid, defender_uid=None, mode="pvp", boss_name=None, fight_id=None, callback=None):
    attacker = get_user(attacker_uid)
    if not attacker.get("class"):
        if callback:
            await callback.message.edit_text("❌ Оберіть клас через /setclass перед боєм!")
        return
    if attacker.get("hp", 0) <= 0:
        attacker["hp"] = attacker["max_hp"]
        attacker["mp"] = attacker["max_mp"]
        await save_data()
    fight_state = None
    if mode == "pvp":
        defender = get_user(defender_uid)
        if defender.get("hp", 0) <= 0 or not defender.get("class"):
            if callback:
                await callback.message.edit_text("❌ Суперник не готовий до бою!")
            return
        fight_state = {
            "attacker": attacker_uid,
            "defender": defender_uid,
            "attacker_hp": attacker["hp"],
            "defender_hp": defender["hp"],
            "attacker_max_hp": attacker["max_hp"],
            "defender_max_hp": defender["max_hp"],
            "attacker_mp": attacker["mp"],
            "defender_mp": defender["mp"],
            "turn": attacker_uid,
            "round": 1,
            "mode": "pvp"
        }
    elif mode == "pve":
        boss = BOSSES[boss_name]
        fight_state = {
            "attacker": attacker_uid,
            "boss_name": boss_name,
            "boss_hp": boss["hp"],
            "boss_max_hp": boss["hp"],
            "boss_dmg": boss["dmg"],
            "attacker_hp": attacker["hp"],
            "attacker_max_hp": attacker["max_hp"],
            "attacker_mp": attacker["mp"],
            "turn": attacker_uid,
            "round": 1,
            "mode": "pve"
        }
    elif mode == "train":
        fight_state = {
            "attacker": attacker_uid,
            "bot_name": "Тренувальний манекен",
            "bot_hp": 100,
            "bot_max_hp": 100,
            "bot_dmg": 10,
            "attacker_hp": attacker["hp"],
            "attacker_max_hp": attacker["max_hp"],
            "attacker_mp": attacker["mp"],
            "turn": attacker_uid,
            "round": 1,
            "mode": "train"
        }
    if fight_state:
        new_fight_id = f"fight_{int(time.time())}_{attacker_uid}"
        pending_fights[new_fight_id] = fight_state
        builder = InlineKeyboardBuilder()
        builder.button(text="⚔️ Атака", callback_data=f"fight_action_{new_fight_id}_attack")
        builder.button(text="💪 Сильна атака (20 MP)", callback_data=f"fight_action_{new_fight_id}_strong")
        builder.button(text="🛡 Захист", callback_data=f"fight_action_{new_fight_id}_defend")
        builder.button(text="💊 Зілля HP (+30% HP, 1 бій)", callback_data=f"fight_action_{new_fight_id}_heal")
        builder.button(text="✨ Навичка класу", callback_data=f"fight_action_{new_fight_id}_skill")
        builder.button(text="🏃 Втеча", callback_data=f"fight_action_{new_fight_id}_flee")
        builder.adjust(2)
        text = generate_fight_text(fight_state)
        if callback:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

def generate_fight_text(state):
    if state["mode"] == "pvp":
        attacker = get_user(state["attacker"])
        defender = get_user(state["defender"])
        return (f"⚔️ *Бій {attacker['nickname']} vs {defender['nickname']}*\nРаунд {state['round']}\n\n"
                f"❤️ *{attacker['nickname']}:* {state['attacker_hp']}/{state['attacker_max_hp']} HP | 💙 MP: {state['attacker_mp']}\n"
                f"❤️ *{defender['nickname']}:* {state['defender_hp']}/{state['defender_max_hp']} HP | 💙 MP: {state['defender_mp']}\n\n"
                f"👉 Хід: *{attacker['nickname'] if state['turn'] == state['attacker'] else defender['nickname']}*")
    elif state["mode"] == "pve":
        attacker = get_user(state["attacker"])
        return (f"🐉 *Бій з {state['boss_name']}*\nРаунд {state['round']}\n\n"
                f"❤️ *{attacker['nickname']}:* {state['attacker_hp']}/{state['attacker_max_hp']} HP | 💙 MP: {state['attacker_mp']}\n"
                f"❤️ *{state['boss_name']}:* {state['boss_hp']}/{state['boss_max_hp']} HP\n\n👉 Ваш хід!")
    else:
        attacker = get_user(state["attacker"])
        return (f"🤖 *Тренувальний бій з {state['bot_name']}*\nРаунд {state['round']}\n\n"
                f"❤️ *{attacker['nickname']}:* {state['attacker_hp']}/{state['attacker_max_hp']} HP | 💙 MP: {state['attacker_mp']}\n"
                f"❤️ *{state['bot_name']}:* {state['bot_hp']}/{state['bot_max_hp']}\n\n👉 Ваш хід!")

@dp.callback_query(lambda c: c.data.startswith("fight_action_"))
async def fight_action(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    fight_id = parts[2]
    action = parts[3]
    if fight_id not in pending_fights:
        return await callback.answer("❌ Бій завершено або недійсний!", show_alert=True)
    fight = pending_fights[fight_id]
    uid = str(callback.from_user.id)
    if fight["turn"] != uid:
        return await callback.answer("❌ Зараз не ваш хід!", show_alert=True)
    attacker = get_user(fight["attacker"])
    class_key = attacker.get("class", "warrior")
    base_dmg = attacker.get("weapon_damage", 5) * CLASSES[class_key]["dmg_bonus"]
    damage = 0
    message = ""
    if action == "attack":
        damage = int(base_dmg + random.randint(-5, 10))
        message = f"⚔️ Ви атакували! Шкода: {damage}"
    elif action == "strong":
        if attacker.get("mp", 0) < 20:
            return await callback.answer("❌ Недостатньо MP для сильної атаки!", show_alert=True)
        damage = int(base_dmg * 1.8)
        attacker["mp"] -= 20
        message = f"💪 Сильна атака! Шкода: {damage} (витрачено 20 MP)"
    elif action == "defend":
        fight["defending"] = True
        message = "🛡 Ви захищаєтесь! Наступна отримана шкода буде зменшена вдвічі."
    elif action == "heal":
        if fight.get("potion_used", False):
            return await callback.answer("❌ Ви вже використали зілля в цьому бою!", show_alert=True)
        heal_amount = int(attacker["max_hp"] * 0.3)
        fight["attacker_hp"] = min(fight["attacker_max_hp"], fight["attacker_hp"] + heal_amount)
        fight["potion_used"] = True
        message = f"💊 Ви використали зілля! Відновлено {heal_amount} HP"
    elif action == "skill":
        mp_cost = {"warrior": 20, "mage": 30, "rogue": 15, "healer": 25}
        cost = mp_cost.get(class_key, 20)
        if attacker.get("mp", 0) < cost:
            return await callback.answer(f"❌ Недостатньо MP! Потрібно {cost}", show_alert=True)
        attacker["mp"] -= cost
        if class_key == "warrior":
            damage = int(base_dmg * 2.5)
            message = f"✨ *Берсерк!* Шкода x2.5: {damage}"
        elif class_key == "mage":
            damage = int(base_dmg * 3.2)
            message = f"✨ *Вогняна куля!* Шкода x3.2: {damage}"
        elif class_key == "rogue":
            damage = int(base_dmg * 2.2)
            message = f"✨ *Критичний удар!* Шкода x2.2: {damage}"
        elif class_key == "healer":
            heal_self = int(attacker["max_hp"] * 0.4)
            fight["attacker_hp"] = min(fight["attacker_max_hp"], fight["attacker_hp"] + heal_self)
            message = f"✨ *Лікування!* Ви відновили {heal_self} HP"
    elif action == "flee":
        if random.random() < 0.3:
            message = "🏃 Ви втекли з бою!"
            pending_fights.pop(fight_id)
            await callback.message.edit_text(message, parse_mode="Markdown")
            return await callback.answer()
        else:
            message = "🏃 Спроба втечі не вдалася!"
    if damage > 0:
        if fight["mode"] == "pvp":
            fight["defender_hp"] -= damage
            if fight.get("defending"):
                fight["defender_hp"] += damage // 2
                fight["defending"] = False
        elif fight["mode"] == "pve":
            fight["boss_hp"] -= damage
        else:
            fight["bot_hp"] -= damage
    winner = None
    loser = None
    if fight["mode"] == "pvp":
        if fight["defender_hp"] <= 0:
            winner, loser = fight["attacker"], fight["defender"]
        elif fight["attacker_hp"] <= 0:
            winner, loser = fight["defender"], fight["attacker"]
    elif fight["mode"] == "pve":
        if fight["boss_hp"] <= 0:
            winner = fight["attacker"]
        elif fight["attacker_hp"] <= 0:
            loser = fight["attacker"]
    else:  # train
        if fight["bot_hp"] <= 0:
            winner = fight["attacker"]
        elif fight["attacker_hp"] <= 0:
            loser = fight["attacker"]
    if winner:
        win_data = await process_fight_result(winner, loser, fight)
        pending_fights.pop(fight_id)
        await callback.message.edit_text(win_data, parse_mode="Markdown")
        return await callback.answer()
    if loser:
        pending_fights.pop(fight_id)
        await callback.message.edit_text(f"💀 *Ви програли бій!* Відновлено 1 HP.", parse_mode="Markdown")
        return await callback.answer()
    if fight["mode"] == "pvp":
        fight["turn"] = fight["defender"] if fight["turn"] == fight["attacker"] else fight["attacker"]
    else:
        bot_dmg = fight["boss_dmg"] if fight["mode"] == "pve" else fight["bot_dmg"]
        bot_name = fight["boss_name"] if fight["mode"] == "pve" else fight["bot_name"]
        if fight.get("defending"):
            bot_dmg = bot_dmg // 2
            fight["defending"] = False
        fight["attacker_hp"] -= bot_dmg
        message += f"\n\n{bot_name} атакує! Шкода: {bot_dmg}"
        if fight["attacker_hp"] <= 0:
            loser = fight["attacker"]
            win_data = await process_fight_result(None, loser, fight)
            pending_fights.pop(fight_id)
            await callback.message.edit_text(win_data, parse_mode="Markdown")
            return await callback.answer()
        fight["turn"] = fight["attacker"]
    fight["round"] += 1
    pending_fights[fight_id] = fight
    builder = InlineKeyboardBuilder()
    builder.button(text="⚔️ Атака", callback_data=f"fight_action_{fight_id}_attack")
    builder.button(text="💪 Сильна атака (20 MP)", callback_data=f"fight_action_{fight_id}_strong")
    builder.button(text="🛡 Захист", callback_data=f"fight_action_{fight_id}_defend")
    builder.button(text="💊 Зілля HP", callback_data=f"fight_action_{fight_id}_heal")
    builder.button(text="✨ Навичка класу", callback_data=f"fight_action_{fight_id}_skill")
    builder.button(text="🏃 Втеча", callback_data=f"fight_action_{fight_id}_flee")
    builder.adjust(2)
    new_text = generate_fight_text(fight)
    await callback.message.edit_text(f"{message}\n\n{new_text}", reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

async def process_fight_result(winner_uid, loser_uid, fight):
    if fight["mode"] == "pvp" and winner_uid:
        winner = get_user(winner_uid)
        loser = get_user(loser_uid)
        winner_elo = winner.get("elo", 1200)
        loser_elo = loser.get("elo", 1200)
        expected = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
        elo_change = int(32 * (1 - expected))
        winner["elo"] += elo_change
        loser["elo"] = max(100, loser_elo - elo_change)
        winner["pvp_wins"] = winner.get("pvp_wins", 0) + 1
        loser["pvp_losses"] = loser.get("pvp_losses", 0) + 1
        reward = int(500 + winner_elo * 0.1)
        winner["coins"] += reward
        winner["xp"] += 100
        winner["last_fight"] = time.time()
        loser["last_fight"] = time.time()
        await save_data()
        await update_quest_progress(winner_uid, "pvp_win")
        return f"🏆 *Перемога!* {winner['nickname']} переміг {loser['nickname']}\n💰 +{reward} монет, +100 XP\n📈 Elo: +{elo_change} (тепер {winner['elo']})"
    elif fight["mode"] == "pve" and winner_uid:
        winner = get_user(winner_uid)
        boss = BOSSES[fight["boss_name"]]
        winner["coins"] += boss["reward_coins"]
        winner["xp"] += boss["reward_xp"]
        winner["diamonds"] = winner.get("diamonds", 0) + boss["reward_diamonds"]
        winner["pve_wins"] = winner.get("pve_wins", 0) + 1
        winner["last_fight"] = time.time()
        await save_data()
        await update_quest_progress(winner_uid, "pve_win")
        return f"🏆 *Перемога над {fight['boss_name']}!*\n💰 +{boss['reward_coins']} монет\n⭐ +{boss['reward_xp']} XP\n💎 +{boss['reward_diamonds']} діамантів"
    elif fight["mode"] == "train" and winner_uid:
        winner = get_user(winner_uid)
        reward = 200
        winner["coins"] += reward
        winner["xp"] += 20
        winner["last_fight"] = time.time()
        await save_data()
        return f"🏆 *Перемога в тренувальному бою!*\n💰 +{reward} монет, +20 XP"
    else:
        loser = get_user(loser_uid)
        loser["hp"] = 1
        loser["mp"] = loser["max_mp"] // 2
        loser["last_fight"] = time.time()
        if fight["mode"] == "pvp":
            loser["pvp_losses"] = loser.get("pvp_losses", 0) + 1
        elif fight["mode"] == "pve":
            loser["pve_losses"] = loser.get("pve_losses", 0) + 1
        await save_data()
        return f"💀 *Поразка!* Ви програли бій.\nВідновлено 1 HP та половину MP."

# ========== БАНДИ (спрощено, без воєн) ==========
MAX_GANG_MEMBERS = 20

def update_gang_level(gang_name):
    gang = gangs_data["gangs"][gang_name]
    if gang["treasury"] >= 10000:
        level = min(10, 1 + int((gang["treasury"] // 10000) ** 0.5))
        if level > gang["level"]:
            gang["level"] = level
            asyncio.ensure_future(save_gangs())
            return True
    return False

@dp.message(F.text == "🏴 Банда")
async def gang_main_menu(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return
    text = (
        "🏴 *Система банд*\n━━━━━━━━━━━━━━━━\n"
        "📌 `/creategang [назва]` – створити банду (тільки власник бота)\n"
        "📌 `/gang` – інформація про вашу банду\n"
        "📌 `/gangdep [сума]` – покласти гроші в казну\n"
        "📌 `/gangwith [сума]` – зняти з казни (лідер)\n"
        "📌 `/gangadd [нік]` – додати учасника (лідер)\n"
        "📌 `/gangremove [нік]` – вигнати учасника (лідер)\n"
        "📌 `/gangleave` – вийти з банди\n"
        "📌 `/gangtransfer [нік]` – передати лідерство\n"
        "📌 `/gangtop` – топ-5 банд\n\n"
        "💡 Банда дає бонус до заробітку: +5% за кожен рівень."
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("creategang"))
async def create_gang(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Тільки власник бота!")
    if not command.args:
        return await message.answer("⚠️ `/creategang <назва>`")
    gang_name = command.args.strip()[:20]
    uid = str(message.from_user.id)
    async with gangs_lock:
        if gang_name in gangs_data["gangs"]:
            return await message.answer("❌ Вже існує!")
        if uid in gangs_data["user_gang"]:
            return await message.answer("❌ Ви вже в банді!")
        gangs_data["gangs"][gang_name] = {
            "owner": uid, "level": 1, "treasury": 0, "members": [uid],
            "wars_won": 0, "wars_lost": 0, "created_at": time.time(), "member_contributions": {uid: 0}
        }
        gangs_data["user_gang"][uid] = gang_name
        await save_gangs()
    await message.answer(f"🏴 *Банда «{gang_name}» створена!* Рівень 1. Ви – лідер.", parse_mode="Markdown")

@dp.message(Command("gang"))
async def gang_info(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    async with gangs_lock:
        gang_name = gangs_data["user_gang"].get(uid)
        if not gang_name:
            return await message.answer("❌ Ви не в банді!")
        g = gangs_data["gangs"][gang_name]
        owner = get_user(g["owner"])
        bonus = int((get_gang_bonus(uid) - 1) * 100)
        members_text = []
        for m_uid in g["members"][:10]:
            u = get_user(m_uid)
            contrib = g["member_contributions"].get(m_uid, 0)
            members_text.append(f"• {u['nickname']} (вніс: {contrib:,}💰)")
        if len(g["members"]) > 10:
            members_text.append(f"... і ще {len(g['members']) - 10}")
        text = (
            f"🏴 *{gang_name}* (рівень {g['level']})\n"
            f"👑 Лідер: `{owner['nickname']}`\n💰 Казня: `{g['treasury']:,} 💰`\n📈 Бонус: +{bonus}%\n"
            f"👥 Учасники ({len(g['members'])}):\n" + "\n".join(members_text)
        )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("gangdep"))
async def gang_deposit(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    async with gangs_lock, get_user_lock(uid):
        gang_name = gangs_data["user_gang"].get(uid)
        if not gang_name:
            return await message.answer("❌ Ви не в банді!")
        try:
            amount = int(command.args)
        except:
            return await message.answer("❌ Введіть число!")
        if amount <= 0:
            return await message.answer("❌ Сума > 0")
        if d["coins"] < amount:
            return await message.answer(f"❌ У вас лише {d['coins']:,} 💰")
        d["coins"] -= amount
        g = gangs_data["gangs"][gang_name]
        g["treasury"] += amount
        g["member_contributions"][uid] = g["member_contributions"].get(uid, 0) + amount
        if update_gang_level(gang_name):
            await message.answer(f"🏆 Банда *{gang_name}* підвищила рівень до {g['level']}! Всі отримали +5% до бонусу!", parse_mode="Markdown")
        await save_data()
        await save_gangs()
    await message.answer(f"✅ Ви поклали `{amount:,} 💰` до казни *{gang_name}*!", parse_mode="Markdown")

@dp.message(Command("gangwith"))
async def gang_withdraw(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    async with gangs_lock:
        gang_name = gangs_data["user_gang"].get(uid)
        if not gang_name:
            return await message.answer("❌ Ви не в банді!")
        g = gangs_data["gangs"][gang_name]
        if g["owner"] != uid:
            return await message.answer("❌ Тільки лідер банди може знімати гроші!")
        try:
            amount = int(command.args)
        except:
            return await message.answer("❌ Введіть суму!")
        if amount <= 0 or amount > g["treasury"]:
            return await message.answer(f"❌ У казні лише {g['treasury']:,} 💰")
        g["treasury"] -= amount
        await save_gangs()
    async with get_user_lock(uid):
        d["coins"] += amount
        await save_data()
    await message.answer(f"✅ Ви зняли `{amount:,} 💰` з казни банди *{gang_name}*!", parse_mode="Markdown")

@dp.message(Command("gangadd"))
async def gang_add_member(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not command.args:
        return await message.answer("⚠️ `/gangadd [нікнейм]`")
    nick = command.args.strip()
    target_uid, td = find_user_by_nick(nick)
    if not td or not td.get("registered") or td.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer(f"❌ Гравця `{nick}` не знайдено або він заморожений!", parse_mode="Markdown")
    async with gangs_lock:
        gang_name = gangs_data["user_gang"].get(uid)
        if not gang_name:
            return await message.answer("❌ Ви не в банді!")
        g = gangs_data["gangs"][gang_name]
        if g["owner"] != uid:
            return await message.answer("❌ Тільки лідер може додавати учасників!")
        if len(g["members"]) >= MAX_GANG_MEMBERS:
            return await message.answer(f"❌ У банді вже {MAX_GANG_MEMBERS} учасників!")
        if target_uid in gangs_data["user_gang"]:
            return await message.answer("❌ Цей гравець вже в іншій банді!")
        gangs_data["user_gang"][target_uid] = gang_name
        g["members"].append(target_uid)
        g["member_contributions"][target_uid] = 0
        await save_gangs()
    await message.answer(f"✅ `{nick}` додано до банди *{gang_name}*!", parse_mode="Markdown")

@dp.message(Command("gangremove"))
async def gang_remove_member(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not command.args:
        return await message.answer("⚠️ `/gangremove [нікнейм]`")
    nick = command.args.strip()
    target_uid, td = find_user_by_nick(nick)
    if not td:
        return await message.answer(f"❌ Гравця `{nick}` не знайдено!", parse_mode="Markdown")
    async with gangs_lock:
        gang_name = gangs_data["user_gang"].get(uid)
        if not gang_name:
            return await message.answer("❌ Ви не в банді!")
        g = gangs_data["gangs"][gang_name]
        if g["owner"] != uid:
            return await message.answer("❌ Тільки лідер може виганяти!")
        if target_uid not in g["members"]:
            return await message.answer("❌ Цей гравець не в вашій банді!")
        if target_uid == uid:
            return await message.answer("❌ Ви не можете вигнати себе! Використайте `/gangleave`")
        g["members"].remove(target_uid)
        if target_uid in gangs_data["user_gang"]:
            del gangs_data["user_gang"][target_uid]
        await save_gangs()
    await message.answer(f"✅ `{nick}` вигнано з банди *{gang_name}*!", parse_mode="Markdown")

@dp.message(Command("gangleave"))
async def gang_leave(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    async with gangs_lock:
        gang_name = gangs_data["user_gang"].get(uid)
        if not gang_name:
            return await message.answer("❌ Ви не в банді!")
        g = gangs_data["gangs"][gang_name]
        if g["owner"] == uid:
            return await message.answer("❌ Лідер не може вийти! Спочатку передайте лідерство через `/gangtransfer`")
        g["members"].remove(uid)
        del gangs_data["user_gang"][uid]
        await save_gangs()
    await message.answer(f"✅ Ви вийшли з банди *{gang_name}*!", parse_mode="Markdown")

@dp.message(Command("gangtransfer"))
async def gang_transfer(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not command.args:
        return await message.answer("⚠️ `/gangtransfer [нікнейм]`")
    nick = command.args.strip()
    target_uid, td = find_user_by_nick(nick)
    if not td or not td.get("registered") or td.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer(f"❌ Гравця `{nick}` не знайдено або він заморожений!", parse_mode="Markdown")
    async with gangs_lock:
        gang_name = gangs_data["user_gang"].get(uid)
        if not gang_name:
            return await message.answer("❌ Ви не в банді!")
        g = gangs_data["gangs"][gang_name]
        if g["owner"] != uid:
            return await message.answer("❌ Ви не лідер!")
        if target_uid not in g["members"]:
            return await message.answer("❌ Цей гравець не в вашій банді!")
        g["owner"] = target_uid
        await save_gangs()
    await message.answer(f"✅ Лідерство передано `{nick}`!", parse_mode="Markdown")

@dp.message(Command("gangtop"))
async def gang_top(message: types.Message):
    async with gangs_lock:
        if not gangs_data["gangs"]:
            return await message.answer("❌ Банд не створено!")
        sorted_gangs = sorted(gangs_data["gangs"].items(), key=lambda x: x[1]["treasury"], reverse=True)[:5]
        text = "🏆 *ТОП-5 банд за казною:*\n━━━━━━━━━━━━━━━━\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (name, data) in enumerate(sorted_gangs):
            text += f"{medals[i]} *{name}* — `{data['treasury']:,} 💰` (рівень {data['level']})\n"
        await message.answer(text, parse_mode="Markdown")

# ========== ПРОФЕСІЇ (Рибалка, Шахта, Коваль, Алхімік, Кухар) ==========
FISH_CD = 1200
MINE_CD = 1500
MAX_FISH_LEVEL = 20
MAX_MINE_LEVEL = 20

def get_fish_price(level):
    return int(5000 * (1.5 ** (level - 1))) if level > 0 else 0
def get_fish_income(level):
    if level <= 0: return 0, 0
    inc = int(200 * (1.6 ** (level - 1)))
    return inc, inc * 2
def get_mine_price(level):
    return int(8000 * (1.6 ** (level - 1))) if level > 0 else 0
def get_mine_income(level):
    if level <= 0: return 0, 0
    inc = int(300 * (1.5 ** (level - 1)))
    return inc, inc * 2

@dp.message(Command("gather"))
async def gather_herbs(message: types.Message):
    """Збір трав для алхіміка"""
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return await message.answer("❌ Зареєструйтесь!")
        # Кулдаун на збір трав – 10 хвилин
        last_gather = d.get("last_gather", 0)
        if time.time() - last_gather < 600:
            left = int(600 - (time.time() - last_gather))
            return await message.answer(f"⏳ Збирати трави можна раз на 10 хвилин. Зачекайте {fmt_time(left)}")
        herbs = random.randint(1, 5)
        d["crafting_materials"]["Трава"] = d["crafting_materials"].get("Трава", 0) + herbs
        d["last_gather"] = time.time()
        await save_data()
    await message.answer(f"🌿 Ви зібрали {herbs} трави! Використовуйте для алхімії.")

@dp.message(F.text == "👔 Професії")
async def professions_menu(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    await message.answer(
        "👔 *Виберіть професію:*\n\n"
        "🎣 **Рибалка** – ловіть рибу та отримуйте ресурси.\n"
        "⛏ **Шахтар** – добувайте руду та корисні копалини.\n"
        "🛠 **Коваль** – створюйте зброю та броню.\n"
        "🧪 **Алхімік** – варіть зілля та еліксири.\n"
        "🍳 **Кухар** – готуйте їжу для відновлення HP/мани.\n\n"
        "Кожна професія має свій рівень та унікальні рецепти.\n"
        "💡 Для алхіміка: `/gather` для збору трав.\n"
        "💡 Рибалка дає `Рибу`, шахта дає `Кристали`.",
        reply_markup=get_professions_kb(), parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "prof_fish")
async def fish_menu_callback(callback: types.CallbackQuery):
    await fish_menu(callback.message)
    await callback.answer()
async def fish_menu(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    level = d.get("fishing_level", 0)
    if level == 0:
        price = get_fish_price(1)
        builder = InlineKeyboardBuilder()
        builder.button(text=f"Купити вудку ({price:,}💰)", callback_data="buy_fishing_1")
        await message.answer(f"🎣 *Риболовля*\nУ вас немає вудки. Перший рівень коштує `{price:,} 💰`.", reply_markup=builder.as_markup(), parse_mode="Markdown")
        return
    last_fish = d.get("last_fish", 0)
    left = cooldown_left(last_fish, FISH_CD)
    inc_min, inc_max = get_fish_income(level)
    can = left == 0
    builder = InlineKeyboardBuilder()
    if can:
        builder.button(text="🎣 Рибалити", callback_data="do_fish")
    if level < MAX_FISH_LEVEL:
        next_price = get_fish_price(level+1)
        builder.button(text=f"⬆ Покращити ({next_price:,}💰)", callback_data=f"buy_fishing_{level+1}")
    builder.adjust(1)
    await message.answer(f"🎣 *Риболовля* (рівень {level})\nДохід: `{inc_min}-{inc_max} 💰`\n⏳ Кулдаун: `{fmt_time(FISH_CD)}`\n{'✅ Готово' if can else f'⏳ Чекайте {fmt_time(left)}'}", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("buy_fishing_"))
async def buy_fishing(callback: types.CallbackQuery):
    level = int(callback.data.split("_")[2])
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        price = get_fish_price(level)
        if d["coins"] < price:
            return await callback.answer(f"❌ Не вистачає {price - d['coins']:,}💰", show_alert=True)
        d["coins"] -= price
        d["fishing_level"] = level
        d["last_fish"] = 0
        await save_data()
    await callback.message.edit_text(f"✅ Вудка покращена до рівня {level}!")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "do_fish")
async def do_fish(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        level = d.get("fishing_level", 0)
        if level == 0:
            return await callback.answer("❌ Немає вудки!", show_alert=True)
        left = cooldown_left(d.get("last_fish", 0), FISH_CD)
        if left > 0:
            return await callback.answer(f"⏳ Чекайте {fmt_time(left)}", show_alert=True)
        inc_min, inc_max = get_fish_income(level)
        await apply_event_effects()
        income = int(random.randint(inc_min, inc_max) * event_multipliers.get("fish", 1.0))
        if d.get("premium_until", 0) > time.time():
            income *= 2
        # Додаємо рибу в матеріали
        fish_count = random.randint(1, 3)
        d["crafting_materials"]["Риба"] = d["crafting_materials"].get("Риба", 0) + fish_count
        d["coins"] += income
        d["xp"] += 10
        d["last_fish"] = time.time()
        d.setdefault("stats", {})["fish_count"] = d["stats"].get("fish_count", 0) + 1
        await save_data()
    await update_quest_progress(uid, "fish")
    await callback.message.edit_text(f"🎣 *Ви зловили рибу!* +{income:,}💰, +{fish_count}🐟, +10 XP", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "prof_mine")
async def mine_menu_callback(callback: types.CallbackQuery):
    await mine_menu(callback.message)
    await callback.answer()
async def mine_menu(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    level = d.get("mining_level", 0)
    if level == 0:
        price = get_mine_price(1)
        builder = InlineKeyboardBuilder()
        builder.button(text=f"Купити кирку ({price:,}💰)", callback_data="buy_mining_1")
        await message.answer(f"⛏ *Шахта*\nУ вас немає кирки. Перший рівень коштує `{price:,} 💰`.", reply_markup=builder.as_markup(), parse_mode="Markdown")
        return
    last_mine = d.get("last_mine", 0)
    left = cooldown_left(last_mine, MINE_CD)
    inc_min, inc_max = get_mine_income(level)
    can = left == 0
    builder = InlineKeyboardBuilder()
    if can:
        builder.button(text="⛏ Копати", callback_data="do_mine")
    if level < MAX_MINE_LEVEL:
        next_price = get_mine_price(level+1)
        builder.button(text=f"⬆ Покращити ({next_price:,}💰)", callback_data=f"buy_mining_{level+1}")
    builder.adjust(1)
    await message.answer(f"⛏ *Шахта* (рівень {level})\nДохід: `{inc_min}-{inc_max} 💰`\n⏳ Кулдаун: `{fmt_time(MINE_CD)}`\n{'✅ Готово' if can else f'⏳ Чекайте {fmt_time(left)}'}", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("buy_mining_"))
async def buy_mining(callback: types.CallbackQuery):
    level = int(callback.data.split("_")[2])
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        price = get_mine_price(level)
        if d["coins"] < price:
            return await callback.answer(f"❌ Не вистачає {price - d['coins']:,}💰", show_alert=True)
        d["coins"] -= price
        d["mining_level"] = level
        d["last_mine"] = 0
        await save_data()
    await callback.message.edit_text(f"✅ Кирка покращена до рівня {level}!")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "do_mine")
async def do_mine(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        level = d.get("mining_level", 0)
        if level == 0:
            return await callback.answer("❌ Немає кирки!", show_alert=True)
        left = cooldown_left(d.get("last_mine", 0), MINE_CD)
        if left > 0:
            return await callback.answer(f"⏳ Чекайте {fmt_time(left)}", show_alert=True)
        inc_min, inc_max = get_mine_income(level)
        await apply_event_effects()
        income = int(random.randint(inc_min, inc_max) * event_multipliers.get("mine", 1.0))
        # Додаємо кристали та руду
        crystals = random.randint(1, 2)
        d["crafting_materials"]["Кристал"] = d["crafting_materials"].get("Кристал", 0) + crystals
        if random.random() < 0.3:
            ore = random.randint(1, 2)
            d["crafting_materials"]["Руда"] = d["crafting_materials"].get("Руда", 0) + ore
            income += 500
        if d.get("premium_until", 0) > time.time():
            income *= 2
        d["coins"] += income
        d["xp"] += 12
        d["last_mine"] = time.time()
        d.setdefault("stats", {})["mine_count"] = d["stats"].get("mine_count", 0) + 1
        await save_data()
    await update_quest_progress(uid, "mine")
    await callback.message.edit_text(f"⛏ *Ви добули ресурси!* +{income:,}💰, +{crystals}💎, +12 XP", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "prof_blacksmith")
async def blacksmith_menu(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    d = get_user(uid)
    level = d.get("blacksmith_level", 0)
    text = f"🛠 *Коваль* (рівень {level})\nВаші матеріали:\n"
    mats = d.get("crafting_materials", {})
    for mat, cnt in mats.items():
        text += f"• {mat}: {cnt}\n"
    recipes = {
        "Сталевий меч": {"materials": {"Руда": 5, "Вугілля": 2}, "xp": 50},
        "Залізний шолом": {"materials": {"Руда": 3, "Вугілля": 1}, "xp": 40},
    }
    builder = InlineKeyboardBuilder()
    for item, recipe in recipes.items():
        required = ", ".join([f"{k} x{v}" for k,v in recipe["materials"].items()])
        text += f"• {item} – {required} (+{recipe['xp']} XP)\n"
        builder.button(text=f"Створити {item}", callback_data=f"craft_blacksmith_{item}")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("craft_blacksmith_"))
async def do_blacksmith(callback: types.CallbackQuery):
    item = callback.data.split("_", 2)[2]
    recipes = {"Сталевий меч": {"materials": {"Руда": 5, "Вугілля": 2}, "xp": 50}, "Залізний шолом": {"materials": {"Руда": 3, "Вугілля": 1}, "xp": 40}}
    recipe = recipes.get(item)
    if not recipe:
        return
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        for mat, needed in recipe["materials"].items():
            if d["crafting_materials"].get(mat, 0) < needed:
                return await callback.answer(f"❌ Не вистачає {mat}!", show_alert=True)
        for mat, needed in recipe["materials"].items():
            d["crafting_materials"][mat] -= needed
        d["inventory"][item] = d["inventory"].get(item, 0) + 1
        d["blacksmith_level"] = d.get("blacksmith_level", 0) + 1
        d["xp"] += recipe["xp"]
        d["crafting_count"] = d.get("crafting_count", 0) + 1
        await save_data()
    await update_quest_progress(uid, "craft")
    await callback.message.edit_text(f"✅ Ви створили {item}! +{recipe['xp']} XP")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "prof_alchemist")
async def alchemist_menu(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    d = get_user(uid)
    level = d.get("alchemist_level", 0)
    text = f"🧪 *Алхімік* (рівень {level})\nВаші матеріали:\n"
    mats = d.get("crafting_materials", {})
    for mat, cnt in mats.items():
        text += f"• {mat}: {cnt}\n"
    recipes = {
        "Зілля здоров'я": {"materials": {"Трава": 3}, "xp": 30},
        "Зілля мани": {"materials": {"Кристал": 2}, "xp": 30},
    }
    builder = InlineKeyboardBuilder()
    for item, recipe in recipes.items():
        required = ", ".join([f"{k} x{v}" for k,v in recipe["materials"].items()])
        text += f"• {item} – {required} (+{recipe['xp']} XP)\n"
        builder.button(text=f"Створити {item}", callback_data=f"craft_alchemist_{item}")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("craft_alchemist_"))
async def do_alchemist(callback: types.CallbackQuery):
    item = callback.data.split("_", 2)[2]
    recipes = {"Зілля здоров'я": {"materials": {"Трава": 3}, "xp": 30}, "Зілля мани": {"materials": {"Кристал": 2}, "xp": 30}}
    recipe = recipes.get(item)
    if not recipe:
        return
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        for mat, needed in recipe["materials"].items():
            if d["crafting_materials"].get(mat, 0) < needed:
                return await callback.answer(f"❌ Не вистачає {mat}!", show_alert=True)
        for mat, needed in recipe["materials"].items():
            d["crafting_materials"][mat] -= needed
        d["inventory"][item] = d["inventory"].get(item, 0) + 1
        d["alchemist_level"] = d.get("alchemist_level", 0) + 1
        d["xp"] += recipe["xp"]
        d["crafting_count"] = d.get("crafting_count", 0) + 1
        await save_data()
    await update_quest_progress(uid, "craft")
    await callback.message.edit_text(f"✅ Ви створили {item}! +{recipe['xp']} XP")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "prof_cook")
async def cook_menu(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    d = get_user(uid)
    level = d.get("cook_level", 0)
    text = f"🍳 *Кухар* (рівень {level})\nВаші матеріали:\n"
    mats = d.get("crafting_materials", {})
    for mat, cnt in mats.items():
        text += f"• {mat}: {cnt}\n"
    recipes = {
        "Стейк": {"materials": {"Риба": 2}, "xp": 20},
        "Яблучний пиріг": {"materials": {"Яблуко": 3, "Борошно": 1}, "xp": 40},
    }
    builder = InlineKeyboardBuilder()
    for item, recipe in recipes.items():
        required = ", ".join([f"{k} x{v}" for k,v in recipe["materials"].items()])
        text += f"• {item} – {required} (+{recipe['xp']} XP)\n"
        builder.button(text=f"Приготувати {item}", callback_data=f"craft_cook_{item}")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("craft_cook_"))
async def do_cook(callback: types.CallbackQuery):
    item = callback.data.split("_", 2)[2]
    recipes = {"Стейк": {"materials": {"Риба": 2}, "xp": 20}, "Яблучний пиріг": {"materials": {"Яблуко": 3, "Борошно": 1}, "xp": 40}}
    recipe = recipes.get(item)
    if not recipe:
        return
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        for mat, needed in recipe["materials"].items():
            if d["crafting_materials"].get(mat, 0) < needed:
                return await callback.answer(f"❌ Не вистачає {mat}!", show_alert=True)
        for mat, needed in recipe["materials"].items():
            d["crafting_materials"][mat] -= needed
        d["inventory"][item] = d["inventory"].get(item, 0) + 1
        d["cook_level"] = d.get("cook_level", 0) + 1
        d["xp"] += recipe["xp"]
        d["crafting_count"] = d.get("crafting_count", 0) + 1
        await save_data()
    await update_quest_progress(uid, "craft")
    await callback.message.edit_text(f"✅ Ви приготували {item}! +{recipe['xp']} XP")
    await callback.answer()

# ========== КАЗИНО (з захистом новачка) ==========
@dp.message(F.text == "🎰 Казино")
async def casino_main(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    builder = InlineKeyboardBuilder()
    builder.button(text="🎡 Рулетка", callback_data="casino_roulette")
    builder.button(text="🎲 Кістки (з ботом)", callback_data="casino_dice_bot")
    builder.button(text="🎡 Колесо фортуни (безкоштовно щогодини)", callback_data="casino_wheel")
    builder.button(text="📊 Моя статистика", callback_data="casino_stats")
    builder.adjust(2)
    await message.answer(
        "🎰 *КАЗИНО BANDIT*\n━━━━━━━━━━━━━━━━\n"
        "🎡 *Рулетка* – ставте на число або колір\n"
        "🎲 *Кістки* – гра проти бота\n"
        "🎡 *Колесо фортуни* – безкоштовно раз на годину\n\n"
        f"💰 Ваш баланс: `{d['coins']:,} 💰`\n💎 Діаманти: `{d.get('diamonds', 0)}`\n"
        f"⚠️ Новачкам (XP<500) – макс. ставка 30% від готівки.",
        reply_markup=builder.as_markup(), parse_mode="Markdown"
    )

temp_bets = {}
@dp.callback_query(lambda c: c.data == "casino_roulette")
async def casino_roulette(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    for i in range(1, 37):
        builder.button(text=str(i), callback_data=f"roulette_bet_{i}")
    builder.button(text="🔴 Червоне", callback_data="roulette_bet_red")
    builder.button(text="⚫ Чорне", callback_data="roulette_bet_black")
    builder.button(text="🟢 Зелене (0)", callback_data="roulette_bet_0")
    builder.button(text="1-12", callback_data="roulette_bet_1-12")
    builder.button(text="13-24", callback_data="roulette_bet_13-24")
    builder.button(text="25-36", callback_data="roulette_bet_25-36")
    builder.button(text="Парне", callback_data="roulette_bet_even")
    builder.button(text="Непарне", callback_data="roulette_bet_odd")
    builder.adjust(6)
    await callback.message.edit_text("🎡 *Рулетка*\nОберіть ставку:", reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("roulette_bet_"))
async def roulette_choose_bet(callback: types.CallbackQuery):
    bet_type = callback.data.split("_")[2]
    uid = str(callback.from_user.id)
    temp_bets[uid] = {"game": "roulette", "bet_type": bet_type}
    await callback.message.answer(f"🎡 Ви обрали ставку: *{bet_type}*\nТепер надішліть суму ставки (мінімум 100💰):", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "casino_dice_bot")
async def casino_dice_bot(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    temp_bets[uid] = {"game": "dice_bot"}
    await callback.message.answer("🎲 *Гра в кістки з ботом*\nВведіть суму ставки (мінімум 100💰):", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "casino_wheel")
async def casino_wheel(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        last_wheel = d.get("last_wheel", 0)
        if time.time() - last_wheel < 3600:
            left = 3600 - (time.time() - last_wheel)
            return await callback.answer(f"⏳ Наступне безкоштовне обертання через {fmt_time(int(left))}", show_alert=True)
        prizes = [100, 200, 500, 1000, 5000, 10000, 0, 0, 0, 0]
        win = random.choice(prizes)
        if win > 0:
            d["coins"] += win
            await callback.message.answer(f"🎡 *Колесо фортуни!*\nВи виграли `{win:,} 💰`!")
        else:
            await callback.message.answer(f"🎡 *Колесо фортуни!*\nВи нічого не виграли. Спробуйте через годину!")
        d["last_wheel"] = time.time()
        await save_data()
    await callback.answer()

@dp.callback_query(lambda c: c.data == "casino_stats")
async def casino_stats(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    d = get_user(uid)
    text = (
        f"📊 *Статистика в казино*\n"
        f"🎰 Ігор зіграно: {d.get('stats', {}).get('casino_games', 0)}\n"
        f"🏆 Виграшів: {d.get('stats', {}).get('casino_wins', 0)}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

async def casino_check_bet(d, amount):
    if amount < 100:
        return False, "❌ Мінімальна ставка 100💰"
    if amount > d["coins"]:
        return False, f"❌ Недостатньо грошей! У вас {d['coins']:,}💰"
    if is_newbie(d):
        max_bet = int(d["coins"] * 0.3)
        if amount > max_bet:
            return False, f"⚠️ Ви новачок (XP<500). Максимальна ставка для вас — 30% від готівки = {max_bet}💰"
    return True, ""

@dp.message()
async def handle_casino_bet(message: types.Message):
    uid = str(message.from_user.id)
    if uid not in temp_bets:
        return
    try:
        amount = int(message.text.strip())
    except:
        await message.answer("❌ Введіть число!")
        return
    bet_data = temp_bets.pop(uid)
    async with get_user_lock(uid):
        d = get_user(uid)
        ok, err = await casino_check_bet(d, amount)
        if not ok:
            await message.answer(err)
            return
        d["coins"] -= amount
        d.setdefault("stats", {})["casino_games"] = d["stats"].get("casino_games", 0) + 1
        if bet_data["game"] == "roulette":
            result_num = random.randint(0, 36)
            if result_num == 0:
                result_color = "green"
            elif result_num % 2 == 0:
                result_color = "black"
            else:
                result_color = "red"
            win_mult = 0
            bet_type = bet_data["bet_type"]
            if bet_type == str(result_num):
                win_mult = 35
            elif bet_type == "red" and result_color == "red":
                win_mult = 2
            elif bet_type == "black" and result_color == "black":
                win_mult = 2
            elif bet_type == "0" and result_num == 0:
                win_mult = 35
            elif bet_type == "1-12" and 1 <= result_num <= 12:
                win_mult = 3
            elif bet_type == "13-24" and 13 <= result_num <= 24:
                win_mult = 3
            elif bet_type == "25-36" and 25 <= result_num <= 36:
                win_mult = 3
            elif bet_type == "even" and result_num % 2 == 0 and result_num != 0:
                win_mult = 2
            elif bet_type == "odd" and result_num % 2 == 1:
                win_mult = 2
            if win_mult > 0:
                win_amount = amount * win_mult
                d["coins"] += win_amount
                d["stats"]["casino_wins"] = d["stats"].get("casino_wins", 0) + 1
                await save_data()
                await message.answer(f"🎡 *Рулетка*\nВипало число: {result_num} ({result_color})\n✅ ВИГРАШ! +{win_amount:,}💰")
                await update_quest_progress(uid, "casino_win")
            else:
                await save_data()
                await message.answer(f"🎡 *Рулетка*\nВипало число: {result_num} ({result_color})\n❌ ПРОГРАШ! -{amount:,}💰")
        elif bet_data["game"] == "dice_bot":
            user_roll = random.randint(1, 6)
            bot_roll = random.randint(1, 6)
            if user_roll > bot_roll:
                d["coins"] += amount * 2
                d["stats"]["casino_wins"] = d["stats"].get("casino_wins", 0) + 1
                await save_data()
                await message.answer(f"🎲 *Кістки*\nВи: {user_roll} | Бот: {bot_roll}\n✅ Виграли! +{amount*2:,}💰")
                await update_quest_progress(uid, "casino_win")
            elif user_roll < bot_roll:
                await save_data()
                await message.answer(f"🎲 *Кістки*\nВи: {user_roll} | Бот: {bot_roll}\n❌ Програли! -{amount:,}💰")
            else:
                d["coins"] += amount
                await save_data()
                await message.answer(f"🎲 *Кістки*\nВи: {user_roll} | Бот: {bot_roll}\n🤝 Нічия! Ставка повернута.")

# ========== ТВАРИНИ ==========
@dp.message(F.text == "🐾 Тварина")
async def pet_system(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    pet = d.get("pet")
    if not pet:
        builder = InlineKeyboardBuilder()
        builder.button(text="🐱 Кіт (5💎) - +5% до роботи", callback_data="buy_pet_cat")
        builder.button(text="🐶 Собака (10💎) - +10% до критичного удару", callback_data="buy_pet_dog")
        builder.button(text="🐉 Дракончик (50💎) - +20% до шкоди в бою", callback_data="buy_pet_dragon")
        builder.adjust(1)
        await message.answer(
            "🐾 *Магазин домашніх тварин*\n"
            f"🐱 Кіт (5💎) → +5% до роботи\n"
            f"🐶 Собака (10💎) → +10% до критичного удару\n"
            f"🐉 Дракончик (50💎) → +20% до шкоди в бою\n\n"
            f"💎 Ваші діаманти: {d.get('diamonds', 0)}",
            reply_markup=builder.as_markup(), parse_mode="Markdown"
        )
        return
    pet_hunger = d.get("pet_hunger", 100)
    status = "✅ Ситий" if pet_hunger > 30 else "⚠️ Голодний" if pet_hunger > 0 else "❌ Голодний"
    builder = InlineKeyboardBuilder()
    builder.button(text="🍖 Погодувати (1000💰 +10 голоду)", callback_data="feed_pet")
    builder.button(text="💎 Купити корм (5💎 +50 голоду)", callback_data="feed_pet_diamonds")
    builder.adjust(1)
    await message.answer(
        f"🐾 *Ваш улюбленець: {pet}*\n"
        f"🍖 Голод: {pet_hunger}/100 ({status})\n"
        f"💡 Голод зменшується на 5 щогодини.",
        reply_markup=builder.as_markup(), parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("buy_pet_"))
async def buy_pet(callback: types.CallbackQuery):
    pet_type = callback.data.split("_")[2]
    pet_name = {"cat": "Кіт", "dog": "Собака", "dragon": "Дракончик"}.get(pet_type)
    price = {"cat": 5, "dog": 10, "dragon": 50}.get(pet_type)
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("pet"):
            return await callback.answer("❌ У вас вже є тварина!", show_alert=True)
        diamonds = d.get("diamonds", 0)
        if diamonds < price:
            return await callback.answer(f"❌ Не вистачає діамантів! Потрібно {price}💎", show_alert=True)
        d["diamonds"] = diamonds - price
        d["pet"] = pet_name
        d["pet_hunger"] = 100
        await save_data()
    await callback.message.edit_text(f"✅ Ви придбали {pet_name}! Не забувайте годувати 🍖")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "feed_pet")
async def feed_pet(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if not d.get("pet"):
            return await callback.answer("❌ У вас немає тварини!", show_alert=True)
        if d["coins"] < 1000:
            return await callback.answer("❌ Недостатньо грошей! Потрібно 1000💰", show_alert=True)
        d["coins"] -= 1000
        d["pet_hunger"] = min(100, d.get("pet_hunger", 100) + 10)
        await save_data()
    await callback.message.edit_text("🍖 Ви погодували тварину! +10 голоду.")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "feed_pet_diamonds")
async def feed_pet_diamonds(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if not d.get("pet"):
            return await callback.answer("❌ У вас немає тварини!", show_alert=True)
        diamonds = d.get("diamonds", 0)
        if diamonds < 5:
            return await callback.answer("❌ Не вистачає діамантів! Потрібно 5💎", show_alert=True)
        d["diamonds"] = diamonds - 5
        d["pet_hunger"] = min(100, d.get("pet_hunger", 100) + 50)
        await save_data()
    await callback.message.edit_text("🍖 Ви придбали елітний корм! +50 голоду.")
    await callback.answer()

# ========== ПОГОДА (лише візуальна) ==========
WEATHER_TYPES = ["☀️ Сонячно", "🌧 Дощ", "⛈ Шторм", "❄️ Сніг", "🌫 Туман"]
current_weather = "☀️ Сонячно"
weather_until = time.time() + 3600

async def update_weather():
    global current_weather, weather_until
    while True:
        await asyncio.sleep(3600)
        current_weather = random.choice(WEATHER_TYPES)
        weather_until = time.time() + 3600
        for uid, data in user_data.items():
            if data.get("registered"):
                try:
                    await bot.send_message(uid, f"🌤 *Погода змінилася!*\nТепер {current_weather}", parse_mode="Markdown")
                except: pass

@dp.message(F.text == "🌦 Погода")
async def weather_info(message: types.Message):
    global current_weather, weather_until
    left = max(0, int(weather_until - time.time()))
    text = f"🌦 *Поточна погода:* {current_weather}\n⏳ Зміниться через: {fmt_time(left)}\n\n✨ Погода впливає лише на атмосферу, не на множники."
    await message.answer(text, parse_mode="Markdown")

# ========== КЕЙСИ ==========
CASES = {
    "Звичайний кейс": {"price": 5000, "items": ["1000💰", "2000💰", "5000💰", "Зілля HP", "Досвід 100 XP"]},
    "Срібний кейс": {"price": 25000, "items": ["5000💰", "10000💰", "25000💰", "Рідкісний скін", "Діаманти x5"]},
    "Золотий кейс": {"price": 100000, "items": ["25000💰", "50000💰", "100000💰", "Легендарний скін", "Діаманти x20"]},
}

@dp.message(F.text == "🎁 Кейси")
async def cases_menu(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    builder = InlineKeyboardBuilder()
    for case_name, case_data in CASES.items():
        builder.button(text=f"{case_name} ({case_data['price']:,}💰)", callback_data=f"open_case_{case_name}")
    builder.adjust(1)
    await message.answer(f"🎁 *Відкрийте кейс!*\n💰 Ваш баланс: {d['coins']:,}", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("open_case_"))
async def open_case(callback: types.CallbackQuery):
    case_name = callback.data.split("_", 2)[2]
    case_data = CASES.get(case_name)
    if not case_data:
        return await callback.answer("❌ Невідомий кейс!")
    uid = str(callback.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d["coins"] < case_data["price"]:
            return await callback.answer(f"❌ Недостатньо грошей! Потрібно {case_data['price']:,}💰", show_alert=True)
        d["coins"] -= case_data["price"]
        reward = random.choice(case_data["items"])
        if reward == "1000💰":
            d["coins"] += 1000
            reward_text = "1000💰"
        elif reward == "2000💰":
            d["coins"] += 2000
            reward_text = "2000💰"
        elif reward == "5000💰":
            d["coins"] += 5000
            reward_text = "5000💰"
        elif reward == "25000💰":
            d["coins"] += 25000
            reward_text = "25000💰"
        elif reward == "50000💰":
            d["coins"] += 50000
            reward_text = "50000💰"
        elif reward == "100000💰":
            d["coins"] += 100000
            reward_text = "100000💰"
        elif reward == "Зілля HP":
            d["inventory"]["Зілля HP"] = d["inventory"].get("Зілля HP", 0) + 1
            reward_text = "Зілля HP x1"
        elif reward == "Рідкісний скін":
            skins = ["Тіньовий кинджал", "Полум'яний меч", "Льодяна сокира"]
            skin = random.choice(skins)
            d["inventory"][skin] = d["inventory"].get(skin, 0) + 1
            reward_text = f"Скін: {skin}"
        elif reward == "Легендарний скін":
            skins = ["Драконоборець", "Блискавка", "Кровопивець"]
            skin = random.choice(skins)
            d["inventory"][skin] = d["inventory"].get(skin, 0) + 1
            reward_text = f"Легендарний скін: {skin}"
        elif reward == "Досвід 100 XP":
            d["xp"] += 100
            reward_text = "100 XP"
        elif reward == "Діаманти x5":
            d["diamonds"] = d.get("diamonds", 0) + 5
            reward_text = "5💎"
        elif reward == "Діаманти x20":
            d["diamonds"] = d.get("diamonds", 0) + 20
            reward_text = "20💎"
        else:
            reward_text = reward
        d["cases_opened"] = d.get("cases_opened", 0) + 1
        await save_data()
    await callback.message.edit_text(f"🎁 *Ви відкрили {case_name}!*\nВи отримали: {reward_text}", parse_mode="Markdown")
    await callback.answer()

# ========== ЩОДЕННІ ЗАВДАННЯ ==========
DAILY_TASKS = [
    {"desc": "Заробити 5000💰", "type": "earn", "target": 5000},
    {"desc": "Виконати 5 робіт", "type": "work", "target": 5},
    {"desc": "Пограбувати 1 гравця", "type": "rob", "target": 1},
    {"desc": "Зібрати врожай на фермі 2 рази", "type": "farm", "target": 2},
    {"desc": "Виграти в казино 1 раз", "type": "casino_win", "target": 1},
    {"desc": "Перемогти в PvP 1 раз", "type": "pvp_win", "target": 1},
    {"desc": "Перемогти боса", "type": "pve_win", "target": 1},
    {"desc": "Відкрити 1 кейс", "type": "case_open", "target": 1},
]

async def reset_daily_tasks():
    while True:
        now = time.time()
        for uid, data in user_data.items():
            if data.get("registered") and not data.get("frozen"):
                last_reset = data.get("last_daily_task_reset", 0)
                if now - last_reset >= 86400:
                    tasks = random.sample(DAILY_TASKS, 3)
                    data["daily_tasks"] = [{"desc": t["desc"], "type": t["type"], "target": t["target"], "progress": 0, "reward_coins": 5000, "reward_xp": 100, "reward_diamonds": 1} for t in tasks]
                    data["last_daily_task_reset"] = now
                    asyncio.ensure_future(save_data())
                    try:
                        await bot.send_message(uid, "📅 *Нові щоденні завдання!* Введіть `/tasks` для перегляду.", parse_mode="Markdown")
                    except: pass
        await asyncio.sleep(3600)

@dp.message(Command("tasks"))
async def show_tasks(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if not d.get("registered"):
        return await message.answer("❌ Зареєструйтесь!")
    tasks = d.get("daily_tasks", [])
    if not tasks:
        return await message.answer("📅 Сьогодні немає активних завдань.")
    text = "📅 *Ваші щоденні завдання:*\n\n"
    for i, task in enumerate(tasks, 1):
        text += f"{i}. {task['desc']} – {task['progress']}/{task['target']}\n"
    await message.answer(text, parse_mode="Markdown")

async def update_daily_task_progress(uid, task_type, amount=1):
    async with get_user_lock(uid):
        d = get_user(uid)
        tasks = d.get("daily_tasks", [])
        updated = False
        for task in tasks:
            if task["type"] == task_type and task["progress"] < task["target"]:
                task["progress"] += amount
                updated = True
                if task["progress"] >= task["target"]:
                    d["coins"] += task["reward_coins"]
                    d["xp"] += task["reward_xp"]
                    d["diamonds"] = d.get("diamonds", 0) + task["reward_diamonds"]
                    await save_data()
                    try:
                        await bot.send_message(uid, f"✅ *Завдання виконано!*\n{task['desc']}\nОтримано: {task['reward_coins']}💰, {task['reward_xp']} XP, {task['reward_diamonds']}💎", parse_mode="Markdown")
                    except: pass
        if updated:
            await save_data()

# ========== СТАТИСТИКА ==========
@dp.message(F.text == "📊 Статистика")
async def stats_button(message: types.Message):
    await player_stats(message, None)

@dp.message(Command("stats"))
async def player_stats(message: types.Message, command: CommandObject):
    uid = str(message.from_user.id)
    if command and command.args:
        nick = command.args.strip()
        t_uid, td = find_user_by_nick(nick)
        if not td or not td.get("registered") or td.get("frozen"):
            return await message.answer("❌ Гравець не знайдений або заморожений!")
        uid = t_uid
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen"):
            return await message.answer("❌ Акаунт заморожено!")
        st = d.get("stats", {})
        text = (
            f"📊 *Статистика {d['nickname']}:*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔨 Робіт: {st.get('work_count', 0)}\n"
            f"💰 Пограбувань: {st.get('rob_count', 0)}\n"
            f"🎲 Ігор виграно: {st.get('games_won', 0)}\n"
            f"🎲 Ігор програно: {st.get('games_lost', 0)}\n"
            f"🎣 Риболовля: {st.get('fish_count', 0)}\n"
            f"⛏ Шахта: {st.get('mine_count', 0)}\n"
            f"🌾 Зборів ферми: {st.get('farm_count', 0)}\n"
            f"🛠 Крафтів: {d.get('crafting_count', 0)}\n"
            f"🏅 Рибалка: {d.get('fishing_level', 0)} | Шахта: {d.get('mining_level', 0)}\n"
            f"🏅 Коваль: {d.get('blacksmith_level', 0)} | Алхімік: {d.get('alchemist_level', 0)} | Кухар: {d.get('cook_level', 0)}\n"
            f"⚔️ PvP: {d.get('pvp_wins', 0)}/{d.get('pvp_losses', 0)} (Elo: {d.get('elo', 1200)})\n"
            f"🐉 PvE: {d.get('pve_wins', 0)}/{d.get('pve_losses', 0)}\n"
            f"🎰 Казино: виграшів {st.get('casino_wins', 0)}, ігор {st.get('casino_games', 0)}\n"
            f"📦 Відкрито кейсів: {d.get('cases_opened', 0)}\n"
            f"👥 Рефералів: {len(d.get('referrals', []))}\n"
            f"💎 Діаманти: {d.get('diamonds', 0)}\n"
            f"💎 Загальний капітал: {d['coins']+d['bank']+d.get('bank_deposit',0):,}💰\n"
            f"🐾 Тварина: {d.get('pet', 'Немає')} (голод {d.get('pet_hunger', 100)}/100)\n"
            f"🏴 Банда: {gangs_data['user_gang'].get(uid, 'немає')}\n"
        )
    await message.answer(text, parse_mode="Markdown")

# ========== БАЛАНС ==========
@dp.message(F.text == "💰 Баланс")
async def bal_button(message: types.Message):
    uid = str(message.from_user.id)
    d = get_user(uid)
    if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
        return await message.answer("❌ Акаунт заморожено або світ на паузі!")
    if not d.get("registered") and message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Зареєструйтесь!")
    await message.answer(f"💰 Готівка: `{d['coins']:,}`\n🏦 Банк: `{d['bank']:,}`\n💎 Всього: `{d['coins']+d['bank']:,}`\n💎 Діаманти: `{d.get('diamonds', 0)}`", parse_mode="Markdown")

# ========== РЕФЕРАЛИ ==========
@dp.message(F.text == "👥 Запросити")
async def invite_ref(message: types.Message):
    uid = str(message.from_user.id)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={uid}"
    d = get_user(uid)
    referrals = d.get("referrals", [])
    text = f"👥 *Реферальна система*\nВаше посилання: `{link}`\nЗапрошено друзів: {len(referrals)}\n\nЗа кожного друга: +5000💰, +10💎, +5% від його доходу тиждень"
    await message.answer(text, parse_mode="Markdown")

# ========== ПЕРЕМИКАННЯ СТОРІНОК ==========
@dp.message(F.text == "Далі ➡️")
async def go_next_page(message: types.Message):
    await message.answer("📟 Друга сторінка меню.", reply_markup=get_second_kb())

@dp.message(F.text == "⬅️ Назад")
async def go_back_page(message: types.Message):
    await message.answer("🏠 Головне меню.", reply_markup=get_main_kb())

# ========== ЩОДЕННИЙ БОНУС ЗІ СТРІКОМ ==========
@dp.message(Command("daily"))
async def daily_bonus(message: types.Message):
    uid = str(message.from_user.id)
    async with get_user_lock(uid):
        d = get_user(uid)
        if d.get("frozen") or admin_config["global_freeze_until"] > time.time():
            return await message.answer("❌ Ваш акаунт заморожено або світ на паузі!")
        if not d.get("registered") and message.from_user.id != ADMIN_ID:
            return
        last = d.get("last_daily", 0)
        now = time.time()
        if now - last < 86400:
            left = int(86400 - (now - last))
            return await message.answer(f"📅 *Вже отримано!* Повертайся через `{fmt_time(left)}` ⏳", parse_mode="Markdown")
        # Стрік: якщо минуло менше 48 годин – збільшуємо, інакше скидаємо
        streak = d.get("streak_daily", 0)
        if now - last < 172800:  # 2 дні
            streak += 1
        else:
            streak = 1
        d["streak_daily"] = streak
        bonus_coins = 2000 + min(5000, streak * 250)
        bonus_xp = 50 + min(500, streak * 20)
        d["coins"] += bonus_coins
        d["xp"] += bonus_xp
        d["last_daily"] = now
        rank_up = check_rank_up(d)
        check_achievements(d, uid)
        await save_data()
        text = f"📅 *Щоденний бонус!*\nСтрік: {streak} днів\nОтримано: `{bonus_coins:,} 💰` та `{bonus_xp} XP`"
        if rank_up:
            text += f"\n\n🎉 *Новий ранг: {rank_up}!*"
        await message.answer(text, parse_mode="Markdown")

# ========== АВТОВІДНОВЛЕННЯ HP/MP ==========
async def auto_recovery():
    while True:
        await asyncio.sleep(3600)  # кожну годину
        for uid, data in user_data.items():
            if data.get("registered") and not data.get("frozen"):
                changed = False
                if data.get("hp", 0) < data.get("max_hp", 100):
                    data["hp"] = min(data["max_hp"], data.get("hp", 0) + int(data["max_hp"] * 0.2))
                    changed = True
                if data.get("mp", 0) < data.get("max_mp", 50):
                    data["mp"] = min(data["max_mp"], data.get("mp", 0) + int(data["max_mp"] * 0.3))
                    changed = True
                if changed:
                    try:
                        await bot.send_message(uid, "💚 *Автовідновлення!* Ваше HP та MP відновлено на 20% та 30% відповідно.", parse_mode="Markdown")
                    except: pass
        await save_data()

# ========== ФОНОВІ ЗАВДАННЯ (без лотереї) ==========
async def stock_background():
    while True:
        await asyncio.sleep(1800)
        update_stock_prices()

async def weather_background():
    while True:
        await asyncio.sleep(3600)
        global current_weather, weather_until
        current_weather = random.choice(WEATHER_TYPES)
        weather_until = time.time() + 3600
        for uid, data in user_data.items():
            if data.get("registered"):
                try:
                    await bot.send_message(uid, f"🌤 *Погода змінилася!* Тепер {current_weather}", parse_mode="Markdown")
                except: pass

async def pet_hunger_background():
    while True:
        await asyncio.sleep(3600)
        for uid, data in user_data.items():
            if data.get("registered") and data.get("pet"):
                hunger = data.get("pet_hunger", 100) - 5
                data["pet_hunger"] = max(0, hunger)
                if hunger <= 0 and hunger > -5:
                    try:
                        await bot.send_message(uid, f"⚠️ Ваша тварина {data['pet']} голодна! Бонуси тимчасово не діють.", parse_mode="Markdown")
                    except: pass
        await save_data()

async def random_event_background():
    while True:
        await asyncio.sleep(3600)
        now = time.time()
        async with events_lock:
            if now - events_data.get("last_random_event", 0) >= 7200 and random.random() < 0.5:
                etype = random.choice(EVENT_TYPES)
                duration = random.randint(15, 45)
                events_data["active_event"] = etype
                events_data["event_end"] = now + duration*60
                events_data["last_random_event"] = now
                await save_events()
                await apply_event_effects()
                for uid, data in user_data.items():
                    if data.get("registered"):
                        try:
                            await bot.send_message(uid, f"🌍 *Випадкова подія!* {etype} діє {duration} хв.", parse_mode="Markdown")
                        except: pass

async def daily_tasks_reset_background():
    while True:
        await asyncio.sleep(3600)
        now = time.time()
        for uid, data in user_data.items():
            if data.get("registered") and not data.get("frozen"):
                last_reset = data.get("last_daily_task_reset", 0)
                if now - last_reset >= 86400:
                    tasks = random.sample(DAILY_TASKS, 3)
                    data["daily_tasks"] = [{"desc": t["desc"], "type": t["type"], "target": t["target"], "progress": 0, "reward_coins": 5000, "reward_xp": 100, "reward_diamonds": 1} for t in tasks]
                    data["last_daily_task_reset"] = now
                    await save_data()
                    try:
                        await bot.send_message(uid, "📅 *Нові щоденні завдання!* Введіть `/tasks` для перегляду.", parse_mode="Markdown")
                    except: pass

# ========== ЗАПУСК ==========
async def main():
    logging.info("🔥 Запуск бота Bandit Ultimate...")
    asyncio.create_task(stock_background())
    asyncio.create_task(weather_background())
    asyncio.create_task(pet_hunger_background())
    asyncio.create_task(random_event_background())
    asyncio.create_task(daily_tasks_reset_background())
    asyncio.create_task(auto_recovery())
    asyncio.create_task(update_weather())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Бот зупинено")
