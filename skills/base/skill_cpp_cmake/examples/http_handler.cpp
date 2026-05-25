// REST API server using cpp-httplib + nlohmann/json — production pattern
// vcpkg deps: cpp-httplib, nlohmann-json
// CMake: find_package(httplib CONFIG REQUIRED) + find_package(nlohmann_json CONFIG REQUIRED)
#pragma once
#include <httplib.h>
#include <nlohmann/json.hpp>
#include <algorithm>
#include <atomic>
#include <iostream>
#include <optional>
#include <string>
#include <vector>

using json = nlohmann::json;

// ─── Model ────────────────────────────────────────────────────────────────────

struct User {
    int         id;
    std::string name;
    std::string email;
    std::string role;
    bool        active{true};
};

json user_to_json(const User& u) {
    return {
        {"id",     u.id},
        {"name",   u.name},
        {"email",  u.email},
        {"role",   u.role},
        {"active", u.active},
    };
}

std::optional<User> user_from_json(const json& j) {
    try {
        return User{
            0,
            j.at("name").get<std::string>(),
            j.at("email").get<std::string>(),
            j.value("role", "viewer"),
            j.value("active", true),
        };
    } catch (...) {
        return std::nullopt;
    }
}

// ─── In-memory repository (replace with SQLite/PostgreSQL in production) ─────

struct UserRepository {
    std::vector<User>  data;
    std::atomic<int>   next_id{1};

    UserRepository() {
        data.push_back({next_id++, "Sarah Johnson",    "s.johnson@acmecorp.com",  "admin"});
        data.push_back({next_id++, "Michael Williams", "m.williams@acmecorp.com", "editor"});
        data.push_back({next_id++, "Emma Chen",        "e.chen@startup.io",       "viewer"});
    }

    std::vector<User> find_all() const { return data; }

    std::optional<User> find_by_id(int id) const {
        auto it = std::find_if(data.begin(), data.end(),
                               [id](const User& u) { return u.id == id; });
        return (it != data.end()) ? std::make_optional(*it) : std::nullopt;
    }

    User& save(User u) {
        u.id = next_id++;
        return data.emplace_back(std::move(u));
    }

    bool remove(int id) {
        auto it = std::find_if(data.begin(), data.end(),
                               [id](const User& u) { return u.id == id; });
        if (it == data.end()) return false;
        data.erase(it);
        return true;
    }
};

// ─── Middleware helpers ───────────────────────────────────────────────────────

// Sets JSON Content-Type and CORS headers on every response
void set_cors(httplib::Response& res) {
    res.set_header("Access-Control-Allow-Origin",  "*");
    res.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization");
}

void json_response(httplib::Response& res, int status, const json& body) {
    set_cors(res);
    res.status = status;
    res.set_content(body.dump(2), "application/json");
}

void error_response(httplib::Response& res, int status, const std::string& message) {
    json_response(res, status, {{"error", message}});
}

// Basic Bearer token validation — replace with real JWT verification
bool is_authorized(const httplib::Request& req) {
    auto auth = req.get_header_value("Authorization");
    return auth.rfind("Bearer ", 0) == 0;  // stub: just checks prefix
}

// ─── Route setup ─────────────────────────────────────────────────────────────

void setup_routes(httplib::Server& svr, UserRepository& repo) {
    // OPTIONS preflight (CORS)
    svr.Options(".*", [](const httplib::Request&, httplib::Response& res) {
        set_cors(res);
        res.status = 204;
    });

    // GET /api/users
    svr.Get("/api/users", [&repo](const httplib::Request& req, httplib::Response& res) {
        json arr = json::array();
        for (const auto& u : repo.find_all()) arr.push_back(user_to_json(u));
        json_response(res, 200, arr);
    });

    // GET /api/users/:id
    svr.Get(R"(/api/users/(\d+))", [&repo](const httplib::Request& req, httplib::Response& res) {
        int id = std::stoi(req.matches[1]);
        if (auto u = repo.find_by_id(id)) {
            json_response(res, 200, user_to_json(*u));
        } else {
            error_response(res, 404, "User not found");
        }
    });

    // POST /api/users
    svr.Post("/api/users", [&repo](const httplib::Request& req, httplib::Response& res) {
        try {
            auto body = json::parse(req.body);
            auto user = user_from_json(body);
            if (!user) { error_response(res, 400, "Invalid user payload"); return; }
            const auto& saved = repo.save(*user);
            json_response(res, 201, user_to_json(saved));
        } catch (const json::parse_error&) {
            error_response(res, 400, "Invalid JSON");
        }
    });

    // DELETE /api/users/:id
    svr.Delete(R"(/api/users/(\d+))", [&repo](const httplib::Request& req, httplib::Response& res) {
        int id = std::stoi(req.matches[1]);
        if (repo.remove(id)) {
            json_response(res, 200, {{"message", "User deleted"}});
        } else {
            error_response(res, 404, "User not found");
        }
    });

    // Health check
    svr.Get("/health", [](const httplib::Request&, httplib::Response& res) {
        json_response(res, 200, {{"status", "ok"}, {"version", "1.0.0"}});
    });
}

// ─── Entry point ─────────────────────────────────────────────────────────────

int main() {
    UserRepository repo;
    httplib::Server svr;

    svr.set_exception_handler([](const auto& req, auto& res, std::exception_ptr ep) {
        try { std::rethrow_exception(ep); }
        catch (const std::exception& e) {
            error_response(res, 500, e.what());
        }
    });

    setup_routes(svr, repo);

    const int PORT = 8080;
    std::cout << "Server running on http://localhost:" << PORT << "\n";
    svr.listen("0.0.0.0", PORT);
    return 0;
}
