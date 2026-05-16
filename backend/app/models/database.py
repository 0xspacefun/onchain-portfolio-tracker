from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

Base = declarative_base()

class Wallet(Base):
    __tablename__ = 'wallets'
    
    id = Column(Integer, primary_key=True)
    address = Column(String(255), unique=True, nullable=False, index=True)
    label = Column(String(255), default='')
    chain = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    public_id = Column(String(64), index=True)  # for shared links
    
    balances = relationship('TokenBalance', back_populates='wallet', cascade='all, delete-orphan')
    defi_positions = relationship('DefiPosition', back_populates='wallet', cascade='all, delete-orphan')
    nft_holdings = relationship('NFTHolding', back_populates='wallet', cascade='all, delete-orphan')
    transactions = relationship('Transaction', back_populates='wallet', cascade='all, delete-orphan')
    snapshots = relationship('PortfolioSnapshot', back_populates='wallet', cascade='all, delete-orphan')

class TokenBalance(Base):
    __tablename__ = 'token_balances'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    token_address = Column(String(255), nullable=False)
    symbol = Column(String(20), nullable=False)
    name = Column(String(100), default='')
    decimals = Column(Integer, default=18)
    balance = Column(Float, default=0)
    balance_raw = Column(String(50), default='0')
    price_usd = Column(Float, default=0)
    value_usd = Column(Float, default=0)
    chain = Column(String(50), nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    wallet = relationship('Wallet', back_populates='balances')

class DefiPosition(Base):
    __tablename__ = 'defi_positions'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    protocol = Column(String(100), nullable=False)
    protocol_logo = Column(String(255), default='')
    chain = Column(String(50), nullable=False)
    position_type = Column(String(50), nullable=False)  # staking, lp, farming, lending, etc
    token_address = Column(String(255), nullable=False)
    token_symbol = Column(String(20), nullable=False)
    token_name = Column(String(100), default='')
    balance = Column(Float, default=0)
    balance_raw = Column(String(50), default='0')
    value_usd = Column(Float, default=0)
    reward_tokens = Column(JSON, default=[])  # [{'symbol': 'X', 'balance': Y, 'value_usd': Z}]
    reward_pending = Column(Float, default=0)
    apy = Column(Float, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    tx_hash = Column(String(255), default='')
    
    wallet = relationship('Wallet', back_populates='defi_positions')

class NFTHolding(Base):
    __tablename__ = 'nft_holdings'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    contract_address = Column(String(255), nullable=False)
    token_id = Column(String(100), nullable=False)
    name = Column(String(255), default='')
    description = Column(Text, default='')
    image_url = Column(String(500), default='')
    collection_name = Column(String(255), default='')
    floor_price = Column(Float, default=0)
    floor_price_token = Column(String(20), default='ETH')
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    wallet = relationship('Wallet', back_populates='nft_holdings')

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    tx_hash = Column(String(255), unique=True, nullable=False, index=True)
    block_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    from_address = Column(String(255), nullable=False)
    to_address = Column(String(255), nullable=False)
    value = Column(Float, default=0)
    gas_used = Column(Integer, default=0)
    gas_price_gwei = Column(Float, default=0)
    gas_cost_usd = Column(Float, default=0)
    status = Column(String(20), default='success')  # success, failed, pending
    chain = Column(String(50), nullable=False)
    token_symbol = Column(String(20), default='')
    token_amount = Column(Float, default=0)
    category = Column(String(50), default='')  # swap, transfer, mint, bridge, etc
    method_name = Column(String(100), default='')
    decoded_args = Column(JSON, default={})
    
    wallet = relationship('Wallet', back_populates='transactions')

class PortfolioSnapshot(Base):
    __tablename__ = 'portfolio_snapshots'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    total_value_usd = Column(Float, default=0)
    tokens_value_usd = Column(Float, default=0)
    defi_value_usd = Column(Float, default=0)
    nft_value_usd = Column(Float, default=0)
    snapshot_date = Column(DateTime, default=datetime.utcnow, index=True)
    
    wallet = relationship('Wallet', back_populates='snapshots')

class PriceCache(Base):
    __tablename__ = 'price_cache'
    
    id = Column(Integer, primary_key=True)
    coin_id = Column(String(100), nullable=False, index=True)  # coingecko coin id
    symbol = Column(String(20), nullable=False)
    price_usd = Column(Float, default=0)
    market_cap = Column(Float, default=0)
    volume_24h = Column(Float, default=0)
    price_change_24h = Column(Float, default=0)
    price_change_percentage_24h = Column(Float, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

def get_engine(db_url):
    return create_engine(db_url, connect_args={'check_same_thread': False} if 'sqlite' in db_url else {})

def init_db(db_url):
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()