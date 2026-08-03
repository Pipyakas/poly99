#include "json.h"

#include <cstdlib>
#include <cstring>

namespace polyjson {

namespace {

struct Parser {
    const std::string& s;
    size_t pos;

    explicit Parser(const std::string& text) : s(text), pos(0) {}

    void skipWs() {
        while (pos < s.size()) {
            char c = s[pos];
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') pos++;
            else break;
        }
    }

    bool fail(std::string& error, const char* msg) {
        error = std::string(msg) + " at offset " + std::to_string(pos);
        return false;
    }

    bool parseValue(Value& out, std::string& error) {
        skipWs();
        if (pos >= s.size()) return fail(error, "unexpected end");
        char c = s[pos];
        switch (c) {
            case '{': return parseObject(out, error);
            case '[': return parseArray(out, error);
            case '"': {
                std::string str;
                if (!parseString(str, error)) return false;
                out.data = str;
                return true;
            }
            case 't':
                if (s.compare(pos, 4, "true") == 0) { out.data = true; pos += 4; return true; }
                return fail(error, "invalid literal");
            case 'f':
                if (s.compare(pos, 5, "false") == 0) { out.data = false; pos += 5; return true; }
                return fail(error, "invalid literal");
            case 'n':
                if (s.compare(pos, 4, "null") == 0) { out.data = std::monostate{}; pos += 4; return true; }
                return fail(error, "invalid literal");
            default:
                if (c == '-' || (c >= '0' && c <= '9')) return parseNumber(out, error);
                return fail(error, "unexpected character");
        }
    }

    bool parseObject(Value& out, std::string& error) {
        pos++; // '{'
        Object obj;
        skipWs();
        if (pos < s.size() && s[pos] == '}') { pos++; out.data = obj; return true; }
        for (;;) {
            skipWs();
            if (pos >= s.size()) return fail(error, "unterminated object");
            if (s[pos] != '"') return fail(error, "expected key string");
            std::string key;
            if (!parseString(key, error)) return false;
            skipWs();
            if (pos >= s.size() || s[pos] != ':') return fail(error, "expected ':'");
            pos++;
            Value val;
            if (!parseValue(val, error)) return false;
            obj[key] = val;
            skipWs();
            if (pos >= s.size()) return fail(error, "unterminated object");
            if (s[pos] == ',') { pos++; continue; }
            if (s[pos] == '}') { pos++; break; }
            return fail(error, "expected ',' or '}'");
        }
        out.data = obj;
        return true;
    }

    bool parseArray(Value& out, std::string& error) {
        pos++; // '['
        Array arr;
        skipWs();
        if (pos < s.size() && s[pos] == ']') { pos++; out.data = arr; return true; }
        for (;;) {
            Value val;
            if (!parseValue(val, error)) return false;
            arr.push_back(val);
            skipWs();
            if (pos >= s.size()) return fail(error, "unterminated array");
            if (s[pos] == ',') { pos++; continue; }
            if (s[pos] == ']') { pos++; break; }
            return fail(error, "expected ',' or ']'");
        }
        out.data = arr;
        return true;
    }

    bool parseString(std::string& str, std::string& error) {
        pos++; // opening quote
        str.clear();
        while (pos < s.size()) {
            char c = s[pos];
            if (c == '"') { pos++; return true; }
            if (c == '\\') {
                pos++;
                if (pos >= s.size()) return fail(error, "bad escape");
                char e = s[pos++];
                switch (e) {
                    case '"': str += '"'; break;
                    case '\\': str += '\\'; break;
                    case '/': str += '/'; break;
                    case 'n': str += '\n'; break;
                    case 't': str += '\t'; break;
                    case 'r': str += '\r'; break;
                    default: str += e; break;
                }
                continue;
            }
            str += c;
            pos++;
        }
        return fail(error, "unterminated string");
    }

    bool parseNumber(Value& out, std::string& error) {
        size_t start = pos;
        if (pos < s.size() && s[pos] == '-') pos++;
        while (pos < s.size() && ((s[pos] >= '0' && s[pos] <= '9') || s[pos] == '.' || s[pos] == 'e' || s[pos] == 'E' || s[pos] == '+' || s[pos] == '-')) pos++;
        if (pos == start) return fail(error, "invalid number");
        out.data = strtod(s.substr(start, pos - start).c_str(), NULL);
        return true;
    }
};

} // namespace

bool parse(const std::string& text, Value& out, std::string& error) {
    Parser p(text);
    if (!p.parseValue(out, error)) return false;
    p.skipWs();
    if (p.pos != text.size()) return p.fail(error, "trailing characters");
    return true;
}

} // namespace polyjson
