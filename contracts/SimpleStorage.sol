// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title SimpleStorage - Minimal demo contract
contract SimpleStorage {
    uint256 private _value;

    event ValueChanged(address indexed setter, uint256 oldValue, uint256 newValue);

    function set(uint256 newValue) external {
        uint256 old = _value;
        _value = newValue;
        emit ValueChanged(msg.sender, old, newValue);
    }

    function get() external view returns (uint256) {
        return _value;
    }
}
