//
// Created by Kshitij Das on 2026.09.11.
//

#ifndef CURRENCY_CONVERTER_DASHBOARD_CSV_PARSER_H
#define CURRENCY_CONVERTER_DASHBOARD_CSV_PARSER_H

#include <string>
#include <istream>
#include "ccd/models.h"

namespace ccd {
    ParseResult parseCsv(std::istream& in);

    ParseResult parseCsvFile(const std::string& path);

    ParseResult  parseCsvText(const std::string& text);
}

#endif //CURRENCY_CONVERTER_DASHBOARD_CSV_PARSER_H
