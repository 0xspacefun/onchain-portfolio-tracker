from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters
from telegram.constants import ParseMode

TELEGRAM_COMMANDS = """
📊 *Portfolio Tracker Bot*

Commands:
• /start - Show welcome message
• /help - Show all commands
• /balance `0x...` - Check wallet balance
• /add `0x...` `chain` `label` - Add wallet to track
• /list - List all tracked wallets
• /portfolio - View full portfolio summary
• /recent - Show recent transactions
• /price `BTC` - Check token price
• /share - Get your public portfolio link
• /alert `token` `price` - Set price alert

Reply to any message to summarize it!
"""

def get_allowed_users(config):
    return [u.strip() for u in config.ALLOWED_TELEGRAM_USERS if u.strip()]

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to Portfolio Tracker!*\n\nTrack your multi-chain crypto portfolio in real-time.\n\n" + TELEGRAM_COMMANDS,
        parse_mode=ParseMode.MARKDOWN
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TELEGRAM_COMMANDS, parse_mode=ParseMode.MARKDOWN)

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.models.database import init_db, get_session, Wallet
    from app.config import config_by_name
    
    config = config_by_name.get('development', config_by_name['default'])
    engine = init_db(config.DATABASE_URL)
    session = get_session(engine)
    
    wallets = session.query(Wallet).filter_by(is_active=True).all()
    session.close()
    
    if not wallets:
        await update.message.reply_text("No wallets tracked yet. Use /add to add one!")
        return
    
    text = "📛 *Your Wallets:*\n\n"
    for i, w in enumerate(wallets, 1):
        label = w.label or 'Unnamed'
        text += f"{i}. {label}\n   `{w.address[:10]}...` ({w.chain})\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /balance `0x...`", parse_mode=ParseMode.MARKDOWN)
        return
    
    address = context.args[0]
    chain = context.args[1] if len(context.args) > 1 else 'ethereum'
    
    from app.services.chain_scanner import get_scanner
    from app.services.price_service import get_price_service, batch_get_prices
    from app.config import config_by_name
    
    config = config_by_name.get('development', config_by_name['default'])
    scanner = get_scanner()
    price_svc = get_price_service(config.COINGECKO_API_KEY)
    
    try:
        address = scanner.checksum_address(address)
    except:
        await update.message.reply_text("❌ Invalid address format")
        return
    
    # Get native balance
    native_bal = scanner.get_native_balance(address, chain)
    eth_price = price_svc.get_price(['ethereum']).get('ethereum', {}).get('usd', 0)
    eth_value = native_bal * eth_price
    
    # Get tokens
    common_tokens = {
        'ethereum': [
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            '0xdAC17F958D2ee523a2206206994597C13D831ec7',
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
        ],
        'base': ['0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'],
    }
    
    tokens = common_tokens.get(chain, [])
    token_balances = scanner.get_token_balances(address, chain, tokens)
    
    all_symbols = ['ETH'] + [tb['symbol'] for tb in token_balances]
    prices = batch_get_prices(all_symbols, price_svc)
    
    text = f"💰 *Balance for*\n`{address[:20]}...`\n\n"
    text += f"**ETH:** {native_bal:.6f} (${eth_value:.2f})\n"
    
    total = eth_value
    for tb in token_balances:
        price = prices.get(tb['symbol'], 0)
        value = tb['balance'] * price
        total += value
        text += f"**{tb['symbol']}:** {tb['balance']:.4f} (${value:.2f})\n"
    
    text += f"\n💎 *Total:* ${total:.2f}"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /add `0x...` `chain` `label`", parse_mode=ParseMode.MARKDOWN)
        return
    
    address = context.args[0]
    chain = context.args[1] if len(context.args) > 1 else 'ethereum'
    label = ' '.join(context.args[2:]) if len(context.args) > 2 else ''
    
    from app.models.database import Wallet, init_db, get_session
    from app.config import config_by_name
    from app.services.chain_scanner import get_scanner
    
    scanner = get_scanner()
    
    if not scanner.is_valid_address(address):
        await update.message.reply_text("❌ Invalid address format")
        return
    
    address = scanner.checksum_address(address)
    
    config = config_by_name.get('development', config_by_name['default'])
    engine = init_db(config.DATABASE_URL)
    session = get_session(engine)
    
    existing = session.query(Wallet).filter_by(address=address, chain=chain).first()
    if existing:
        session.close()
        await update.message.reply_text("⚠️ Wallet already tracked!")
        return
    
    import uuid
    wallet = Wallet(
        address=address,
        chain=chain,
        label=label,
        public_id=str(uuid.uuid4())[:8],
    )
    session.add(wallet)
    session.commit()
    session.close()
    
    await update.message.reply_text(f"✅ Wallet added!\n\n📛 Label: {label or 'Unnamed'}\n🔗 Chain: {chain}\n🆔 ID: {wallet.public_id}", parse_mode=ParseMode.MARKDOWN)

async def portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.models.database import init_db, get_session, Wallet
    from app.config import config_by_name
    from app.services.chain_scanner import get_scanner
    from app.services.price_service import get_price_service, batch_get_prices
    
    config = config_by_name.get('development', config_by_name['default'])
    engine = init_db(config.DATABASE_URL)
    session = get_session(engine)
    
    wallets = session.query(Wallet).filter_by(is_active=True).all()
    scanner = get_scanner()
    price_svc = get_price_service(config.COINGECKO_API_KEY)
    
    total = 0
    lines = []
    
    for w in wallets:
        native = scanner.get_native_balance(w.address, w.chain)
        prices = batch_get_prices(['ETH'], price_svc)
        eth_price = prices.get('ETH', 0)
        
        val = native * eth_price
        total += val
        
        label = w.label or 'Wallet'
        lines.append(f"• {label}: ${val:.2f}")
    
    session.close()
    
    text = f"📊 *Portfolio Summary*\n\n"
    text += "\n".join(lines)
    text += f"\n\n💎 *Total:* ${total:.2f}"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /price `BTC`", parse_mode=ParseMode.MARKDOWN)
        return
    
    symbol = context.args[0].upper()
    from app.services.price_service import get_price_service, batch_get_prices
    from app.config import config_by_name
    
    config = config_by_name.get('development', config_by_name['default'])
    price_svc = get_price_service(config.COINGECKO_API_KEY)
    
    prices = batch_get_prices([symbol], price_svc)
    price = prices.get(symbol)
    
    if price:
        await update.message.reply_text(f"**{symbol}:** ${price:.2f}", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ Price not found for {symbol}")

def setup_telegram_bot(config):
    """Initialize and configure Telegram bot"""
    if not config.TELEGRAM_BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN not set - Telegram bot disabled")
        return None
    
    allowed_users = get_allowed_users(config)
    
    async def auth_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if allowed_users and str(update.message.from_user.id) not in allowed_users:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return True
        return False
    
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("add", add_cmd))
    application.add_handler(CommandHandler("portfolio", portfolio_cmd))
    application.add_handler(CommandHandler("price", price_cmd))
    
    return application

if __name__ == '__main__':
    from app.config import config_by_name
    config = config_by_name.get('development', config_by_name['default'])
    app = setup_telegram_bot(config)
    if app:
        print("🤖 Telegram bot starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        print("❌ Telegram bot not configured")