# fourier_dexhand_sdk

## Introduction

The DexHand SDK provides a set of interfaces for communication with the underlying dexterous hand device, enabling control and data interaction via the UDP protocol. The device is identified by its IP address.

Default Left Hand IP: `192.168.137.19`  
Default Right Hand IP: `192.168.137.39`  

The SDK supports both Python3 and C++ interfaces, and currently can only be used in Linux systems.

## Getting Started

Ensure that the device is properly connected and the network configuration is correct. Please follow the instructions below to install and use the fourier_dexhand_sdk.

### For Python Users
#### Dependencies

- Linux system (currently only Linux is supported)
- Python 3.10 (recommended)
- pybind11
- dexhandpy

#### Installation

Python Library Installation:  
```bash
# pybind11
pip install pybind11
# released
pip install dexhandpy
```
#### Run the Example

```bash
cd example/python/
python3 fourier_dexhand_sdk_demo.py
```

### For C++ Users

#### Dependencies

- Linux system (currently only Linux is supported)  
- C++17 compiler（GCC or Clang）  
- libFourierDexHand.so dynamic library file 

#### Build the Project

```bash
cd example/cpp/
mkdir build && cd build
cmake ..
make
```
#### Run the Example

```bash
../bin/fourier_dexhand_sdk_demo
```

## Communication Configuration

Connect the computer to the dexterous hand using an Ethernet cable. Configure the corresponding wired network IP address of the computer as a static IP, for example: `192.168.137.10`

## API Documentation

### Python  
[fourier_dexhand_sdk_python_api](doc/EN/fourier_dexhand_sdk_python_api.md)

### C++  
[fourier_dexhand_sdk_cpp_api](doc/EN/fourier_dexhand_sdk_cpp_api.md)

## Example

### Python 
[fourier_dexhand_sdk_demo.py](example/python/fourier_dexhand_sdk_demo.py)

### C++
[fourier_dexhand_sdk_demo.cpp](example/cpp/fourier_dexhand_sdk_demo.cpp)

## Issues
Please report any issues or bugs! We will do our best to fix them.

## License

[Apache 2.0](LICENSE) © Fourier