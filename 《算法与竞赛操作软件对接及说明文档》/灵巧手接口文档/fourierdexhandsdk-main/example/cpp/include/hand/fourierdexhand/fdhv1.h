#ifndef __FDHV1_H__
#define __FDHV1_H__

#include "basehand.h"
#include "handprotocol.h"

#define FDHV1_RIGHT_TYPE  "FDH-6R"
#define FDHV1_LEFT_TYPE   "FDH-6L"
#define FDHV1_UNKNOW_TYPE   "FDH-6X"

namespace BaseHandProtocol
{
    class Fdhv1 : public BaseHand
    {
    private:
        std::string ip_;
        uint32_t wait_replt_counts_max = 100000;
        std::vector<float> max_limited;
        std::string setCfgReply = "Please wait three seconds, then reboot ";
        TimeoutCfg_t definetimeout;
        std::string get_pva_com = "{\"method\":\"GET\",\"cmd\":\"/pva\"}";

        // std::string get_config_comm = "{\"method\":\"GET\",\"cmd\":\"/config\"}";
        // std::string get_config_ctrl = "{\"method\":\"GET\",\"cmd\":\"/config\"}";

        // std::string get_status_protocol = "{\"method\":\"GET\",\"cmd\":\"/errorcode\"}";

        // std::string calibration_protocol = "{\"method\":\"SET\",\"cmd\":\"/calibration\"}";
        std::string disable_protocol = "{\"method\":\"SET\",\"cmd\":\"/disable\"}";
        std::string enable_protocol = "{\"method\":\"SET\",\"cmd\":\"/enable\"}";
        // std::string set_pwm_protocol = "{\"method\":\"SET\",\"cmd\":\"/pwm\"}";
        // std::string set_pos_protocol = "{\"method\":\"SET\",\"cmd\":\"/pos\"}";

        // std::string set_config_comm = "{\"method\":\"SET\",\"cmd\":\"/config\",\"type\":0,\"sn\":\"FDH12XXXXXXXXXXX\",\"ip\":\"192.168.137.221\",\"mac\":\"AA-BB-CC-DD-EE-FF\",\"gateway\":\"192.168.137.1\",\"save_config\":true}";
        // std::string get_ctrl_mode = "{\"method\":\"GET\",\"cmd\":\"/ctrl_mode\"}";

    public:
        Fdhv1(std::string ip);
        ~Fdhv1();

        FdhReturnCode calibration() override;
        FdhReturnCode enable() override;
        FdhReturnCode disable() override;
        FdhReturnCode reboot() override;

        FdhReturnCode get_cnt(std::vector<long> &fdb) override;
        FdhReturnCode get_pos(std::vector<float> &fdb) override;
        FdhReturnCode get_current(std::vector<float> &fdb) override;
        FdhReturnCode get_velocity(std::vector<float> &fdb) override;

        FdhReturnCode get_errorcode(std::vector<long> &fdb) override; //
        FdhReturnCode get_status(std::vector<uint8_t> &fdb) override;
        FdhReturnCode clear_errorcode() override;

        FdhReturnCode get_comm_config(HandCfg_t &cfg) override;
        FdhReturnCode set_comm_config(HandCfg_t cfg) override;

        FdhReturnCode get_pos_limited(std::vector<float> &fdb) override;
        FdhReturnCode get_velocity_limited(std::vector<float> &fdb) override;
        FdhReturnCode get_current_limited(std::vector<float> &fdb) override;

        FdhReturnCode get_gateway(std::string &gateway);

        FdhReturnCode set_velocity_limited(uint8_t id, float max_speed) override; //
        FdhReturnCode set_pos_limited(uint8_t id, float start_angel, float end_angle) override;
        FdhReturnCode set_current_limited(uint8_t id, float max_current) override;

        FdhReturnCode set_pos(std::vector<float> pos) override;
        FdhReturnCode set_velocity(std::vector<float> _cmd) override;
        FdhReturnCode set_current(std::vector<float> _cmd) override;

        FdhReturnCode fast_set_positions(std::vector<float> pos) override;

        FdhReturnCode set_pwm(std::vector<float> _cmd) override;

        FdhReturnCode get_ts_matrix(std::vector<std::vector<uint8_t>> &matrix) override;
        FdhReturnCode get_ts_tashan(std::vector<std::vector<float>> &tashan) override;
        FdhReturnCode get_ntc(int &temp) override;


        FdhReturnCode set_sn(std::string sn);
        FdhReturnCode set_mac(std::vector<int> mac);
        FdhReturnCode set_ip(std::vector<int> ip);
        FdhReturnCode set_type(int type);
        FdhReturnCode set_gateway(std::vector<int> gateway);

        FdhReturnCode reset_pid();

        FdhReturnCode set_pos_pid(uint8_t id, std::vector<float> _pid);
        FdhReturnCode set_velocity_pid(uint8_t id, std::vector<float> _pid);
        FdhReturnCode set_current_pid(uint8_t id, std::vector<float> _pid);

        FdhReturnCode get_pvc(std::vector<std::vector<float>> &fdb) override;

        FdhReturnCode set_pvc(std::vector<std::vector<float>> pvc) override;
        FdhReturnCode set_pd_params(std::vector<std::vector<float>> params) override;
        FdhReturnCode set_ctrl_mode(CtrlType mode) override;

        FdhReturnCode set_controller_config(CtrlCfg_t config) override;
        FdhReturnCode get_controller_config(CtrlCfg_t &config) override;
        FdhReturnCode get_controller_type(CtrlType &mode) override;

        FdhReturnCode set_timeout_max(TimeoutCfg_t timeout);
        FdhReturnCode get_timeout_max(TimeoutCfg_t &timeout);

        FdhReturnCode fast_get_positions(std::vector<float> &fdb);
        FdhReturnCode fast_set_speed(std::vector<float> speed);

        FdhReturnCode fast_get_speed(std::vector<float> &speed);
        FdhReturnCode fast_set_current(std::vector<float> current);

        FdhReturnCode fast_get_current(std::vector<float> &current);
        FdhReturnCode fast_set_pos_speed(std::vector<std::vector<float>> pos_speed);
        FdhReturnCode fast_set_pos_pid(std::vector<std::vector<float>> pid);
        FdhReturnCode fast_set_speed_pid(std::vector<std::vector<float>> pid);
        FdhReturnCode fast_set_current_pid(std::vector<std::vector<float>> pid);

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
