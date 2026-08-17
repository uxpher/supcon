# fourier_dexhand_sdk

## 简介

DexHand SDK 提供了一套与底层灵巧手设备通信的接口，通过 UDP 协议实现控制和数据交互。设备以 IP 地址作为唯一标识。

默认左手 IP `<192.168.137.19>`  
默认右手 IP `<192.168.137.39>`  

SDK 支持 python3 和 c++ 接口，当前仅支持在linux系统中使用。

## 开始使用

开始使用前，请确认设备正确连接且网络配置无误，跟从以下说明来安装并使用fourier_dexhand_sdk。

### 对于 Python 用户
#### 依赖

- Linux系统 (目前仅支持Linux系统)
- Python 3.10 (推荐)
- pybind11
- dexhandpy

#### 安装

Python库安装:  

```bash
# pybind11
pip install pybind11
# released
pip install dexhandpy
```

#### 运行示例

```bash
cd example/python/
python3 fourier_dexhand_sdk_demo.py
```

### 对于 C++ 用户

#### 依赖

- Linux系统 (目前仅支持Linux系统)  
- C++17编译器（GCC或Clang）  
- libFourierDexHand.so动态库文件 


#### 构建项目

```bash
cd example/cpp/
mkdir build && cd build
cmake ..
make
```
#### 运行示例

```bash
../bin/fourier_dexhand_sdk_demo
```

## 通信配置

使用网线连接计算机和灵巧手，将计算机对应的有线网络IP地址配置成静态IP，例如：`192.168.137.10`

## 接口说明

### Python  
[fourier_dexhand_sdk_python_api](doc/CN/fourier_dexhand_sdk_python_api.md)

### C++  
[fourier_dexhand_sdk_cpp_api](doc/CN/fourier_dexhand_sdk_cpp_api.md)

## 示例程序

### Python 
[fourier_dexhand_sdk_demo.py](example/python/fourier_dexhand_sdk_demo.py)

### C++
[fourier_dexhand_sdk_demo.cpp](example/cpp/fourier_dexhand_sdk_demo.cpp)

## License

[Apache 2.0](LICENSE) © Fourier