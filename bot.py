# -*- coding: utf-8 -*-

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import gspread
import os
import json

TOKEN = "TON_TOKEN_ICI"

# ==========================
# GOOGLE SHEETS
# ==========================
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(creds_dict)

sh = gc.open("trackovapbot")
stock_sheet = sh.worksheet("Stock")

# ==========================
# SAFE FLOAT
# ==========================
def to_float(x):
    try:
        return float(str(x).replace(",", "."))
    except:
        return 0.0

# ==========================
# LIRE STOCK
# ==========================
def lire_stock():
    data = stock_sheet.get_all_records()
    stock = {}
    for r in data:
        nom = str(r.get("Goût", "")).strip().lower()
        if nom:
            stock[nom] = r
    return stock

# ==========================
# TROUVER PRODUIT
# ==========================
def trouver(stock, texte):
    texte = texte.lower().replace(" ", "")
    for k in stock:
        if texte in k.replace(" ", ""):
            return k
    return None

# ==========================
# UPDATE STOCK + CA
# ==========================
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
    prix_achat = to_float(infos.get("Prix achat"))

    new_stock = stock_actuel - qty
    new_ca = ca + price

    stock_sheet.update(
        f"B{row}:D{row}",
        [[new_stock, prix_achat, new_ca]]
    )

    return True, new_stock

# ==========================
# HANDLER
# ==========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text.lower().strip()

    # STOCK
    if text == "stock":
        stock = lire_stock()
        msg = "📦 STOCK:\n\n"
        for k, v in stock.items():
            msg += f"{k} → {v.get('Stock',0)}\n"
        await update.message.reply_text(msg)

    # CA
    elif text == "ca":
        stock = lire_stock()
        total = sum(to_float(v.get("CA")) for v in stock.values())
        await update.message.reply_text(f"💰 CA: {round(total,2)}€")

    # VENTE
    elif text.startswith("vente"):

        parts = text.split()

        if len(parts) < 4:
            await update.message.reply_text("❌ Format: vente produit quantité prix")
            return

        try:
            qty = int(parts[-2])
            price = float(parts[-1].replace(",", "."))
            prod = " ".join(parts[1:-2])
        except:
            await update.message.reply_text("❌ Nombre invalide")
            return

        ok, res = update_stock(prod, qty, price)

        if ok:
            await update.message.reply_text(f"✅ Vente OK\nStock: {res}")
        else:
            await update.message.reply_text(f"❌ {res}")

    else:
        await update.message.reply_text("❌ Commande inconnue")

# ==========================
# START BOT (V20 CLEAN)
# ==========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT, handle))

    print("🤖 BOT V20 STABLE LANCÉ")

    app.run_polling()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
