#pragma once

#include <map>
#include <string>
#include <variant>
#include <vector>

namespace polyjson {

struct Value;

using Object = std::map<std::string, Value>;
using Array = std::vector<Value>;

struct Value {
    std::variant<std::monostate, double, std::string, bool, Object, Array> data;

    bool isNull() const { return data.index() == 0; }
    bool isNumber() const { return data.index() == 1; }
    bool isString() const { return data.index() == 2; }
    bool isBool() const { return data.index() == 3; }
    bool isObject() const { return data.index() == 4; }
    bool isArray() const { return data.index() == 5; }

    double asNumber(double def = 0.0) const {
        return isNumber() ? std::get<double>(data) : def;
    }
    const std::string& asString() const {
        static const std::string empty;
        return isString() ? std::get<std::string>(data) : empty;
    }
    const Value* get(const std::string& key) const {
        if (!isObject()) return nullptr;
        const Object& o = std::get<Object>(data);
        auto it = o.find(key);
        return (it == o.end()) ? nullptr : &it->second;
    }
};

bool parse(const std::string& text, Value& out, std::string& error);

} // namespace polyjson
