#include <iostream>
#include <vector>
#include <iomanip>
#include <thread>

#include "dexhand.h"


int main()
{
    FdHand::DexHand dexHand;

    // init search device
    FdHand::Ret initResult = dexHand.init();
    if (initResult != FdHand::Ret::SUCCESS)
    {
        std::cerr << "init failed! error: " << static_cast<int>(initResult) << std::endl;
        return -1;
    }
    std::cout << "init successfully!" << std::endl;

    // get IP list
    std::vector<std::string> ipList = dexHand.get_ip_list();
    if (ipList.empty())
    {
        std::cerr << "no device connected" << std::endl;
        return -1;
    }

    std::cout << "connected IP list:" << std::endl;
    for (const auto &ip : ipList)
    {
        std::cout << "- " << ip << std::endl;
    }

    // create thread for each device
    std::vector<std::thread> threadList;
    for (const auto &ip : ipList)
    {
        threadList.emplace_back([&, ip]() {
            std::string deviceName = dexHand.get_name(ip);
            std::cout << "device name: " << deviceName << std::endl;

            std::string deviceType = dexHand.get_type(ip);
            std::cout << "device type: " << deviceType << std::endl;

            std::string driverVersion = dexHand.get_driver_ver(ip);
            std::cout << "driver version: " << driverVersion << std::endl;

            std::string hardwareVersion = dexHand.get_hardware_ver(ip);
            std::cout << "hardware version: " << hardwareVersion << std::endl;

            // get current position
            std::vector<float> currentPosition = dexHand.get_pos(ip);
            if (currentPosition.empty())
            {
                std::cerr << "get current position failed" << std::endl;
            }
            else
            {
                std::cout << "currentPosition: ";
                for (const auto &pos : currentPosition)
                {
                    std::cout << std::fixed << std::setprecision(2) << pos << " ";
                }
                std::cout << std::endl;
            }

            // set position
            std::vector<float> targetPosition;
            if (deviceName == "fdhv2")
            {
                targetPosition.assign(12, 1.0);
            }
            else
            {
                targetPosition.assign(6, 1.0);
            }
            FdHand::Ret setPositionResult = dexHand.set_pos(ip, targetPosition);
            if (setPositionResult == FdHand::Ret::SUCCESS)
            {
                std::cout << "set position successfully!" << std::endl;
            }
            else
            {
                std::cerr << "set position failed! error: " << static_cast<int>(setPositionResult) << std::endl;
            }

            // get ts_matrix
            if (deviceName == "fdhv2")
            {
                auto tsMatrix = dexHand.get_ts_matrix(ip);
                if (!tsMatrix.empty())
                {
                    std::cout << "tsMatrix: ";
                    for (const auto &matrix : tsMatrix)
                    {
                        for (const auto &m: matrix)
                        {
                            printf("%u ", m);
                        }
                        std::cout << std::endl;
                    }
                }
                else
                {
                    std::cerr << "get tsMatrix failed!" << std::endl;
                }
            }

            std::vector<std::vector<float>> pvc = dexHand.get_pvc(ip);
            if (pvc.empty())
            {
                std::cerr << "get pvc failed" << std::endl;
            }
            else
            {
                std::cout << "p: ";
                for (const auto &p : pvc[0])
                {
                    std::cout << std::fixed << std::setprecision(2) << p << " ";
                }
                std::cout << std::endl;

                std::cout << "v: ";
                for (const auto &v : pvc[1])
                {
                    std::cout << std::fixed << std::setprecision(2) << v << " ";
                }
                std::cout << std::endl;

                std::cout << "c: ";
                for (const auto &c : pvc[2])
                {
                    std::cout << std::fixed << std::setprecision(2) << c << " ";
                }
                std::cout << std::endl;
            }

            HandCfg_t config = dexHand.get_hand_config(ip);
            std::cout << "result " << config.result << ", ip: " << config.ip << ", gateway: " << config.gateway << ", sn: " << config.sn << std::endl;

            // reboot
            FdHand::Ret rebootResult = dexHand.reboot(ip);
            if (rebootResult == FdHand::Ret::SUCCESS)
            {
                std::cout << "reboot successfully!" << std::endl;
            }
            else
            {
                std::cerr << "reboot failed! error: " << static_cast<int>(rebootResult) << std::endl;
            }
        });
    }

    for (auto &thread : threadList)
    {
        thread.join();
    }

    return 0;
}