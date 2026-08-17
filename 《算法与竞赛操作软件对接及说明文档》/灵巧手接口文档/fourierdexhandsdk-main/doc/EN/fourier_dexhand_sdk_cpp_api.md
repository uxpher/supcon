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

All DexHand-related interfaces are encapsulated under the `FdHand` namespace.

### Ret Enum Class

Defines the Ret enumeration class to represent the results of interface operations.

```c++
enum class Ret
{
    SUCCESS = 0,
    FAIL = -1,
    TIMEOUT = -2
};
```

### DexHand Interface Class

#### init

Initializes the DexHand dexterous hand device and scans all connected devices.

```c++
Ret init(int flg = 0);
```

##### Parameters

`flg` (int, default 0): Initialization flag, reserved for future expansion.

##### Return Values

`Ret::SUCCESS`:  
`Ret::FAIL`:  
`Ret::TIMEOUT`:  

#### get\_ip\_list

Gets the list of IP addresses of connected devices. Each IP address corresponds to one dexterous hand.

```c++
std::vector<std::string> get_ip_list();
```

##### Return Values

A list of IP addresses of connected devices (list of strings).

#### get\_name

Gets the device name.

```c++
// Device names:
// Inspire：   “FSH”
// DexHand-FDH6： “fdhv1”
// DexHand-FDH12： “fdhv2”
std::string get_name(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.

##### Return Values

Device name (string).

#### get\_type

Gets the device type.

```c++
// Device types:
// Inspire： “Hand”
// FDH6：    “FDH-6L”，“FDH-6R”
// FDH12：   “FDH-12L”，“FDH-12R”
std::string get_type(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.

##### Return Value

Device type (string).

#### get\_driver\_ver

Gets the driver firmware version.

```c++
std::string get_driver_ver(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.

##### Return Value

Driver version (string, format: 0.0.0.0).

#### get\_hardware\_ver

Gets the hardware PCB version.

```c++
std::string get_hardware_ver(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.

##### Return Value

Hardware version (string, format: 0.0.0.0).

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

```c++
Ret set_pos(std::string ip, std::vector<float> pos);
```

##### Parameters

`ip` (std::string): Target device IP.  
`pos` (std::vector<float>): Target positions (list of floats).  
6 degrees of freedom: Each range is [0-1].  
Index Finger 1, Middle Finger 2, Ring Finger 3, Little Finger 4, Thumb 5-6.  
12 degrees of freedom: See the definition in the interface documentation.  

##### Return Value

`Ret::SUCCESS`:  
`Ret::FAIL`:  

#### get\_pos

Gets the current position of the target device.

```c++
std::vector<float> get_pos(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.  

##### Return Value

Current position (list of floats), returns an empty list if communication fails.

#### reboot

Restarts the device.

```c++
Ret reboot();
Ret reboot(std::string ip);
```

##### Parameters

`ip` (std::string, optional): Target device IP, restarts all devices if not specified.

##### Return Value

`Ret::SUCCESS`:  
`Ret::FAIL`:  

#### get_ts_matrix

Gets the touch sensor data.

```c++
std::vector<std::vector<uint8_t>> get_ts_matrix(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.  

##### Return Value

6*96 byte data list, returns an empty list on failure.

#### get_pvc

Gets the position in radians, speed, and current.

```c++
std::vector<std::vector<float>> get_pvc(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.  

##### Return Value

Returns the position, speed, and current arrays, or an empty list on failure.

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

```c++
Ret set_pvc(std::string ip, std::vector<std::vector<float>> pvc);
```

##### Parameters

`ip` (std::string): Target device IP.  
`pvc` (std::vector<std::vector<float>>): Position, speed, and current arrays

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure

#### set_pd_params

Sets the PD control parameters.

```c++
Ret set_pd_params(std::string ip, std::vector<std::vector<float>> params);
```

##### Parameters

`ip` (std::string): Target device IP.  
`params` (std::vector<std::vector<float>>): PD control parameters, 2D array

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### set_ctrl_mode

Sets the control mode.

```c++
Ret set_ctrl_mode(std::string ip, CtrlType mode);
```

| Mode | Set-point | Description |
| ---- | --------- | ----------- |
| Position mode (default) | any valid angle in `pos_des` | Position loop closed; **velocity** and **current** are only saturated. <br> Enter `-1` to disable the limit (replaced internally by the maximum allowed value). **DO NOT use excessive current—serious hand injury may occur!** |
| PD position mode | `ctrl_mode = PD_POS` | Output torque = `Kp·pos_err + Kd·vel_err + feedforward` <br> where `pos_err = pos_des − pos_fbk` (rad) <br> `vel_err = vel_des − vel_fbk` (rad/s) <br> `feedforward` is supplied by the user. |

##### Parameters

`ip` (std::string): Target device IP.  
`mode` (CtrlType): control mode

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### get_hand_config

Gets the device configuration.

```c++
HandCfg_t get_hand_config(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.  

##### Return Value

`HandCfg_t`: current hand config

#### set_hand_config

Sets hand config

```c++
Ret set_hand_config(std::string ip, HandCfg_t config);
```

##### Parameters

`ip` (std::string): Target device IP.  
`config` config.

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### get_errorcode

Gets the error code

```c++
std::vector<long> get_errorcode(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.  

##### Return Value

Error code list

#### set_controller_config

Sets control parameters

```c++
Ret set_controller_config(std::string ip, CtrlCfg_t config);
```

##### Parameters

`ip` (std::string): Target device IP.  
`config` (CtrlCfg_t): control parameters  

##### Return Value

`Ret::SUCCESS`: Success  
`Ret::FAIL`: Failure  

#### get_controller_config

Gets control parameters

```c++
CtrlCfg_t get_controller_config(std::string ip);
```

##### Parameters

`ip` (std::string): Target device IP.  

##### Return Value

`CtrlCfg_t`：control parameters  

### HandType Enum Class

```c++
enum class HandType {
    FDH_X = 0,
    FDH_L = 1,
    FDH_R = 2
};
```

### CtrlType Enum Class

```c++
enum class CtrlType {
    NONE,
    POS_LOOP = 2,
    PD_LOOP,
    POS_VEL_CUR_LOOP,
};
```

### HandCfg_t Config Class

```c++
class HandCfg_t
{
public:
    int result = 0;
    HandType type = HandType::FDH_X;
    std::string sn;
    std::array<uint8_t, 6> mac;
    std::string ip;
    std::string gateway;
    bool enWriteIntoChip = true;
}
```

### CtrlCfg_t Contrl Config Class

```c++
class CtrlCfg_t
{
public:
    uint8_t result = 0;
    std::array<float, 12> PDKp;
    std::array<float, 12> PDKd;
    std::array<float, 12> PosKp;
    std::array<float, 12> PosKi;
    std::array<float, 12> PosKd;
    bool enWriteIntoChip = false;
};
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
|  reboot()  |   |  √  |  √  |
|  reboot(ip)  |   |  √  |  √  |
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
