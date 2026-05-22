import random
import asyncio
from collections import defaultdict
from typing import Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

# (중요) TOKEN 바꿔라
TOKEN = "_"
BOT_USERNAME = "_bot"


SUSPECTS = ["김철수", "이영희", "박민수", "최지훈", "한수진", "오세훈"]
WEAPONS = ["칼", "권총", "독", "밧줄", "망치", "유리병"]
ROOMS = ["거실", "부엌", "침실", "욕실", "서재", "차고"]

GAMES: Dict[int, "Game"] = {}

# ================= GAME =================
class Game:
    def __init__(self, chat_id, max_players, difficulty=None):
        self.chat_id = chat_id
        self.max_players = max_players
        self.players = []
        self.names = {}
        self.turn_index = 0
        self.solution = {}
        self.hands = defaultdict(list)

        self.ask_state = {}
        self.guess_state = {}

        self.logs = []
        self.log_message_id = None

        # 🔥 추가: 메모 시스템
        self.notes = defaultdict(lambda: {
            "has": set(),
            "not": set()
        })
        
        self.fixed_show_card = {}  # 대상별 고정 카드


    def add_player(self, uid, name):
        if uid not in self.players:
            self.players.append(uid)
            self.names[uid] = name

    def get_name(self, p):
        return "🤖 AI" if p == "AI" else self.names.get(p, str(p))

    def all_players(self):
        return [self.players[0], "AI"] if self.max_players == 1 else self.players

    def current(self):
        return self.all_players()[self.turn_index % len(self.all_players())]

    def next(self):
        self.turn_index += 1

    def log(self, txt):
        self.logs.append(txt)
        if len(self.logs) > 10:
            self.logs.pop(0)

    def start(self):
        self.solution = {
            "suspect": random.choice(SUSPECTS),
            "weapon": random.choice(WEAPONS),
            "room": random.choice(ROOMS),
        }

        cards = [c for c in SUSPECTS if c != self.solution["suspect"]] + \
                [w for w in WEAPONS if w != self.solution["weapon"]] + \
                [r for r in ROOMS if r != self.solution["room"]]

        random.shuffle(cards)

        players = self.all_players()

        for i, c in enumerate(cards):
            self.hands[players[i % len(players)]].append(c)

        self.turn_index = 0


# ================= UTIL =================
def kb(items, prefix):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(i, callback_data=f"{prefix}:{i}")] for i in items]
    )


async def render(context, g):
    text = "🕵️ Clue\n\n"
    text += f"🎯 턴: {g.get_name(g.current())}\n\n"

    # 🔥 AI 턴일 때 안내 문구 추가
    if g.current() == "AI":
        text += "🤖 AI가 생각중...\n\n"

    text += "📜 로그\n"
    for l in g.logs:
        text += f"- {l}\n"

    current = g.current()

    # 🔥 버튼 조건부 표시
    if current != "AI":
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("질문", callback_data="ask")],
            [InlineKeyboardButton("추리", callback_data="guess")]
        ])
    else:
        buttons = None  # AI 턴에는 버튼 없음

    if g.log_message_id is None:
        m = await context.bot.send_message(
            g.chat_id,
            text,
            reply_markup=buttons
        )
        g.log_message_id = m.message_id
    else:
        await context.bot.edit_message_text(
            chat_id=g.chat_id,
            message_id=g.log_message_id,
            text=text,
            reply_markup=buttons
        )

    # 🔥 AI 턴이면 자동 실행 (기존 유지)
    if g.current() == "AI":
        await ai_turn(context, g)


# async def render(context, g):
#     text = "🕵️ Clue\n\n"
#     text += f"🎯 턴: {g.get_name(g.current())}\n\n"
#     text += "📜 로그\n"
#     for l in g.logs:
#         text += f"- {l}\n"

#     buttons = InlineKeyboardMarkup([
#         [InlineKeyboardButton("질문", callback_data="ask")],
#         [InlineKeyboardButton("추리", callback_data="guess")]
#     ])

#     if g.log_message_id is None:
#         m = await context.bot.send_message(g.chat_id, text, reply_markup=buttons)
#         g.log_message_id = m.message_id
#     else:
#         await context.bot.edit_message_text(
#             chat_id=g.chat_id,
#             message_id=g.log_message_id,
#             text=text,
#             reply_markup=buttons
#         )

#     if g.current() == "AI":
#         await ai_turn(context, g)


# ================= AI =================
# async def ai_turn(context, g):
#     await asyncio.sleep(1)

#     action = random.choice(["ask", "guess"])

#     if action == "ask":
#         suspect = random.choice(SUSPECTS)
#         weapon = random.choice(WEAPONS)
#         room = random.choice(ROOMS)

#         g.log(f"🤖 AI → {g.get_name(g.players[0])} 질문: {suspect}/{weapon}/{room}")

#     else:
#         suspect = random.choice(SUSPECTS)
#         weapon = random.choice(WEAPONS)
#         room = random.choice(ROOMS)

#         if {
#             "suspect": suspect,
#             "weapon": weapon,
#             "room": room
#         } == g.solution:
#             g.log("🤖 AI 정답!")
#             await render(context, g)
#             del GAMES[g.chat_id]
#             return
#         else:
#             g.log("🤖 AI 실패")

#     g.next()
#     await render(context, g)

# ================= AI =================
async def ai_turn(context, g):
    await asyncio.sleep(1)

    ai = "AI"
    player = g.players[0]

    notes = g.notes[player]  # AI는 "플레이어 정보" 기준으로 추리

    def filter_candidates(all_items):
        return [
            x for x in all_items
            if x not in notes["has"] and x not in notes["not"]
        ] or all_items  # fallback
        

    suspects = filter_candidates(SUSPECTS)
    weapons = filter_candidates(WEAPONS)
    rooms = filter_candidates(ROOMS)

    # 🔥 확정 가능하면 바로 추리
    if len(suspects) == 1 and len(weapons) == 1 and len(rooms) == 1:
        suspect = suspects[0]
        weapon = weapons[0]
        room = rooms[0]

        if {
            "suspect": suspect,
            "weapon": weapon,
            "room": room
        } == g.solution:
            g.log("🤖 AI 정답!")
            await render(context, g)
            del GAMES[g.chat_id]
            return
        else:
            g.log("🤖 AI 확정 추리 실패")

        g.next()
        await render(context, g)
        return

    # 🔥 행동 선택 (조금 더 똑똑하게)
    action = "ask" if random.random() < 0.7 else "guess"

    if action == "ask":
        suspect = random.choice(suspects)
        weapon = random.choice(weapons)
        room = random.choice(rooms)

        g.log(f"🤖 AI → {g.get_name(player)} 질문: {suspect}/{weapon}/{room}")

        # 🔥 실제 카드 체크 (AI도 결과 반영해야 똑똑해짐)
        cards = g.hands[player]
        matches = [c for c in [suspect, weapon, room] if c in cards]

        if matches:
            card = random.choice(matches)
            g.notes[player]["has"].add(card)
        else:
            g.notes[player]["not"].update([suspect, weapon, room])

    else:
        suspect = random.choice(suspects)
        weapon = random.choice(weapons)
        room = random.choice(rooms)

        if {
            "suspect": suspect,
            "weapon": weapon,
            "room": room
        } == g.solution:
            g.log("🤖 AI 정답!")
            await render(context, g)
            del GAMES[g.chat_id]
            return
        else:
            g.log("🤖 AI 실패")

    g.next()
    await render(context, g)


# ================= NOTE COMMAND =================
async def note(update, context):
    chat = update.effective_chat.id
    user = update.effective_user.id

    g = GAMES.get(chat)
    if not g:
        return await update.message.reply_text("게임 없음")

    text = "🧠 추리 메모\n\n"

    for target, data in g.notes.items():
        text += f"[{g.get_name(target)}]\n"
        if data["has"]:
            text += "✔ 있음: " + ", ".join(data["has"]) + "\n"
        if data["not"]:
            text += "❌ 없음: " + ", ".join(data["not"]) + "\n"
        text += "\n"

    await update.message.reply_text(text)


# ================= COMMAND =================
async def create(update, context):
    chat = update.effective_chat.id
    args = context.args

    g = Game(chat, int(args[0]), args[1] if len(args) > 1 else None)
    GAMES[chat] = g

    await update.message.reply_text("방 생성됨 /join")


async def join(update, context):
    chat = update.effective_chat.id
    user = update.effective_user
    g = GAMES.get(chat)

    if not g:
        return await update.message.reply_text("방 없음 /create 먼저")

    g.add_player(user.id, user.first_name)

    if len(g.players) == g.max_players:
        g.start()

        for p in g.players:
            await context.bot.send_message(p, f"카드: {g.hands[p]}")

        g.log("게임 시작")
        await render(context, g)


async def help_command(update, context):
    text = (
        "📖 Clue Bot 사용법\n\n"
        "🎮 게임 흐름\n"
        "- /create [인원] : 방 생성\n"
        "- /join : 게임 참여\n"
        "- 인원 다 차면 자동 시작\n\n"
        "🕵️ 게임 명령\n"
        "- 질문 : 상대에게 카드 확인\n"
        "- 추리 : 정답 맞추기\n\n"
        "🧠 추가 기능\n"
        "- /note : 지금까지 확인된 카드 메모 보기\n\n"
        "💡 규칙\n"
        "- 질문하면 상대 카드 중 1개만 공개됨\n"
        "- 없으면 '없음' 처리\n"
        "- 먼저 정답 맞추면 승리\n"
    )
    await update.message.reply_text(text)

# ================= ASK =================
async def start_ask(update, context, g):
    q = update.callback_query
    user = g.current()

    if q.from_user.id != user:
        return await q.answer("니 턴 아님")

    targets = ["AI"] if g.max_players == 1 else [p for p in g.players if p != user]

    await q.edit_message_text(
        "🎯 대상 선택",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(g.get_name(p), callback_data=f"a_t:{p}")]
            for p in targets
        ])
    )


async def handle_ask(update, context):
    q = update.callback_query
    g = GAMES.get(q.message.chat.id)
    user = g.current()

    k, v = q.data.split(":")
    s = g.ask_state.setdefault(user, {})

    if k == "a_t":
        s["target"] = v if v == "AI" else int(v)
        await q.edit_message_text("범인", reply_markup=kb(SUSPECTS, "a_s"))

    elif k == "a_s":
        s["suspect"] = v
        await q.edit_message_text("무기", reply_markup=kb(WEAPONS, "a_w"))

    elif k == "a_w":
        s["weapon"] = v
        await q.edit_message_text("장소", reply_markup=kb(ROOMS, "a_r"))

    elif k == "a_r":
        s["room"] = v

        target = s["target"]
        cards = g.hands[target]

        g.log(f"{g.get_name(user)} → {g.get_name(target)} 질문: {s['suspect']}/{s['weapon']}/{s['room']}")

        matches = [c for c in [s["suspect"], s["weapon"], s["room"]] if c in cards]

        if matches:
            if target not in g.fixed_show_card:
                g.fixed_show_card[target] = random.choice(matches)

            card = g.fixed_show_card[target]

            await context.bot.send_message(user, f"🔍 확인된 카드: {card}")
            g.log("카드 공개")

            # 🔥 메모 추가 (있음)
            g.notes[target]["has"].add(card)

        else:
            await q.answer("없음")
            g.log("없음")

            # 🔥 메모 추가 (없음)
            g.notes[target]["not"].update([s["suspect"], s["weapon"], s["room"]])

        g.next()
        await render(context, g)


# ================= GUESS =================
async def start_guess(update, context, g):
    q = update.callback_query
    user = g.current()

    if q.from_user.id != user:
        return await q.answer("니 턴 아님")

    await q.edit_message_text("범인 선택", reply_markup=kb(SUSPECTS, "g_s"))


async def handle_guess(update, context):
    q = update.callback_query
    g = GAMES.get(q.message.chat.id)
    user = g.current()

    k, v = q.data.split(":")
    s = g.guess_state.setdefault(user, {})

    if k == "g_s":
        s["suspect"] = v
        await q.edit_message_text("무기", reply_markup=kb(WEAPONS, "g_w"))

    elif k == "g_w":
        s["weapon"] = v
        await q.edit_message_text("장소", reply_markup=kb(ROOMS, "g_r"))

    elif k == "g_r":
        s["room"] = v

        if s == g.solution:
            g.log("정답!")
            await render(context, g)
            del GAMES[g.chat_id]
            return

        g.log("실패")
        g.next()
        await render(context, g)


# ================= BUTTON =================
async def button(update, context):
    q = update.callback_query
    await q.answer()

    g = GAMES.get(q.message.chat.id)
    if not g:
        return

    if q.data == "ask":
        await start_ask(update, context, g)

    elif q.data == "guess":
        await start_guess(update, context, g)

    elif q.data.startswith("a_"):
        await handle_ask(update, context)

    elif q.data.startswith("g_"):
        await handle_guess(update, context)


# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("create", create))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("note", note))  # 🔥 추가됨
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button))

    print("RUN")
    app.run_polling()