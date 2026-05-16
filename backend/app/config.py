import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{BASE_DIR}/portfolio.db')
    
    # Redis (for Celery)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # API Keys
    COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY', '')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    ALLOWED_TELEGRAM_USERS = os.getenv('ALLOWED_TELEGRAM_USERS', '').split(',')
    
    # Chain RPCs
    ETH_RPC = os.getenv('ETH_RPC', 'https://eth.llamarpc.com')
    BASE_RPC = os.getenv('BASE_RPC', 'https://mainnet.base.org')
    ARB_RPC = os.getenv('ARB_RPC', 'https://arb1.arbitrum.io/rpc')
    OP_RPC = os.getenv('OP_RPC', 'https://mainnet.optimism.io')
    BSC_RPC = os.getenv('BSC_RPC', 'https://bsc-dataseed.binance.org')
    POLYGON_RPC = os.getenv('POLYGON_RPC', 'https://polygon-rpc.com')
    SOLANA_RPC = os.getenv('SOLANA_RPC', 'https://api.mainnet-beta.solana.com')
    
    # Refresh intervals (seconds)
    PRICE_REFRESH_INTERVAL = 60  # 1 minute
    PORTFOLIO_REFRESH_INTERVAL = 900  # 15 minutes
    NFT_REFRESH_INTERVAL = 300  # 5 minutes

    # Public portfolio
    PUBLIC_PORTFOLIO_SECRET = os.getenv('PUBLIC_PORTFOLIO_SECRET', '')
    
class Development(Config):
    DEBUG = True

class Production(Config):
    DEBUG = False

config_by_name = {
    'development': Development,
    'production': Production,
    'default': Development
}