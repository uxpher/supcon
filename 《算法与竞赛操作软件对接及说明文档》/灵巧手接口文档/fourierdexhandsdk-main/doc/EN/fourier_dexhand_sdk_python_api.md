# DexHand SDK Interface Documentation

## Introduction

The DexHand SDK provides a set of interfaces to communicate with the underlying dexterous hand device, enabling control and data interaction via the UDP protocol. Devices are identified by their IP addresses.

Default Left Hand IP: `192.168.137.19`  
Default Right Hand IP: `192.168.137.39`  

currently can only be used in Linux systems.

## Version Update

|  Version  |  Date  |  Author  |  Update Content  |  Remarks  |
| --- | --- | --- | --- | --- |
|  0.0.1  |  2025-04-25  |   |  Initial version  |   |
| 0.0.2 | 2026-01-29 |      | Add control-mode documentation and specify the recommended Python version |      |

## Interface Description

### Ret Enum Class

Defines the Ret enumeration class to represent the results of interface operations.

```python
class Ret:
    SUCCESS = 0  # success
    FAIL = -1    # fail
    TIMEOUT = -2 # timeout
```

### DexHand Interface Class

#### init

Initializes the DexHand dexterous hand device and scans all connected devices.

```python
def init(flg: int = 0) -> Ret:
    pass
```

##### Parameters

`flg` (int, default 0): Initialization flag, reserved for future expansion.

##### Return Values

`Ret::SUCCESS`:  
`Ret::FAIL`:  

#### get\_ip\_list

Gets the list of IP addresses of connected devices. Each IP address corresponds to one dexterous hand.

```python
def get_ip_list() -> List[str]:
    pass
```

##### Return Values

A list of IP addresses of connected devices (list of strings).

#### get\_name

Gets the device name.

```python
'''
Device names:
Inspire：       “FSH”  
DexHand-FDH6：  “fdhv1”
DexHand-FDH12： “fdhv2” 
'''
def get_name(ip: str) -> str:
    pass
```

##### Parameters

`ip` (str):  Target device IP.

##### Return Values

Device name (str).

#### get\_type

Gets the device type.

```python
'''
Device types:
Inspire： “Hand”
FDH6：    “FDH-6L”，“FDH-6R”
FDH12：   “FDH-12L”，“FDH-12R”
'''
def get_type(ip: str) -> str:
    pass
```

##### Parameters

`ip` (str): Target device IP.

##### Return Value

Device type (str).

#### get\_driver\_ver

Gets the driver firmware version.

```python
def get_driver_ver(ip: str) -> str:
    pass
```

##### Parameters

`ip` (str): Target device IP.

##### Return Value

Driver version (str, format: 0.0.0.0).

#### get\_hardware\_ver

Gets the hardware PCB version.

```python
def get_hardware_ver(ip: str) -> str:
    pass
```

##### Parameters

`ip` (str): Target device IP.

##### Return Value

Hardware version (str, format: 0.0.0.0).

#### set\_pos

Sets the target position of the device. A list of 6/12 degrees of freedom. Write -1 for positions that are not controlled.

6 degrees of freedom correspond to the following positions and ranges:  
Index Finger 1: 0-1  
Middle Finger 2: 0-1  
Ring Finger 3: 0-1  
Little Finger 4: 0-1  
Thumb 5-6: 0-1  

![fdh6-1.png](../images/fdh6-1.png)

12 degrees of freedom correspond to the following positions and ranges:  
Index Finger 1-3：0-1750，0-1780，0-576  
Middle Finger 4-5：0-1750，0-1780  
Ring Finger 6-7：0-1750， 0-1780  
Little Finger 8-9：0-1750， 0-1780  
Thumb 10-12：0-1700，0-1700，0-1700  

![fdh12-2.png](../images/fdh12-2.png)

![fdh12-1.png](../images/fdh12-1.png)

```python
def set_pos(ip: str, pos: List[float]) -> Ret:
    pass
```

##### Parameters

`ip` (str): Target device IP.  
`pos` (List[float]): Target positions (list of floats).  
6 degrees of freedom: Each range is [0-1].  
Index Finger 1, Middle Finger 2, Ring Finger 3, Little Finger 4, Thumb 5-6.  
12 degrees of freedom: See the definition in the interface documentation.

##### Return Value

`Ret.SUCCESS`:  
`Ret.FAIL`:  

#### get\_pos

Gets the current position of the target device.

```python
def get_pos(ip: str) -> List[float]:
    pass
```

##### Parameters

ip (str): Target device IP.  

##### Return Value

Current position (list of floats), returns an empty list if communication fails.

#### reboot

Restarts the device.

```python
def reboot() -> Ret:
    pass

def reboot(ip: str) -> Ret:
    pass
```

##### Parameters

`ip` (str, optional): Target device IP, restarts all devices if not specified.

##### Return Value

`Ret.SUCCESS`:  
`Ret.FAIL`:  

#### get_ts_matrix

Get touch sensor data.

```python
def get_ts_matrix(ip: str) -> List[List[int]]:
    pass
```

##### Parameters

`ip` (str): Target device IP.

##### Return Value

A 6*96 byte data list. Returns an empty list on failure.

#### get_pvc

Get position (radians), velocity, and current.

```python
def get_pvc(ip: str) -> List[List[float]]:
    pass
```

##### Parameters

`ip` (str): Target device IP.

##### Return Value

Returns an array of position, velocity, and current. Returns an empty list on failure.

#### set_pvc

Sets position (in radians), velocity, and current values for finger joints. The behavior depends on the device model  

FDH12 Default Mode: Position control (radians) using P parameter. In PD control mode, uses PVC parameters (Position/Velocity feedforward/Current feedforward).  
FDH12 Joint Range Limits (Radians):  
Index1-3：0.2～1.69, 0.01～1.43, -0.04～0.26  
Middle4-5：0.2～1.69, 0.01～1.43  
Ring6-7：0.2～1.69, 0.01～1.43  
Little8-9：0.2～1.69, 0.01～1.43  
Thumb10-12：-0.02～1.23, 0.14～1.35, 0.2～1.57  

FDH6 Default Mode: Position-Velocity control (PV parameters).  
FDH6 Joint Range Limits (Radians):  
Index1：0.17～1.78  
Middle2：0.17～1.78  
Ring3：0.17～1.78  
Little4：0.17～1.78  
Thumb5-6：0.12-1.28, 0.0-1.68  

```python
def set_pvc(ip: str, pvc: List[List[float]]) -> Ret:
    pass
```

##### Parameters

`ip` (str): Target device IP.  
`pvc` (List[List[float]]): Array of position, velocity, and current.

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### set_pd_params

Set PD parameters.

```python
def set_pd_params(ip: str, params: List[List[float]]) -> Ret:
    pass
```

##### Parameters

`ip` (str): Target device IP.  
`params` (List[List[float]]): PD parameters.

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### set_ctrl_mode

Set control mode.

```python
def set_ctrl_mode(ip: str, mode: CtrlType) -> Ret:
    pass
```

| Mode                    | Set-point                   | Description                                                                                                                                                                                                                     |
| ----------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Position mode (default) | any valid angle in`pos_des` | Position loop closed;**velocity** and **current** are only saturated. <br> Enter `-1` to disable the limit (replaced internally by the maximum allowed value). **DO NOT use excessive current—serious hand injury may occur!** |
| PD position mode        | `ctrl_mode = PD_POS`        | Output torque =`Kp·pos_err + Kd·vel_err + feedforward` <br> where `pos_err = pos_des − pos_fbk` (rad) <br> `vel_err = vel_des − vel_fbk` (rad/s) <br> `feedforward` is supplied by the user.                                |

##### Parameters

`ip` (str): Target device IP.  
`mode` (CtrlType): control mode.

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### get_hand_config

Get device configuration.

```python
def get_hand_config(ip: str) -> HandCfg_t:
    pass
```

##### Parameters

`ip` (str): Target device IP.  

##### Return Value

`HandCfg_t`: Current configuration.

#### set_hand_config

Write configuration.

```python
def set_hand_config(ip: str, config: HandCfg_t) -> Ret:
    pass
```

##### Parameters

`ip` (str): Target device IP.  
`config` (HandCfg_t): Configuration.  

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### get_errorcode

Get error code

```python
def get_errorcode(ip: str) -> List(int):
    pass
```

##### Parameters

`ip` (str): Target device IP.  

##### Return Value

Error code list

#### set_controller_config

Set control parameters

```python
def set_controller_config(ip: str, config: CtrlCfg_t) -> Ret:
    pass
```

##### Parameters

`ip` (str): Target device IP.  
`config` (CtrlCfg_t): control parameters  

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### get_controller_config

Get control parameters

```python
def get_controller_config(ip: str) -> CtrlCfg_t:
    pass
```

##### Parameters

`ip` (str): Target device IP.  

##### Return Value

`CtrlCfg_t`：control parameters  

### HandType Enum Class

```python
class HandType(Enum):
    FDH_X = 0
    FDH_L = 1
    FDH_R = 2
```

### CtrlType Enum Class

```python
class CtrlType(Enum):
    NONE = 0
    POS_LOOP = 2
    PD_LOOP = 3
    POS_VEL_CUR_LOOP = 4
```

### HandCfg_t Config Class

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

### CtrlCfg_t Contrl Config Class

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

## Interface Support List

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
|  reboot(ip)  |   |  √  | √  |
|  get_ts_matrix  |   |    |  √  |
|  get_pvc  |   |  √   |  √  |
|  set_pvc  |   |   √  |  √  |
|  set_pd_params  |   |     |  √  |
|  set_ctrl_mode  |   |     |  √  |
|  get_ctrl_mode  |   |     |  √  |
|  get_hand_config  |   |  √   |  √  |
|  set_hand_config  |   |  √   |  √  |
|  get_errorcode  |   |    √  |    √ |
|  get_controller_config  |   |    |    √ |
|  set_controller_config  |   |    |    √ |

## Notes
