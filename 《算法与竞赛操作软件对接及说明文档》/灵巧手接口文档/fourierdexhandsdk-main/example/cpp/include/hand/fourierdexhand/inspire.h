#ifndef __INSPIRE_H__
#define __INSPIRE_H__

#include "basehand.h"
#define kSend_Frame_Head1 0xEB
#define kSend_Frame_Head2 0x90

#define kRcv_Frame_Head1 0x90
#define kRcv_Frame_Head2 0xEB

#define kCmd_Handg3_Read 0x11
#define kCmd_Handg3_Write 0x12

namespace BaseHandProtocol
{
    class Inspire : public BaseHand
    {
    private:
        std::string ip_;
        uint8_t ID = 1;
        std::string set_config_comm = "{\"method\":\"SET\",\"reqTarget\":\"/config\",\"property\":\"\",\"static_IP\":[192,168,137,19]}";
        unsigned short combineTo16Bit(unsigned char highByte, unsigned char lowByte);
        TimeoutCfg_t definetimeout;

    public:
        Inspire(std::string ip);
        ~Inspire();

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
    };
}
#endif
