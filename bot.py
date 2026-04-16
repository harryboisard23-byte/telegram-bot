# -*- coding: utf-8 -*-

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import gspread
import os
import json
import traceback
import sys

# ==========================
# CONFIGURATION
# ==========================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

# ==========================
# VÉRIFICATIONS AU DÉMARRAGE
# ==========================
print("🔄 Démarrage du bot...")

if not TOKEN:
    print("❌ ERREUR: Variable TELEGRAM_TOKEN manquante")
    sys.exit(1)

if not GOOGLE_CREDENTIALS:
    print("❌ ERREUR: Variable GOOGLE_CREDENTIALS manquante")
    sys.exit(1)

print(f"✅ TOKEN trouvé: {TOKEN[:10]}...")
print(f"✅ CREDENTIALS trouvé: {len(GOOGLE_CREDENTIALS)} caractères")

# ==========================
# GOOGLE SHEETS
# ==========================
try:
    # Nettoie le JSON (enlève retours à la ligne problématiques)
    clean_creds = GOOGLE_CREDENTIALS.replace('\n', '\\n')
    creds_dict = json.loads(clean_creds)
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open("trackovapbot")
    stock_sheet = sh.worksheet("Stock")
    print("✅ Connexion Google Sheets OK")
except json.JSONDecodeError as e:
    print(f"❌ ERREUR JSON (credentials mal formatés): {e}")
    print("💡 Astuce: Encode ton JSON en base64 ou mets-le sur une seule ligne")
    sys.exit(1)
except gspread.SpreadsheetNotFound:
    print("❌ ERREUR: Spreadsheet 'trackovapbot' introuvable")
    print("💡 Vérifie le nom et le partage avec le service account")
    sys.exit(1)
except Exception as e:
    print(f"❌ ERREUR Google Sheets: {e}")
    traceback.print_exc()
    sys.exit(1)

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
    for idx, r in enumerate(data, start=2):
        nom = str(r.get("Goût", "")).strip()
        if nom:
            stock[nom.lower()] = {
                **r,
                "_row": idx,
                "_nom_original": nom
            }
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
    prod_key = trouver(stock, prod)

    if not prod_key:
        return False, "Produit introuvable"

    infos = stock[prod_key]
    row = infos["_row"]

    stock_actuel = int(to_float(infos.get("Stock")))
    if qty > stock_actuel:
        return False, f"Stock insuffisant ({stock_actuel} dispo)"

    ca = to_float(infos.get("CA"))
    prix_achat = to_float(infos.get("Prix achat"))

    new_stock = stock_actuel - qty
    new_ca = ca + price

    stock_sheet.update(f"B{row}:D{row}", [[new_stock, prix_achat, new_ca]])

    return True, new_stock

# ==========================
# HANDLER
# ==========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower().strip()

    if text == "aide":
        msg = """🤖 COMMANDES:

• stock → Voir le stock
• ca → Voir le chiffre d'affaires
• vente [produit] [quantité] [prix] → Enregistrer une vente

Exemple: vente fraise 2 15"""
        await update.message.reply_text(msg)

    elif text == "stock":
        try:
            stock = lire_stock()
            msg = "📦 STOCK:\n\n"
            for k, v in stock.items():
                nom = v.get("_nom_original", k)
                qty = v.get("Stock", 0)
                msg += f"• {nom} → {qty}\n"
            await update.message.reply_text(msg)
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {e}")

    elif text == "ca":
        try:
            stock = lire_stock()
            total = sum(to_float(v.get("CA")) for v in stock.values())
            await update.message.reply_text(f"💰 CA Total: {round(total, 2)}€")
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {e}")

    elif text.startswith("vente"):
        parts = text.split()

        if len(parts) < 4:
            await update.message.reply_text("❌ Format: vente [produit] [quantité] [prix]\nExemple: vente fraise 2 15")
            return

        try:
            qty = int(parts[-2])
            price = float(parts[-1].replace(",", "."))
            prod = " ".join(parts[1:-2])
        except:
            await update.message.reply_text("❌ Quantité ou prix invalide")
            return

        try:
            ok, res = update_stock(prod, qty, price)
            if ok:
                await update.message.reply_text(f"✅ Vente enregistrée\n📦 Stock restant: {res}")
            else:
                await update.message.reply_text(f"❌ {res}")
        except Exception as e:
            await update.message.reply_text(f"❌ Erreur: {e}")

    else:
        await update.message.reply_text("❌ Commande inconnue\nTape 'aide' pour voir les commandes")

# ==========================
# MAIN
# ==========================
def main():
    try:
        print("🔄 Construction de l'application...")
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT, handle))
        print("🤖 BOT PRÊT - Lancement du polling...")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ ERREUR FATALE: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()



if __name__ == "__main__":
    main()
