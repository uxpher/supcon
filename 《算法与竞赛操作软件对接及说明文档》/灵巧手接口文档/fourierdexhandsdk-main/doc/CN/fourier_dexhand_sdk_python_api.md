# DexHand SDK 接口文档

## 简介

DexHand SDK 提供了一套与底层灵巧手设备通信的接口，通过 UDP 协议实现控制和数据交互。设备以 IP 地址作为唯一标识。

默认左手IP： `192.168.137.19`  
默认右手IP： `192.168.137.39`  

当前仅支持在linux系统中使用。

## 版本更新记录

|  版本号  |  日期  |  作者  |  更新内容  |  备注  |
| --- | --- | --- | --- | --- |
|  0.0.1  |  2025-04-25  |   |  初版  |   |
| 0.0.2 | 2026-01-29 |      | 补充控制模式说明并新增推荐 Python 版本 |      |

## 接口描述

### Ret 枚举类

定义了返回值枚举类 Ret，用于表示接口操作结果。

```python
class Ret:
    SUCCESS = 0  # 成功
    FAIL = -1    # 失败
    TIMEOUT = -2 # 超时
```

### DexHand 接口类

#### init

初始化 DexHand 灵巧手设备，扫描已连接所有设备。

```python
def init(flg: int = 0) -> Ret:
    pass
```

##### 参数

`flg` (int, 默认 0): 初始化标志，保留扩展。

##### 返回值

`Ret::SUCCESS`: 初始化成功  
`Ret::FAIL`: 初始化失败  

#### get\_ip\_list

获取已连接设备的 IP 地址列表。一个IP地址对应一个灵巧手。

```python
def get_ip_list() -> List[str]:
    pass
```

##### 返回值

已连接设备的 IP 地址列表（字符串列表）。

#### get\_name

获取设备名称。

```python
'''
设备名称：
Inspire：       “FSH”  
DexHand-FDH6：  “fdhv1”
DexHand-FDH12： “fdhv2” 
'''
def get_name(ip: str) -> str:
    pass
```

##### 参数

`ip` (str): 目标设备 IP 地址。

##### 返回值

设备名称（字符串）。

#### get\_type

获取设备类型。

```python
'''
设备类型：
Inspire： “Hand”
FDH6：    “FDH-6L”，“FDH-6R”
FDH12：   “FDH-12L”，“FDH-12R”
'''
def get_type(ip: str) -> str:
    pass
```

##### 参数

`ip` (str): 目标设备 IP 地址。

##### 返回值

设备类型（字符串）。

#### get\_driver\_ver

获取驱动固件版本号

```python
def get_driver_ver(ip: str) -> str:
    pass
```

##### 参数

`ip` (str): 目标设备 IP 地址。

##### 返回值

驱动版本号（字符串，格式：0.0.0.0）。

#### get\_hardware\_ver

获取机械PCB版本号

```python
def get_hardware_ver(ip: str) -> str:
    pass
```

##### 参数

`ip` (str): 目标设备 IP 地址。

##### 返回值

硬件版本号（字符串，格式：0.0.0.0）。

#### set\_pos

设置目标设备位置。6/12自由度长度列表。某个位置不控制写-1

6自由度对应位置和范围如下所示:  
食指1：0-1  
中指2：0-1  
无名指3：0-1  
小指4：0-1  
拇指5-6: 0-1  

![fdh6-1.png](../images/fdh6-1.png)

12自由度对应位置和范围如下图所示：  
食指1-3：0-1750，0-1780，0-576  
中指4-5：0-1750，0-1780  
无名指6-7：0-1750， 0-1780  
小指8-9：0-1750， 0-1780  
拇指10-12：0-1700，0-1700，0-1700  

![fdh12-2.png](../images/fdh12-2.png)

![fdh12-1.png](../images/fdh12-1.png)

```python
def set_pos(ip: str, pos: List[float]) -> Ret:
    pass
```

##### 参数

`ip` (str): 目标设备 IP 地址。  
`pos` (List[float]): 目标位置（浮点数列表）。  
6 自由度：每个自由度范围为 [0-1]。  
食指 1、中指 2、无名指 3、小指 4、拇指 5-6。  
12 自由度：详见接口文档中的自由度定义。  

##### 返回值

`Ret.SUCCESS`: 设置成功。  
`Ret.FAIL`: 设置失败。  

#### get\_pos

获取目标设备当前位置。

```python
def get_pos(ip: str) -> List[float]:
    pass
```

##### 参数

ip (str): 目标设备 IP 地址。

##### 返回值

当前位置（浮点数列表），通信失败返回空列表。

#### reboot

重启设备。

```python
def reboot() -> Ret:
    pass

def reboot(ip: str) -> Ret:
    pass
```

##### 参数

`ip` (str, 可选): 目标设备 IP 地址，不指定时重启所有设备。

##### 返回值

`Ret.SUCCESS`: 重启成功。  
`Ret.FAIL`: 重启失败。  

#### get_ts_matrix

获取触摸传感器数据。

```python
def get_ts_matrix(ip: str) -> List[List[int]]:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。

##### 返回值

6*96字节数据列表，失败返回空列表。

#### get_pvc

获取位置弧度，速度，电流。

```python
def get_pvc(ip: str) -> List[List[float]]:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。

##### 返回值

返回位置弧度，速度，电流数组，失败返回空列表。

#### set_pvc

设置位置弧度，速度，电流  
FDH12默认模式位置弧度控制，p参数弧度，PD控制模式pvc参数弧度/速度前馈/电流前馈  
FDH12关节弧度范围：  
食指1-3：0.2～1.69, 0.01～1.43, -0.04～0.26  
中指4-5：0.2～1.69, 0.01～1.43  
无名指6-7：0.2～1.69, 0.01～1.43  
小指8-9：0.2～1.69, 0.01～1.43  
拇指10-12：-0.02～1.23, 0.14～1.35, 0.2～1.57  

FDH6默认弧度速度控制模式，pv参数弧度/速度  
FDH6关节弧度范围：  
食指1：0.17～1.78  
中指2：0.17～1.78  
无名指3：0.17～1.78  
小指4：0.17～1.78  
拇指5-6：0.12-1.28, 0.0-1.68  

```python
def set_pvc(ip: str, pvc: List[List[float]]) -> Ret:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。
`pvc` (List[List[float]]): 位置弧度，速度，电流数组

##### 返回值

`Ret::SUCCESS`: 成功  
`Ret::FAIL`: 失败  

#### set_pd_params

设置pd参数

```python
def set_pd_params(ip: str, params: List[List[float]]) -> Ret:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。
`params` (List[List[float]]): pd参数

##### 返回值

`Ret::SUCCESS`: 成功  
`Ret::FAIL`: 失败  

#### set_ctrl_mode

设置控制模式

```python
def set_ctrl_mode(ip: str, mode: CtrlType) -> Ret:
    pass
```

| 模式             | 设定值                 | 说明                                                                                                                                                                        |
| ---------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 位置模式（默认） | `pos_des` 任意有效角度 | 位置闭环，**速度**与**电流**仅做限制<br>不限制请填 `-1`（内部会替换默认值）。请不要使用过大的电流值，会造成手的严重损伤！！                                                 |
| PD 位置模式      | `ctrl_mode = PD_POS`   | 输出 torque =`Kp·pos_err + Kd·vel_err + feedforward`<br>其中 `pos_err = pos_des - pos_fbk`（rad）<br>`vel_err = vel_des - vel_fbk`（rad/s）<br>`feedforward` 由用户输入。 |


##### 参数

`ip` (str): 目标设备 IP。
`mode` 控制模式

##### 返回值

`Ret::SUCCESS`: 成功  
`Ret::FAIL`: 失败  

#### get_ctrl_mode

获取控制模式

```python
def get_ctrl_mode(ip: str) -> CtrlType:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。

##### 返回值

`CtrlType`: 当前模式  

#### get_hand_config

获取设备配置。

```python
def get_hand_config(ip: str) -> HandCfg_t:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。

##### 返回值

`HandCfg_t`: 当前配置

#### set_hand_config

写入配置

```python
def set_hand_config(ip: str, config: HandCfg_t) -> Ret:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。
`config` 配置。

##### 返回值

`Ret::SUCCESS`: 成功  
`Ret::FAIL`: 失败  

#### get_errorcode

获取错误码

```python
def get_errorcode(ip: str) -> List(int):
    pass
```

##### 参数

`ip` (str): 目标设备 IP。

##### 返回值

错误码列表

#### set_controller_config

设置控制参数

```python
def set_controller_config(ip: str, config: CtrlCfg_t) -> Ret:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。  
`config` (CtrlCfg_t): 控制参数  

##### 返回值

`Ret::SUCCESS`: 成功  
`Ret::FAIL`: 失败  

#### get_controller_config

获取控制参数

```python
def get_controller_config(ip: str) -> CtrlCfg_t:
    pass
```

##### 参数

`ip` (str): 目标设备 IP。

##### 返回值

`CtrlCfg_t`：控制参数  

### HandType 枚举类

```python
class HandType(Enum):
    FDH_X = 0
    FDH_L = 1
    FDH_R = 2
```

### CtrlType 枚举类

```python
class CtrlType(Enum):
    NONE = 0
    POS_LOOP = 2
    PD_LOOP = 3
    POS_VEL_CUR_LOOP = 4
```

### HandCfg_t 配置类

```python
class HandCfg_t:
    def __init__(self):
        self.result = 0
        self.type = HandType.FDH_X
        self.sn = ""
        self.mac = [0,0,0,0,0,0]
        self.ip = ""
        self.gateway = ""
        self.enWriteIntoChip = True
```

### CtrlCfg_t 控制配置类

```python
class CtrlCfg_t:
    def __init__(self):
        self.result = 0
        self.PDKp = [-1]*12
        self.PDKd = [-1]*12
        self.PosKp = [-1]*12
        self.PosKi = [-1]*12
        self.PosKd = [-1]*12
        self.enWriteIntoChip = False
```

## 接口支持列表

|  interface  |  inspire  |  fdh6  |  fdh12  |
| --- | --- | --- | --- |
|  init  |  √  |  √  |  √  |
|  get_ip_list  |  √  |  √  |  √  |
|  get_name  |  √  |  √  |  √  |
|  get_type  |  √  |  √  |  √  |
|  get_driver_ver  |  √  |  √  |  √  |
|  get_hardware_ver  |  √  |  √  |  √  |
|  set_pos  |  √  |  √  |  √  |
|  get_pos  |  √  |  √  |  √  |
|  reboot()  |   |  √  |  √ |
|  reboot(ip)  |   |  √  |  √ |
|  get_ts_matrix  |   |    |  √  |
|  get_pvc  |   |  √   |  √  |
|  set_pvc  |   |  √   |  √  |
|  set_pd_params  |   |     |  √  |
|  set_ctrl_mode  |   |      |  √  |
|  get_ctrl_mode  |   |      |  √  |
|  get_hand_config  |   |  √   |  √  |
|  set_hand_config  |   |  √   |  √  |
|  get_errorcode  |   |    √  |    √ |
|  get_controller_config  |   |    |    √ |
|  set_controller_config  |   |    |    √ |

## 注意事项
