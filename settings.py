import json

with open('abi/router_abi.json') as f:
    router_abi = json.load(f)
with open('abi/btc_b_abi.json') as f:
    btc_b_abi = json.load(f)

#delay range in seconds
START = 10
END = 360