# -*- coding: utf-8 -*-

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import gspread
from datetime import datetime
import os
import json

# ==========================
# TOKEN
# ==========================
TOKEN = "TON_TOKEN_ICI"

# ==========================
# GOOGLE SHEETS (RENDER SAFE)
# ==========================
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(creds_dict)

sh = gc.open("trackovapbot")
stock_sheet = sh.worksheet("Stock")
vente_sheet = sh.worksheet("Vente")

# ==========================
# SAFE FLOAT
# ==========================
def to_float(val):
    try:
        return float(str(val).replace(",", "."))
    except:
        return 0.0

# ==========================
# LIRE STOCK
# ==========================
def lire_stock():
    data = stock_sheet.get_all_records()
    stock = {}
    for ligne in data:
        nom = str(ligne.get("Goût", "")).strip().lower()
        if nom:
            stock[nom] = ligne
    return stock

# ==========================
# FIND PRODUCT
# ==========================
def trouver_produit(stock, texte):
    texte = texte.lower().replace(" ", "")
    for nom in stock:
        if texte in nom.replace(" ", ""):
            return nom
    return None

# ==========================
# UPDATE STOCK + CA + PROFIT
# ==========================
def update_stock(produit, quantite, prix):

    stock = lire_stock()
    produit = trouver_produit(stock, produit)

    if not produit:
        return False, "Produit introuvable"

    infos = stock[produit]

    stock_actuel = int(to_float(infos.get("Stock", 0)))

    if quantite > stock_actuel:
        return False, "Stock insuffisant"

    ligne = stock_sheet.find(produit).row

    ancien_ca = to_float(infos.get("CA", 0))
    ancien_profit = to_float(infos.get("Profit", 0))
    prix_achat = to_float(infos.get("Prix achat", 0))

    nouveau_ca = ancien_ca + prix
    nouveau_profit = ancien_profit + (prix - prix_achat * quantite)
    nouveau_stock = stock_actuel - quantite

    # UPDATE SAFE (1 seule requête → évite API 400)
    stock_sheet.update(
        f"B{ligne}:E{ligne}",
        [[nouveau_stock, prix_achat, nouveau_ca, nouveau_profit]]
    )

    return True, nouveau_stock

# ==========================
# HANDLER
# ==========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text.lower().strip()

    # STOCK
    if text == "stock":
        stock = lire_stock()
        msg = "📦 STOCK:\n\n"
        for k, v in stock.items():
            msg += f"{k} → {v.get('Stock', 0)}\n"
        await update.message.reply_text(msg)

    # CA
    elif text == "ca":
        stock = lire_stock()
        total = sum(to_float(v.get("CA", 0)) for v in stock.values())
        await update.message.reply_text(f"💰 CA TOTAL: {round(total,2)}€")

    # VENTE
    elif text.startswith("vente"):

        parts = text.split()

        if len(parts) < 4:
            await update.message.reply_text("❌ Format: vente produit quantité prix")
            return

        try:
            quantite = int(parts[-2])
            prix = float(parts[-1].replace(",", "."))
            produit = " ".join(parts[1:-2])
        except:
            await update.message.reply_text("❌ Nombre invalide")
            return

        ok, res = update_stock(produit, quantite, prix)

        if not ok:
            await update.message.reply_text(f"❌ {res}")
        else:
            await update.message.reply_text(f"✅ Vente OK\nStock restant: {res}")

    else:
        await update.message.reply_text("❌ Commande inconnue")

# ==========================
# START BOT (FIX RENDER SAFE)
# ==========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("🤖 BOT ULTRA STABLE LANCÉ")

    # IMPORTANT : PAS D'ASYNCICI RUN ICI
    app.run_polling()

if __name__ == "__main__":
    main()
