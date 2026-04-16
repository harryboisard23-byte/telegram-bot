# -*- coding: utf-8 -*-

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import gspread
from datetime import datetime

TOKEN = "8709654109:AAGWu3dCOLYUssS46R-ZK27CBF_7dxJDh3o"

gc = gspread.service_account(filename="credentials.json")
sh = gc.open("trackovapbot")

stock_sheet = sh.worksheet("Stock")
vente_sheet = sh.worksheet("Vente")

# ==========================
# CLAVIER
# ==========================
keyboard = [
    ["Vente", "Stock"],
    ["CA"]
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==========================
# ETAT USER
# ==========================
user_state = {}

# ==========================
# SAFE FLOAT (ULTRA FIX)
# ==========================
def safe_float(val):
    try:
        if val is None:
            return 0.0

        val = str(val)
        val = val.replace(",", ".")
        val = val.replace("€", "")
        val = val.strip()

        if val == "":
            return 0.0

        return float(val)

    except:
        return 0.0

# ==========================
# LECTURE STOCK
# ==========================
def lire_stock():
    data = stock_sheet.get_all_records()
    clean = {}

    for row in data:
        gout = str(row.get("Goût", "")).strip()
        if gout:
            clean[gout] = row

    return clean

# ==========================
# RECHERCHE PRODUIT
# ==========================
def find_product(stock, recherche):
    r = recherche.lower().replace(" ", "")

    for k in stock.keys():
        if r in k.lower().replace(" ", ""):
            return k

    return None

# ==========================
# UPDATE STOCK (SAFE)
# ==========================
def update_stock(produit, quantite, prix):

    stock = lire_stock()
    produit_trouve = find_product(stock, produit)

    if not produit_trouve:
        return False, "Produit introuvable"

    infos = stock[produit_trouve]

    stock_dispo = int(safe_float(infos.get("Stock")))

    if quantite > stock_dispo:
        return False, "Stock insuffisant"

    nouvelle_qte = stock_dispo - quantite

    cell = stock_sheet.find(produit_trouve)
    row = cell.row

    # 🔥 SAFE colonnes
    ancien_ca = safe_float(
        infos.get("Chiffre d affaires")
        or infos.get("CA")
    )

    ancien_profit = safe_float(infos.get("Profit"))

    prix_achat = safe_float(
        infos.get("Prix achat")
    )

    # 🔥 calcul
    ca = ancien_ca + prix
    profit = ancien_profit + (prix - (prix_achat * quantite))

    # 🔥 update sans bug API
    stock_sheet.update(f"B{row}", [[nouvelle_qte]])
    stock_sheet.update(f"D{row}", [[ca]])
    stock_sheet.update(f"E{row}", [[profit]])

    return True, (produit_trouve, nouvelle_qte)

# ==========================
# LOG VENTE
# ==========================
def log_vente(produit, quantite, prix, user):
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vente_sheet.append_row([date, produit, quantite, prix, user])

# ==========================
# DASHBOARD
# ==========================
def dashboard():
    stock = lire_stock()

    ca = 0
    profit = 0
    total = 0

    for v in stock.values():

        ca += safe_float(
            v.get("Chiffre d affaires")
            or v.get("CA")
        )

        profit += safe_float(v.get("Profit"))

        try:
            total += int(safe_float(v.get("Stock")))
        except:
            total += 0

    return ca, profit, total

# ==========================
# HANDLER
# ==========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    text = update.message.text.strip()

    # MENU
    if text.lower() in ["start", "/start", "menu"]:
        user_state[user_id] = None
        await update.message.reply_text("👋 Menu", reply_markup=reply_markup)
        return

    # VENTE
    if text.lower() == "vente":
        user_state[user_id] = {"step": "produit"}
        await update.message.reply_text("🛒 Produit ?")
        return

    # STOCK
    if text.lower() == "stock":
        stock = lire_stock()
        msg = "📦 STOCK:\n\n"

        for k, v in stock.items():
            msg += f"{k}: {int(safe_float(v.get('Stock')))} | CA: {safe_float(v.get('Chiffre d affaires'))}€ | Profit: {safe_float(v.get('Profit'))}€\n"

        await update.message.reply_text(msg, reply_markup=reply_markup)
        return

    # CA
    if text.lower() == "ca":
        ca, profit, total = dashboard()

        await update.message.reply_text(
            f"📊 DASHBOARD\n\n💰 CA: {ca}€\n📈 Profit: {profit}€\n📦 Stock: {total}",
            reply_markup=reply_markup
        )
        return

    # FLOW VENTE
    if user_id in user_state and user_state[user_id]:

        state = user_state[user_id]

        if state["step"] == "produit":
            state["produit"] = text
            state["step"] = "quantite"
            await update.message.reply_text("📦 Quantité ?")
            return

        elif state["step"] == "quantite":
            try:
                state["quantite"] = int(text)
            except:
                await update.message.reply_text("❌ Nombre invalide")
                return

            state["step"] = "prix"
            await update.message.reply_text("💰 Prix total ?")
            return

        elif state["step"] == "prix":
            try:
                state["prix"] = float(text.replace(",", "."))
            except:
                await update.message.reply_text("❌ Prix invalide")
                return

            success, result = update_stock(
                state["produit"],
                state["quantite"],
                state["prix"]
            )

            if not success:
                await update.message.reply_text(f"❌ {result}")
                user_state[user_id] = None
                return

            user = update.message.from_user.username or "inconnu"
            log_vente(state["produit"], state["quantite"], state["prix"], user)

            prod, stock_restant = result

            await update.message.reply_text(
                f"✅ Vente OK\n{prod}\n-{state['quantite']}\nStock: {stock_restant}",
                reply_markup=reply_markup
            )

            user_state[user_id] = None
            return

    await update.message.reply_text("❌ Utilise les boutons", reply_markup=reply_markup)

# ==========================
# RUN
# ==========================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, handle_message))

print("🤖 BOT 100% SAFE ANTI APOSTROPHE OK")
app.run_polling()
