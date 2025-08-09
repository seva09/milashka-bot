# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import random, re, os

app = Flask(__name__)

# ===== Настройки по умолчанию =====
DEFAULT_CALLYOU = "подружка"      # как она к тебе обращается
DEFAULT_MODE     = "auto"         # soft | hard | auto

# Словари фраз
GREETINGS = [
    "О, привет, {name}! Я тут. Что делаем — болтаем или батлим?",
    "Приветики, {name}! Как ты там, всё норм?",
    "Йоу, {name}! Я заряжена. Поехали!"
]
SMALLTALK = [
    "Я на связи, {name}. Что делаем?",
    "Тут я, {name}. Давай по делу.",
    "На месте, {name}. С чего начнём?"
]
COMFORT = [
    "Эй, {name}, не кисни. Дышим глубже — вырулим 💪",
    "{name}, я рядом. Пойдём шаг за шагом, ок?",
    "Понимаю тебя, {name}. Отдохни минутку и продолжим."
]
ANGRY_SOFT = [
    "{name}, да ну их к чёрту. Ты — молодец, фокус на своём.",
    "Понимаю. Мир шумит, а ты держись. Я рядом.",
    "Нервотрёпка — ерунда. {name}, давай лучше сделаем нужное."
]
ANGRY_HARD = [
    "Слушай, {name}. Отставить нытьё — делай ход и не трать нервы.",
    "Окей, наезд принят. По фактам: либо делаешь, либо отпускаешь.",
    "Остываем. Чушь не повторяем. Дальше по делу."
]
BATTLE_START = ["Стартуем батл 🎤 Твой ход!", "Поехали! Я на вайбе. Кидай строчку."]
BATTLE_LINES = [
    "Я как Wi-Fi — на высоте лечу, а ты как 3G — глючишь по пути.",
    "Ты искра, я пожар. Микрофон мой — это факт, без прелюдий."
]
LOVE = ["Обнимаю тебя крепко, {name} 💗", "{name}, ты у меня огонь. Всегда рядом."]
FLIRT = ["Ха, знаю-знаю 😉 но приятно слышать!", "Ну всё, я растаяла, {name} 😌"]

# Маркёры грубости (триггеры для жёсткого тона в авто-режиме)
RUDE_MARKERS = [
    "дура","идиот","туп","мерз","фигн","задолбал","заткн","офигел","бесит","сра","хрен","лох",
    "пошел","пошёл","пошла","пошли","иди сюда","пошёл ты сам","пошла ты"
]

# ===== Вспомогалки =====
def pick(xs): return random.choice(xs)
def norm(t):  return (t or "").strip().lower()
def rude(t):  return any(m in t for m in RUDE_MARKERS)

def get_state(payload):
    s = (payload.get("state") or {}).get("session") or {}
    return s.get("call_you", DEFAULT_CALLYOU), s.get("mode", DEFAULT_MODE)

def set_name_cmd(t, name):
    m = re.search(r"(зови|обращайся|называй)\s+меня\s+([a-zа-я0-9_\- ]{2,20})", t)
    return m.group(2).strip() if m else name

def set_mode_cmd(t, mode):
    if "жестк" in t or "жёстк" in t: return "hard"
    if "мягк" in t: return "soft"
    if "авто"  in t: return "auto"
    return mode

def route(t, name, mode):
    # Комментарии: «коммент: …» / «комментарий: …»
    if t.startswith("коммент:") or t.startswith("комментарий:"):
        content = t.split(":",1)[1].strip() if ":" in t else ""
        if not content:
            return "Озвучь текст комментария после слова «коммент:»."
        if mode=="hard" or (mode=="auto" and rude(content)):
            return "Слышу наезд. По фактам: остынь и перестань нести чушь. Дальше работаем."
        return "Приняла комментарий. Спокойно: отпусти и двигайся дальше."

    # Привет/старт
    if t in ("","привет","старт","начать","йоу","запуск"):
        return pick(GREETINGS).format(name=name)

    # Смолтолк
    if any(k in t for k in ["как дела","ты где","ты тут","что делаешь"]):
        return pick(SMALLTALK).format(name=name)

    # Поддержка
    if any(k in t for k in ["груст","плохо","тяжело","стресс","устал"]):
        return pick(COMFORT).format(name=name)

    # Злость
    if any(k in t for k in ["злюсь","бесят","бесит","достал","задолбал","токсик"]):
        return (pick(ANGRY_HARD) if (mode=="hard" or (mode=="auto" and rude(t))) else pick(ANGRY_SOFT)).format(name=name)

    # Батл
    if any(k in t for k in ["батл","рэп","бит"]):
        return pick(BATTLE_LINES) if ("мой ход" in t or "строка" in t) else pick(BATTLE_START)

    # Любовь/флирт
    if any(k in t for k in ["люблю","обними","сердце","поддержи"]): return pick(LOVE).format(name=name)
    if any(k in t for k in ["красивая","умная","моя","зая","киса"]):  return pick(FLIRT).format(name=name)

    # По умолчанию
    return f"Поняла тебя, {name}. Скажи конкретнее, что нужно — и делаем."

def make_response(payload, text, name, mode, end=False):
    return {
        "version":"1.0",
        "session": payload.get("session", {}),
        "response":{"text":text, "tts":text, "end_session":end},
        "session_state":{"call_you":name, "mode":mode}
    }

# ===== Вход для Алисы (Webhook) =====
@app.route("/alice", methods=["POST"])
def alice_webhook():
    payload = request.get_json(silent=True) or {}
    req = (payload.get("request") or {})
    text = req.get("original_utterance") or req.get("command") or ""
    t = norm(text)

    name, mode = get_state(payload)   # достаём состояние
    name = set_name_cmd(t, name)      # «зови меня Заей»
    mode = set_mode_cmd(t, mode)      # «жёсткий/мягкий/авто режим»

    answer = route(t, name, mode)
    return jsonify(make_response(payload, answer, name, mode))

@app.route("/", methods=["GET"])
def ping():
    return "Milashka alive"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
