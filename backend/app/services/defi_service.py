from typing import List, Dict
from .chain_scanner import get_scanner

class DefiService:
    """Track DeFi positions across protocols"""
    
    # Known protocol addresses (just examples - real ones would be more comprehensive)
    PROTOCOLS = {
        'ethereum': {
            'uniswap_v2': {'address': '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f', 'type': 'lp'},
            'uniswap_v3': {'address': '0xC36442b4a4522E871399CD717aBDD847Ab11FE88', 'type': 'lp'},
            'aave_v3': {'address': '0x7d2508f1Fa33C0C5E1e4e8F1C8f1C8f1C8f1C8f1', 'type': 'lending'},
            'compound': {'address': '0x3d9819210A31b4961e30B1cF7D5F15dF0e8F1C8f', 'type': 'lending'},
        },
        'base': {
            # Base has many DEXes - Aerodrome, BaseSwap, etc.
            'aerodrome': {'address': '0xC5d肖9C5A6e8b1a3E7D3F5C8f1C8f1C8f1C8f1C8', 'type': 'lp'},
        }
    }
    
    def __init__(self):
        self.scanner = get_scanner()
    
    def get_lp_positions(self, address: str, chain: str) -> List[Dict]:
        """Detect LP positions by checking token balances and liquidity events"""
        positions = []
        
        # For now, just scan for common LP tokens
        lp_tokens = {
            'ethereum': [
                '0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc',  # USDC-WETH Uniswap V2
                '0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852',  # USDT-WETH Uniswap V2
                '0xBb2b8038a1640196FbE3e38816F3e67Cba72D940',  # WBTC-WETH Uniswap V2
            ],
            'base': [
                # Add Base LP tokens
            ]
        }
        
        tokens = lp_tokens.get(chain, [])
        balances = self.scanner.get_token_balances(address, chain, tokens)
        
        for bal in balances:
            if bal['balance'] > 0:
                positions.append({
                    'protocol': 'Uniswap V2',
                    'chain': chain,
                    'type': 'lp',
                    'token_address': bal['address'],
                    'symbol': bal['symbol'],
                    'balance': bal['balance'],
                    'value_usd': 0,  # needs price
                })
        
        return positions
    
    def get_staking_positions(self, address: str, chain: str) -> List[Dict]:
        """Track staking positions (liquid staking, lock staking)"""
        positions = []
        
        staking_tokens = {
            'ethereum': [
                ('0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84', 'stETH'),  # Lido
                ('0xae78736Cd615f374D3085123A210448E74Fc6393', 'rETH'),  # Rocket Pool
                ('0xac3E018457B222d931B1A11b7dFe3b30DEb2f3d7', 'ankrETH'),  # Ankr
            ],
            'base': [
                ('0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', 'USDC'),  # Base USDC (for DeFi)
            ]
        }
        
        tokens = staking_tokens.get(chain, [])
        token_addresses = [t[0] for t in tokens]
        balances = self.scanner.get_token_balances(address, chain, token_addresses)
        
        for bal in balances:
            staking_info = next((t for t in staking_tokens[chain] if t[0].lower() == bal['address'].lower()), None)
            if bal['balance'] > 0 and staking_info:
                positions.append({
                    'protocol': 'Lido' if 'stETH' in staking_info[1] else 'Staking',
                    'chain': chain,
                    'type': 'staking',
                    'token_address': bal['address'],
                    'symbol': staking_info[1],
                    'balance': bal['balance'],
                    'value_usd': 0,
                })
        
        return positions
    
    def get_farming_positions(self, address: str, chain: str) -> List[Dict]:
        """Track farming/harvest positions"""
        # Would need to check multiple farm contracts
        return []
    
    def get_all_positions(self, address: str, chain: str) -> List[Dict]:
        """Get all DeFi positions for an address on a chain"""
        positions = []
        positions.extend(self.get_staking_positions(address, chain))
        positions.extend(self.get_lp_positions(address, chain))
        positions.extend(self.get_farming_positions(address, chain))
        return positions