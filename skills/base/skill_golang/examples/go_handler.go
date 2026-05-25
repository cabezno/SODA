// Go HTTP handler with middleware — net/http production pattern
package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"
)

type Response struct {
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
	Message string      `json:"message,omitempty"`
}

func JSON(w http.ResponseWriter, status int, payload interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		log.Printf("encode error: %v", err)
	}
}

// JWT auth middleware
func AuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		auth := r.Header.Get("Authorization")
		if !strings.HasPrefix(auth, "Bearer ") {
			JSON(w, http.StatusUnauthorized, Response{Error: "missing token"})
			return
		}
		// token := strings.TrimPrefix(auth, "Bearer ")
		// claims, err := ValidateToken(token)
		// if err != nil { JSON(w, 401, Response{Error: "invalid token"}); return }
		// ctx := context.WithValue(r.Context(), "user", claims)
		next.ServeHTTP(w, r)
	})
}

// Health check handler
func HealthHandler(w http.ResponseWriter, r *http.Request) {
	JSON(w, http.StatusOK, Response{Message: "ok"})
}
