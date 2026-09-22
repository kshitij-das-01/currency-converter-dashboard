//
// Created by Kshitij Das on 2026.09.11.
//

#ifndef CURRENCY_CONVERTER_DASHBOARD_MODELS_H
#define CURRENCY_CONVERTER_DASHBOARD_MODELS_H

#include <string>
#include <vector>
#include <unordered_map>

namespace ccd {
    struct ParseResult {
        std::unordered_map<std::string, std::vector<std::pair<std::string,double>>> series;
        std::size_t rowsTotal = 0;
        std::size_t rowsSkipped = 0;

        std::string dateMin, dateMax;
    };

    struct ConversionResult {
        std::string from, to, date;
        double amount = 0.0, rate = 0.0, result = 0.0;
    };

    struct StatsResult {
        double min = 0, max = 0, avg = 0, pctChange = 0, stddev = 0;
        int count = 0;
        std::string firstDate, lastDate;
    };

    struct Error {
        enum class Code {
            Ok,
            UnknownCurrency,
            InvalidAmount,
            InvalidDate,
            EmptyRange,
            BadWindow,
            Internal
        };

        Code code = Code::Ok;
        std::string message;

        explicit operator bool() const {
            return code != Code::Ok;
        }
    };
}

#endif //CURRENCY_CONVERTER_DASHBOARD_MODELS_H
