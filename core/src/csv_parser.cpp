//
// Created by Kshitij Das on 2026.09.11.
//
#include "ccd/csv_parser.h"

#include <algorithm>
#include <cctype>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>

namespace ccd {
    namespace {
        inline std::string trim(const std::string& s) {
            size_t b = 0, e = s.size();

            while (b < e && std::isspace(static_cast<unsigned char>(s[b]))) ++b;
            while (e > b && std::isspace(static_cast<unsigned char>(s[e-1]))) --e;

            return s.substr(b,e-b);
        }

        std::string normalizeDate(std::string s) {
            s = trim(s);

            if (s.size() < 8)
                return "";
            char sep = 0;

            if (s.size() >= 5 && s[4] == '-')
                sep = '-';
            else if (s.size() >= 5 && s[4] == '/')
                sep = '/';
            else if (s.size() >= 5 && s[4] == '.')
                sep = '.';
            else
                return "";

            std::string parts[3];
            int idx = 0;
            std::string cur;

            for (char c : s) {
                if (c == sep) {
                    if (idx >= 2)
                        return "";
                    parts[idx] = cur;
                    cur.clear();
                }
                else {
                    cur.push_back(c);
                }
            }

            if (idx != 2) return "";
            parts[2] = cur;

            for (int i = 0; i < 3; ++i) {
                if (parts[i].empty())
                    return "";

                for (char c : parts[i])
                    if (!std::isdigit(static_cast<unsigned char>(c)))
                        return "";
            }

            const int y = std::stoi(parts[0]);
            const int m = std::stoi(parts[1]);
            const int d = std::stoi(parts[2]);

            if (y < 1900 || y > 2100) return "";
            if (m < 1 || m > 12) return "";
            if (d < 1 || d > 31) return "";
            char buf[11];
            std::snprintf(buf, sizeof(buf), "%04d-%02d-%02d", y, m, d);
            return std::string(buf);
        }

        bool parseDouble(std::string_view tok, double& out) {
            size_t b = 0, e = tok.size();

            while (b < e && std::isspace(static_cast<unsignedchar>(tok[b]))) ++b;

            while (e > b && std::isspace(static_cast<unsigned char>(tok[e-1]))) --e;

            tok = tok.substr(b, e-b);
            if (tok.empty())
                return false;

            for (char c : tok) {
                bool ok = std::isdigit(static_cast<unsigned char>(c))
                        || c == '.' || c == '-' || c == '+' || c == 'e' || c == 'E';
                if (!ok) return false;
            }

            std::string s(tok);
            const char& start = s.c_str();
            char* endp = nullptr;
            errno = 0;

            double v = std::strtod(start, &endp);

            if (endp != start + s.size()) return false;
            if (start == endp) return false;
            if (!std::isfinite(v)) return false;

            out = v;
            return true;
        }

        std::vector<std::string> splitCsvLine(const std::string& line) {
            std::vector<std::string> out;
            std::string cur;
            bool inQuotes = false;

            for (size_t i = 0; i < line.size(); i++) {
                const char c = line[i];
                if (inQuotes) {
                    if (c == '"') {
                        if (i+1 < line.size() && line[i+1] == '"') {
                            cur.push_back('"'); i++;
                        }
                        else inQuotes = false;
                    }
                    else {
                        cur.push_back(c);
                    }
                }
                else {
                    if (c == '"') inQuotes = true;
                    else if (c == ',') {
                        out.push_back(cur); cur.clear();
                    }
                    else cur.push_back(c);
                }
            }
            out.push_back(cur);
            return out;
        }
    }

    ParseResult parseCsvText(const std::string &text) {
        ParseResult res;

        // 1. Split into logical lines
        std::vector<std::string> lines;

        {
            std::string line;

            for (char c : text) {
                if (c == '\n' || c == '\r') {
                    lines.push_back(line);
                    line.clear();
                }

                else line.push_back(c);
            }

            if (!line.empty() || (!text.empty() && text.back() == '\n')
                || (!text.empty() && text.back() == '\r')) {
                if (!line.empty())
                    lines.push_back(line);
            }
            else if (!line.empty()) {
                lines.push_back(line);
            }
        }

        if (lines.empty() && !text.empty()) {
            lines.push_back(text);

            if (!lines.back().empty() && lines.back().back() == '\r')
                lines.back().pop_back();
        }

        if (lines.empty()) return res;

        // 2. Header - column 0 is Date, rest are currency codes
        std::vector<std::string> header = splitCsvLine(lines[0]);
        if (header.empty())
            return res;

        std::vector<std::string> cols;
        cols.reserve(!header.empty() ? header.size() - 1 : 0);

        for (size_t i = 1; i < header.size(); i++) {
            cols.push_back(trim(header[i]));
        }

        for (auto& c : cols) {
            res.series[c] = {};
        }

        // 3. Data rows
        for (size_t li = 1; li < lines.size(); li++) {
            const std::string& raw = lines[li];

            if (raw.empty())
                continue;
            std::vector<std::string> cells = splitCsvLine(raw);

            if (cells.empty())
                continue;

            std::string date = normalizeDate(cells[0]);
            if (date.empty()) {
                ++res.rowsSkipped; continue;
            }

            std::vector<std::pair<std::string, double>> pending;
            pending.reserve(cols.size());

            bool rowOk = true;
            for (size_t ci = 0; ci < cols.size(); ci++) {
                std::string tok = (ci + 1 < cols.size()) ? trim(cells[ci+1]) : std::string();

                if (tok.empty())
                    continue;
                double v = 0.0;
                if (!parseDouble(tok, v)) {
                    rowOk = false; break;
                }
                pending.emplace_back(cols[ci], v);
            }

            if (!rowOk) {
                ++res.rowsSkipped; continue;
            }

            ++res.rowsTotal;
            if (res.dateMin.empty() || date < res.dateMin)
                res.dateMin = date;
            if (res.dateMax.empty() || date > res.dateMax)
                res.dateMax = date;

            for (auto& kv : pending) {
                res.series[kv.first].emplace_back(date, kv.second);
            }
        }

        // 4. Defensive sort
        for (auto& kv : res.series) {
            auto& vec = kv.second;

            bool sorted = std::is_sorted(vec.begin(), vec.end(),
                [](const auto& a, const auto& b) {
                    return a.first < b.first;
                });

            if (!sorted) {
                std::sort(vec.begin(), vec.end(),
                    [](const auto& a, const auto& b) { return a.first < b.first; });
            }

            vec.erase(std::unique(vec.begin(), vec.end(),
                [](const auto& a, const auto& b) { return a.first == b.first; }), vec.end());
        }

        for (auto it = res.series.begin(); it != res.series.end();) {
            if (it->second.empty()) it = res.series.erase(it);
            else ++it;
        }

        return res;
    }

    ParseResult parseCsv(std::istream& in) {
        std::ostringstream ss;
        ss << in.rdbuf();

        return parseCsvText(ss.str());
    }

    ParseResult parseCsvFile(const std::string& path) {
        std::ifstream in(path, std::ios::binary);
        if (!in) return ParseResult{};

        std::ostringstream ss;
        ss << in.rdbuf();

        return parseCsvText(ss.str());
    }

}
