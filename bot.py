import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import sqlite3
import random
import json
import secrets
from discord.ui import Button, View

SHOP_FILE = "shop.json"
# Exemple simple de stockage utilisateur
user_data = {}

def get_user(user_id):
    return user_data.get(user_id, (user_id, 1000.0))  # par défaut 1000€

def update_user(user_id, euros):
    user_data[user_id] = (user_id, euros)


def load_shop():
    try:
        with open(SHOP_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_shop(data):
    with open(SHOP_FILE, "w") as f:
        json.dump(data, f, indent=4)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Connexion à la base SQLite
db = sqlite3.connect("eurobot.db")
cursor = db.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    euros REAL DEFAULT 10.0,
    inventory TEXT DEFAULT '',
    last_daily TEXT DEFAULT '1970-01-01',
    job TEXT DEFAULT '',
    last_job TEXT DEFAULT '1970-01-01',
    bank REAL DEFAULT 0.0
)''')
db.commit()

# ---------------- UTILS ----------------
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        db.commit()
        return get_user(user_id)
    return user

def update_inventory(user_id, item):
    user = get_user(user_id)
    inventory = user[2].split(',') if user[2] else []
    inventory.append(item)
    new_inventory = ','.join(inventory)
    cursor.execute("UPDATE users SET inventory = ? WHERE user_id = ?", (new_inventory, user_id))
    db.commit()

# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")
    apply_inflation.start()

# ---------------- COMMANDES ----------------
@bot.command()
async def help(ctx):
    commands = [
        "!info - Informations sur le systeme d'achat",
        "!solde - Affiche ton solde et ta banque 💶",
        "!give @user montant - Donner de l'argent à un autre 💸",
        "!daily - Réclame ta récompense quotidienne 🗓️",
        "!top - Voir le classement des plus riches 🏆",
        "!shop - Voir les objets en vente 🛒",
        "!buy objet - Acheter un objet 🎁",
        "!inventaire - Voir ton inventaire 🎒",
        "!depot montant - Déposer de l'argent en banque 🏦",
        "!retrait montant - Retirer de l'argent de la banque 💵",
        "!job métier - Travailler et gagner de l'argent 💼",
        "!addmoney - Ajouter de l'argent a un compte",
        "!updateshop - Commande pour update le Shop",
        "!aide - Affiche l'aide",
        "!equivalence - Affiche l'équivalence de la monnaie en argent réel",
        "!gamble - Jouer au Jeu pour gagner de l'argent",
        "!blackjack - Jouer au Blackjack",
        "!crypto - Parier sur certaines Cryptomonnaie"
    ]
    await ctx.send("**📖 Commandes disponibles :**\n" + "\n".join(commands))

@bot.command()
async def solde(ctx):
    user = get_user(str(ctx.author.id))
    euros = float(user[1])
    bank = float(user[6])
    await ctx.send(f"💶 {ctx.author.mention}, tu as {euros:.2f}€ en main et {bank:.2f}€ à la banque.")

@bot.command()
async def give(ctx, member: discord.Member, amount: float):
    if amount <= 0:
        return await ctx.send("❌ Montant invalide.")
    sender = get_user(str(ctx.author.id))
    receiver = get_user(str(member.id))
    if sender[1] < amount:
        return await ctx.send("❌ Solde insuffisant.")
    cursor.execute("UPDATE users SET euros = euros - ? WHERE user_id = ?", (amount, str(ctx.author.id)))
    cursor.execute("UPDATE users SET euros = euros + ? WHERE user_id = ?", (amount, str(member.id)))
    db.commit()
    await ctx.send(f"✅ {ctx.author.mention} a donné {amount:.2f}€ à {member.mention}.")

@bot.command()
async def daily(ctx):
    user = get_user(str(ctx.author.id))
    today = datetime.utcnow().date()
    last_claim = datetime.strptime(user[3], "%Y-%m-%d").date()
    if today <= last_claim:
        return await ctx.send("🕒 Tu as déjà récupéré ton daily aujourd'hui.")
    cursor.execute("UPDATE users SET euros = euros + 2, last_daily = ? WHERE user_id = ?", (today.strftime("%Y-%m-%d"), str(ctx.author.id)))
    db.commit()
    await ctx.send(f"💸 {ctx.author.mention}, tu as reçu 2.00€ aujourd'hui !")

@bot.command()
async def top(ctx):
    cursor.execute("SELECT user_id, euros FROM users ORDER BY euros DESC LIMIT 5")
    top_users = cursor.fetchall()
    msg = "**🏆 Top 5 des plus riches :**\n"
    for i, (uid, euros) in enumerate(top_users, 1):
        user = await bot.fetch_user(int(uid))
        msg += f"{i}. {user.name} → {euros:.2f}€\n"
    await ctx.send(msg)

@bot.command()
async def addmoney(ctx, member: discord.Member, amount: float):
    if str(ctx.author.id) != "1191815509134553138":
        return await ctx.send("⛔ Seul l'utilisateur autorisé peut utiliser cette commande.")
    get_user(str(member.id))
    cursor.execute("UPDATE users SET euros = euros + ? WHERE user_id = ?", (amount, str(member.id)))
    db.commit()
    await ctx.send(f"✅ {amount:.2f}€ ajoutés à {member.mention}.")

# ---------------- BOUTIQUE ----------------




@bot.command()
async def inventaire(ctx):
    user = get_user(str(ctx.author.id))
    inv = user[2].split(',') if user[2] else []
    if not inv:
        return await ctx.send("🎒 Ton inventaire est vide.")
    items = ' '.join(inv)
    await ctx.send(f"🎒 Inventaire de {ctx.author.mention} : {items}")

# ---------------- BANQUE ----------------
@bot.command()
async def depot(ctx, montant: float):
    user = get_user(str(ctx.author.id))
    if montant <= 0 or user[1] < montant:
        return await ctx.send("❌ Montant invalide ou insuffisant.")
    cursor.execute("UPDATE users SET euros = euros - ?, bank = bank + ? WHERE user_id = ?", (montant, montant, str(ctx.author.id)))
    db.commit()
    await ctx.send(f"🏦 Dépôt de {montant:.2f}€ effectué à la banque.")

@bot.command()
async def retrait(ctx, montant: float):
    user = get_user(str(ctx.author.id))
    if montant <= 0 or user[6] < montant:
        return await ctx.send("❌ Montant invalide ou insuffisant à la banque.")
    cursor.execute("UPDATE users SET bank = bank - ?, euros = euros + ? WHERE user_id = ?", (montant, montant, str(ctx.author.id)))
    db.commit()
    await ctx.send(f"💵 Retrait de {montant:.2f}€ effectué depuis la banque.")

# ---------------- JOBS ----------------
jobs = {"livreur": (5, 10), "dev": (15, 30), "voleur": (0, 50)}

@bot.command()
async def job(ctx, metier: str):
    metier = metier.lower()
    if metier not in jobs:
        return await ctx.send("❌ Métier inconnu.")
    user = get_user(str(ctx.author.id))
    today = datetime.utcnow().date()
    last_job = datetime.strptime(user[5], "%Y-%m-%d").date()
    if today <= last_job:
        return await ctx.send("🕒 Tu as déjà travaillé aujourd'hui.")
    gain = round(random.uniform(*jobs[metier]), 2)
    cursor.execute("UPDATE users SET euros = euros + ?, last_job = ?, job = ? WHERE user_id = ?", (gain, today.strftime("%Y-%m-%d"), metier, str(ctx.author.id)))
    db.commit()
    await ctx.send(f"💼 {ctx.author.mention}, tu as travaillé comme **{metier}** et gagné {gain:.2f}€ !")


@bot.command()
async def info(ctx):
    messages = [
        "📝 Vous pouvez faire une **demande d'achat** auprès des administrateurs.",
        "💳 Les paiements sont acceptés via **PayPal** ou en **cryptomonnaie**.",
        "🎁 Une fois vos crédits ajoutés, vous pourrez effectuer des achats dans le système avec une **large sélection d'objets et services**."
    ]
    await ctx.send("**ℹ️ Informations sur le système d'achat :**\n" + "\n".join(messages))

@bot.command()
async def aide(ctx):
    messages = [
        "📩 Vous pouvez **ouvrir un ticket** pour que les administrateurs s'occupent de votre problème.",
        "❗ Si vous avez une question urgente, **mentionnez un admin** ou posez-la directement ici.",
        "💡 Utilisez aussi la commande `!help` pour voir la liste des commandes disponibles."
    ]
    await ctx.send("**🆘 Aide et assistance :**\n" + "\n".join(messages))

# ---------------- COMMANDES SHOP ADMIN ----------------
@bot.command()
async def updateshop(ctx, *args):
    if str(ctx.author.id) != "1191815509134553138":
        return await ctx.send("⛔ Seul l'utilisateur autorisé peut modifier la boutique.")
    
    if len(args) < 2:
        return await ctx.send("❌ Format attendu : `!updateshop NomDuProduit Prix`")

    try:
        price = float(args[-1])
        item_name = " ".join(args[:-1])
    except ValueError:
        return await ctx.send("❌ Le prix doit être un nombre (ex: `!updateshop Carte Netflix 12.99`)")

    shop = load_shop()
    shop[item_name] = price
    save_shop(shop)
    await ctx.send(f"✅ Produit **{item_name}** ajouté ou mis à jour : {price:.2f}€.")


# ---------------- BOUTIQUE PUBLIQUE ----------------
@bot.command()
async def shop(ctx):
    shop = load_shop()
    if not shop:
        return await ctx.send("🛒 La boutique est vide pour le moment.")
    msg = "**🛍️ Boutique disponible :**\n"
    for item, price in shop.items():
        msg += f"• {item} → {price:.2f}€\n"
    await ctx.send(msg)

@bot.command()
async def buy(ctx, *, item_name: str):
    shop = load_shop()
    if item_name not in shop:
        return await ctx.send("❌ Cet article n'existe pas.")
    user = get_user(str(ctx.author.id))
    price = float(shop[item_name])
    if user[1] < price:
        return await ctx.send("❌ Tu n'as pas assez d'argent.")
    cursor.execute("UPDATE users SET euros = euros - ? WHERE user_id = ?", (price, str(ctx.author.id)))
    db.commit()
    admin_user = await bot.fetch_user(1191815509134553138)
    await admin_user.send(f"📩 Nouvelle demande d'achat : {ctx.author.name} ({ctx.author.id}) souhaite acheter **{item_name}** pour {price:.2f}€.")
    await ctx.send(f"📨 Ta demande d'achat pour **{item_name}** a été envoyée à l'administrateur.")

@bot.command()
async def equivalence(ctx):
    user = get_user(str(ctx.author.id))
    euros = float(user[1])
    shop = load_shop()
    if not shop:
        return await ctx.send("🛒 La boutique est vide.")

    msg = [
        "🤔 Tu veux savoir combien de produits tu peux acheter avec ton argent ?",
        f"💶 Tu as **{euros:.2f}€**.",
        "📊 Voici l’équivalence de ton argent en produits disponibles :"
    ]

    for item, price in shop.items():
        if price <= 0:
            continue
        quantite = int(euros // price)
        msg.append(f"• {item} → **{quantite} fois** (à {price:.2f}€ chacun)")

    await ctx.send("\n".join(msg))

@bot.command()
async def gamble(ctx, montant: float):
    if montant <= 0:
        await ctx.send("❌ Le montant doit être supérieur à 0.")
        return

    user = get_user(str(ctx.author.id))
    euros = float(user[1])
    if euros < montant:
        await ctx.send("❌ Tu n'as pas assez d'argent pour parier cette somme.")
        return

    rand = random.SystemRandom()
    chance = rand.uniform(0, 100)

    if chance < 28.5:
        multiplicateur = rand.uniform(1.6, 3.5)
        gain = montant * multiplicateur
        new_total = euros + gain
        cursor.execute("UPDATE users SET euros = ? WHERE user_id = ?", (new_total, str(ctx.author.id)))
        db.commit()
        await ctx.send(f"🎉 GG {ctx.author.mention} ! Tu gagnes **{gain:.2f}€** avec un multiplicateur x{multiplicateur:.2f}. Nouveau solde : {new_total:.2f}€")
    else:
        perte = montant
        new_total = euros - perte
        cursor.execute("UPDATE users SET euros = ? WHERE user_id = ?", (new_total, str(ctx.author.id)))
        db.commit()
        await ctx.send(f"😵‍💫 Dommage {ctx.author.mention}, tu perds **{perte:.2f}€**. Nouveau solde : {new_total:.2f}€")




class BlackjackGame(View):
    def __init__(self, ctx, montant, joueur, dealer, user_euros):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.montant = montant
        self.joueur = joueur
        self.dealer = dealer
        self.user_euros = user_euros
        self.total_joueur = self.valeur_main(joueur)
        self.total_dealer = self.valeur_main(dealer)
        self.done = False

    def tirer_carte(self):
        cartes = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        return random.choice(cartes)

    def valeur_main(self, main):
        total = 0
        aces = 0
        for carte in main:
            if carte in ['J', 'Q', 'K']:
                total += 10
            elif carte == 'A':
                aces += 1
                total += 11
            else:
                total += int(carte)
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total

    def display_state(self):
        return (
            f"🃏 **BLACKJACK**\n"
            f"• Tes cartes : {' '.join(self.joueur)} (Total: {self.total_joueur})\n"
            f"• Carte visible du dealer : {self.dealer[0]}"
        )

    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author

    @discord.ui.button(label="🃙 Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if self.done:
            return

        self.joueur.append(self.tirer_carte())
        self.total_joueur = self.valeur_main(self.joueur)

        if self.total_joueur > 21:
            self.done = True
            new_total = self.user_euros - self.montant
            cursor.execute("UPDATE users SET euros = ? WHERE user_id = ?", (new_total, str(self.ctx.author.id)))
            db.commit()
            await interaction.response.edit_message(
                content=f"{self.display_state()}\n💥 Tu as dépassé 21... Tu perds **{self.montant:.2f}€**.",
                view=None
            )
        else:
            await interaction.response.edit_message(content=self.display_state(), view=self)

    @discord.ui.button(label="🛑 Stand", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if self.done:
            return

        # Le bot joue
        while self.total_dealer < 17:
            self.dealer.append(self.tirer_carte())
            self.total_dealer = self.valeur_main(self.dealer)

        self.done = True
        result_msg = f"• Tes cartes : {' '.join(self.joueur)} (Total: {self.total_joueur})\n"
        result_msg += f"• Cartes du dealer : {' '.join(self.dealer)} (Total: {self.total_dealer})\n"

        if self.total_dealer > 21 or self.total_joueur > self.total_dealer:
            gain = self.montant
            new_total = self.user_euros + gain
            cursor.execute("UPDATE users SET euros = ? WHERE user_id = ?", (new_total, str(self.ctx.author.id)))
            db.commit()
            result_msg += f"🎉 Tu gagnes **{gain:.2f}€** !"
        elif self.total_joueur == self.total_dealer:
            result_msg += f"🤝 Égalité ! Tu récupères ta mise."
        else:
            new_total = self.user_euros - self.montant
            cursor.execute("UPDATE users SET euros = ? WHERE user_id = ?", (new_total, str(self.ctx.author.id)))
            db.commit()
            result_msg += f"😞 Le dealer gagne. Tu perds **{self.montant:.2f}€**."

        await interaction.response.edit_message(content=result_msg, view=None)


@bot.command()
async def blackjack(ctx, montant: float):
    if montant <= 0:
        return await ctx.send("❌ Le montant doit être supérieur à 0.")

    user = get_user(str(ctx.author.id))
    euros = float(user[1])
    if euros < montant:
        return await ctx.send("❌ Tu n'as pas assez d'argent pour jouer cette somme.")

    def tirer_carte():
        cartes = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        return random.choice(cartes)

    joueur = [tirer_carte(), tirer_carte()]
    dealer = [tirer_carte(), tirer_carte()]

    game = BlackjackGame(ctx, montant, joueur, dealer, euros)
    await ctx.send(game.display_state(), view=game)




# Initialisation
crypto_prices = {
    "BTC": 30000.0,
    "ETH": 2000.0,
    "DOGE": 0.1
}

price_history = {coin: [] for coin in crypto_prices}

# Tâche qui met à jour les prix toutes les heures
@tasks.loop(minutes=60)
async def update_crypto_prices():
    for coin in crypto_prices:
        variation = random.uniform(-0.08, 0.08)
        crypto_prices[coin] *= (1 + variation)
        crypto_prices[coin] = round(crypto_prices[coin], 2)

        # Stocker dans l'historique (max 24 entrées)
        price_history[coin].append(crypto_prices[coin])
        if len(price_history[coin]) > 24:
            price_history[coin].pop(0)

    print("💱 Crypto-prices updated.")

# Initialisation DB
db = sqlite3.connect("eurobot.db")
cursor = db.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS crypto_wallet (
    user_id TEXT,
    coin TEXT,
    amount REAL DEFAULT 0.0,
    PRIMARY KEY (user_id, coin)
)''')
db.commit()

# Commande principale
@commands.command()
async def crypto(ctx, action: str = None, coin: str = None, montant: float = None):
    user_id = str(ctx.author.id)
    coin = coin.upper() if coin else None

    if action == "prix":
        msg = "**📊 Prix actuels des cryptos :**\n"
        for c, p in crypto_prices.items():
            direction = "🔺" if len(price_history[c]) >= 2 and price_history[c][-1] > price_history[c][-2] else "🔻"
            msg += f"• {c} → {p:.2f}€/unité {direction}\n"
        await ctx.send(msg)

    elif action == "wallet":
        cursor.execute("SELECT coin, amount FROM crypto_wallet WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        if not rows:
            return await ctx.send("📭 Ton portefeuille crypto est vide.")
        msg = "**👛 Ton portefeuille crypto :**\n"
        for c, a in rows:
            prix = crypto_prices[c]
            valeur = a * prix
            msg += f"• {c} → {a:.6f} ({valeur:.2f}€)\n"
        await ctx.send(msg)

    elif action == "buy" and coin and montant:
        if coin not in crypto_prices:
            return await ctx.send("❌ Crypto inconnue.")
        cursor.execute("SELECT euros FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row or row[0] < montant or montant <= 0:
            return await ctx.send("❌ Solde insuffisant ou montant invalide.")
        prix_unitaire = crypto_prices[coin]
        quantite = montant / prix_unitaire
        cursor.execute("UPDATE users SET euros = euros - ? WHERE user_id = ?", (montant, user_id))
        cursor.execute("INSERT INTO crypto_wallet (user_id, coin, amount) VALUES (?, ?, ?) ON CONFLICT(user_id, coin) DO UPDATE SET amount = amount + ?",
                       (user_id, coin, quantite, quantite))
        db.commit()
        await ctx.send(f"✅ Tu as acheté {quantite:.6f} {coin} pour {montant:.2f}€.")

    elif action == "sell" and coin:
        if coin not in crypto_prices:
            return await ctx.send("❌ Crypto inconnue.")
        cursor.execute("SELECT amount FROM crypto_wallet WHERE user_id = ? AND coin = ?", (user_id, coin))
        row = cursor.fetchone()
        if not row or row[0] <= 0:
            return await ctx.send(f"❌ Tu ne possèdes pas de {coin}.")
        quantite = row[0]
        valeur = quantite * crypto_prices[coin]
        cursor.execute("UPDATE users SET euros = euros + ? WHERE user_id = ?", (valeur, user_id))
        cursor.execute("UPDATE crypto_wallet SET amount = 0 WHERE user_id = ? AND coin = ?", (user_id, coin))
        db.commit()
        await ctx.send(f"💸 Tu as vendu {quantite:.6f} {coin} pour {valeur:.2f}€.")

    else:
        await ctx.send("❓ Utilisation :\n"
                       "`!crypto prix` → voir les prix\n"
                       "`!crypto wallet` → ton portefeuille\n"
                       "`!crypto buy BTC 100` → acheter du BTC pour 100€\n"
                       "`!crypto sell BTC` → vendre ton BTC")

# Dans on_ready()
# update_crypto_prices.start()
# bot.add_command(crypto)


# ---------------- INFLATION ----------------
@tasks.loop(hours=24)
async def apply_inflation():
    cursor.execute("UPDATE users SET euros = euros * 0.98, bank = bank * 0.99")
    db.commit()
    print("📉 Inflation appliquée : -2% liquide, -1% banque")

# ---------------- RUN ----------------
bot.run("MTQwMDA4NzY4NjA3NjgyOTc5Nw.GyVdr8.lIyB-pFtqOkFCXFWklxd6AP2WoiDZeEWuMIufw")
