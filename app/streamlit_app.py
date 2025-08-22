import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from web3 import Web3
from web3.middleware import construct_sign_and_send_raw_middleware
from eth_account import Account
from dotenv import load_dotenv
from hexbytes import HexBytes

from solcx import install_solc, set_solc_version, compile_standard

# ----------------------------
# Paths & Constants
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
CONTRACTS_DIR = ROOT_DIR / "contracts"
ABI_CACHE_DIR = BASE_DIR / "abi_cache"
DEPLOYMENTS_FILE = BASE_DIR / "deployments.json"
ENV_FILE = BASE_DIR / ".env"

SOLC_VERSION = "0.8.20"  # 与合约保持一致
SUPPORTED_CONTRACTS = {
    "SimpleStorage": CONTRACTS_DIR / "SimpleStorage.sol",
    "DemoERC20": CONTRACTS_DIR / "DemoERC20.sol",
    "PlatformRegistry": CONTRACTS_DIR / "PlatformRegistry.sol",
}

# ----------------------------
# Utils
# ----------------------------
def ensure_dirs():
    ABI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not DEPLOYMENTS_FILE.exists():
        DEPLOYMENTS_FILE.write_text(json.dumps([], indent=2), encoding="utf-8")

def load_env():
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)

def read_json(p: Path):
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def write_json(p: Path, data: Any):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def link_tx(network: str, tx_hash: str) -> str:
    if network.lower() == "mumbai":
        return f"https://mumbai.polygonscan.com/tx/{tx_hash}"
    elif network.lower() == "polygon":
        return f"https://polygonscan.com/tx/{tx_hash}"
    else:
        return tx_hash

def link_addr(network: str, addr: str) -> str:
    if network.lower() == "mumbai":
        return f"https://mumbai.polygonscan.com/address/{addr}"
    elif network.lower() == "polygon":
        return f"https://polygonscan.com/address/{addr}"
    else:
        return addr

# ----------------------------
# Web3 Provider
# ----------------------------
@dataclass
class ChainConfig:
    name: str
    rpc_url_env: str
    default_rpc: str
    chain_id: int

CHAINS = {
    "Mumbai (Testnet)": ChainConfig("Mumbai", "RPC_URL_MUMBAI", "https://polygon-mumbai-bor.publicnode.com", 80001),
    "Polygon (Mainnet)": ChainConfig("Polygon", "RPC_URL_MAINNET", "https://polygon-bor.publicnode.com", 137),
}

class Web3Provider:
    def __init__(self, rpc_url: str, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
        if not self.w3.is_connected():
            raise RuntimeError("无法连接 RPC，请检查网络或 RPC URL。")
        if private_key.startswith("0x"):
            self.account = Account.from_key(private_key)
        else:
            self.account = Account.from_key("0x" + private_key)
        # 本地签名中间件
        self.w3.middleware_onion.add(construct_sign_and_send_raw_middleware(self.account))
        self.w3.eth.default_account = self.account.address

    def balance_eth(self) -> float:
        wei = self.w3.eth.get_balance(self.account.address)
        return self.w3.from_wei(wei, "ether")

# ----------------------------
# Solidity Compiler
# ----------------------------
class Compiler:
    def __init__(self, solc_version: str = SOLC_VERSION):
        self.solc_version = solc_version
        try:
            set_solc_version(solc_version)
        except Exception:
            install_solc(solc_version)
            set_solc_version(solc_version)

    def compile(self, contract_name: str, source_path: Path) -> Tuple[List, Dict]:
        """
        编译并缓存 ABI/Bytecode
        返回: (abi, {"bytecode":bytecode})
        """
        sources = {source_path.name: {"content": source_path.read_text(encoding="utf-8")}}
        compiled = compile_standard(
            {
                "language": "Solidity",
                "sources": sources,
                "settings": {
                    "optimizer": {"enabled": True, "runs": 200},
                    "outputSelection": {"*": {"*": ["abi", "evm.bytecode"]}},
                },
            },
            allow_paths=str(CONTRACTS_DIR),
        )
        contracts = compiled["contracts"][source_path.name]
        if contract_name not in contracts:
            raise ValueError(f"未在 {source_path.name} 中找到合约 {contract_name}")

        abi = contracts[contract_name]["abi"]
        bytecode = contracts[contract_name]["evm"]["bytecode"]["object"]
        # cache
        abi_path = ABI_CACHE_DIR / f"{contract_name}.abi.json"
        bin_path = ABI_CACHE_DIR / f"{contract_name}.bin"
        write_json(abi_path, abi)
        bin_path.write_text(bytecode, encoding="utf-8")
        return abi, {"bytecode": bytecode}

    def load_cached(self, contract_name: str) -> Optional[Tuple[List, str]]:
        abi_path = ABI_CACHE_DIR / f"{contract_name}.abi.json"
        bin_path = ABI_CACHE_DIR / f"{contract_name}.bin"
        if abi_path.exists() and bin_path.exists():
            return read_json(abi_path), bin_path.read_text(encoding="utf-8")
        return None

# ----------------------------
# Deployment Records
# ----------------------------
def add_record(network: str, ctype: str, address: str, tx_hash: str, constructor_args: Dict):
    records = read_json(DEPLOYMENTS_FILE) or []
    records.append({
        "time": int(time.time()),
        "network": network,
        "contract_type": ctype,
        "address": Web3.to_checksum_address(address),
        "tx_hash": tx_hash,
        "constructor_args": constructor_args,
    })
    write_json(DEPLOYMENTS_FILE, records)

def load_records(network_filter: Optional[str] = None):
    records = read_json(DEPLOYMENTS_FILE) or []
    if network_filter:
        return [r for r in records if r["network"].lower().startswith(network_filter.lower())]
    return records

# ----------------------------
# UI Helpers
# ----------------------------
def success_tx(w3: Web3, net_name: str, receipt):
    txh = receipt.transactionHash.hex()
    st.success(f"交易已确认 ✅  区块: {receipt.blockNumber} | Gas Used: {receipt.gasUsed}")
    st.markdown(f"[在 Polygonscan 查看交易]({link_tx('mumbai' if 'mumbai' in net_name.lower() else 'polygon', txh)})")

def pretty_dict(d: Dict[str, Any]) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False)

def convert_args(inputs_abi: List[Dict], args_raw: List[str]) -> List[Any]:
    """
    基础类型转换：uint*, int*, address, bool, string, 以及对应的数组类型
    """
    converted = []
    for spec, raw in zip(inputs_abi, args_raw):
        t = spec["type"]
        if t.startswith("uint") or t.startswith("int"):
            converted.append(int(raw))
        elif t == "address":
            converted.append(Web3.to_checksum_address(raw))
        elif t == "bool":
            converted.append(str(raw).lower() in ("1", "true", "yes", "y", "t"))
        elif t == "string":
            converted.append(raw)
        elif t.endswith("[]"):
            base = t[:-2]
            arr = json.loads(raw) if str(raw).strip().startswith("[") else [x.strip() for x in str(raw).split(",") if x.strip() != ""]
            if base.startswith("uint") or base.startswith("int"):
                converted.append([int(x) for x in arr])
            elif base == "address":
                converted.append([Web3.to_checksum_address(x) for x in arr])
            elif base == "string":
                converted.append([str(x) for x in arr])
            else:
                raise ValueError(f"暂不支持的数组类型: {t}")
        else:
            converted.append(raw)
    return converted

def pretty_result(res: Any) -> str:
    try:
        if isinstance(res, (list, tuple)):
            return json.dumps([decode_hexbytes(x) for x in res], indent=2, ensure_ascii=False, default=str)
        return json.dumps(decode_hexbytes(res), indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(res)

def decode_hexbytes(obj: Any):
    if isinstance(obj, HexBytes):
        return obj.hex()
    if isinstance(obj, (list, tuple)):
        return [decode_hexbytes(x) for x in obj]
    if isinstance(obj, dict):
        return {k: decode_hexbytes(v) for k, v in obj.items()}
    return obj

def format_event_log(lg) -> Dict[str, Any]:
    return {
        "event": lg["event"],
        "address": lg["address"],
        "blockNumber": lg["blockNumber"],
        "transactionHash": lg["transactionHash"].hex(),
        "args": decode_hexbytes(dict(lg["args"])),
    }

# ---------------------------- Optimized Functions ----------------------------
def deploy_contract(provider, contract, constructor_args, chain_name, contract_type):
    """
    Deploy a contract and handle transaction.
    """
    try:
        tx = contract.constructor(*constructor_args).build_transaction({
            "from": provider.account.address,
            "nonce": provider.w3.eth.get_transaction_count(provider.account.address),
        })
        tx["gas"] = provider.w3.eth.estimate_gas(tx)
        tx["gasPrice"] = provider.w3.eth.gas_price
        tx_hash = provider.w3.eth.send_transaction(tx)
        receipt = provider.w3.eth.wait_for_transaction_receipt(tx_hash)
        add_record(chain_name, contract_type, receipt.contractAddress, tx_hash.hex(), dict(zip(contract.constructor_abi["inputs"], constructor_args)))
        return receipt
    except Exception as e:
        raise RuntimeError(f"部署失败：{e}")

def interact_with_contract(contract, function_name, args, is_write, provider=None):
    """
    Interact with a contract function (read or write).
    """
    try:
        func = getattr(contract.functions, function_name)
        if is_write:
            tx = func(*args).build_transaction({
                "from": provider.account.address,
                "nonce": provider.w3.eth.get_transaction_count(provider.account.address),
            })
            tx["gas"] = provider.w3.eth.estimate_gas(tx)
            tx["gasPrice"] = provider.w3.eth.gas_price
            tx_hash = provider.w3.eth.send_transaction(tx)
            receipt = provider.w3.eth.wait_for_transaction_receipt(tx_hash)
            return receipt
        else:
            return func(*args).call()
    except Exception as e:
        raise RuntimeError(f"交互失败：{e}")

# ----------------------------
# Streamlit App
# ----------------------------
def main():
    st.set_page_config(page_title="Polygon 智能合约迷你平台", page_icon="🏦", layout="wide")
    ensure_dirs()
    load_env()

    st.title("🏦 Polygon 智能合约迷你平台")
    st.caption("部署 · 交互 · 事件 · 记录（教育/演示用途）")

    # Sidebar: network & keys
    with st.sidebar:
        st.header("网络与账户")
        chain_key = st.selectbox(
            "选择网络",
            list(CHAINS.keys()),
            index=0,
            help="选择要连接的区块链网络。Mumbai 是 Polygon 的测试网，适合开发调试；Polygon Mainnet 是主网。"
        )
        chain = CHAINS[chain_key]
        rpc_default = os.getenv(chain.rpc_url_env, chain.default_rpc)
        rpc_url = st.text_input("RPC URL", value=rpc_default, help="RPC 是与区块链节点通信的接口地址。可使用公共节点或服务商（Alchemy/Infura）提供的 URL。")
        pk_default = os.getenv("PRIVATE_KEY", "")
        private_key = st.text_input("私钥（仅测试环境）", type="password", value=pk_default, help="用于本地签名交易的私钥。仅限测试环境使用，切勿泄露！")
        connect = st.button("连接", help="点击连接到所选网络，并加载账户信息。")

    if not connect:
        st.info("请在左侧填入 RPC 与私钥后点击『连接』。")
        st.stop()

    try:
        provider = Web3Provider(rpc_url, private_key)
    except Exception as e:
        st.error(f"连接失败：{e}")
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("地址", provider.account.address)
        st.markdown(f"[在浏览器查看]({link_addr('mumbai' if chain.name=='Mumbai' else 'polygon', provider.account.address)})")
    with col2:
        st.metric("余额 (MATIC)", f"{provider.balance_eth():.6f}")
    with col3:
        st.metric("链 ID", provider.w3.eth.chain_id)

    # 科普说明
    with st.expander("❓科普：什么是 RPC / 私钥 / 本地签名？", expanded=False):
        st.markdown(
            "- **RPC**：你的应用与区块链节点通信的 HTTP 接口。\n"
            "- **私钥**：控制账户资产与签名交易的密钥。这里用于本地签名并发送到 RPC。请仅使用测试钱包。\n"
            "- **本地签名**：交易先在本机用私钥签名，再发送到节点，节点不会接触你的私钥。"
        )

    compiler = Compiler()

    tabs = st.tabs(["📦 部署合约", "🔧 交互合约", "📡 事件日志", "🗂️ 部署记录"])

    # ---------------- Deploy Tab ----------------
    with tabs[0]:
        st.subheader("部署模板合约")
        with st.expander("❓科普：部署是什么？", expanded=False):
            st.markdown(
                "部署即把合约字节码发布到区块链，生成**合约地址**。部署交易需要支付 Gas。下面我们提供常见的模板供演示。"
            )

        template = st.selectbox(
            "选择模板",
            list(SUPPORTED_CONTRACTS.keys()),
            help="选择要部署的合约模板：\n- SimpleStorage：读写整数并发事件\n- DemoERC20：最小 ERC20（演示）\n- PlatformRegistry：链上登记薄（演示）"
        )
        # compile (use cache if available)
        cached = compiler.load_cached(template)
        abi, bytecode = cached if cached else compiler.compile(template, SUPPORTED_CONTRACTS[template])

        constructor_inputs = []  # Dynamically generate constructor inputs
        if template == "DemoERC20":
            name = st.text_input("Token 名称", value="Demo Token")
            symbol = st.text_input("Token 符号", value="DEMO")
            initial = safe_int_input(st.text_input("初始总量", value="1000000"), 10 ** 18)
            
            if initial is not None:
                constructor_inputs = [name, symbol, initial]
            else:
                st.error("初始总量必须是有效的整数")
        elif template == "SimpleStorage":
            st.write("无需构造参数。")
        
        deploy_button = st.button(
            f"部署 {template}",
            disabled=template == "DemoERC20" and len(constructor_inputs) == 0
        )

        if deploy_button:
            try:
                contract = provider.w3.eth.contract(abi=abi, bytecode=bytecode)
                receipt = deploy_contract(provider, contract, constructor_inputs, chain.name, template)
                st.success(f"部署成功：{receipt.contractAddress}")
                success_tx(provider.w3, chain.name, receipt)
            except Exception as e:
                st.error(str(e))

    # ---------------- Interact Tab ----------------
    with tabs[1]:
        st.subheader("与合约交互")
        contract_type = st.selectbox("合约类型", list(SUPPORTED_CONTRACTS.keys()))
        cached = compiler.load_cached(contract_type)
        abi = cached[0] if cached else compiler.compile(contract_type, SUPPORTED_CONTRACTS[contract_type])[0]
        address_input = st.text_input("合约地址（0x...）")

        if address_input and Web3.is_address(address_input):
            contract = provider.w3.eth.contract(address=Web3.to_checksum_address(address_input), abi=abi)
            for f in contract.functions:
                f_abi = f.abi
                name = f_abi["name"]
                inputs = f_abi.get("inputs", [])
                is_write = f_abi["stateMutability"] in ("nonpayable", "payable")
                with st.expander(f"{'✍️' if is_write else '🔍'} {name}"):
                    args = [st.text_input(f"{i['name']} ({i['type']})") for i in inputs]
                    if st.button(f"{'发送交易' if is_write else '调用'} {name}"):
                        try:
                            args_converted = convert_args(inputs, args)
                            result = interact_with_contract(contract, name, args_converted, is_write, provider if is_write else None)
                            if is_write:
                                success_tx(provider.w3, chain.name, result)
                            else:
                                st.code(pretty_result(result), language="json")
                        except Exception as e:
                            st.error(str(e))

    # ---------------- Events Tab ----------------
    with tabs[2]:
        st.subheader("事件日志")
        with st.expander("❓科普：什么是事件？", expanded=False):
            st.markdown(
                "事件是合约在执行时发出的日志，保存在区块中，常用于前端监听与索引。读取事件不花 Gas。"
            )

        contract_type = st.selectbox("选择 ABI 类型", list(SUPPORTED_CONTRACTS.keys()), key="evt_ctype",
                                     help="选择与目标合约匹配的 ABI 类型（本平台内置三种）。")
        cached = compiler.load_cached(contract_type)
        if cached:
            abi = cached[0]
        else:
            abi, _ = compiler.compile(contract_type, SUPPORTED_CONTRACTS[contract_type])
        address_input = st.text_input("合约地址（0x...）", key="evt_addr", help="输入要查询事件的合约地址。")
        default_from = max(provider.w3.eth.block_number - 5000, 0)
        from_block = st.number_input("起始区块（包含）", min_value=0, value=default_from,
                                     help="从哪个区块号开始查询（包含）。较大范围查询会更慢。")
        to_block_opt = st.text_input("结束区块（留空=最新）", value="", help="可指定结束区块号；留空表示查询到最新区块。")

        if address_input and Web3.is_address(address_input):
            contract = provider.w3.eth.contract(address=Web3.to_checksum_address(address_input), abi=abi)
            event_names = [a["name"] for a in abi if a.get("type") == "event"]
            if not event_names:
                st.warning("该 ABI 没有事件。")
            else:
                sel_evt = st.selectbox("事件名称", event_names, help="选择想要查询的事件。")
                if st.button("查询事件", help="从链上拉取指定区间内的事件日志。"):
                    try:
                        to_block = provider.w3.eth.block_number if to_block_opt.strip() == "" else int(to_block_opt)
                        evt = contract.events.__getattr__(sel_evt)
                        logs = evt().get_logs(fromBlock=int(from_block), toBlock=int(to_block))
                        st.write(f"共 {len(logs)} 条事件")
                        for lg in logs:
                            st.code(pretty_result(format_event_log(lg)), language="json")
                    except Exception as e:
                        st.error(f"查询失败：{e}")
        else:
            st.info("请输入有效的合约地址。")

    # ---------------- Records Tab ----------------
    with tabs[3]:
        st.subheader("本地部署记录")
        with st.expander("❓科普：为什么要记录部署？", expanded=False):
            st.markdown("为了便于回溯与排查，我们将部署信息存入本地 `deployments.json`。")

        records = load_records(chain.name)
        if not records:
            st.info("暂无记录。去『部署合约』试试！")
        else:
            for r in reversed(records):
                with st.expander(f"{r['contract_type']} @ {r['address']}", expanded=False):
                    st.json(r)
                    st.markdown(f"[查看交易]({link_tx('mumbai' if chain.name=='Mumbai' else 'polygon', r['tx_hash'])})")
                    st.markdown(f"[查看地址]({link_addr('mumbai' if chain.name=='Mumbai' else 'polygon', r['address'])})")

# Add to Utils section
def safe_int_input(value: str, multiplier: int = 1) -> Optional[int]:
    try:
        return int(value) * multiplier if value.strip() else None
    except ValueError:
        return None

if __name__ == "__main__":
    main()
