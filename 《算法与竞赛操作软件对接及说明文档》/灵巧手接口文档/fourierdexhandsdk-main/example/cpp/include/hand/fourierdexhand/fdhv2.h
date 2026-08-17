#ifndef __FDHV2_H__
#define __FDHV2_H__

#include <vector>
#include "basehand.h"
#include "handprotocol.h"

#define FDHV2_RIGHT_TYPE "FDH-12R"
#define FDHV2_LEFT_TYPE "FDH-12L"
#define FDHV2_UNKNOW_TYPE "FDH-12X"

namespace BaseHandProtocol
{
    class Fdhv2 : public BaseHand
    {
    private:
        std::string ip_;

        // send msg list
        std::string get_matrix_com = "{\"method\":\"GET\",\"cmd\":\"/matrix\"}";
        std::string get_tashan_com = "{\"method\":\"GET\",\"cmd\":\"/tashan\"}";
        std::string get_pva_com = "{\"method\":\"GET\",\"cmd\":\"/pva\"}";

        std::string get_config_comm = "{\"method\":\"GET\",\"cmd\":\"/config\"}";
        std::string get_config_ctrl = "{\"method\":\"GET\",\"cmd\":\"/config\"}";

        std::string get_status_protocol = "{\"method\":\"GET\",\"cmd\":\"/errorcode\"}";

        std::string calibration_protocol = "{\"method\":\"SET\",\"cmd\":\"/calibration\"}";
        std::string disable_protocol = "{\"method\":\"SET\",\"cmd\":\"/disable\"}";
        std::string enable_protocol = "{\"method\":\"SET\",\"cmd\":\"/enable\"}";
        std::string reboot_protocol = "{\"method\":\"SET\",\"cmd\":\"/reboot\"}";
        std::string set_pwm_protocol = "{\"method\":\"SET\",\"cmd\":\"/pwm\"}";
        std::string set_pos_protocol = "{\"method\":\"SET\",\"cmd\":\"/pos\"}";

        std::string set_config_comm = "{\"method\":\"SET\",\"cmd\":\"/config\",\"type\":0,\"sn\":\"FDH12XXXXXXXXXXX\",\"ip\":\"192.168.137.221\",\"mac\":\"\",\"gateway\":\"192.168.137.1\",\"save_config\":true}";
        std::string get_ctrl_mode = "{\"method\":\"GET\",\"cmd\":\"/ctrl_mode\"}";
        TimeoutCfg_t definetimeout;
    
        public:
        Fdhv2(std::string ip);
        ~Fdhv2();

        FdhReturnCode calibration() override;
        FdhReturnCode enable() override;
        FdhReturnCode disable() override;
        FdhReturnCode reboot() override;

        FdhReturnCode get_cnt(std::vector<long> &fdb) override;
        FdhReturnCode get_pos(std::vector<float> &fdb) override;
        FdhReturnCode get_current(std::vector<float> &fdb) override;
        FdhReturnCode get_velocity(std::vector<float> &fdb) override;

        FdhReturnCode get_errorcode(std::vector<long> &fdb) override;
        FdhReturnCode get_status(std::vector<uint8_t> &fdb) override;
        FdhReturnCode clear_errorcode() override;

        FdhReturnCode get_comm_config(HandCfg_t &cfg) override;
        FdhReturnCode set_comm_config(HandCfg_t cfg) override;

        FdhReturnCode set_controller_config(CtrlCfg_t config) override;
        FdhReturnCode get_controller_config(CtrlCfg_t &config) override;
        FdhReturnCode get_controller_type(CtrlType &mode) override;

        FdhReturnCode get_pos_limited(std::vector<float> &fdb) override;
        FdhReturnCode get_velocity_limited(std::vector<float> &fdb) override;
        FdhReturnCode get_current_limited(std::vector<float> &fdb) override;

        FdhReturnCode set_velocity_limited(uint8_t id, float max_speed) override;
        FdhReturnCode set_pos_limited(uint8_t id, float start_angel, float end_angle) override;
        FdhReturnCode set_current_limited(uint8_t id, float max_current) override;

        FdhReturnCode set_pos(std::vector<float> _cmd) override;
        FdhReturnCode set_velocity(std::vector<float> _cmd) override;
        FdhReturnCode set_current(std::vector<float> _cmd) override;

        FdhReturnCode set_pwm(std::vector<float> _cmd) override;

        FdhReturnCode fast_set_positions(std::vector<float> pos) override;

        FdhReturnCode get_ts_matrix(std::vector<std::vector<uint8_t>> &matrix) override;
        FdhReturnCode get_ts_tashan(std::vector<std::vector<float>> &tashan) override;
        FdhReturnCode get_ntc(int &temp) override;

        FdhReturnCode get_pvc(std::vector<std::vector<float>> &fdb) override;

        FdhReturnCode set_pvc(std::vector<std::vector<float>> pvc) override;
        FdhReturnCode set_pd_params(std::vector<std::vector<float>> params) override;
        FdhReturnCode set_ctrl_mode(CtrlType mode) override;

        FdhReturnCode set_timeout_max(TimeoutCfg_t timeout) override;
        FdhReturnCode get_timeout_max(TimeoutCfg_t &timeout) override;

        FdhReturnCode fast_get_positions(std::vector<float> &fdb) override;
        FdhReturnCode fast_set_speed(std::vector<float> speed);
        FdhReturnCode fast_get_speed(std::vector<float> &speed);
        FdhReturnCode fast_set_current(std::vector<float> current);
        FdhReturnCode fast_get_current(std::vector<float> &current);
        FdhReturnCode fast_set_pos_speed(std::vector<std::vector<float>> pos_speed);

        FdhReturnCode fast_get_pos_limit(std::vector<float> &fdb);
        FdhReturnCode fast_get_speed_limit(std::vector<float> &fdb);
        FdhReturnCode fast_get_current_limit(std::vector<float> &fdb);

        FdhReturnCode fast_set_pos_limit(std::vector<float> para);
        FdhReturnCode fast_set_speed_limit(std::vector<float> para);
        FdhReturnCode fast_set_current_limit(std::vector<float> para);

        FdhReturnCode fast_get_pwm(std::vector<int> &fdb);
        FdhReturnCode fast_get_radian(std::vector<float> &fdb);
        FdhReturnCode fast_get_radian_speed(std::vector<float> &fdb);
        FdhReturnCode fast_get_radian_limit(std::vector<float> &fdb);

        FdhReturnCode fast_set_pwm(std::vector<int> para);
        FdhReturnCode fast_set_dog_time(float para);
        FdhReturnCode fast_set_radian(std::vector<float> para);
        FdhReturnCode fast_set_radian_speed(std::vector<float> para);
        FdhReturnCode fast_set_radian_limit(std::vector<float> para);

        FdhReturnCode fast_get_cnt(std::vector<int> &fdb);
        FdhReturnCode fast_get_status(std::vector<float> &fdb);



    private:
        uint32_t timeout_cnt = 0;
        FdhReturnCode fast_send_sync(Request &request, int timeout = 100);
        FdhReturnCode fast_send_async(Request &request);
    };
}
#endif
