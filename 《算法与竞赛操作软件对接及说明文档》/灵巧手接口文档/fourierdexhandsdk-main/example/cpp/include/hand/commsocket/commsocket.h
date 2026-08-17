/**
 * @file commsocket.h
 * @brief DexHand灵巧手udp通信接口类
 * -
 * 本文件定义了DexHand灵巧手udp通信接口类。该类提供了以下功能:
 * - 创建socket
 * - 发送数据
 * - 接受数据
 * -
 * @author Fourier
 * @date 2025-02-26
 * @copyright Copyright (c) 2025 Fourier. All rights reserved.
 */

 #ifndef __COMMSOCKET_H__
 #define __COMMSOCKET_H__
 
 #include <cstring>
 #include <iostream>
 #include <vector>
 
 #include <unistd.h>
 
 // #define FDHX_TOOLS
 
 #ifndef FDHX_TOOLS
     #include <arpa/inet.h>
     #include <netinet/in.h>
     #include <sys/types.h>
     #include <sys/socket.h>
 #else
     #include "qudpsocket.h"
 #endif
 
 namespace CommSocket
 {
     namespace Transmit
     {
         enum class TransmitResult {SUCCESS, FAIL, TIMEOUT};
 
         class UDPSocket
         {
         public:
             UDPSocket(std::string ip, uint16_t remote_port);
             ~UDPSocket();
 
             TransmitResult SendData(std::vector<uint8_t> &send_data);
             TransmitResult SendData(std::string &send_data);
             TransmitResult SendData(const unsigned char *send_data, uint16_t data_length);
 
             TransmitResult ReceiveData(std::string &rec_ptr);
             TransmitResult ReceiveData(char *rec_ptr, int &size);
 
         private:
 #ifndef FDHX_TOOLS
             int sfd;
             struct sockaddr_in ser_addr_;
 #else
             std::unique_ptr< QUdpSocket > socket;
             QHostAddress ip_h;
             quint16 port;
 #endif
         };
     } // namespace Transmit
 }
 
 #endif // __COMMSOCKET_H__
 