from web3 import Web3
import requests
from typing import List, Dict, Optional
from eth_abi import decode
from eth_abi.exceptions import InsufficientDataBytes

class ChainScanner:
    """Multi-chain wallet scanner using public RPCs"""
    
    CHAINS = {
        'ethereum': {
            'rpc': 'https://eth.llamarpc.com',
            'chain_id': 1,
            'explorer': 'https://etherscan.io',
            'native_symbol': 'ETH',
            'gas_token': 'ETH'
        },
        'base': {
            'rpc': 'https://mainnet.base.org',
            'chain_id': 8453,
            'explorer': 'https://basescan.org',
            'native_symbol': 'ETH',
            'gas_token': 'ETH'
        },
        'arbitrum': {
            'rpc': 'https://arb1.arbitrum.io/rpc',
            'chain_id': 42161,
            'explorer': 'https://arbiscan.io',
            'native_symbol': 'ETH',
            'gas_token': 'ETH'
        },
        'optimism': {
            'rpc': 'https://mainnet.optimism.io',
            'chain_id': 10,
            'explorer': 'https://optimistic.etherscan.io',
            'native_symbol': 'ETH',
            'gas_token': 'ETH'
        },
        'bsc': {
            'rpc': 'https://bsc-dataseed.binance.org',
            'chain_id': 56,
            'explorer': 'https://bscscan.com',
            'native_symbol': 'BNB',
            'gas_token': 'BNB'
        },
        'polygon': {
            'rpc': 'https://polygon-rpc.com',
            'chain_id': 137,
            'explorer': 'https://polygonscan.com',
            'native_symbol': 'MATIC',
            'gas_token': 'MATIC'
        },
    }
    
    ERC20_ABI = [
        {'inputs': [], 'name': 'decimals', 'outputs': [{'type': 'uint8'}], 'stateMutability': 'view', 'type': 'function'},
        {'inputs': [], 'name': 'symbol', 'outputs': [{'type': 'string'}], 'stateMutability': 'view', 'type': 'function'},
        {'inputs': [{'name': 'account', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'},
    ]
    
    def __init__(self):
        self.w3 = {chain: Web3(Web3.HTTPProvider(cfg['rpc'])) for chain, cfg in self.CHAINS.items()}
    
    def is_valid_address(self, address: str) -> bool:
        return Web3.is_address(address)
    
    def checksum_address(self, address: str) -> str:
        return Web3.to_checksum_address(address)
    
    def get_native_balance(self, address: str, chain: str) -> float:
        """Get native token balance (ETH, BNB, MATIC, etc.)"""
        if chain not in self.w3:
            return 0
        web3 = self.w3[chain]
        try:
            balance = web3.eth.get_balance(address)
            return float(web3.from_wei(balance, 'ether'))
        except:
            return 0
    
    def get_token_balances(self, address: str, chain: str, token_addresses: List[str]) -> List[Dict]:
        """Get ERC20 token balances"""
        if chain not in self.w3:
            return []
        web3 = self.w3[chain]
        results = []
        
        for token_addr in token_addresses:
            try:
                token_addr = self.checksum_address(token_addr)
                contract = web3.eth.contract(address=token_addr, abi=self.ERC20_ABI)
                
                balance = contract.functions.balanceOf(address).call()
                decimals = contract.functions.decimals().call()
                symbol = contract.functions.symbol().call()
                
                balance_float = float(balance) / (10 ** decimals)
                results.append({
                    'address': token_addr,
                    'symbol': symbol,
                    'balance': balance_float,
                    'raw_balance': str(balance),
                    'decimals': decimals
                })
            except Exception as e:
                print(f'Error fetching token {token_addr} on {chain}: {e}')
                continue
        return results
    
    def get_transaction_history(self, address: str, chain: str, limit: int = 50) -> List[Dict]:
        """Get recent transactions from explorer API"""
        chain_cfg = self.CHAINS.get(chain, {})
        explorer = chain_cfg.get('explorer', '')
        
        if not explorer:
            return []
        
        try:
            api_key = ''  # could use Etherscan free tier
            url = f'{explorer}/api?module=account&action=txlist&address={address}&sort=desc&apikey={api_key}'
            resp = requests.get(url, timeout=15)
            data = resp.json()
            
            if data.get('status') == '1':
                txs = data.get('result', [])[:limit]
                return [self._parse_etherscan_tx(tx, chain) for tx in txs]
        except Exception as e:
            print(f'Tx history error for {chain}: {e}')
        
        return []
    
    def _parse_etherscan_tx(self, tx: Dict, chain: str) -> Dict:
        """Parse Etherscan-style API response"""
        return {
            'hash': tx.get('hash', ''),
            'block_number': int(tx.get('blockNumber', 0)),
            'timestamp': int(tx.get('timeStamp', 0)),
            'from': tx.get('from', ''),
            'to': tx.get('to', ''),
            'value': float(tx.get('value', 0)) / 1e18,
            'gas_used': int(tx.get('gasUsed', 0)),
            'gas_price_gwei': float(tx.get('gasPrice', 0)) / 1e9,
            'status': 'success' if tx.get('isError') == '0' else 'failed',
            'input': tx.get('input', ''),
            'method_id': tx.get('methodId', ''),
        }

    def get_token_transfer_history(self, address: str, chain: str, token_addr: str = '') -> List[Dict]:
        """Get ERC20 token transfers"""
        chain_cfg = self.CHAINS.get(chain, {})
        explorer = chain_cfg.get('explorer', '')
        
        if not explorer:
            return []
        
        try:
            url = f'{explorer}/api?module=account&action=tokentx&address={address}&sort=desc'
            if token_addr:
                url += f'&contractaddress={token_addr}'
            resp = requests.get(url, timeout=15)
            data = resp.json()
            
            if data.get('status') == '1':
                return data.get('result', [])[:50]
        except:
            pass
        return []
    
    @staticmethod
    def decode_method_id(method_id: str) -> Optional[str]:
        """Decode 4-byte method ID to function name"""
        # Common method IDs
        methods = {
            '0xa9059cbb': 'transfer',
            '0x095ea7b3': 'approve',
            '0x23b872dd': 'transferFrom',
            '0xb6f9de95': 'swap',
            '0x38ed1739': 'swap',
            '0x7ff36ab5': 'swap',
            '0x5ae95576': 'deposit',
            '0xe8e33700': 'addLiquidity',
            '0xf305d719': 'addLiquidityETH',
        }
        return methods.get(method_id.lower())

# Singleton
_scanner = None

def get_scanner() -> ChainScanner:
    global _scanner
    if _scanner is None:
        _scanner = ChainScanner()
    return _scanner