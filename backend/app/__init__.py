from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import logging
import os

from app.models.database import init_db, get_session, Wallet, TokenBalance, PortfolioSnapshot
from app.services.price_service import get_price_service, batch_get_prices
from app.services.chain_scanner import get_scanner
from app.config import config_by_name

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(config_name='default'):
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static')
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    config = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(config)
    
    CORS(app)
    
    # Initialize database
    engine = init_db(config.DATABASE_URL)
    
    # Register blueprints
    from app.routes.wallet_routes import wallet_bp
    app.register_blueprint(wallet_bp)
    
    # Dashboard route
    @app.route('/')
    def index():
        return render_template('dashboard.html')
    
    @app.route('/api/portfolio/summary')
    def portfolio_summary():
        """Get aggregated portfolio across all wallets"""
        session = get_session(engine)
        wallets = session.query(Wallet).filter_by(is_active=True).all()
        
        scanner = get_scanner()
        price_svc = get_price_service(config.COINGECKO_API_KEY)
        
        total_value = 0
        chain_breakdown = {}
        wallet_summaries = []
        
        for wallet in wallets:
            address = wallet.address
            chain = wallet.chain
            
            # Get native balance
            native_balance = scanner.get_native_balance(address, chain)
            
            # Get common tokens
            common_tokens = {
                'ethereum': [
                    '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',  # USDC
                    '0xdAC17F958D2ee523a2206206994597C13D831ec7',  # USDT
                    '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                    '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',  # WBTC
                ],
                'base': ['0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'],
                'arbitrum': ['0xaf88d065e77c8cC2239327C5EDb3A432268e5831'],
                'optimism': ['0x0b2C639c533813f4Aa9D7837CAf62653d103Ff92'],
            }
            
            tokens = common_tokens.get(chain, [])
            token_balances = scanner.get_token_balances(address, chain, tokens)
            
            # Calculate values
            all_symbols = ['ETH'] + [tb['symbol'] for tb in token_balances]
            prices = batch_get_prices(all_symbols, price_svc)
            
            wallet_value = 0
            items = []
            
            eth_price = prices.get('ETH', 0)
            eth_value = native_balance * eth_price
            wallet_value += eth_value
            items.append({'symbol': 'ETH', 'balance': native_balance, 'value_usd': eth_value})
            
            for tb in token_balances:
                price = prices.get(tb['symbol'], 0)
                value = tb['balance'] * price
                wallet_value += value
                items.append({'symbol': tb['symbol'], 'balance': tb['balance'], 'value_usd': value})
            
            total_value += wallet_value
            
            if chain not in chain_breakdown:
                chain_breakdown[chain] = {'value_usd': 0, 'count': 0}
            chain_breakdown[chain]['value_usd'] += wallet_value
            chain_breakdown[chain]['count'] += 1
            
            wallet_summaries.append({
                'address': address,
                'label': wallet.label or '',
                'chain': chain,
                'total_value_usd': wallet_value,
                'items': items,
                'public_id': wallet.public_id,
            })
        
        session.close()
        
        return jsonify({
            'success': True,
            'total_value_usd': total_value,
            'chain_breakdown': chain_breakdown,
            'wallet_count': len(wallets),
            'wallets': wallet_summaries,
        })
    
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'version': '1.0.0'})
    
    # Background scheduler for price updates
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=lambda: logger.info('Price refresh tick'), trigger='interval', seconds=config.PRICE_REFRESH_INTERVAL)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    
    return app

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)