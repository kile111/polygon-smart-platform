// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title PlatformRegistry - Optional on-chain registry for demo
contract PlatformRegistry {
    enum ContractType { Unknown, SimpleStorage, DemoERC20 }

    struct Entry {
        address contractAddress;
        ContractType ctype;
        address deployer;
        uint256 blockNumber;
    }

    Entry[] public entries;

    event Registered(address indexed deployer, address indexed contractAddress, ContractType ctype);

    function register(address contractAddress, ContractType ctype) external {
        entries.push(Entry({
            contractAddress: contractAddress,
            ctype: ctype,
            deployer: msg.sender,
            blockNumber: block.number
        }));
        emit Registered(msg.sender, contractAddress, ctype);
    }

    function total() external view returns (uint256) {
        return entries.length;
    }

    function get(uint256 index) external view returns (Entry memory) {
        return entries[index];
    }
}
