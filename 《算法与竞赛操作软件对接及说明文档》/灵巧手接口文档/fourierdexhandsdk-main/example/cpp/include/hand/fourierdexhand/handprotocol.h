/**
 * @file handprotocol.h
 * @brief DexHand灵巧手协议接口
 * -
 * 本文件定义了DexHand灵巧手协议接口类。该类提供了以下功能:
 * - 解析数据
 * - 打包数据
 * -
 * @author Fourier
 * @date 2025-02-28
 * @copyright Copyright (c) 2025 Fourier. All rights reserved.
 */

#ifndef __HANDPROTOCOL_H__
#define __HANDPROTOCOL_H__

#include <vector>
#include <cstdint>
#include <mutex>
#include <condition_variable>
#include <atomic>

namespace BaseHandProtocol {

/* command */
const uint8_t CMD_GET_PVC                 = 0x01;
const uint8_t CMD_SET_PVC                 = 0x02;
const uint8_t CMD_SET_PD_PARAMS           = 0x03;
const uint8_t CMD_SET_CTRL_MODE           = 0x04;
const uint8_t CMD_GET_ERRORCODE           = 0x06;
const uint8_t CMD_FAST_SET_POS            = 0x07;
const uint8_t CMD_GET_POS                 = 0x09;
const uint8_t CMD_FAST_SET_SPEED          = 0x0a;
const uint8_t CMD_FAST_GET_SPEED          = 0x0c;
const uint8_t CMD_FAST_SET_CURRENT        = 0x0d;
const uint8_t CMD_FAST_GET_CURRENT        = 0x10;
const uint8_t CMD_FAST_SET_POS_SPEED      = 0x11;
const uint8_t CMD_FAST_SET_POS_LIMIT      = 0x16;
const uint8_t CMD_FAST_GET_POS_LIMIT      = 0x17;
const uint8_t CMD_FAST_SET_SPEED_LIMIT    = 0x18;
const uint8_t CMD_FAST_GET_SPEED_LIMIT    = 0x19;
const uint8_t CMD_FAST_SET_CURRENT_LIMIT  = 0x1a;
const uint8_t CMD_FAST_GET_CURRENT_LIMIT  = 0x1b;
const uint8_t CMD_FAST_SET_PWM            = 0x1c;
const uint8_t CMD_FAST_GET_PWM            = 0x1d;
const uint8_t CMD_FAST_SET_DOG_TIME       = 0x1e;
const uint8_t CMD_FAST_GET_CNT            = 0x20;
const uint8_t CMD_FAST_GET_STATUS         = 0x21;
const uint8_t CMD_FAST_SET_RADIAN         = 0x25;
const uint8_t CMD_FAST_GET_RADIAN         = 0x26;
const uint8_t CMD_FAST_SET_RADIAN_SPEED   = 0x27;
const uint8_t CMD_FAST_GET_RADIAN_SPEED   = 0x28;
const uint8_t CMD_FAST_SET_RADIAN_LIMIT   = 0x29;
const uint8_t CMD_FAST_GET_RADIAN_LIMIT   = 0x30;

struct Request
{
    uint32_t id;
    uint8_t cmd;
    uint8_t need = 1;
    std::vector<uint8_t> request;
    uint8_t response[1024];
    int response_size = 0;
    bool response_flag = false;
    std::mutex mtx;
    std::condition_variable cv;
};

class HandProtocol
{
public:
    static int ParseErrorCodes(const char* data, int size, std::vector<long>& fdb);
    static int ParsePVCs(const char* data, int size, std::vector<std::vector<float>>& fdb);

    static int PackData(Request& request, std::vector<float>& data);
    static int PackData(Request &request, std::vector<int> &data);
    static int PackData(Request &request, float &data);
    static int PackData(Request& request, std::vector<std::vector<float>> &data);
    static int PackData(Request& request, std::vector<long>& data);
    static int PackData(Request& request, uint8_t data);
    static int PackData(Request& request);
    static int unPackData(Request& request, std::vector<float>& fdb);
    static int unPackData(Request& request, std::vector<long>& fdb);
    static int unPackData(Request &request, std::vector<int> &fdb);
    static bool CheckCRC(const uint8_t *data, int size);
    static uint16_t CalculateCRC16(const uint8_t *data, int size);
};

uint32_t get_request_id();

} // namespace BaseHandProtocol

#endif /* __HANDPROTOCOL_H__ */

