import json
import random
import asyncio
from web3 import AsyncWeb3
from web3.providers.async_rpc import AsyncHTTPProvider

with open('abi/router_abi.json') as f:
    router_abi = json.load(f)
with open('abi/btc_b_abi.json') as f:
    btc_b_abi = json.load(f)

START = 90
END = 360


class Chain():
    def __init__(self, rpc_url, bridge_address, btc_b_address, chain_id, chain_name, blockExplorerUrl):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self.bridge_address = self.w3.to_checksum_address(bridge_address)
        self.bridge_contract = self.w3.eth.contract(address=self.bridge_address, abi=router_abi)
        self.btc_b_address = self.w3.to_checksum_address(btc_b_address)
        self.btc_b_contract = self.w3.eth.contract(address=self.btc_b_address, abi=btc_b_abi)
        self.chain_id = chain_id
        self.chain_name = chain_name
        self.blockExplorerUrl = blockExplorerUrl


class ChainFactory:
    """Factory class to initialize different chains."""

    @staticmethod
    def create_chain(chain_type):
        chains = {
            "polygon": {
                'rpc_url': 'https://rpc.ankr.com/polygon/f28e0053c2134f128d94266f8e08e9894c43ebd78697eb21ba523282f358bb59',
                'bridge_address': '0x2297aEbD383787A160DD0d9F71508148769342E3',
                'btc_b_address': '0x2297aEbD383787A160DD0d9F71508148769342E3',
                'chain_id': 109,
                'chain_name': 'Polygon',
                'blockExplorerUrl': 'https://polygonscan.com'
            },
            "bsc": {
                'rpc_url': 'https://rpc.ankr.com/bsc/f28e0053c2134f128d94266f8e08e9894c43ebd78697eb21ba523282f358bb59',
                'bridge_address': '0x2297aEbD383787A160DD0d9F71508148769342E3',
                'btc_b_address': '0x2297aEbD383787A160DD0d9F71508148769342E3',
                'chain_id': 102,
                'chain_name': 'BSC',
                'blockExplorerUrl': 'https://bscscan.com'
            },
            "avalanche": {
                'rpc_url': 'https://rpc.ankr.com/avalanche/f28e0053c2134f128d94266f8e08e9894c43ebd78697eb21ba523282f358bb59',
                'bridge_address': '0x2297aebd383787a160dd0d9f71508148769342e3',
                'btc_b_address': '0x152b9d0FdC40C096757F570A51E494bd4b943E50',
                'chain_id': 106,
                'chain_name': 'Avalanche',
                'blockExplorerUrl': 'https://snowtrace.io'
            },
            "arbitrum": {
                'rpc_url': 'https://rpc.ankr.com/arbitrum/f28e0053c2134f128d94266f8e08e9894c43ebd78697eb21ba523282f358bb59',
                'bridge_address': '0x2297aEbD383787A160DD0d9F71508148769342E3',
                'btc_b_address': '0x2297aEbD383787A160DD0d9F71508148769342E3',
                'chain_id': 110,
                'chain_name': 'Arbitrum',
                'blockExplorerUrl': 'https://arbiscan.io'
            },
            "optimism": {
                'rpc_url': 'https://rpc.ankr.com/optimism/f28e0053c2134f128d94266f8e08e9894c43ebd78697eb21ba523282f358bb59',
                'bridge_address': '0x2297aEbD383787A160DD0d9F71508148769342E3',
                'btc_b_address': '0x2297aEbD383787A160DD0d9F71508148769342E3',
                'chain_id': 111,
                'chain_name': 'Optimism',
                'blockExplorerUrl': 'https://optimistic.etherscan.io/'
            }
        }

        if chain_type.lower() not in chains:
            raise ValueError(f"Chain type {chain_type} is not supported.")

        return Chain(**chains[chain_type.lower()])


class SwapTransaction:
    """Handles the swap transaction logic."""

    @staticmethod
    async def execute(chain_from, chain_to, wallet):
        try:
            account = chain_from.w3.eth.account.from_key(wallet)
            address = account.address
            address_edited = address.rpartition('x')[2]

            nonce, gas_price, btc_b_balance = await asyncio.gather(
                chain_from.w3.eth.get_transaction_count(address),
                chain_from.w3.eth.gas_price,
                check_balance(address, chain_from.btc_b_contract)
            )

            adapterParams = '0x0002000000000000000000000000000000000000000000000000000000000003d0900000000000000000000000000000000000000000000000000000000000000000' + address_edited
            fees = await chain_from.bridge_contract.functions.estimateSendFee(
                chain_to.chain_id,
                '0x000000000000000000000000' + address_edited,
                btc_b_balance,
                True,
                adapterParams
            ).call()
            fee = fees[0]

            allowance = await chain_from.btc_b_contract.functions.allowance(address, chain_from.bridge_address).call()

            if allowance < btc_b_balance:
                max_amount = chain_from.w3.to_wei(2 ** 64 - 1, 'ether')
                approve_txn = await chain_from.btc_b_contract.functions.approve(
                    chain_from.bridge_address,
                    max_amount
                ).build_transaction({
                    'from': address,
                    'gas': 150000,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                })
                signed_approve_txn = chain_from.w3.eth.account.sign_transaction(approve_txn, wallet)
                approve_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
                print(
                    f"{chain_from.__class__.__name__} | BTC.b APPROVED {chain_from.blockExplorerUrl}/tx/{approve_txn_hash.hex()}")

                await asyncio.sleep(30)

            _from = address
            _chainId = chain_to.chain_id
            _toaddress = '0x000000000000000000000000' + address_edited
            _amount = int(btc_b_balance)
            _minamount = int(btc_b_balance)
            _callparams = [address, "0x0000000000000000000000000000000000000000", adapterParams]

            swap_txn = await chain_from.bridge_contract.functions.sendFrom(
                _from, _chainId, _toaddress, _amount, _minamount, _callparams
            ).build_transaction({
                'from': address,
                'value': fee,
                'gas': 500000,
                'gasPrice': gas_price,
                'nonce': nonce,
            })

            signed_swap_txn = chain_from.w3.eth.account.sign_transaction(swap_txn, wallet)
            swap_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            return swap_txn_hash

        except Exception as e:
            print(f"Error: {e}")


# Create chain instances using the factory
polygon = ChainFactory.create_chain("polygon")
bsc = ChainFactory.create_chain("bsc")
avalanche = ChainFactory.create_chain("avalanche")
arbitrum = ChainFactory.create_chain("arbitrum")
optimism = ChainFactory.create_chain("optimism")


async def check_balance(address, contract):
    balance = await contract.functions.balanceOf(address).call()
    return balance


async def work(wallet):
    # List of chain pairs to swap between, using chain names (which will be used to create chains dynamically)
    chains = [
        # Example pairs: (from_chain_name, to_chain_name, contract, swap_function, token_name, from_chain_label, to_chain_label)
        ("polygon", "bsc")
        # Add more pairs as necessary
    ]

    # Initialize account and address from wallet private key
    account = avalanche.w3.eth.account.from_key(wallet)
    address = account.address
    print(f'Wallet: {address} | Start')

    # Loop through each chain pair and perform the swap logic
    for from_chain_name, to_chain_name in chains:
        # Create chain instances dynamically using the ChainFactory
        from_chain = ChainFactory.create_chain(from_chain_name)
        to_chain = ChainFactory.create_chain(to_chain_name)
        print(f'For wallet: {address} bridge goes from: {from_chain.chain_name} to: {to_chain.chain_name} ')

        # Use random start delay between 60 and 390 seconds
        start_delay = random.randint(START, END)
        print(f'For wallet: {address} delay: {start_delay} ')
        await asyncio.sleep(start_delay)

        # Dynamically get the contract object based on the contract attribute name
        contract = getattr(from_chain, from_chain.btc_b_contract)

        # Check the balance on the from chain for the specified contract
        balance = await check_balance(address, contract)
        print(f'For wallet: {address} in chain {from_chain.chain_name} balance: {balance} ')

        # Ensure the balance is sufficient before proceeding
        while balance < 30000:
            await asyncio.sleep(random.randint(START, END))  # Random delay before checking balance again
            balance = await check_balance(address, contract)

        try:
            # Perform the swap
            txn_hash = await SwapTransaction.execute(from_chain, to_chain, wallet)
            print(
                f"{from_chain.chain_name} -> {to_chain.chain_name} | BTC.b | {address} | Transaction: {from_chain.blockExplorerUrl}/tx/{txn_hash.hex()}")
        except Exception as e:
            print(f"Error during swap: {e}")

    print(f'Wallet: {address} | Finish')


async def main():
    # Read wallet addresses from a text file
    with open('wallets.txt', 'r') as f:
        WALLETS = [row.strip() for row in f]

    tasks = []
    for wallet in WALLETS:
        tasks.append(asyncio.create_task(work(wallet)))

    # Run all tasks concurrently
    await asyncio.gather(*tasks)

    print(f'Thats all fox, looks like we are done here. ')


if __name__ == '__main__':
    asyncio.run(main())
