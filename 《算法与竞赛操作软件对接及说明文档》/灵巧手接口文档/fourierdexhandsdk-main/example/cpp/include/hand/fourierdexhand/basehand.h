#ifndef __BASEHAND_H__
#define __BASEHAND_H__

#include <iostream>
#include <memory>
#include <chrono>
#include <cstring>
#include <vector>
#include <mutex> 
#include "./../rapidjson/stringbuffer.h"
#include "./../rapidjson/writer.h"
#include "./../rapidjson/document.h"
#include "./../rapidjson/rapidjson.h"
#include "./../commsocket/commsocket.h"

using namespace CommSocket;

#define BROADCAST_ADDR "192.168.137.255"
#define LEFT_DEFAULT_ADDR "192.168.137.19"
#define RIGHT_DEFAULT_ADDR "192.168.137.39"

#define CTROLLER_PORT 2333
#define COMMUNICATION_PORT 2334
#define FAST_BYTE_PORT 2335

#define INSPIRE_NAME "FSH"
#define DEXHAND_FDH6 "fdhv1"
#define DEXHAND_FDH12 "fdhv2"

#define DEXHAND_TYPE_6L "FDH-6L"
#define DEXHAND_TYPE_6R "FDH-6R"

#define DEXHAND_TYPE_12L "FDH-12L"
#define DEXHAND_TYPE_12R "FDH-12R"

#define INSPIRE_TYPE "Hand"

namespace BaseHandProtocol
{
    enum class FdhReturnCode
    {
        SUCCESS = 0,
        FAIL = -1,
        TIMEOUT = -2
    };

    enum class HandType {
        FDH_X = 0,
        FDH_L = 1,
        FDH_R = 2
    };

    enum class CtrlType {
        NONE,
        POS_LOOP = 2,
        PD_LOOP,
        POS_VEL_CUR_LOOP
    };
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

            HandCfg_t()
            {
                result = 0;
                mac.fill(0);
            }
    };

    class CtrlCfg_t
    {
        public:
            int result = 0;
            std::array<float, 12> PDKp;
            std::array<float, 12> PDKd;
            std::array<float, 12> PosKp;
            std::array<float, 12> PosKi;
            std::array<float, 12> PosKd;
            bool enWriteIntoChip = false;

            CtrlCfg_t()
            {
                PDKp.fill(-1);
                PDKd.fill(-1);
                PosKp.fill(-1);
                PosKi.fill(-1);
                PosKd.fill(-1);
            }
    };

    class TimeoutCfg_t
    {
        public:
            int result;
            int get_pos;
            int get_errorcode;
            int get_matrix;
            int get_pvc;
            TimeoutCfg_t()
            {
                result = 0;
                get_pos = 20;
                get_errorcode = 20;
                get_matrix = 20;
                get_pvc = 20;
            }
    };

    class BaseHand
    {
    public:
        std::shared_ptr<Transmit::UDPSocket> ctrl_udp_socket;
        std::shared_ptr<Transmit::UDPSocket> comm_udp_socket;
        std::shared_ptr<Transmit::UDPSocket> fast_udp_socket;

    protected:
        mutable std::mutex mtx_ctrl;
        mutable std::mutex mtx_comm;
        mutable std::mutex mtx_fast;
        
        std::vector<float> position_;
        std::vector<float> velocity_;
        std::vector<float> current_;
        std::vector<int> ipStringToVector(const std::string &ipStr);
        std::string vectorToIpString(const std::vector<int> &ipVec);
        std::string macToString(const uint8_t mac[6]);
        bool stringToMac(const std::string &macStr, uint8_t *mac);
        bool isValidIPv4(const std::string &ip);

    public:
        virtual ~BaseHand() = default;

        virtual FdhReturnCode calibration() = 0;
        virtual FdhReturnCode enable() = 0;
        virtual FdhReturnCode disable() = 0;
        virtual FdhReturnCode reboot() = 0;

        virtual FdhReturnCode get_cnt(std::vector<long> &fdb) = 0;
        virtual FdhReturnCode get_pos(std::vector<float> &fdb) = 0;
        virtual FdhReturnCode get_current(std::vector<float> &fdb) = 0;
        virtual FdhReturnCode get_velocity(std::vector<float> &fdb) = 0;

        virtual FdhReturnCode get_errorcode(std::vector<long> &fdb) = 0;
        virtual FdhReturnCode get_status(std::vector<uint8_t> &fdb) = 0;
        virtual FdhReturnCode clear_errorcode() = 0;

        virtual FdhReturnCode get_comm_config(HandCfg_t &cfg) = 0;
        virtual FdhReturnCode set_comm_config(HandCfg_t cfg) = 0;

        virtual FdhReturnCode get_pos_limited(std::vector<float> &fdb) = 0;
        virtual FdhReturnCode get_velocity_limited(std::vector<float> &fdb) = 0;
        virtual FdhReturnCode get_current_limited(std::vector<float> &fdb) = 0;

        virtual FdhReturnCode set_velocity_limited(uint8_t id, float max_speed) = 0;
        virtual FdhReturnCode set_pos_limited(uint8_t id, float start_angel, float end_angle) = 0;
        virtual FdhReturnCode set_current_limited(uint8_t id, float max_current) = 0;

        virtual FdhReturnCode set_pos(std::vector<float> _cmd) = 0;
        virtual FdhReturnCode set_velocity(std::vector<float> _cmd) = 0;
        virtual FdhReturnCode set_current(std::vector<float> _cmd) = 0;
        virtual FdhReturnCode set_pwm(std::vector<float> _cmd) = 0;
        virtual FdhReturnCode fast_set_positions(std::vector<float> pos) = 0;

        virtual FdhReturnCode fast_get_positions(std::vector<float> &fdb);
        virtual FdhReturnCode fast_set_speed(std::vector<float> speed);
        virtual FdhReturnCode fast_get_speed(std::vector<float> &speed);
        virtual FdhReturnCode fast_set_current(std::vector<float> current);
        virtual FdhReturnCode fast_get_current(std::vector<float> &current);
        virtual FdhReturnCode fast_set_pos_speed(std::vector<std::vector<float>> pos_speed);

        virtual FdhReturnCode fast_get_pos_limit(std::vector<float> &fdb);
        virtual FdhReturnCode fast_get_speed_limit(std::vector<float> &fdb);
        virtual FdhReturnCode fast_get_current_limit(std::vector<float> &fdb);

        virtual FdhReturnCode fast_set_pos_limit(std::vector<float> para);
        virtual FdhReturnCode fast_set_speed_limit(std::vector<float> para);
        virtual FdhReturnCode fast_set_current_limit(std::vector<float> para);

        virtual FdhReturnCode fast_get_pwm(std::vector<int> &fdb);
        virtual FdhReturnCode fast_get_radian(std::vector<float> &fdb);
        virtual FdhReturnCode fast_get_radian_speed(std::vector<float> &fdb);
        virtual FdhReturnCode fast_get_radian_limit(std::vector<float> &fdb);

        virtual FdhReturnCode fast_set_pwm(std::vector<int> para);
        virtual FdhReturnCode fast_set_dog_time(float para);
        virtual FdhReturnCode fast_set_radian(std::vector<float> para);
        virtual FdhReturnCode fast_set_radian_speed(std::vector<float> para);
        virtual FdhReturnCode fast_set_radian_limit(std::vector<float> para);

        virtual FdhReturnCode fast_get_cnt(std::vector<int> &fdb);
        virtual FdhReturnCode fast_get_status(std::vector<float> &fdb);


        virtual FdhReturnCode get_ts_matrix(std::vector<std::vector<uint8_t>> &matrix) = 0;
        virtual FdhReturnCode get_ts_tashan(std::vector<std::vector<float>> &tashan) = 0;
        virtual FdhReturnCode get_ntc(int &temp) = 0;

        virtual FdhReturnCode get_pvc(std::vector<std::vector<float>> &fdb) = 0;

        virtual FdhReturnCode set_pvc(std::vector<std::vector<float>> pvc);
        virtual FdhReturnCode set_pd_params(std::vector<std::vector<float>> params);
        virtual FdhReturnCode set_ctrl_mode(CtrlType mode);

        virtual FdhReturnCode set_controller_config(CtrlCfg_t config);
        virtual FdhReturnCode get_controller_config(CtrlCfg_t &config);
        virtual FdhReturnCode get_controller_type(CtrlType &mode);

        virtual FdhReturnCode set_timeout_max(TimeoutCfg_t timeout);
        virtual FdhReturnCode get_timeout_max(TimeoutCfg_t &timeout);
    };
}

#endif /* __BASEHAND_H__ */
