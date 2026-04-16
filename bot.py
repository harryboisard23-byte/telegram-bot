# -*- coding: utf-8 -*-

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import gspread
from datetime import datetime
import os
import json

# ==========================
# CONFIG
# ==========================
TOKEN = "8709654109:AAGWu3dCOLYUssS46R-ZK27CBF_7dxJDh3o"

# ==========================
# GOOGLE SHEETS (VERSION RENDER FIX)
# ==========================
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
gc = gspread.service_account_from_dict(creds_dict)

sh = gc.open("trackovapbot")
stock_sheet = sh.worksheet("Stock")
vente_sheet = sh.worksheet("Vente")

# ==========================
# FONCTION SAFE FLOAT
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
        nom = str(ligne.get("Goût", "")).lower().strip()
        if nom:
            stock[nom] = ligne
    return stock

# ==========================
# TROUVER PRODUIT (SMART)
# ==========================
def trouver_produit(stock, texte):
    texte = texte.lower()
    for nom in stock:
        if texte in nom:
            return nom
    return None

# ==========================
# AJOUTER VENTE
# ==========================
def ajouter_vente(produit, quantite, prix_total, user):
    stock = lire_stock()

    if produit not in stock:
        return False, "Produit introuvable"

    ligne_index = list(stock.keys()).index(produit) + 2

    stock_actuel = int(stock[produit].get("Stock", 0))
    prix_achat = to_float(stock[produit].get("Prix achat", 0))
    ancien_ca = to_float(stock[produit].get("CA", 0))
    ancien_profit = to_float(stock[produit].get("Profit", 0))

    if quantite > stock_actuel:
        return False, "Stock insuffisant"

    nouveau_stock = stock_actuel - quantite
    nouveau_ca = ancien_ca + prix_total
    profit = prix_total - (prix_achat * quantite)
    nouveau_profit = ancien_profit + profit

    # ✅ UPDATE SAFE (UN SEUL BLOC → PAS D’ERREUR 400)
    stock_sheet.update(f"B{ligne_index}:E{ligne_index}", [[
        nouveau_stock,
        prix_achat,
        nouveau_ca,
        nouveau_profit
    ]])

    # Historique
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vente_sheet.append_row([date, produit, quantite, prix_total, user])

    return True, nouveau_stock

# ==========================
# CALCUL CA TOTAL
# ==========================
def calcul_ca_total():
    data = stock_sheet.get_all_records()
    total = 0
    for ligne in data:
        total += to_float(ligne.get("CA", 0))
    return total

# ==========================
# BOUTONS
# ==========================
keyboard = ReplyKeyboardMarkup(
    [["📦 Stock", "💰 CA"]],
    resize_keyboard=True
)

# ==========================
# HANDLER
# ==========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.lower().strip()
        user = update.message.from_user.first_name

        # ======================
        # STOCK
        # ======================
        if text in ["stock", "📦 stock"]:
            stock = lire_stock()
            msg = "📦 STOCK :\n\n"

            for nom, infos in stock.items():
                msg += f"{nom} → {infos.get('Stock', 0)}\n"

            await update.message.reply_text(msg, reply_markup=keyboard)

        # ======================
        # CA
        # ======================
        elif text in ["ca", "💰 ca"]:
            total = calcul_ca_total()
            await update.message.reply_text(
                f"💰 CA TOTAL : {round(total,2)}€",
                reply_markup=keyboard
            )

        # ======================
        # VENTE
        # ======================
        elif text.startswith("vente"):

            parts = text.split()

            if len(parts) < 3:
                await update.message.reply_text("❌ Format: vente produit quantité prix")
                return

            # 🔥 FIX PARSING
            try:
                quantite = int(parts[-2])
                prix = float(parts[-1].replace(",", "."))
                produit_txt = " ".join(parts[1:-2])
            except:
                await update.message.reply_text("❌ Nombre invalide")
                return

            stock = lire_stock()
            produit = trouver_produit(stock, produit_txt)

            if not produit:
                await update.message.reply_text("❌ Produit introuvable")
                return

            success, result = ajouter_vente(produit, quantite, prix, user)

            if success:
                await update.message.reply_text(
                    f"✅ Vente OK\n{produit} -{quantite}\nStock restant: {result}",
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text(f"❌ {result}")

        else:
            await update.message.reply_text("❌ Commande inconnue", reply_markup=keyboard)

    except Exception as e:
        print("ERREUR :", e)
        await update.message.reply_text(f"💥 Erreur : {e}")

# ==========================
# START BOT
# ==========================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, handle_message))

print("🤖 BOT ULTRA STABLE LANCÉ")
app.run_polling()
