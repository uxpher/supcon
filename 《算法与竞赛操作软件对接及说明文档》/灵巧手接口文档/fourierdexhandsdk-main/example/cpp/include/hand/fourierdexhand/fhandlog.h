/**
 * @file fhandlog.h
 * @brief 日志管理类
 * -
 * 本文件定义了DexHand灵巧手log接口类。该类提供了以下功能:
 * - 初始化日志
 * - 设置日志打印级别
 * - 打印日志：LOG_DEBUG("debug message")
 * -
 * @date 2025-03-14
 * @copyright Copyright (c) 2025 Fourier. All rights reserved.
 */
#pragma once

#include "spdlog/spdlog.h"
#include "spdlog/sinks/stdout_color_sinks.h"
#include "spdlog/sinks/rotating_file_sink.h"

#include <memory>
#include <mutex>
#include <iostream>


/* 日志配置文件 打印级别 文件大小 文件个数 */
#define LOG_FILE "fhand.log"
#define LOG_LEVEL spdlog::level::debug
#define MAX_FILE_SIZE 20*1024*1024
#define MAX_FILES 20

class LogManager
{
public:
    static void Init(
        const std::string& logfile = LOG_FILE,
        spdlog::level::level_enum level = LOG_LEVEL,
        size_t max_file_size = MAX_FILE_SIZE,
        size_t max_files = MAX_FILES
    )
    {
        auto& instance = GetInstance();
        std::lock_guard<std::mutex> lock(instance.init_mutex_);
        if (!instance.initialized_)
        {
            instance.InitImpl(logfile, level, max_file_size, max_files);
        }
    }

    static void SetLevel(spdlog::level::level_enum level)
    {
        std::lock_guard<std::mutex> lock(GetInstance().init_mutex_);
        GetInstance().logger_->set_level(level);
    }

    static std::shared_ptr<spdlog::logger> GetLogger()
    {
        auto& instance = GetInstance();
        std::lock_guard<std::mutex> lock(instance.init_mutex_);
        if (!instance.initialized_)
        {
            instance.InitImpl();
        }
        return instance.logger_;
    }

    static void Shutdown()
    {
        spdlog::shutdown();
    }

private:
    LogManager() = default;
    static LogManager& GetInstance()
    {
        static LogManager instance;
        return instance;
    }

    void InitImpl(
        const std::string& logfile = LOG_FILE,
        spdlog::level::level_enum level = LOG_LEVEL,
        size_t max_file_size = MAX_FILE_SIZE,
        size_t max_files = MAX_FILES
    )
    {
        try
        {
            std::string logDir;
            const char* home_dir = std::getenv("HOME");
            if (home_dir)
            {
#ifdef _WIN32
                logDir = std::string(home_dir) + "\\dexhandlog";
#else
                logDir = std::string(home_dir) + "/dexhandlog";
#endif
            }
            else
            {
#ifdef _WIN32
                logDir = "dexhandlog";
#else
                logDir = "./dexhandlog";
#endif
            }

            std::string file;
#ifdef _WIN32
            file = logDir + "\\" + logfile;
#else
            file = logDir + "/" + logfile;
#endif
            std::cout << "dexhand log file: " << file << std::endl;

            auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
            auto file_sink = std::make_shared<spdlog::sinks::rotating_file_sink_mt>(file, max_file_size, max_files);

            console_sink->set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%^%L%$:%s:%#] %v");
            file_sink->set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%L:%s:%#] %v");

            logger_ = std::make_shared<spdlog::logger>("SDK", spdlog::sinks_init_list{console_sink, file_sink});
            logger_->set_level(level);
            logger_->flush_on(level);
            spdlog::register_logger(logger_);

            initialized_ = true;
        }
        catch (const spdlog::spdlog_ex& ex)
        {
            std::cerr << "Log system init failed: " << ex.what() << std::endl;

            auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
            logger_ = std::make_shared<spdlog::logger>("SDK", console_sink);
            logger_->set_level(level);

            spdlog::register_logger(logger_);

            initialized_ = true;
        }
    }

    std::shared_ptr<spdlog::logger> logger_;
    std::mutex init_mutex_;
    bool initialized_ = false;
};

#define LOG_TRACE(...)    SPDLOG_LOGGER_TRACE(LogManager::GetLogger().get(), __VA_ARGS__)
#define LOG_DEBUG(...)    SPDLOG_LOGGER_DEBUG(LogManager::GetLogger().get(), __VA_ARGS__)
#define LOG_INFO(...)     SPDLOG_LOGGER_INFO(LogManager::GetLogger().get(), __VA_ARGS__)
#define LOG_WARN(...)     SPDLOG_LOGGER_WARN(LogManager::GetLogger().get(), __VA_ARGS__)
#define LOG_ERROR(...)    SPDLOG_LOGGER_ERROR(LogManager::GetLogger().get(), __VA_ARGS__)
#define LOG_CRITICAL(...) SPDLOG_LOGGER_CRITICAL(LogManager::GetLogger().get(), __VA_ARGS__)
