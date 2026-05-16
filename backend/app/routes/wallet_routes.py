from flask import Blueprint, request, jsonify
from app.services.chain_scanner import get_scanner
from app.services.price_service import get_price_service, batch_get_prices
from app.services.defi_service import DefiService
from app.services.nft_service import get_nft_service
from app.models.database import Wallet, TokenBalance, DefiPosition, NFTHolding, Transaction
from app.models.database import init_db, get_session
from app.config import config_by_name

wallet_bp = Blueprint('wallet', __name__)
scanner = get_scanner()
defi_service = DefiService()
nft_service = get_nft_service()

def get_config():
    return config_by_name.get('development', config_by_name['default'])

@wallet_bp.route('/api/wallets', methods=['GET'])
def get_wallets():
    """List all tracked wallets"""
    config = get_config()
    engine = init_db(config.DATABASE_URL)
    session = get_session(engine)
    
    wallets = session.query(Wallet).filter_by(is_active=True).all()
    result = [{
        'id': w.id,
        'address': w.address,
        'label': w.label,
        'chain': w.chain,
        'public_id': w.public_id,
        'created_at': w.created_at.isoformat() if w.created_at else None,
    } for w in wallets]
    
    session.close()
    return jsonify({'success': True, 'wallets': result})

@wallet_bp.route('/api/wallet', methods=['POST'])
def add_wallet():
    """Add a new wallet to track"""
    data = request.get_json()
    address = data.get('address', '').strip()
    chain = data.get('chain', 'ethereum').lower()
    label = data.get('label', '')
    
    if not address:
        return jsonify({'success': False, 'error': 'Address required'}), 400
    
    if not scanner.is_valid_address(address):
        return jsonify({'success': False, 'error': 'Invalid address format'}), 400
    
    address = scanner.checksum_address(address)
    
    config = get_config()
    engine = init_db(config.DATABASE_URL)
    session = get_session(engine)
    
    existing = session.query(Wallet).filter_by(address=address, chain=chain).first()
    if existing:
        session.close()
        return jsonify({'success': False, 'error': 'Wallet already tracked'}), 409
    
    import uuid
    wallet = Wallet(
        address=address,
        chain=chain,
        label=label,
        public_id=str(uuid.uuid4())[:8],
    )
    session.add(wallet)
    session.commit()
    
    result = {
        'id': wallet.id,
        'address': wallet.address,
        'chain': wallet.chain,
        'label': wallet.label,
        'public_id': wallet.public_id,
    }
    session.close()
    
    return jsonify({'success': True, 'wallet': result}), 201

@wallet_bp.route('/api/wallet/<int:wallet_id>', methods=['DELETE'])
def remove_wallet(wallet_id):
    """Remove a wallet from tracking"""
    config = get_config()
    engine = init_db(config.DATABASE_URL)
    session = get_session(engine)
    
    wallet = session.query(Wallet).filter_by(id=wallet_id).first()
    if not wallet:
        session.close()
        return jsonify({'success': False, 'error': 'Wallet not found'}), 404
    
    session.delete(wallet)
    session.commit()
    session.close()
    
    return jsonify({'success': True, 'message': 'Wallet removed'})

@wallet_bp.route('/api/wallet/<address>/balance', methods=['GET'])
def get_wallet_balance(address):
    """Get complete balance for a wallet"""
    chain = request.args.get('chain', 'ethereum').lower()
    config = get_config()
    price_svc = get_price_service(config.COINGECKO_API_KEY)
    
    address = scanner.checksum_address(address)
    
    # Get native balance
    native_balance = scanner.get_native_balance(address, chain)
    
    # Get common token balances
    common_tokens = {
        'ethereum': [
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',  # USDC
            '0xdAC17F958D2ee523a2206206994597C13D831ec7',  # USDT
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
            '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',  # WBTC
        ],
        'base': [
            '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        ],
        'arbitrum': [
            '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
        ],
    }
    
    tokens = common_tokens.get(chain, [])
    token_balances = scanner.get_token_balances(address, chain, tokens)
    
    all_symbols = ['ETH'] + [tb['symbol'] for tb in token_balances]
    prices = batch_get_prices(all_symbols, price_svc)
    
    result = {
        'address': address,
        'chain': chain,
        'native': {
            'symbol': 'ETH' if chain != 'bsc' else 'BNB',
            'balance': native_balance,
            'price_usd': prices.get('ETH', 0),
            'value_usd': native_balance * prices.get('ETH', 0),
        },
        'tokens': []
    }
    
    for tb in token_balances:
        price = prices.get(tb['symbol'], 0)
        result['tokens'].append({
            'symbol': tb['symbol'],
            'balance': tb['balance'],
            'price_usd': price,
            'value_usd': tb['balance'] * price,
        })
    
    total_value = result['native']['value_usd'] + sum(t['value_usd'] for t in result['tokens'])
    
    return jsonify({
        'success': True,
        'balance': result,
        'total_value_usd': total_value,
    })

@wallet_bp.route('/api/wallet/<address>/defi', methods=['GET'])
def get_wallet_defi(address):
    """Get DeFi positions for a wallet"""
    chain = request.args.get('chain', 'ethereum').lower()
    
    address = scanner.checksum_address(address)
    positions = defi_service.get_all_positions(address, chain)
    
    return jsonify({'success': True, 'positions': positions})

@wallet_bp.route('/api/wallet/<address>/nft', methods=['GET'])
def get_wallet_nft(address):
    """Get NFT holdings for a wallet"""
    chain = request.args.get('chain', 'ethereum').lower()
    
    nfts = nft_service.get_nfts_for_address(address, chain)
    
    return jsonify({'success': True, 'nfts': nfts})

@wallet_bp.route('/api/wallet/<address>/txhistory', methods=['GET'])
def get_wallet_txhistory(address):
    """Get transaction history for a wallet"""
    chain = request.args.get('chain', 'ethereum').lower()
    limit = int(request.args.get('limit', 50))
    
    address = scanner.checksum_address(address)
    txs = scanner.get_transaction_history(address, chain, limit)
    
    return jsonify({'success': True, 'transactions': txs})

@wallet_bp.route('/api/portfolio/<public_id>', methods=['GET'])
def get_public_portfolio(public_id):
    """Get public portfolio view by ID"""
    config = get_config()
    engine = init_db(config.DATABASE_URL)
    session = get_session(engine)
    
    wallet = session.query(Wallet).filter_by(public_id=public_id, is_active=True).first()
    if not wallet:
        session.close()
        return jsonify({'success': False, 'error': 'Portfolio not found'}), 404
    
    address = wallet.address
    chain = wallet.chain
    
    native_balance = scanner.get_native_balance(address, chain)
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
    
    price_svc = get_price_service(config.COINGECKO_API_KEY)
    all_symbols = ['ETH'] + [tb['symbol'] for tb in token_balances]
    prices = batch_get_prices(all_symbols, price_svc)
    
    items = []
    eth_price = prices.get('ETH', 0)
    items.append({
        'symbol': 'ETH',
        'balance': native_balance,
        'value_usd': native_balance * eth_price,
    })
    
    for tb in token_balances:
        price = prices.get(tb['symbol'], 0)
        items.append({
            'symbol': tb['symbol'],
            'balance': tb['balance'],
            'value_usd': tb['balance'] * price,
        })
    
    total_value = sum(i['value_usd'] for i in items)
    
    session.close()
    
    return jsonify({
        'success': True,
        'portfolio': {
            'label': wallet.label,
            'address': wallet.address,
            'chain': wallet.chain,
            'total_value_usd': total_value,
            'items': items,
        }
    })