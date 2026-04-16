# -*- coding: utf-8 -*-

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from flask import Flask, request
import gspread
import os
import json

TOKEN = "8709654109:AAGWu3dCOLYUssS46R-ZK27CBF_7dxJDh3o"

# ==========================
# GOOGLE SHEETS
# ==========================
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(creds_dict)

sh = gc.open("trackovapbot")
stock_sheet = sh.worksheet("Stock")

# ==========================
def to_float(x):
    try:
        return float(str(x).replace(",", "."))
    except:
        return 0.0

def lire_stock():
    data = stock_sheet.get_all_records()
    return {str(r.get("Goût","")).lower(): r for r in data if r.get("Goût")}

def trouver(stock, txt):
    txt = txt.lower().replace(" ", "")
    for k in stock:
        if txt in k.replace(" ", ""):
            return k
    return None

def update_stock(prod, qty, price):
    stock = lire_stock()
    prod = trouver(stock, prod)

    if not prod:
        return False, "Produit introuvable"

    infos = stock[prod]

    stock_actuel = int(to_float(infos.get("Stock")))
    if qty > stock_actuel:
        return False, "Stock insuffisant"

    row = stock_sheet.find(prod).row

    ca = to_float(infos.get("CA"))
    profit = to_float(infos.get("Profit"))
    prix_achat = to_float(infos.get("Prix achat"))

    new_stock = stock_actuel - qty
    new_ca = ca + price
    new_profit = profit + (price - prix_achat * qty)

    stock_sheet.update(f"B{row}:E{row}", [[new_stock, prix_achat, new_ca, new_profit]])

    return True, new_stock

# ==========================
# TELEGRAM HANDLER
# ==========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()

    if text == "stock":
        stock = lire_stock()
        msg = "📦 STOCK:\n\n"
        for k,v in stock.items():
            msg += f"{k} → {v.get('Stock',0)}\n"
        await update.message.reply_text(msg)

    elif text == "ca":
        stock = lire_stock()
        total = sum(to_float(v.get("CA")) for v in stock.values())
        await update.message.reply_text(f"💰 CA: {round(total,2)}€")

    elif text.startswith("vente"):
        parts = text.split()

        if len(parts) < 4:
            await update.message.reply_text("❌ vente produit quantité prix")
            return

        try:
            qty = int(parts[-2])
            price = float(parts[-1].replace(",", "."))
            prod = " ".join(parts[1:-2])
        except:
            await update.message.reply_text("❌ erreur nombre")
            return

        ok, res = update_stock(prod, qty, price)

        if ok:
            await update.message.reply_text(f"✅ OK stock: {res}")
        else:
            await update.message.reply_text(f"❌ {res}")

# ==========================
# FLASK SERVER (WEBHOOK)
# ==========================
app_flask = Flask(__name__)
app_bot = ApplicationBuilder().token(TOKEN).build()
app_bot.add_handler(MessageHandler(filters.TEXT, handle))

@app_flask.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_bot.bot)
    app_bot.update_queue.put_nowait(update)
    return "ok"

@app_flask.route("/")
def home():
    return "Bot running"

# ==========================
# START
# ==========================
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))

    app_bot.initialize()
    app_bot.start()

    # IMPORTANT : set webhook
    app_bot.bot.set_webhook(url=f"https://TON-URL-RENDER.onrender.com/{TOKEN}")

    app_flask.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
