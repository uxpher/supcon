#ifndef __FHAND_H__
#define __FHAND_H__

#include "./fourierdexhand/basehand.h"
#include "./fourierdexhand/inspire.h"
#include "./fourierdexhand/fdhv1.h"
#include "./fourierdexhand/fdhv2.h"

#define SDK_VERSION "0.2.2"

using namespace BaseHandProtocol;

namespace hand_ws
{
    class Fhand
    {
    public:
        std::vector<std::unique_ptr<BaseHand>> hand_ptr;
        std::vector<std::string> ip_unique, type, name, driver_ver, hardware_ver, sn;
        std::vector<std::vector<unsigned int>> mac;

    private:
        std::vector<std::string> ip;

    private:
        FdhReturnCode broadcast();
        FdhReturnCode find_hand();

    public:
        Fhand(/* args */);
        ~Fhand();

        FdhReturnCode init();

        FdhReturnCode get_status(std::string _ip, std::vector<uint8_t> &status);
        FdhReturnCode get_errorcode(std::string _ip, std::vector<long> &errorcode);
        FdhReturnCode clear_errorcode(std::string _ip);

        FdhReturnCode calibration(std::string _ip);
        FdhReturnCode enable(std::string _ip);
        FdhReturnCode disable(std::string _ip);
        FdhReturnCode reboot(std::string _ip);

        FdhReturnCode set_position(std::string _ip, std::vector<float> position);
        FdhReturnCode get_position(std::string _ip, std::vector<float> &position);
        FdhReturnCode fast_set_positon(std::string _ip, std::vector<float> position);
        FdhReturnCode fast_get_positon(std::string _ip, std::vector<float> &position);
        FdhReturnCode fast_set_speed(std::string _ip, std::vector<float> speed);
        FdhReturnCode fast_get_speed(std::string _ip, std::vector<float> &speed);
        FdhReturnCode fast_set_current(std::string _ip, std::vector<float> current);
        FdhReturnCode fast_get_current(std::string _ip, std::vector<float> &current);
        FdhReturnCode fast_set_pos_speed(std::string _ip, std::vector<std::vector<float>> pos_speed);

        FdhReturnCode fast_get_pos_limit(std::string _ip, std::vector<float> &fdb);
        FdhReturnCode fast_get_current_limit(std::string _ip, std::vector<float> &fdb);
        FdhReturnCode fast_get_speed_limit(std::string _ip, std::vector<float> &fdb);

        FdhReturnCode fast_set_pos_limit(std::string _ip, std::vector<float> para);
        FdhReturnCode fast_set_speed_limit(std::string _ip, std::vector<float> para);
        FdhReturnCode fast_set_current_limit(std::string _ip, std::vector<float> para);

        FdhReturnCode fast_get_pwm(std::string _ip, std::vector<int> &fdb);
        FdhReturnCode fast_get_radian(std::string _ip, std::vector<float> &fdb);
        FdhReturnCode fast_get_radian_speed(std::string _ip, std::vector<float> &fdb);
        FdhReturnCode fast_get_radian_limit(std::string _ip, std::vector<float> &fdb);

        FdhReturnCode fast_set_pwm(std::string _ip, std::vector<int> para);
        FdhReturnCode fast_set_dog_time(std::string _ip, float para);
        FdhReturnCode fast_set_radian(std::string _ip, std::vector<float> para);
        FdhReturnCode fast_set_radian_speed(std::string _ip, std::vector<float> para);
        FdhReturnCode fast_set_radian_limit(std::string _ip, std::vector<float> para);

        FdhReturnCode fast_get_cnt(std::string _ip, std::vector<int> &fdb);
        FdhReturnCode fast_get_status(std::string _ip, std::vector<float> &fdb);


        /**
         * @brief get the pvc (position, velocity, current)
         * @param _ip
         * @param pvc position, velocity, current
         * @return FdhReturnCode
         */
        FdhReturnCode get_pvc(std::string _ip, std::vector<std::vector<float>> &pvc);

        FdhReturnCode set_pvc(std::string _ip, std::vector<std::vector<float>> pvc);
        FdhReturnCode set_pd_params(std::string _ip, std::vector<std::vector<float>> params);
        FdhReturnCode set_ctrl_mode(std::string _ip, CtrlType mode);

        FdhReturnCode set_pwm(std::string _ip, std::vector<float> pwm);

        FdhReturnCode get_ts_matrix(std::string _ip, std::vector<std::vector<uint8_t>> &ts_matrix);

        FdhReturnCode get_comm_config(std::string _ip, HandCfg_t &config);
        FdhReturnCode set_comm_config(std::string _ip, HandCfg_t config);

        FdhReturnCode set_controller_config(std::string _ip, CtrlCfg_t config);
        FdhReturnCode get_controller_config(std::string _ip, CtrlCfg_t &config);
        FdhReturnCode get_controller_type(std::string _ip, CtrlType &mode);

        FdhReturnCode set_timeout_max(std::string _ip, TimeoutCfg_t timeout);
        FdhReturnCode get_timeout_max(std::string _ip, TimeoutCfg_t &timeout);
    };

}
#endif
