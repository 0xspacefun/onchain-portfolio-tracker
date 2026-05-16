import requests
from typing import List, Dict, Optional
from web3 import Web3

class NFTService:
    """NFT gallery and floor price tracking"""
    
    CHAIN_CONFIG = {
        'ethereum': {
            'rpc': 'https://eth.llamarpc.com',
            'alchemy': 'https://eth-mainnet.g.alchemy.com/v2/demo',  # Replace with real key
            'opensea': 'https://api.opensea.io',
        },
        'base': {
            'rpc': 'https://mainnet.base.org',
            'opensea': 'https://api.opensea.io',
        }
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'PortfolioTracker/1.0'})
    
    def get_nfts_for_address(self, address: str, chain: str = 'ethereum') -> List[Dict]:
        """Get all NFTs held by an address"""
        # Try OpenSea API first (free tier)
        try:
            url = f"https://api.opensea.io/api/v2/accounts/{address}/nfts"
            params = {
                'chain': chain if chain != 'ethereum' else 'ethereum',
                'limit': 50
            }
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return [self._parse_opensea_nft(nft) for nft in data.get('nfts', [])]
        except Exception as e:
            print(f'OpenSea API error: {e}')
        
        # Fallback: Manual NFT detection by contract addresses
        return self._scan_known_collections(address, chain)
    
    def _scan_known_collections(self, address: str, chain: str) -> List[Dict]:
        """Scan for NFTs in known collections"""
        known_collections = {
            'ethereum': [
                '0x49cF6f5d44E70224e2E23fDcdd2C053F30aDA28B',  # Clone X
                '0x23581767a7ae301c8e691190312c8B2222e8f841',  # BAYC
                '0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D',  # PFP
                '0x8a90CAb2b38dba80c64b7734f58eB83d2F1E2D3C4',  # Example
                '0x57f1887a8bf2b0077c7c0a5b5c0c5c5c5c5c5c5c',  # ENS
            ],
            'base': [
                '0xac7949Bd225f3d8d11F6F8f6b5c5c5c5c5c5c5c5',  # Example
            ]
        }
        
        nfts = []
        contracts = known_collections.get(chain, [])
        
        for contract_addr in contracts:
            nft_data = self._fetch_nft_contract(address, contract_addr, chain)
            if nft_data:
                nfts.append(nft_data)
        
        return nfts
    
    def _fetch_nft_contract(self, address: str, contract_addr: str, chain: str) -> Optional[Dict]:
        """Fetch NFTs from a specific contract"""
        try:
            rpc = self.CHAIN_CONFIG.get(chain, {}).get('rpc')
            if not rpc:
                return None
            
            web3 = Web3(Web3.HTTPProvider(rpc))
            contract_addr = web3.to_checksum_address(contract_addr)
            
            # ERC721 balance check
            erc721_abi = [{
                "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }]
            
            contract = web3.eth.contract(address=contract_addr, abi=erc721_abi)
            balance = contract.functions.balanceOf(address).call()
            
            if balance > 0:
                return {
                    'contract_address': contract_addr,
                    'name': 'NFT Collection',
                    'balance': balance,
                    'collection_name': 'Unknown',
                    'image_url': '',
                    'floor_price': 0,
                }
        except:
            pass
        return None
    
    def _parse_opensea_nft(self, nft: Dict) -> Dict:
        """Parse OpenSea API response"""
        return {
            'contract_address': nft.get('contract', ''),
            'token_id': str(nft.get('identifier', '')),
            'name': nft.get('name', ''),
            'description': nft.get('description', ''),
            'image_url': nft.get('image_url', nft.get('image', {}).get('url', '')),
            'collection_name': nft.get('collection', ''),
            'floor_price': float(nft.get('floor_price', 0) or 0),
            'floor_price_currency': nft.get('floor_price_currency', 'ETH'),
        }
    
    def get_floor_price(self, contract_address: str, chain: str = 'ethereum') -> Optional[float]:
        """Get floor price for an NFT collection"""
        try:
            url = f"https://api.opensea.io/api/v2/collections/{contract_address}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get('floor_price', 0) or 0)
        except:
            pass
        return None
    
    def get_collection_stats(self, contract_address: str) -> Dict:
        """Get collection stats (floor, volume, etc)"""
        try:
            url = f"https://api.opensea.io/api/v2/collections/{contract_address}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'name': data.get('name', ''),
                    'floor_price': float(data.get('floor_price', 0) or 0),
                    'floor_price_currency': data.get('floor_price_currency', 'ETH'),
                    'total_supply': data.get('total_supply', 0),
                    'owned_by': data.get('owned_by', 0),
                    'volume_24h': float(data.get('volume', {}).get('24h', 0) or 0),
                }
        except:
            pass
        return {}

# Singleton
_nft_service = None

def get_nft_service() -> NFTService:
    global _nft_service
    if _nft_service is None:
        _nft_service = NFTService()
    return _nft_service