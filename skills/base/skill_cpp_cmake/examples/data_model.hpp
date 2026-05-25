// Modern C++20 domain model — RAII, smart pointers, repository pattern, serialization
// No raw new/delete. Non-copyable entities. Move-only semantics where appropriate.
#pragma once
#include <algorithm>
#include <chrono>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

// ─── Timestamp helper ─────────────────────────────────────────────────────────

using Clock     = std::chrono::system_clock;
using TimePoint = std::chrono::time_point<Clock>;

inline TimePoint now() { return Clock::now(); }

// ─── Validation helpers ───────────────────────────────────────────────────────

namespace validate {

inline void not_empty(const std::string& v, const char* field) {
    if (v.empty()) throw std::invalid_argument(std::string(field) + " must not be empty");
}

inline void email(const std::string& v) {
    if (v.find('@') == std::string::npos || v.find('.') == std::string::npos)
        throw std::invalid_argument("Invalid email: " + v);
}

inline void positive(int v, const char* field) {
    if (v <= 0) throw std::invalid_argument(std::string(field) + " must be positive");
}

} // namespace validate

// ─── Base entity — non-copyable, movable ─────────────────────────────────────

class Entity {
public:
    explicit Entity(int id) : id_(id), created_at_(now()) {
        validate::positive(id, "id");
    }
    virtual ~Entity() = default;

    Entity(const Entity&)            = delete;
    Entity& operator=(const Entity&) = delete;
    Entity(Entity&&)                 = default;
    Entity& operator=(Entity&&)      = default;

    int              id()         const noexcept { return id_; }
    const TimePoint& created_at() const noexcept { return created_at_; }

    bool operator==(const Entity& o) const noexcept { return id_ == o.id_; }
    bool operator< (const Entity& o) const noexcept { return id_ <  o.id_; }

private:
    int       id_;
    TimePoint created_at_;
};

// ─── User ─────────────────────────────────────────────────────────────────────

enum class UserRole { Viewer, Editor, Admin };

inline std::string role_to_string(UserRole r) {
    switch (r) {
        case UserRole::Admin:  return "admin";
        case UserRole::Editor: return "editor";
        default:               return "viewer";
    }
}

inline UserRole role_from_string(const std::string& s) {
    if (s == "admin")  return UserRole::Admin;
    if (s == "editor") return UserRole::Editor;
    return UserRole::Viewer;
}

class User final : public Entity {
public:
    User(int id, std::string name, std::string email,
         UserRole role = UserRole::Viewer, bool active = true)
        : Entity(id),
          name_(std::move(name)),
          email_(std::move(email)),
          role_(role),
          active_(active)
    {
        validate::not_empty(name_,  "name");
        validate::not_empty(email_, "email");
        validate::email(email_);
    }

    const std::string& name()  const noexcept { return name_; }
    const std::string& email() const noexcept { return email_; }
    UserRole           role()  const noexcept { return role_; }
    bool               active()const noexcept { return active_; }

    void set_name(std::string name) {
        validate::not_empty(name, "name");
        name_ = std::move(name);
    }
    void set_role(UserRole role)   { role_   = role;   }
    void deactivate()              { active_ = false;  }

private:
    std::string name_;
    std::string email_;
    UserRole    role_;
    bool        active_;
};

// ─── Generic repository interface ─────────────────────────────────────────────

template<typename T>
    requires std::is_base_of_v<Entity, T>
class IRepository {
public:
    virtual ~IRepository() = default;

    virtual std::optional<std::reference_wrapper<const T>> find_by_id(int id) const = 0;
    virtual std::vector<std::reference_wrapper<const T>>   find_all()          const = 0;
    virtual const T& save(std::unique_ptr<T> entity)                                 = 0;
    virtual bool     remove(int id)                                                  = 0;
    virtual std::size_t count()                                             const = 0;
};

// ─── In-memory user repository ────────────────────────────────────────────────

class UserRepository final : public IRepository<User> {
public:
    UserRepository() {
        // Realistic seed data — remove/replace in production
        save(std::make_unique<User>(1, "Sarah Johnson",    "s.johnson@acmecorp.com",  UserRole::Admin));
        save(std::make_unique<User>(2, "Michael Williams", "m.williams@acmecorp.com", UserRole::Editor));
        save(std::make_unique<User>(3, "Emma Chen",        "e.chen@startup.io",       UserRole::Viewer));
        save(std::make_unique<User>(4, "James Garcia",     "j.garcia@enterprise.net", UserRole::Editor));
    }

    std::optional<std::reference_wrapper<const User>> find_by_id(int id) const override {
        auto it = find_ptr(id);
        if (it == store_.end()) return std::nullopt;
        return std::cref(**it);
    }

    std::vector<std::reference_wrapper<const User>> find_all() const override {
        std::vector<std::reference_wrapper<const User>> result;
        result.reserve(store_.size());
        for (const auto& p : store_) result.emplace_back(*p);
        return result;
    }

    const User& save(std::unique_ptr<User> entity) override {
        // Replace if id already exists
        auto it = find_ptr(entity->id());
        if (it != store_.end()) {
            *it = std::move(entity);
            return **it;
        }
        return *store_.emplace_back(std::move(entity));
    }

    bool remove(int id) override {
        auto it = find_ptr(id);
        if (it == store_.end()) return false;
        store_.erase(it);
        return true;
    }

    std::size_t count() const override { return store_.size(); }

private:
    using Store = std::vector<std::unique_ptr<User>>;
    Store store_;

    Store::const_iterator find_ptr(int id) const {
        return std::find_if(store_.cbegin(), store_.cend(),
                            [id](const auto& p) { return p->id() == id; });
    }
    Store::iterator find_ptr(int id) {
        return std::find_if(store_.begin(), store_.end(),
                            [id](const auto& p) { return p->id() == id; });
    }
};
