import requests
import time
from typing import Dict, List, Optional
from functools import lru_cache

class PriceService:
    """Fetch crypto prices from CoinGecko (free tier + pro)"""
    
    BASE_URL = 'https://pro-api.coingecko.com/api/v3'
    
    def __init__(self, api_key: str = ''):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        if api_key:
            self.session.headers['x-cg-pro-api-key'] = api_key
    
    def get_price(self, coin_ids: List[str], vs_currencies: str = 'usd') -> Dict:
        """Get prices for multiple coins"""
        if not coin_ids:
            return {}
        
        url = f'{self.BASE_URL}/simple/price'
        params = {
            'ids': ','.join(coin_ids),
            'vs_currencies': vs_currencies,
            'include_24hr_change': 'true',
            'include_market_cap': 'true'
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f'Price fetch error: {e}')
            return {}
    
    def get_token_price(self, contract_address: str, chain: str = 'ethereum') -> Optional[float]:
        """Get price for a specific token by contract address"""
        coin_id = self._contract_to_coingecko_id(contract_address, chain)
        if not coin_id:
            return None
        prices = self.get_price([coin_id])
        return prices.get(coin_id, {}).get('usd')
    
    def search_coins(self, query: str) -> List[Dict]:
        """Search for coins by name/symbol"""
        url = f'{self.BASE_URL}/search'
        try:
            resp = self.session.get(url, params={'query': query}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get('coins', [])[:10]
        except:
            return []
    
    def get_market_chart(self, coin_id: str, days: int = 30) -> Dict:
        """Get price chart data"""
        url = f'{self.BASE_URL}/coins/{coin_id}/market_chart'
        params = {'vs_currency': 'usd', 'days': days}
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except:
            return {}
    
    @staticmethod
    def _contract_to_coingecko_id(contract: str, chain: str) -> Optional[str]:
        """Map contract address to CoinGecko ID"""
        # Common mappings
        mappings = {
            ('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', 'ethereum'): 'weth',
            ('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'ethereum'): 'usd-coin',
            ('0xdAC17F958D2ee523a2206206994597C13D831ec7', 'ethereum'): 'tether',
            ('0x6B175474E89094C44Da98b954EedeAC495271d0F', 'ethereum'): 'dai',
            ('0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', 'ethereum'): 'wrapped-bitcoin',
            ('0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0', 'ethereum'): 'matic-network',
        }
        contract = contract.lower()
        return mappings.get((contract, chain))

# Price cache singleton
_price_service = None

def get_price_service(api_key: str = '') -> PriceService:
    global _price_service
    if _price_service is None:
        _price_service = PriceService(api_key)
    return _price_service

def batch_get_prices(symbols: List[str], price_service: PriceService) -> Dict[str, float]:
    """Convert symbols to CoinGecko IDs and fetch prices"""
    symbol_to_id = {
        'ETH': 'ethereum', 'WETH': 'weth', 'BTC': 'bitcoin', 'WBTC': 'wrapped-bitcoin',
        'USDC': 'usd-coin', 'USDT': 'tether', 'DAI': 'dai', 'MATIC': 'matic-network',
        'ARB': 'arbitrum', 'OP': 'optimism', 'BASE': 'base', 'SOL': 'solana',
        'BNB': 'binancecoin', 'AVAX': 'avalanche-2', 'LINK': 'chainlink',
        'UNI': 'uniswap', 'AAVE': 'aave', 'MKR': 'maker', 'CRV': 'curve-dao-token',
    }
    
    coin_ids = [symbol_to_id.get(s.upper()) for s in symbols if symbol_to_id.get(s.upper())]
    if not coin_ids:
        return {}
    
    prices = price_service.get_price(coin_ids)
    result = {}
    for symbol in symbols:
        coin_id = symbol_to_id.get(symbol.upper())
        if coin_id and coin_id in prices:
            result[symbol.upper()] = prices[coin_id].get('usd', 0)
    return result