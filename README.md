# Polygon Smart Contract Mini Platform

一个用于部署和交互 Polygon 智能合约的迷你平台，支持测试网（Mumbai）和主网。

## 功能特点

- 📦 一键部署智能合约
- 🔧 便捷的合约交互界面
- 📡 事件日志查询
- 🗂️ 本地部署记录
- 💫 支持 Mumbai 测试网和 Polygon 主网

## 快速开始

### 环境要求

- Python 3.8+
- Git
- 网络连接

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/yourusername/polygon-smart-platform.git
cd polygon-smart-platform
```

2. 创建并激活虚拟环境
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
```bash
cp app/.env.example app/.env
```
编辑 `.env` 文件，填入：
```
PRIVATE_KEY=你的私钥（不要带0x前缀）
RPC_URL_MUMBAI=Mumbai测试网RPC地址（可选）
RPC_URL_MAINNET=Polygon主网RPC地址（可选）
```

### 运行平台

```bash
cd app
streamlit run streamlit_app.py
```

## 使用指南

### 合约部署

1. 选择网络（Mumbai测试网/Polygon主网）
2. 输入RPC URL（可使用默认公共节点）
3. 输入私钥（仅测试环境使用！）
4. 点击"连接"
5. 选择要部署的合约模板
6. 填写构造函数参数（如果有）
7. 点击"部署"按钮

### 合约交互

1. 选择合约类型
2. 输入已部署的合约地址
3. 展开想要调用的函数
4. 填写参数（如果需要）
5. 点击"调用"或"发送交易"

### 事件查询

1. 选择合约类型
2. 输入合约地址
3. 选择要查询的事件
4. 设置查询区块范围
5. 点击"查询事件"

## 内置合约模板

1. **SimpleStorage**
   - 简单的存储合约
   - 可读写一个整数值
   - 写入时发出事件

2. **DemoERC20**
   - 基础的ERC20代币合约
   - 包含代币名称、符号、总量
   - 支持转账等基本操作

3. **PlatformRegistry**
   - 链上登记簿示例
   - 可记录部署信息
   - 用于演示目的

## 安全提示

- 私钥仅用于测试，切勿使用主网资产私钥
- Mumbai测试网仅用于开发测试
- 在主网部署前请仔细审计合约代码

## 文件结构

```
polygon-smart-platform/
├── app/
│   ├── streamlit_app.py    # 主程序
│   ├── .env.example        # 环境变量示例
│   ├── abi_cache/         # ABI缓存目录
│   └── deployments.json   # 部署记录
├── contracts/             # 合约源码
│   ├── SimpleStorage.sol
│   ├── DemoERC20.sol
│   └── PlatformRegistry.sol
└── README.md
```

## 贡献指南

欢迎提交Issue和Pull Request来改进这个项目。

## 许可证

MIT License